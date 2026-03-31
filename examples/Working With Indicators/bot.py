import logging
from strategytester5.tester import StrategyTester
import MetaTrader5 as mt5
import pandas as pd
from ta.trend import sma_indicator

if not mt5.initialize():
    raise RuntimeError("Failed to initialize mt5.")

tester_config = {
        "bot_name": "Working With Indicators",
        "symbols": ["USDJPY"],
        "timeframe": "H1",
        "start_date": "01.01.2026 00:00",
        "end_date": "27.03.2026 00:00",
        "modelling" : "Open price only",
        "deposit": 1000,
        "leverage": "1:100"
}

tester = StrategyTester(tester_config=tester_config, mt5_instance=mt5, logging_level=logging.DEBUG)
sim_mt5 = tester.simulated_mt5 # extract the simulated metatrader5 from the StrategyTester object and assign it to a simple variable
logger = tester.logger

# ---------------------- inputs ----------------------------

symbol  = tester_config["symbols"][0] # it should be one among the symbols in symbols list from tester.json (config file/dictionary)
timeframe = sim_mt5.TIMEFRAME_H1 # This should be an integer so you should convert timeframe in string into integer

# ---------------------------------------------------------

def on_tick():

    indicator_window = 20
    rates = sim_mt5.copy_rates_from_pos(symbol=symbol, timeframe=timeframe, start_pos=0, count=indicator_window)

    if rates is None or len(rates) < indicator_window: # if no information was found, or less than expected rates were returned
        return # prevent further calculations

    rates_df = pd.DataFrame(data=rates)

    # print(rates_df.head(-10))
    sma_indicator_values = sma_indicator(rates_df["close"], window=indicator_window)

    logger.info(f"Current sma({indicator_window}) : {sma_indicator_values.iloc[-1]}") # print the last calculated value in the array

tester.run(on_tick_function=on_tick) # very important!