from __future__ import annotations

from typing import Union
from .OrderInfo import COrderInfo

from strategytester5.MetaTrader5.api import OverLoadedMetaTrader5API
import MetaTrader5
from strategytester5.MetaTrader5 import TradeOrder


class CHistoryOrderInfo(COrderInfo):
    def __init__(self, order: TradeOrder, terminal: Union[OverLoadedMetaTrader5API|MetaTrader5]):

        """
        A lightweight Python wrapper that resembles the MQL5 Standard Library class
        `CHistoryOrderInfo` and provides convenient, read-only access to MetaTrader 5
        history order properties.

        This class acts like a cursor over a single selected historical order stored in
        `self._order`. The selected order can be supplied at construction time or later
        via `select_order()` / `select_by_index()`.

        [MQL5 Reference](https://www.mql5.com/en/docs/standardlibrary/tradeclasses/chistoryorderinfo)

        Parameters
        ----------
        order : Any, optional
            A history order object returned by MetaTrader 5 Python history functions
            such as `mt5.history_orders_get()`.
        terminal : Initialize native MetaTrader5 API or the simulated one from the StrategyTester instance

        Notes
        -----
        - If no order is selected, properties return `None` or `"N/A"`.
        - `time_setup`, `time_done`, and `time_expiration` are returned as timezone-aware
        UTC datetimes where possible.
        - This wrapper does not modify terminal state; it only reads history order data.

        Method groups mirror the MQL5 layout:
        - Integer properties: TimeSetup, OrderType, State, TypeFilling, TypeTime, Magic, etc.
        - Double properties: VolumeInitial, VolumeCurrent, PriceOpen, StopLoss, TakeProfit, etc.
        - String properties: Symbol, Comment, ExternalId
        - Generic accessors: InfoInteger, InfoDouble, InfoString
        - Selection helpers: Ticket, SelectByIndex
        """
        
        super().__init__(order, terminal)