import logging
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)  # insert(0) so it wins over other paths

import MetaTrader5 as mt5
from strategytester5.tester import StrategyTester
from strategytester5.trade_classes.Trade import CTrade
import json
from datetime import datetime
    
# Get path to the folder where this script lives
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    with open(os.path.join(BASE_DIR, "tester.json"), 'r', encoding='utf-8') as file: # reading a JSON file
        # Deserialize the file data into a Python object
        configs_json = json.load(file)
except Exception as e:
    raise RuntimeError(e)

if not mt5.initialize():
    raise RuntimeError(f"Failed to initialize MT5, Error = {mt5.last_error()}")

tester_configs = configs_json["tester"]
tester = StrategyTester(tester_config=tester_configs, logging_level=logging.DEBUG, mt5_instance=mt5) # very important

# ---------------------- inputs ----------------------------

symbol = "EURUSD"
timeframe = "PERIOD_H1"
magic_number = 10012026
slippage = 100
sl = 700
tp = 500

# ---------------------------------------------------------

m_trade = CTrade(terminal=tester.simulated_mt5, magic_number=magic_number, filling_type_symbol=symbol, deviation_points=slippage, logger=tester.logger)
symbol_info = tester.simulated_mt5.symbol_info(symbol=symbol)

def pos_exists(magic: int, pos_type: int) -> bool:

    for position in tester.simulated_mt5.positions_get():
        if position.type == pos_type and position.magic == magic:
            return True
    
    return False

def martingale_lot_size(initial_lot: float, current_time: datetime, multiplier: float=2) -> float:

    end_date = datetime.strptime(tester_configs["start_date"], "%d.%m.%Y %H:%M")
    deals = tester.simulated_mt5.history_deals_get(date_from=end_date, date_to=current_time)

    if not deals:
        return initial_lot

    last_deal = deals[-1]

    if last_deal.entry == mt5.DEAL_ENTRY_OUT: # a closed operation
        if last_deal.profit < 0: # if the deal made a loss
            return last_deal.volume * multiplier

    return initial_lot


def on_tick():
    
    tick_info = tester.simulated_mt5.symbol_info_tick(symbol=symbol)
    
    ask = tick_info.ask
    bid = tick_info.bid
    curr_time = tick_info.time

    pts = symbol_info.point

    lot_size = 0.01
    final_lot_size = martingale_lot_size(initial_lot=lot_size, current_time=curr_time, multiplier=2)

    if not pos_exists(magic=magic_number, pos_type=tester.simulated_mt5.POSITION_TYPE_BUY):  # If a position of such kind doesn't exist
        m_trade.buy(volume=final_lot_size, symbol=symbol, price=ask, sl=ask - sl * pts, tp=ask + tp * pts, comment="Tester buy")  # we open a buy position

    if not pos_exists(magic=magic_number, pos_type=tester.simulated_mt5.POSITION_TYPE_SELL):  # If a position of such kind doesn't exist
        m_trade.sell(volume=final_lot_size, symbol=symbol, price=bid, sl=bid + sl * pts, tp=bid - tp * pts, comment="Tester sell")  # we open a sell position

tester.run(on_tick_function=on_tick) # very important!