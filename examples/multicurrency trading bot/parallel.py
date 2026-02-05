import sys
import os

from pandas.core.internals.blocks import get_block_type

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)  # insert(0) so it wins over other paths

from strategytester5.tester import StrategyTester, MetaTrader5 as mt5
from strategytester5.trade_classes.Trade import CTrade
from strategytester5 import PeriodSeconds, TIMEFRAME2STRING_MAP, STRING2TIMEFRAME_MAP
from datetime import datetime
import json
import os
import logging
import numpy as np
import pandas as pd
from ta.trend import sma_indicator

# Get path to the folder where this script lives
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    with open(os.path.join(BASE_DIR, "tester.json"), 'r', encoding='utf-8') as file: # reading a JSON file
        # Deserialize the file data into a Python object
        configs_json = json.load(file)
except Exception as e:
    raise RuntimeError(e)

tester_configs = configs_json["tester"]

if not mt5.initialize():
    raise RuntimeError(f"Failed to initialize MT5, Error = {mt5.last_error()}")

tester = StrategyTester(mt5_instance=mt5,
                        tester_config=tester_configs,
                        logging_level=logging.DEBUG,
                        POLARS_COLLECT_ENGINE="streaming")

# ---------------------- inputs ----------------------------

timeframe = tester_configs["timeframe"]
magic_number = 10012026
slippage = 100
sl = 700
tp = 500

symbols = tester_configs["symbols"]
# timeframes = [mt5.TIMEFRAME_M15, mt5.TIMEFRAME_H1, mt5.TIMEFRAME_H4, mt5.TIMEFRAME_D1]

# ---------------------------------------------------------

m_trade_objects = {
    symbol: CTrade(
        simulator=tester,
        magic_number=magic_number,
        filling_type_symbol=symbol,
        deviation_points=slippage
    )
    for symbol in symbols
}

def pos_exists(magic: int, symbol: str, type: int) -> bool:

    for position in tester.positions_get():
        if position.type == type and position.magic == magic and position.symbol == symbol:
            return True

    return False

def martingale_lotsize(initial_lot: float, symbol: str, current_time: datetime, multiplier: float=2) -> float:

    end_date = datetime.strptime(tester_configs["start_date"], "%d.%m.%Y %H:%M")
    deals = tester.history_deals_get(date_from=end_date, date_to=current_time)

    if not deals:
        return initial_lot

    last_deal = deals[-1]

    if last_deal.entry == mt5.DEAL_ENTRY_OUT: # a closed operation
        if last_deal.profit < 0 and last_deal.symbol == symbol: # if the deal made a loss on the current instrument
            return last_deal.volume * multiplier

    return initial_lot

def is_newbar(current_time: datetime, tf: int) -> bool:

    """A function to help in detecting the opening of a bar"""

    tf_seconds = PeriodSeconds(tf)
    curr_ts = int(current_time.timestamp())

    return curr_ts % tf_seconds == 0

def on_tick_multicurrency(symbol: str):

    m_trade = m_trade_objects[symbol]
    tick_info = tester.symbol_info_tick(symbol=symbol)

    if tick_info is None:  # if the process of obtaining ticks wasn't successful
        return

    ask = tick_info.ask
    bid = tick_info.bid

    rates_df = None
    tf = STRING2TIMEFRAME_MAP[timeframe]
    if is_newbar(tester.current_time, tf):
        rates = tester.copy_rates_from_pos(symbol=symbol, timeframe=tf, start_pos=0, count=20)
        rates_df = pd.json_normalize(rates) # a data structure is JSON-like

    if rates_df.empty:
        return

    sma_10 = sma_indicator(close=rates_df["close"], window=10)

    symbol_info = tester.symbol_info(symbol)
    pts = symbol_info.point
    volume = martingale_lotsize(initial_lot=symbol_info.volume_min, symbol=symbol, current_time=tester.current_time)

    if ask < sma_10.iloc[-1]: # if price is below the SMA 10
        if not pos_exists(magic=magic_number, symbol=symbol, type=mt5.POSITION_TYPE_BUY):  # If a position of such kind doesn't exist
            m_trade.buy(volume=volume, symbol=symbol, price=ask, sl=ask - sl * pts, tp=ask + tp * pts, comment="Tester buy")  # we open a buy position

    if ask > sma_10.iloc[-1]: # if price is above the SMA 10
        if not pos_exists(magic=magic_number, symbol=symbol, type=mt5.POSITION_TYPE_SELL):  # If a position of such kind doesn't exist
            m_trade.sell(volume=volume, symbol=symbol, price=bid, sl=bid + sl * pts, tp=bid - tp * pts, comment="Tester sell")  # we open a sell position

tester.ParallelOnTick(ontick_func=on_tick_multicurrency) # very important!
