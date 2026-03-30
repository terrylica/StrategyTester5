import logging
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)  # insert(0) so it wins over other paths

from strategytester5.tester import StrategyTester
import MetaTrader5 as mt5
from strategytester5.trade_classes.Trade import CTrade
import json

# Get path to the folder where this script lives
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    with open(os.path.join(BASE_DIR, "tester.json"), 'r', encoding='utf-8') as file: # reading a JSON file
        # Deserialize the file data into a Python object
        tester_configs = json.load(file)
except Exception as e:
    raise RuntimeError(e)

if not mt5.initialize():
    raise RuntimeError("Failed to initialize mt5.")

tester = StrategyTester(tester_config=tester_configs["tester"], mt5_instance=mt5, logging_level=logging.DEBUG)

# ---------------------- inputs ----------------------------

symbol = "USDJPY" # it should be one among the symbols in symbols list from tester.json (config file/dictionary)
timeframe = "PERIOD_H1"
magic_number = 10012026
slippage = 100
sl = 700
tp = 500

# ---------------------------------------------------------

m_trade = CTrade(terminal=tester.simulated_mt5, magic_number=magic_number, filling_type_symbol=symbol, deviation_points=slippage, logger=tester.logger)

def pos_exists(magic: int, type: int) -> bool:
    """Check if position exists"""
    positions_found = tester.simulated_mt5.positions_get()
    for position in positions_found:
        if position.type == type and position.magic == magic:
            return True

    return False

symbol_info = tester.simulated_mt5.symbol_info(symbol=symbol)

def on_tick():
    
    tick_info = tester.simulated_mt5.symbol_info_tick(symbol=symbol)
    if tick_info is None:
        return

    ask = tick_info.ask
    bid = tick_info.bid
    
    pts = symbol_info.point

    if not pos_exists(magic=magic_number, type=mt5.POSITION_TYPE_BUY):  # If a position of such kind doesn't exist
        m_trade.buy(volume=0.01, symbol=symbol, price=ask, sl=ask - sl * pts, tp=ask + tp * pts, comment="Tester buy")  # we open a buy position

    if not pos_exists(magic=magic_number, type=mt5.POSITION_TYPE_SELL):  # If a position of such kind doesn't exist
        m_trade.sell(volume=0.01, symbol=symbol, price=bid, sl=bid + sl * pts, tp=bid - tp * pts, comment="Tester sell")  # we open a sell position

tester.run(on_tick_function=on_tick) # very important!