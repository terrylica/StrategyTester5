import logging
import sys
import os

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)  # insert(0) so it wins over other paths

import MetaTrader5 as mt5
from strategytester5.tester import StrategyTester
from strategytester5.MQL5.functions import PeriodSeconds
import json
import os
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
    raise RuntimeError(f"Failed to initialize MetaTrader5, Error = {mt5.last_error()}")

tester_configs = configs_json["tester"]
tester = StrategyTester(tester_config=tester_configs, logging_level=logging.DEBUG, mt5_instance=mt5)

# -------------  global variables ----------------

symbols = tester_configs["symbols"]
timeframes = [tester.simulated_mt5.TIMEFRAME_M15,
              tester.simulated_mt5.TIMEFRAME_H1,
              tester.simulated_mt5.TIMEFRAME_H4,
              tester.simulated_mt5.TIMEFRAME_D1]

# ---------------------------------------------------------

def is_new_bar(current_time: int, tf: int) -> bool:

    """A function to help in detecting the opening of a bar"""

    tf_seconds = PeriodSeconds(tf)
    return current_time % tf_seconds == 0

def on_tick():

    for symbol in symbols:
        for tf in timeframes:

            rates = None
            if is_new_bar(tester.simulated_mt5.current_time(), tf):
                rates = tester.simulated_mt5.copy_rates_from_pos(symbol=symbol, timeframe=tf, start_pos=0, count=5)

            if rates is None or len(rates)==0:
                continue
            else:
                rates_df = pd.DataFrame(rates)
                rates_df["time"] = pd.to_datetime(rates_df["time"], unit="s")
                # print(rates_df.head())


tester.run(on_tick_function=on_tick) # very important!

