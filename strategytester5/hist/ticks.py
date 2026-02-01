from datetime import datetime, timedelta
import polars as pl
from strategytester5 import MetaTrader5, ensure_utc, month_bounds, make_tick, TIMEFRAME2STRING_MAP
import numpy as np
import os
from typing import Optional
import logging

def ticks_to_polars(ticks):
    return pl.DataFrame({
        "time": ticks["time"],
        "bid": ticks["bid"],
        "ask": ticks["ask"],
        "last": ticks["last"],
        "volume": ticks["volume"],
        "time_msc": ticks["time_msc"],
        "flags": ticks["flags"],
        "volume_real": ticks["volume_real"],
    })
    
def get_ticks_from_mt5(
                    which_mt5: MetaTrader5,
                    start_datetime: datetime,
                    end_datetime: datetime,
                    symbol: str,
                    logger: Optional[logging.Logger] = None,
                    return_df: bool = False,
                    hist_dir: str = "History",
                ) -> pl.DataFrame:

    start_datetime = ensure_utc(start_datetime)
    end_datetime   = ensure_utc(end_datetime)

    current = start_datetime.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    dfs: list[pl.DataFrame] = []

    while True:
        month_start, month_end = month_bounds(current)

        if month_start.year == end_datetime.year and month_start.month == end_datetime.month:
            month_end = end_datetime

        if month_start > end_datetime:
            break

        if logger is None:
            print(f"Processing ticks for {symbol}: {month_start:%Y-%m-%d} -> {month_end:%Y-%m-%d}")
        else:
            logger.info(f"Processing ticks for {symbol}: {month_start:%Y-%m-%d} -> {month_end:%Y-%m-%d}")

        ticks = which_mt5.copy_ticks_range(symbol, month_start, month_end, which_mt5.COPY_TICKS_ALL)

        if ticks is None or len(ticks) == 0:
            if logger is None:
                print(f"No ticks for {symbol} {month_start:%Y-%m}")
            else:
                logger.warning(f"No ticks for {symbol} {month_start:%Y-%m}")
            current = (month_start + timedelta(days=32)).replace(day=1)
            continue

        df = ticks_to_polars(ticks)

        # Ensure dtypes (MT5 already provides these, but this locks it down)
        df = df.with_columns([
            pl.col("time").cast(pl.Int64),        # seconds
            pl.col("time_msc").cast(pl.Int64),    # milliseconds
        ])

        # year/month derived from "time" (seconds)
        df = df.with_columns(
            pl.from_epoch(pl.col("time"), time_unit="s")
              .dt.replace_time_zone("utc")
              .alias("time_dt")
        ).with_columns([
            pl.col("time_dt").dt.year().alias("year"),
            pl.col("time_dt").dt.month().alias("month"),
        ]).drop("time_dt")

        df.write_parquet(
            os.path.join(hist_dir, "Ticks", symbol),
            partition_by=["year", "month"],
            mkdir=True
        )

        if return_df:
            dfs.append(df)

        current = (month_start + timedelta(days=32)).replace(day=1)

    return pl.concat(dfs, how="vertical") if return_df else None

def get_ticks_from_history(
                        symbol: str,
                        start_datetime: datetime,
                        end_datetime: datetime,
                        POLARS_COLLECT_ENGINE: str,
                        logger: Optional[logging.Logger] = None,
                        hist_dir: str="History",
                    ) -> pl.DataFrame:

    if not isinstance(start_datetime, datetime) or not isinstance(end_datetime, datetime):
        if logger: logger.critical("start_datetime and end_datetime must be datetime type")
        return pl.DataFrame()

    start_dt = ensure_utc(start_datetime)
    end_dt   = ensure_utc(end_datetime)

    t_from_s  = int(start_dt.timestamp())
    t_to_s    = int(end_dt.timestamp())
    # t_from_ms = int(start_dt.timestamp() * 1000)
    # t_to_ms   = int(end_dt.timestamp() * 1000)

    guess_path = os.path.join(hist_dir, "Ticks", symbol)
    if not os.path.exists(guess_path):
        if logger: logger.critical(f"Failed to obtain history, path not found: {guess_path}")
        return pl.DataFrame()

    lf = pl.scan_parquet(guess_path)

    # coarse filter by seconds + exact by milliseconds
    ticks_lf = (
        lf
        .filter(
            (pl.col("time") >= t_from_s) &
            (pl.col("time") <= t_to_s)
        )
        # .filter(
        #     (pl.col("time_msc") >= t_from_ms) &
        #     (pl.col("time_msc") <= t_to_ms)
        # )
        .sort(["time", "time_msc"])
        .select([
            "time", "bid", "ask", "last", "volume", "time_msc", "flags", "volume_real"
        ])
    )

    try:
        return ticks_lf.collect(engine=POLARS_COLLECT_ENGINE)
    except Exception as e:
        if logger: logger.warning(f"Failed to copy ticks {e}")
        return pl.DataFrame()
    
    
