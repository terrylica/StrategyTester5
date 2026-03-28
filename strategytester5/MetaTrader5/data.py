from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
# from threading import Lock
import time

import logging
from typing import Iterable, Optional, Literal, Any
from pathlib import Path
from choreographer.channels import JSONError
from ..MetaTrader5 import AccountInfo, SymbolInfo, TerminalInfo, TICKS_DTYPE, RATES_DTYPE, MULTI_TICKS_DTYPE, MULTI_RATES_DTYPE
from strategytester5.MetaTrader5.constants import MetaTrader5Constants
# import MetaTrader5 as mt5
import polars as pl
import numpy as np
from datetime import datetime, timedelta
import json
from strategytester5 import config

def _warning_log(msg: str, logger: Optional[logging.Logger] = None):
    if logger is None:
        print(msg)
        return

    logger.warning(msg)


class HistoryManager:
    def __init__(self, mt5_instance: Optional[Any] = None,
                 broker_data_path: Optional[str] = config.DEFAULT_BROKER_DATA_PATH,
                 logger: Optional[logging.Logger] = None):

        """

        Args:
            mt5_instance (MetaTrader5) : Initialized MetaTrader5 instance to extract bars from
        """

        self.mt5_instance = mt5_instance
        self.broker_data_dir = broker_data_path
        self.logger = logger
        self._last_start_date: int
        self._last_end_date: int

        # self._mt5_lock = Lock()

    @staticmethod
    def bars_file_path(symbol: str, timeframe_str: str, year: int, month: int,
                       broker_data_dir: Optional[str] = config.DEFAULT_BROKER_DATA_PATH) -> Path:
        return Path(broker_data_dir) / symbol / "Bars" / timeframe_str / f"{year:04d}{month:02d}.parquet"

    @staticmethod
    def ticks_file_path(symbol: str, year: int, month: int, broker_data_dir: Optional[str] = config.DEFAULT_BROKER_DATA_PATH) -> Path:
        return Path(broker_data_dir) / symbol / "Ticks" / f"{year:04d}{month:02d}.parquet"

    @staticmethod
    def month_start(month: int, year: int) -> datetime:
        return datetime(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def next_month(month: int, year: int) -> datetime:
        dt = HistoryManager.month_start(month, year)
        if dt.month == 12:
            return dt.replace(year=dt.year + 1, month=1)
        return dt.replace(month=dt.month + 1)

    @staticmethod
    def month_floor(dt: datetime) -> datetime:
        return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def next_month_dt(dt: datetime) -> datetime:
        dt = HistoryManager.month_floor(dt)
        if dt.month == 12:
            return dt.replace(year=dt.year + 1, month=1)
        return dt.replace(month=dt.month + 1)

    @staticmethod
    def iter_months_between(date_from: datetime, date_to: datetime) -> Iterable[tuple[int, int]]:
        cur = HistoryManager.month_floor(date_from)

        while cur <= date_to:
            yield cur.year, cur.month
            cur = HistoryManager.next_month_dt(cur)

    def _info_log(self, msg: str):
        if self.logger is None:
            print(msg)
            return

        self.logger.info(msg)

    def _error_log(self, msg: str):
        if self.logger is None:
            print(msg)
            return

        self.logger.error(msg)

    def _warning_log(self, msg: str):
        if self.logger is None:
            print(msg)
            return

        self.logger.warning(msg)

    def _critical_log(self, msg: str):
        if self.logger is None:
            print(msg)
            return

        self.logger.critical(msg)

    def synchronize_bars(self,
                         symbol: str,
                         timeframe: int,
                         month: int,
                         year: int,
                         ) -> Optional[pl.DataFrame]:
        """
        Extracts bars (rates) from the MetaTrader 5 terminal, stores them in a nearby location for simulator usage.

        Returns:
            Synchronized bars in a polars DataFrame object

        Args:
            timeframe (int) : A timeframe to extract bars from
            symbol (str) : An instrument in the terminal
            month (int) : The entire month to synchronize
            year (int) : A year which a specified `month` belongs
        """

        if self.mt5_instance is None:
            log = ("Cannot synchronize Bars from MetaTrader5, due to an invalid MetaTrader5 instance.\n" 
                   "If the default MetaTrader5 wasn't installed initially, run `pip install strategytester5[mt5]`")

            self._critical_log(log)
            raise RuntimeError(log)

        start = self.month_start(month, year)
        end = self.next_month(month, year)

        # add it to the market watch
        if not self.mt5_instance.symbol_select(symbol, True):
            err = f"Failed to select or add {symbol} to the MarketWatch, mt5 error = {self.mt5_instance.last_error()}"
            self._error_log(err)
            return None

        self._info_log(f"Fetching bars from MetaTrader5 from {symbol} for: {year:04d}-{month:02d}")

        # with self._mt5_lock:
        rates = self.mt5_instance.copy_rates_range(symbol, timeframe, start, end)
        if rates is None or len(rates)==0:
            warn = f"No bars were received from MetaTrader5 from {symbol} for: {year:04d}-{month:02d}"
            self._warning_log(warn)
            return None

        # rates dataframe
        df = pl.DataFrame(rates)

        file = self.bars_file_path(symbol=symbol, timeframe_str=MetaTrader5Constants.TIMEFRAME2STRING_MAP[timeframe], year=year, month=month,
                                   broker_data_dir=self.broker_data_dir)
        file.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(file)

        return df

    def synchronize_ticks(
            self,
            symbol: str,
            month: int,
            year: int,
    ) -> Optional[pl.DataFrame]:
        """
        Extracts ticks from the MetaTrader 5 terminal, stores them in a nearby location for simulator usage.

        Returns:
            Synchronized ticks in a polars DataFrame object

        Args:
            symbol (str) : An instrument in the terminal
            month (int) : The entire month to synchronize
            year (int) : A year which a specified `month` belongs
        """

        if self.mt5_instance is None:
            log = ("Cannot synchronize ticks from MetaTrader5, due to an invalid MetaTrader5 instance.\n" 
                   "If the default MetaTrader5 wasn't installed initially, run `pip install strategytester5[mt5]`")

            self._critical_log(log)
            raise RuntimeError(log)

        start = self.month_start(month, year)
        end = self.next_month(month, year)

        # add it to the market watch
        if not self.mt5_instance.symbol_select(symbol, True):
            err = f"Failed to select or add {symbol} to the MarketWatch, mt5 error = {self.mt5_instance.last_error()}"
            self._error_log(err)
            return None

        self._info_log(f"Fetching ticks from MetaTrader5 from {symbol} for: {year:04d}-{month:02d}")

        # with self._mt5_lock:
        ticks = self.mt5_instance.copy_ticks_range(symbol, start, end, self.mt5_instance.COPY_TICKS_ALL)
        if ticks is None or len(ticks)==0:
            warn = f"No ticks were received from MetaTrader5 from {symbol} for: {year:04d}-{month:02d}"
            self._warning_log(warn)
            return None

        # rates dataframe
        df = pl.DataFrame(ticks)

        file = self.ticks_file_path(symbol, year=year, month=month, broker_data_dir=self.broker_data_dir)
        file.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(file)

        return df

    def synchronize_all_timeframes(
            self,
            symbols: Iterable[str],
            date_from: datetime,
            date_to: datetime,
            max_workers: int = 4,
    ):

        if date_from > date_to:
            self._warning_log("date_from must be <= date_to")
            return

        all_tfs = list(MetaTrader5Constants.STRING2TIMEFRAME_MAP.values())

        self._info_log("Synchronizing all timeframes...")

        tasks = []

        # Build all jobs (symbol x timeframe x year x month)
        for symbol in symbols:
            for tf in all_tfs:
                for year, month in self.iter_months_between(date_from, date_to):
                    tasks.append((symbol, tf, year, month))

        start = time.time()

        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:

            futures = [
                executor.submit(self.synchronize_bars, sym, tf, month, year)
                for sym, tf, year, month in tasks
            ]

            for fut in as_completed(futures):
                res = fut.result()
                results.append(res)

                # sym, tf, y, m, status = res

        elapsed = time.time() - start
        self._info_log(f"Finished synchronization in {elapsed:.2f}s")

    @staticmethod
    def copy_rates_range_from_parquet(
            symbol: str,
            timeframe: int,
            date_from: datetime,
            date_to: datetime,
            polars_collect_engine: Literal["auto", "in-memory", "streaming", "gpu"] = "auto",
            broker_data_dir: Optional[str] = config.DEFAULT_BROKER_DATA_PATH,
            logger: Optional[logging.Logger] = None
    ):
        if date_from > date_to:
            _warning_log("date_from must be <= date_to", logger)
            return None

        timeframe_str = MetaTrader5Constants.TIMEFRAME2STRING_MAP[timeframe]

        files: list[str] = []
        for year, month in HistoryManager.iter_months_between(date_from, date_to):
            file = HistoryManager.bars_file_path(symbol=symbol, timeframe_str=timeframe_str, year=year, month=month,
                                          broker_data_dir=broker_data_dir)
            if file.exists():
                files.append(str(file))

        if not files:
            _warning_log(
                f"No stored bar history found for {symbol} {timeframe_str} "
                f"between {date_from} and {date_to}", logger
            )
            return None

        t_from = int(date_from.timestamp())
        t_to = int(date_to.timestamp())

        try:
            df = (
                pl.scan_parquet(files)
                .filter(
                    (pl.col("time") >= t_from) &
                    (pl.col("time") <= t_to)
                )
                .sort("time")
                .select([
                    "time",
                    "open",
                    "high",
                    "low",
                    "close",
                    "tick_volume",
                    "spread",
                    "real_volume",
                ])
                .collect(engine=polars_collect_engine)
            )

            if df.is_empty():
                return np.empty(0, dtype=RATES_DTYPE)

            rows = list(
                zip(
                    df["time"].to_list(),
                    df["open"].to_list(),
                    df["high"].to_list(),
                    df["low"].to_list(),
                    df["close"].to_list(),
                    df["tick_volume"].to_list(),
                    df["spread"].to_list(),
                    df["real_volume"].to_list(),
                )
            )

            return np.array(rows, dtype=RATES_DTYPE)

        except Exception as e:
            _warning_log(
                f"Failed to copy stored rates for {symbol} {timeframe_str} "
                f"from {date_from} to {date_to}: {e}", logger
            )
            return None

    @staticmethod
    def _tick_flag_mask(flags: int) -> int:
        if flags == MetaTrader5Constants.COPY_TICKS_ALL:
            return (
                MetaTrader5Constants.TICK_FLAG_BID
                | MetaTrader5Constants.TICK_FLAG_ASK
                | MetaTrader5Constants.TICK_FLAG_LAST
                | MetaTrader5Constants.TICK_FLAG_VOLUME
                | MetaTrader5Constants.TICK_FLAG_BUY
                | MetaTrader5Constants.TICK_FLAG_SELL
            )

        mask = 0
        if flags & MetaTrader5Constants.COPY_TICKS_INFO:
            mask |= MetaTrader5Constants.TICK_FLAG_BID | MetaTrader5Constants.TICK_FLAG_ASK
        if flags & MetaTrader5Constants.COPY_TICKS_TRADE:
            mask |= MetaTrader5Constants.TICK_FLAG_LAST | MetaTrader5Constants.TICK_FLAG_VOLUME

        return mask

    @staticmethod
    def copy_ticks_range_from_parquet(
            symbol: str,
            date_from: datetime,
            date_to: Optional[datetime] = None,
            flags: int = MetaTrader5Constants.COPY_TICKS_ALL,
            limit: Optional[int] = None,
            polars_collect_engine: Literal["auto", "in-memory", "streaming", "gpu"] = "auto",
            broker_data_dir: Optional[str] = config.DEFAULT_BROKER_DATA_PATH,
            logger: Optional[logging.Logger] = None,
    ):

        if limit is None:
            if date_to is None:
                _warning_log("Either date_to or limit must be provided", logger)
                return None
            

            if date_from > date_to:
                _warning_log("date_from must be <= date_to", logger)
                return None

        # ---------------- determine months ----------------
        months_iter = (
            HistoryManager.iter_months_between(date_from, date_to)
            if limit is None
            else HistoryManager.iter_months_between(date_from, date_from + timedelta(days=365 * 20))
        # wide range fallback
        )

        files: list[str] = []
        for year, month in months_iter:
            file = HistoryManager.ticks_file_path(symbol, year, month, broker_data_dir)
            if file.exists():
                files.append(str(file))

        if not files:
            _warning_log(f"No stored tick history found for {symbol}", logger)
            return None

        t_from = int(date_from.timestamp())
        t_to = int(date_to.timestamp()) if date_to else None

        flag_mask = HistoryManager._tick_flag_mask(flags)

        try:
            lf = pl.scan_parquet(files)

            # ---------------- filtering ----------------
            lf = lf.filter(pl.col("time") >= t_from)

            if limit is None:
                lf = lf.filter(pl.col("time") <= t_to)

            lf = lf.filter((pl.col("flags") & flag_mask) != 0)

            # ---------------- sorting ----------------
            lf = lf.sort(["time", "time_msc"])

            # ---------------- limit mode ----------------
            if limit is not None:
                lf = lf.limit(limit)

            df = (
                lf.select([
                    "time",
                    "bid",
                    "ask",
                    "last",
                    "volume",
                    "time_msc",
                    "flags",
                    "volume_real",
                ])
                .collect(engine=polars_collect_engine)
            )

            if df.is_empty():
                return np.empty(0, dtype=TICKS_DTYPE)

            return np.array(
                list(zip(
                    df["time"],
                    df["bid"],
                    df["ask"],
                    df["last"],
                    df["volume"],
                    df["time_msc"],
                    df["flags"],
                    df["volume_real"],
                )),
                dtype=TICKS_DTYPE
            )

        except Exception as e:
            _warning_log(
                f"Failed to copy ticks for {symbol} from {date_from}: {e}",
                logger
            )
            return None

    def _ensure_ticks_month(self, symbol, year, month, sync: bool):
        file = self.ticks_file_path(symbol, year, month, self.broker_data_dir)

        if file.exists():
            return True

        if not sync:
            return False

        df = self.synchronize_ticks(symbol, month, year)
        return df is not None

    def _process_symbol_ticks(
            self,
            symbol: str,
            symbol_id: int,
            date_from: datetime,
            date_to: datetime,
            sync: bool,
            polars_collect_engine: Literal["auto", "in-memory", "streaming", "gpu"] = "auto"
    ) -> Optional[np.ndarray]:

        files = []

        for year, month in self.iter_months_between(date_from, date_to):

            if not self._ensure_ticks_month(symbol, year, month, sync):
                continue

            file = self.ticks_file_path(symbol, year, month, self.broker_data_dir)
            files.append(str(file))

        if not files:
            return None

        t_from = int(date_from.timestamp())
        t_to = int(date_to.timestamp())

        df = (
            pl.scan_parquet(files)
            .filter(
                (pl.col("time") >= t_from) &
                (pl.col("time") <= t_to)
            )
            .collect(engine=polars_collect_engine)
        )

        if df.is_empty():
            return None

        df = df.with_columns(
            pl.lit(symbol_id).alias("symbol_id")
        )

        return np.array(
            list(zip(
                df["time"].to_list(),
                df["bid"].to_list(),
                df["ask"].to_list(),
                df["last"].to_list(),
                df["volume"].to_list(),
                df["time_msc"].to_list(),
                df["flags"].to_list(),
                df["volume_real"].to_list(),
                df["symbol_id"].to_list(),
            )),
            dtype=MULTI_TICKS_DTYPE
        )

    def _ensure_bars_month(self, symbol: str, timeframe: int, year: int, month: int, sync: bool):
        file = self.bars_file_path(
            symbol,
            MetaTrader5Constants.TIMEFRAME2STRING_MAP[timeframe],
            year,
            month,
            self.broker_data_dir,
        )

        if file.exists():
            return True

        if not sync:
            return False

        df = self.synchronize_bars(symbol, timeframe, month, year)
        return df is not None

    def _process_symbol_bars(
            self,
            symbol: str,
            symbol_id: int,
            timeframe: int,
            date_from: datetime,
            date_to: datetime,
            sync: bool,
            polars_collect_engine: Literal["auto", "in-memory", "streaming", "gpu"] = "auto"
    ) -> Optional[np.ndarray]:

        tf_str = MetaTrader5Constants.TIMEFRAME2STRING_MAP[timeframe]

        files = []

        for year, month in self.iter_months_between(date_from, date_to):

            if not self._ensure_bars_month(symbol, timeframe, year, month, sync):
                continue

            file = self.bars_file_path(symbol, tf_str, year, month, self.broker_data_dir)
            files.append(str(file))

        if not files:
            return None

        t_from = int(date_from.timestamp())
        t_to = int(date_to.timestamp())

        df = (
            pl.scan_parquet(files)
            .filter(
                (pl.col("time") >= t_from) &
                (pl.col("time") <= t_to)
            )
            .collect(engine=polars_collect_engine)
        )

        if df.is_empty():
            return None

        df = df.with_columns(
            pl.lit(symbol_id).alias("symbol_id")
        )

        return np.array(
            list(zip(
                df["time"].to_list(),
                df["open"].to_list(),
                df["high"].to_list(),
                df["low"].to_list(),
                df["close"].to_list(),
                df["tick_volume"].to_list(),
                df["spread"].to_list(),
                df["real_volume"].to_list(),
                df["symbol_id"].to_list(),
            )),
            dtype=MULTI_RATES_DTYPE
        )

    def load_ticks_lazy_multi(
            self,
            symbols: list[str],
            date_from: datetime,
            date_to: datetime,
            sync: bool = True,
    ) -> pl.LazyFrame:

        symbol_to_id = {s: i for i, s in enumerate(symbols)}

        lazy_frames = []

        for symbol in symbols:
            files = []

            for year, month in self.iter_months_between(date_from, date_to):
                if not self._ensure_ticks_month(symbol, year, month, sync):
                    continue

                file = self.ticks_file_path(symbol, year, month, self.broker_data_dir)
                files.append(str(file))

            if not files:
                continue

            lf = (
                pl.scan_parquet(files)
                .filter(
                    (pl.col("time") >= int(date_from.timestamp())) &
                    (pl.col("time") <= int(date_to.timestamp()))
                )
                .with_columns(pl.lit(symbol_to_id[symbol]).alias("symbol_id"))
            )

            lazy_frames.append(lf)

        if not lazy_frames:
            err = "No tick data found"
            self.logger.critical(err)
            raise RuntimeError(err)

        return pl.concat(lazy_frames)

    def build_tick_stream(
            self,
            symbols: list[str],
            date_from: datetime,
            date_to: datetime,
            sync: bool = True,
            polars_collect_engine: Literal["auto", "in-memory", "streaming", "gpu"] = "auto"
    ) -> pl.DataFrame:

        lf = self.load_ticks_lazy_multi(symbols, date_from, date_to, sync)

        df = (
            lf
            .sort(["time", "time_msc"])  # global ordering
            .select([
                "time",
                "bid",
                "ask",
                "last",
                "volume",
                "time_msc",
                "flags",
                "volume_real",
                "symbol_id",
            ])
            .collect(engine=polars_collect_engine)  # ⚡ critical
        )

        return df

    def load_bars_lazy_multi(
            self,
            symbols: list[str],
            timeframe: int,
            date_from: datetime,
            date_to: datetime,
            sync: bool = True,
    ) -> pl.LazyFrame:

        symbol_to_id = {s: i for i, s in enumerate(symbols)}
        tf_str = MetaTrader5Constants.TIMEFRAME2STRING_MAP[timeframe]

        lazy_frames = []

        for symbol in symbols:
            files = []

            for year, month in self.iter_months_between(date_from, date_to):
                if not self._ensure_bars_month(symbol, timeframe, year, month, sync):
                    continue

                file = self.bars_file_path(symbol, tf_str, year, month, self.broker_data_dir)
                files.append(str(file))

            if not files:
                continue

            lf = (
                pl.scan_parquet(files)
                .filter(
                    (pl.col("time") >= int(date_from.timestamp())) &
                    (pl.col("time") <= int(date_to.timestamp()))
                )
                .with_columns(pl.lit(symbol_to_id[symbol]).alias("symbol_id"))
            )

            lazy_frames.append(lf)

        if not lazy_frames:
            err = "No bars data found"
            self.logger.critical(err)
            raise RuntimeError(err)

        return pl.concat(lazy_frames)

    def build_bar_stream(
            self,
            symbols: list[str],
            timeframe: int,
            date_from: datetime,
            date_to: datetime,
            sync: bool = True,
            polars_collect_engine: Literal["auto", "in-memory", "streaming", "gpu"] = "auto"
    ) -> pl.DataFrame:

        lf = self.load_bars_lazy_multi(symbols, timeframe, date_from, date_to, sync)

        df = (
            lf
            .sort(["time", "symbol_id"])  # bars don't need time_msc
            .select([
                "time",
                "open",
                "high",
                "low",
                "close",
                "tick_volume",
                "spread",
                "real_volume",
                "symbol_id",
            ])
            .collect(engine=polars_collect_engine)
        )

        return df

def import_account_info(path: Path, logger: Optional[logging.Logger] = None) -> Optional[AccountInfo]:
    if not path.is_file() or not path.exists():
        err = "Broker path does not exist"
        if logger:
            logger.error(err)

        raise FileNotFoundError(err)

    try:
        with path.open(encoding="utf-8") as json_file:
            data = json.load(json_file)

        account_info = AccountInfo(**data["account_info"])

    except Exception as e:
        err = f"Failed to read a file {path} JSON error = {e}"
        if logger:
            logger.error(err)

        raise JSONError(err)

    return account_info


def import_all_symbol_info(path: Path, logger: Optional[logging.Logger] = None) -> Optional[SymbolInfo]:
    if not path.is_file() or not path.exists():
        err = "Broker path does not exist"
        if logger:
            logger.error(err)

        raise FileNotFoundError(err)

    try:
        with path.open(encoding="utf-8") as json_file:
            data = json.load(json_file)

        all_symbol_info = []

        for s in data["all_symbols_info"]:
            all_symbol_info.append(SymbolInfo(**s))

    except Exception as e:
        err = f"Failed to read a file {path} JSON error = {e}"
        if logger:
            logger.error(err)

        raise JSONError(err)

    return tuple(all_symbol_info)

def _ensure_dir(path: Path, logger: Optional[logging.Logger] = None):
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        if logger:
            logger.error(f"Failed to create broker path: {e}")
        raise

def _to_dict(obj):
    """Safely convert namedtuple/dataclass/dict to dict"""
    if hasattr(obj, "_asdict"):
        return obj._asdict()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return dict(obj)

def export_account_info(
    ac_info: AccountInfo | dict,
    file: Path,
    logger: Optional[logging.Logger] = None,
) -> bool:

    file.parent.mkdir(parents=True, exist_ok=True)

    try:
        payload = {
            "account_info": _to_dict(ac_info),
        }

        with file.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        return True

    except Exception as e:
        if logger:
            logger.error(f"Export account_info failed: {e}")
        return False

def export_all_symbol_info(
    all_symbol_info: Iterable[SymbolInfo | dict],
    file: Path,
    logger: Optional[logging.Logger] = None,
) -> bool:

    file.parent.mkdir(parents=True, exist_ok=True)

    try:
        payload = {
            "all_symbols_info": [_to_dict(s) for s in all_symbol_info],
        }

        with file.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        return True

    except Exception as e:
        if logger:
            logger.error(f"Export symbol_info failed: {e}")
        return False

def export_terminal_info(
    terminal_info: TerminalInfo | dict,
    file: Path,
    logger: Optional[logging.Logger] = None,
) -> bool:

    file.parent.mkdir(parents=True, exist_ok=True)

    try:
        payload = {
            "terminal_info": _to_dict(terminal_info),
        }

        with file.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        return True

    except Exception as e:
        if logger:
            logger.error(f"Export terminal_info failed: {e}")
        return False

def import_terminal_info(
    path: Path,
    logger: Optional[logging.Logger] = None,
) -> TerminalInfo:

    if not path.is_file():
        err = "Terminal info file does not exist"
        if logger:
            logger.error(err)
        raise FileNotFoundError(err)

    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)

        return TerminalInfo(**data["terminal_info"])

    except Exception as e:
        err = f"Failed to read {path} JSON error = {e}"
        if logger:
            logger.error(err)
        raise JSONError(err)

