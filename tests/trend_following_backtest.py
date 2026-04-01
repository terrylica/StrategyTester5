import MetaTrader5 as mt5
import pandas as pd
from ta.trend import sma_indicator
import time
from datetime import datetime, timezone
from strategytester5.tester import StrategyTester
from strategytester5.trade_classes.Trade import CTrade
import logging

if not mt5.initialize():
    raise RuntimeError("Failed to initialize mt5.")

tester_config = {
    "bot_name": "Trend Following Bot",
    "symbols": ["EURUSD"],
    "timeframe": "H1",
    "start_date": "01.01.2026 00:00",
    "end_date": "01.03.2026 00:00",
    "modelling": "Open price only",
    "deposit": 1000,
    "leverage": "1:100"
}

tester = StrategyTester(tester_config=tester_config, mt5_instance=mt5, logging_level=logging.DEBUG)
sim_mt5 = tester.simulated_mt5

symbol = "EURUSD"
timeframe = sim_mt5.TIMEFRAME_H1 # one-hour timeframe

magic_number = 1001
slippage = 100

m_trade = CTrade(magic_number=magic_number, filling_type_symbol=symbol, deviation_points=slippage, terminal=sim_mt5)

def pos_exists(symbol: str, magic: int, pos_type: int) -> bool:

    positions = sim_mt5.positions_get()
    if positions is None:
        return False

    for pos in positions:
        if pos.type == pos_type and pos.magic == magic and pos.symbol == symbol:
            return True

    return False


def main():

    window  = 200

    rates = sim_mt5.copy_rates_from_pos(symbol, timeframe, 0, window)

    if rates is None or len(rates) < window:
        return

    rates_df = pd.DataFrame(rates)
    rates_df["time"] = pd.to_datetime(rates_df["time"], unit="s")

    sma_200 = sma_indicator(close=rates_df["close"], window=window)
    current_sma = sma_200.iloc[-1]

    tick_info = sim_mt5.symbol_info_tick(symbol)

    ask = tick_info.ask
    bid = tick_info.bid

    symbol_info = sim_mt5.symbol_info(symbol)
    lot_size = symbol_info.volume_min

    if current_sma > bid: # buy signal
        if not pos_exists(symbol=symbol, magic=magic_number, pos_type=sim_mt5.POSITION_TYPE_BUY):
            m_trade.buy(volume=lot_size, symbol=symbol, price=ask)

    if current_sma < ask: # sell signal
        if not pos_exists(symbol=symbol, magic=magic_number, pos_type=sim_mt5.POSITION_TYPE_SELL):
            m_trade.sell(volume=lot_size, symbol=symbol, price=bid)


tester.run(on_tick_function=main)