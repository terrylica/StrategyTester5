from datetime import datetime, timedelta

import polars as pl
from strategytester5 import MetaTrader5, ensure_utc, TIMEFRAME2STRING_MAP, month_bounds, STRING2TIMEFRAME_MAP
import os
from typing import Optional
import logging

def bars_to_polars(bars):
    
    return pl.DataFrame({
        "time": bars["time"],
        "open": bars["open"],
        "high": bars["high"],
        "low": bars["low"],
        "close": bars["close"],
        "tick_volume": bars["tick_volume"],
        "spread": bars["spread"],
        "real_volume": bars["real_volume"],
    })

def get_bars_from_mt5(
                    which_mt5: MetaTrader5,
                    symbol: str,
                    timeframe: int,
                    start_datetime: datetime,
                    end_datetime: datetime,
                    logger: Optional[logging.Logger] = None,
                    hist_dir: str="History",
                    return_df: bool = False
                    ) -> pl.DataFrame:

    if not isinstance(start_datetime, datetime) or not isinstance(end_datetime, datetime):
        logger.critical(f"start_datetime and end_datetime must be datetime type")
        return None

    start_datetime = ensure_utc(start_datetime)
    end_datetime   = ensure_utc(end_datetime)

    current = start_datetime.replace(day=1, hour=0, minute=0, second=0)

    dfs: list[pl.DataFrame] = []

    if isinstance(timeframe, str):
        str_tf = timeframe
        timeframe = STRING2TIMEFRAME_MAP[timeframe]
    else:
        str_tf = TIMEFRAME2STRING_MAP[timeframe]

    while True:
        month_start, month_end = month_bounds(current)

        if (
            month_start.year == end_datetime.year and
            month_start.month == end_datetime.month
        ):
            month_end = end_datetime

        if month_start > end_datetime:
            break

        if logger is None:
            print(f"\nProcessing bars for {symbol} ({str_tf}): {month_start:%Y-%m-%d} -> {month_end:%Y-%m-%d}")
        else:
            logger.info(f"Processing bars for {symbol} ({str_tf}): {month_start:%Y-%m-%d} -> {month_end:%Y-%m-%d}")
        

        rates = which_mt5.copy_rates_range(
            symbol,
            timeframe,
            month_start,
            month_end
        )

        if rates is None:
            
            if logger is None:
                print(f"\nNo bars for {symbol} {str_tf} {month_start:%Y-%m}")
            else:
                logger.warning(f"No bars for {symbol} {str_tf} {month_start:%Y-%m}")
                
            current = (month_start + timedelta(days=32)).replace(day=1)
            continue

        df = bars_to_polars(rates)

        df = df.with_columns(
            pl.from_epoch("time", time_unit="s")
            .dt.replace_time_zone("utc")
            .alias("time_dt")
        )

        df = df.with_columns([
            pl.col("time_dt").dt.year().alias("year"),
            pl.col("time_dt").dt.month().alias("month"),
        ])

        # DROP datetime, keep time in seconds
        df = df.drop("time_dt")

        df.write_parquet(
            os.path.join(hist_dir, "Bars", symbol, str_tf),
            partition_by=["year", "month"],
            mkdir=True
        )
        
        # if IS_DEBUG:
        #    print(df.head(-10))
        
        if return_df:    
            dfs.append(df)

        current = (month_start + timedelta(days=32)).replace(day=1)

    return pl.concat(dfs, how="vertical") if return_df else None

def get_bars_from_history(
                    symbol: str,
                    timeframe: int,
                    start_datetime: datetime,
                    end_datetime: datetime,
                    POLARS_COLLECT_ENGINE: str,
                    logger: Optional[logging.Logger] = None,
                    hist_dir: str="History") -> pl.DataFrame:

    if not isinstance(start_datetime, datetime) or not isinstance(end_datetime, datetime):
        logger.critical(f"start_datetime and end_datetime must be datetime type")
        return None

    # IMPORTANT: stored time is in milliseconds

    t_from_s = int(ensure_utc(start_datetime).timestamp())
    t_to_s = int(ensure_utc(end_datetime).timestamp())

    if isinstance(timeframe, (int, float)):
        timeframe = TIMEFRAME2STRING_MAP[timeframe]

    guess_path = os.path.join(hist_dir, "Bars", symbol, timeframe)
    if not os.path.exists(guess_path):
        logger.critical(f"Failed to obtain history, data path couldn't be found for {symbol} and {timeframe}: path = {guess_path}")
        return pl.DataFrame()

    lf = pl.scan_parquet(guess_path)

    try:
        lf2 = (
            lf
            .filter(
                (pl.col("time") >= t_from_s) &
                (pl.col("time") <= t_to_s)
            )  # get bars between date_from and date_to
            .sort("time", descending=False)
            .select([
                pl.col("time"),
                pl.col("open"),
                pl.col("high"),
                pl.col("low"),
                pl.col("close"),
                pl.col("tick_volume"),
                pl.col("spread"),
                pl.col("real_volume"),
            ])  # return only what's required
        )

    except Exception as e:
        logger.critical(f"Failed to get bars from {start_datetime} to {end_datetime} {e}")
        return pl.DataFrame()
    
    return lf2.collect(engine=POLARS_COLLECT_ENGINE)