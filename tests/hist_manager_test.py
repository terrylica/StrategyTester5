from strategytester5.MetaTrader5.data import HistoryManager
import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone
import pandas as pd

start_dt = datetime(2026, 1, 2, hour=0, minute=0)
count = 200

end_dt = start_dt - timedelta(hours=count)

rates = HistoryManager.copy_rates_from_parquet("EURUSD", timeframe=mt5.TIMEFRAME_H1, date_from=start_dt, history_start_date=end_dt, count=count,
                                               broker_data_dir="ICMarketsSC-Demo")
rates_df = pd.DataFrame(rates)
rates_df["time"] = pd.to_datetime(rates_df["time"], unit="s", utc=True)

print("from parquet: ",rates_df.head(-10))
print(rates_df.shape)

if not mt5.initialize():
    raise RuntimeError("Failed to Initialize MetaTrader5")

rates = mt5.copy_rates_from("EURUSD", mt5.TIMEFRAME_H1, start_dt, count)
if rates is None:
    print("no data returned from MT5")

rates_df = pd.DataFrame(rates)
rates_df["time"] = pd.to_datetime(rates_df["time"], unit="s", utc=True)

print("from MT5: ",rates_df.head(-10))
print(rates_df.shape)


"""
start_dt = datetime(2026, 2, 1, hour=0, minute=0)
count = 200

end_dt = start_dt + timedelta(hours=count)

rates = HistoryManager.copy_rates_range_from_parquet("EURUSD", timeframe=mt5.TIMEFRAME_H1, date_from=start_dt, date_to=end_dt, broker_data_dir="ICMarketsSC-Demo")
rates_df = pd.DataFrame(rates)
rates_df["time"] = pd.to_datetime(rates_df["time"], unit="s", utc=True)

print("from parquet: ",rates_df.head(-10))

if not mt5.initialize():
    raise RuntimeError("Failed to Initialize MetaTrader5")

rates = mt5.copy_rates_range("EURUSD", mt5.TIMEFRAME_H1, start_dt, end_dt)
if rates is None:
    print("no data returned from MT5")

rates_df = pd.DataFrame(rates)
rates_df["time"] = pd.to_datetime(rates_df["time"], unit="s", utc=True)

print("from MT5: ",rates_df.head(-10))
"""