class TicksGen:
    def __init__(self):
        pass
    
    @staticmethod
    def interpolate_prices(start, end, steps):
        if steps <= 1:
            return [end]
        return np.linspace(start, end, steps).tolist()
    
    def build_support_points(bar: dict) -> list:
        o, h, l, c = bar["open"], bar["high"], bar["low"], bar["close"]

        if c >= o:  # bullish
            return [o, l, h, c]
        else:       # bearish
            return [o, h, l, c]
    
    @staticmethod    
    def __resolve_tick_count(bar: dict) -> int:
        # MT5 internally limits complexity
        return max(1, min(bar["tick_volume"], 20))
    
    @staticmethod
    def generate_ticks_from_bar(bar: dict, symbol_point: float):
        tick_count = TicksGen.__resolve_tick_count(bar)

        time = int(bar["time"])
        spread = bar["spread"]
        base_msc = time * 1000

        step = max(1, 1000 // tick_count)

        ticks = []

        # ---- 1 tick -----
        if tick_count == 1:
            price = bar["close"]
            return [
                make_tick(
                    time,
                    price,
                    price + spread * symbol_point,
                    time_msc=base_msc
                )
            ]

        # ----- 2 ticks ----
        if tick_count == 2:
            return [
                make_tick(bar["time"], bar["open"], bar["open"] + spread * symbol_point, time_msc=base_msc),
                make_tick(bar["time"], bar["close"], bar["close"] + spread * symbol_point, time_msc=base_msc + step),
            ]

        # ---- Support points ----
        support_points = TicksGen.build_support_points(bar)
        segments = len(support_points) - 1
        ticks_per_segment = tick_count // segments
        remainder = tick_count % segments

        t_index = 0
        for i in range(segments):
            start = support_points[i]
            end = support_points[i + 1]
            steps = ticks_per_segment + (1 if i < remainder else 0)

            prices = TicksGen.interpolate_prices(start, end, steps)
            for price in prices:
                ticks.append(
                    make_tick(
                        time=bar["time"],
                        bid=float(price),
                        ask=float(price + spread * symbol_point),
                        time_msc=base_msc + t_index * step
                    )
                )
                t_index += 1

        return ticks[:tick_count]

    @staticmethod
    def generate_ticks_from_bars(
            bars: pl.DataFrame,
            symbol: str,
            symbol_point: float,
            logger: Optional[logging.Logger] = None,
            hist_dir: str = "History",
            return_df: bool = False,
    ) -> pl.DataFrame:

        dfs: list[pl.DataFrame] = []

        # bars.time is seconds int -> add time_dt for partitions
        df_bars = (
            bars
            .with_columns(
                pl.from_epoch(pl.col("time").cast(pl.Int64), time_unit="s")
                .dt.replace_time_zone("utc")
                .alias("time_dt")
            )
            .with_columns([
                pl.col("time_dt").dt.year().alias("year"),
                pl.col("time_dt").dt.month().alias("month"),
            ])
            .sort("time")
        )

        for (year, month), bars_chunk in df_bars.group_by(["year", "month"], maintain_order=True):

            if logger is None:
                print(f"\nGenerating ticks for {symbol}: {year}-{month:02d}")
            else:
                logger.info(f"Generating ticks for {symbol}: {year}-{month:02d}")

            tick_rows = []
            for bar in bars_chunk.iter_rows(named=True):
                ticks = TicksGen.generate_ticks_from_bar(bar, symbol_point)
                if ticks:
                    tick_rows.extend(ticks)

            if not tick_rows:
                continue

            df_ticks = pl.DataFrame(tick_rows)

            # --- normalize schema to MT5-style ---
            # time -> seconds int64
            if df_ticks.schema.get("time") in (pl.Datetime, pl.Datetime("us", time_zone="UTC"), pl.Datetime("ms"),
                                               pl.Datetime("ns")):
                df_ticks = df_ticks.with_columns(
                    (pl.col("time").dt.timestamp("ms") // 1000).cast(pl.Int64).alias("time")
                )
            else:
                df_ticks = df_ticks.with_columns(pl.col("time").cast(pl.Int64))

            # time_msc -> int64 ms
            df_ticks = df_ticks.with_columns(pl.col("time_msc").cast(pl.Int64))

            # year/month from seconds
            df_ticks = (
                df_ticks
                .with_columns(
                    pl.from_epoch(pl.col("time"), time_unit="s")
                    .dt.replace_time_zone("utc")
                    .alias("time_dt")
                )
                .with_columns([
                    pl.col("time_dt").dt.year().alias("year"),
                    pl.col("time_dt").dt.month().alias("month"),
                ])
                .drop("time_dt")
                .sort(["time", "time_msc"])
            )

            df_ticks.write_parquet(
                os.path.join(hist_dir, "Simulated Ticks", symbol),
                partition_by=["year", "month"],
                mkdir=True,
            )

            if return_df:
                dfs.append(df_ticks)

        return pl.concat(dfs, how="vertical") if return_df else None


