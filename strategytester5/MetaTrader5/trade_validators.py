from ..MetaTrader5 import SymbolInfo, Tick
from ..MetaTrader5.constants import MetaTrader5Constants
import logging


class TradeValidators:
    def __init__(self,
                 symbol_info: SymbolInfo,
                 logger: logging.Logger):

        """
        This is the equivalent of MetaTrader5's trade validation system. The methods of this class are used by the simulator before opening or modifying any trade to ensure that the trade would be accepted by the MetaTrader 5 terminal if it were executed in real time.

        Args:
            symbol_info (SymbolInfo): The symbol information object containing the trading parameters for the symbol being traded
            logger (logging.Logger): The logger to use for logging validation warnings and errors
        """

        self.symbol_info = symbol_info
        self.logger = logger

    def is_valid_lotsize(self, lotsize: float) -> bool:

        """
        Checks if a given lotsize is a valid one i.e,. not below the minimum value, not above the maximum accepted lotsize, and a multiple of the volume step value.

        Args:
            lotsize: Lotsize for the new trade

        Returns:
            bool: True if a lotsize is valid, False otherwise
        """

        # Validate lotsize

        if lotsize < self.symbol_info.volume_min:  # check if the received lotsize is smaller than minimum accepted lot of a symbol
            self.logger.warning(
                f"Trade validation failed: lotsize ({lotsize}) is less than minimum allowed ({self.symbol_info.volume_min})")
            return False

        if lotsize > self.symbol_info.volume_max:  # check if the received lotsize is greater than the maximum accepted lot
            self.logger.warning(
                f"Trade validation failed: lotsize ({lotsize}) is greater than maximum allowed ({self.symbol_info.volume_max})")
            return False

        step_count = lotsize / self.symbol_info.volume_step

        if abs(step_count - round(step_count)) > 1e-7:  # check if the stoploss is a multiple of the step size
            self.logger.warning(
                f"Trade validation failed: lotsize ({lotsize}) must be a multiple of step size ({self.symbol_info.volume_step})")
            return False

        return True

    def is_valid_freeze_level(self, tick_info: Tick, entry: float, stop_price: float, order_type: int) -> bool:
        """
        Checks if the entry price or stop loss / take profit price is too close to the current market price based on the symbol's freeze level.

        Args:
            tick_info (Tick): The current tick information for the symbol
            entry (float): The entry price of the order
            stop_price (float): The stop loss or take profit price to validate
            order_type (int): The MetaTrader 5 order type (e.g., BUY, SELL, BUY_LIMIT, etc.)

        """

        freeze_level = self.symbol_info.trade_freeze_level
        if freeze_level <= 0:
            return True  # No freeze restriction

        point = self.symbol_info.point
        freeze_distance = freeze_level * point

        bid = tick_info.bid
        ask = tick_info.ask

        def log_fail(msg: str, distance: float):
            self.logger.warning(
                f"{msg} | distance={distance / point:.1f} pts < "
                f"freeze_level={freeze_level} pts"
            )

        # ---------------- Pending Orders ----------------

        if order_type == MetaTrader5Constants.ORDER_TYPE_BUY_LIMIT:
            dist = ask - entry
            if dist < freeze_distance:
                log_fail("BuyLimit cannot be modified: Ask - OpenPrice", dist)
                return False
            return True

        if order_type == MetaTrader5Constants.ORDER_TYPE_SELL_LIMIT:
            dist = entry - bid
            if dist < freeze_distance:
                log_fail("SellLimit cannot be modified: OpenPrice - Bid", dist)
                return False
            return True

        if order_type == MetaTrader5Constants.ORDER_TYPE_BUY_STOP:
            dist = entry - ask
            if dist < freeze_distance:
                log_fail("BuyStop cannot be modified: OpenPrice - Ask", dist)
                return False
            return True

        if order_type == MetaTrader5Constants.ORDER_TYPE_SELL_STOP:
            dist = bid - entry
            if dist < freeze_distance:
                log_fail("SellStop cannot be modified: Bid - OpenPrice", dist)
                return False
            return True

        # ---------------- Open Positions (SL / TP modification) ----------------

        # Buy position
        if order_type == MetaTrader5Constants.ORDER_TYPE_BUY:
            if stop_price <= 0:
                return True

            if stop_price < entry:  # StopLoss
                dist = bid - stop_price
                if dist < freeze_distance:
                    log_fail("Buy position SL cannot be modified: Bid - SL", dist)
                    return False
            else:  # TakeProfit
                dist = stop_price - bid
                if dist < freeze_distance:
                    log_fail("Buy position TP cannot be modified: TP - Bid", dist)
                    return False

            return True

        # Sell position
        if order_type == MetaTrader5Constants.ORDER_TYPE_SELL:
            if stop_price <= 0:
                return True

            if stop_price > entry:  # StopLoss
                dist = stop_price - ask
                if dist < freeze_distance:
                    log_fail("Sell position SL cannot be modified: SL - Ask", dist)
                    return False
            else:  # TakeProfit
                dist = ask - stop_price
                if dist < freeze_distance:
                    log_fail("Sell position TP cannot be modified: Ask - TP", dist)
                    return False

            return True

        self.logger.error("Unknown MetaTrader 5 order type")
        return False

    def is_max_orders_reached(self, open_orders: int, ac_limit_orders: int) -> bool:
        """Checks whether the maximum number of orders for the account is reached

        Args:
            open_orders (int): The number of opened orders
            ac_limit_orders (int): Maximum number of orders allowed for the account

        Returns:
            bool: True if the threshold is reached, otherwise, it returns false.
        """

        if 0 < ac_limit_orders <= open_orders:
            self.logger.critical(f"Pending Orders limit of {ac_limit_orders} is reached!")
            return True

        return False

    def is_symbol_volume_reached(self, symbol_volume: float, volume_limit: float) -> bool:

        """Checks if the maximum allowed volume is reached for a particular instrument

        Returns:
            bool: True if the condition is reached and False when it is not.
        """

        if 0 < volume_limit <= symbol_volume:
            self.logger.critical(f"Symbol Volume limit of {volume_limit} is reached!")
            return True

        return False

    def is_valid_stops_level(self, entry: float, stop_price: float, stops_type: str = '') -> bool:

        """Checks if either stop loss or take profit is above the minimum allowed distance from the entry price (freeze level + stop level). If stops_type is provided, it will be used in the warning message, otherwise, the message will refer to "Either SL or TP".

        Args:
            entry (float): The entry price of the order
            stop_price (float): The stop loss or take profit price to validate
            stops_type (str, optional): The type of stop to validate ("Stoploss" or "Takeprofit"). Defaults to ''.

        Returns:
            bool: True for valid stop level and False for invalid stop level
        """

        point = self.symbol_info.point
        stop_level = self.symbol_info.trade_stops_level * point

        distance = abs(entry - stop_price)

        if stop_price <= 0:
            return True

        if distance < stop_level:
            self.logger.warning(
                f"{'Either SL or TP' if stops_type == '' else stops_type} is too close to the market. Min allowed distance = {stop_level}")
            return False

        return True

    def is_valid_sl(self, entry: float, sl: float, order_type: int) -> bool:

        """Checks if a given stop loss price is valid for a given entry price and order type. It checks if the stop loss is at a valid distance from the entry price and if it is in the correct direction (below the entry for buy orders and above the entry for sell orders).

        Args:
            entry (float): The entry price of the order
            sl (float): The stop loss price to validate
            order_type (int): The MetaTrader 5 order type (e.g., BUY, SELL, BUY_LIMIT, etc.)

        Returns:
            bool: True for valid stop loss and False for invalid stop loss
        """

        if not self.is_valid_stops_level(entry, sl, "Stoploss"):  # check for stops and freeze levels
            return False

        if sl > 0:
            if order_type in MetaTrader5Constants.BUY_ACTIONS:  # buy action

                if sl >= entry:
                    self.logger.warning(
                        f"Trade validation failed: {MetaTrader5Constants.ORDER_TYPE_MAP[order_type]} stop loss ({sl}) must be below order opening price ({entry})")

                    # print("entry: ", entry, " sl ", sl)
                    return False

            elif order_type in MetaTrader5Constants.SELL_ACTIONS:  # sell action

                if sl <= entry:
                    self.logger.warning(
                        f"Trade validation failed: {MetaTrader5Constants.ORDER_TYPE_MAP[order_type]} stop loss ({sl}) must be above order opening price ({entry})")

                    # print("entry: ", entry, " sl ", sl)
                    return False

            else:
                self.logger.error("Unknown MetaTrader 5 order type")
                return False

        return True

    def is_valid_tp(self, entry: float, tp: float, order_type: int) -> bool:

        """Checks if a given take profit price is valid for a given entry price and order type. It checks if the take profit is at a valid distance from the entry price and if it is in the correct direction (above the entry for buy orders and below the entry for sell orders).

        Args:
            entry (float): The entry price of the order
            tp (float): The take profit price to validate
            order_type (int): The MetaTrader 5 order type (e.g., BUY, SELL, BUY_LIMIT, etc.)

        Returns:
            bool: True for valid take profit and False for invalid take profit
        """

        if not self.is_valid_stops_level(entry, tp, "Takeprofit"):  # check for stops and freeze levels
            return False

        if tp > 0:
            if order_type in MetaTrader5Constants.BUY_ACTIONS:  # buy position
                if tp <= entry:
                    self.logger.warning(
                        f"Trade validation failed: {MetaTrader5Constants.ORDER_TYPE_MAP[order_type]} take profit ({tp}) must be above order opening price ({entry})")
                    return False
            elif order_type in MetaTrader5Constants.SELL_ACTIONS:  # sell position
                if tp >= entry:
                    self.logger.warning(
                        f"Trade validation failed: {MetaTrader5Constants.ORDER_TYPE_MAP[order_type]} take profit ({tp}) must be below order opening price ({entry})")
                    return False
            else:
                self.logger.error("Unknown MetaTrader 5 order type")
                return False

        return True

    @staticmethod
    def price_equal(a: float, b: float, eps: float = 1e-8) -> bool:
        return abs(a - b) <= eps

    def is_valid_entry_price(self, tick_info: Tick, price: float, order_type: int) -> bool:
        """
        Checks if the entry price is valid for a given tick and position type. It checks if the entry price is equal to the current ask (for buy orders) or bid (for sell orders) within a small epsilon.

        Args:
            tick_info (Tick): The current tick information for the symbol
            price (float): The entry price to validate
            order_type (int): The MetaTrader 5 order type (e.g., BUY, SELL)

        Returns:
            bool: True for valid entry price and False for invalid entry price

        """

        eps = pow(10, -self.symbol_info.digits)
        if order_type == MetaTrader5Constants.ORDER_TYPE_BUY:  # BUY
            if not self.price_equal(a=price, b=tick_info.ask, eps=eps):
                self.logger.warning(f"Trade validation failed: Buy price {price} != ask {tick_info.ask}")
                return False

        elif order_type == MetaTrader5Constants.ORDER_TYPE_SELL:  # SELL
            if not self.price_equal(a=price, b=tick_info.bid, eps=eps):
                self.logger.warning(f"Trade validation failed: Sell price {price} != bid {tick_info.bid}")
                return False
        else:
            self.logger.error("Unknown MetaTrader 5 position type")
            return False

        return True

    @staticmethod
    def is_valid_pending_price(price, tick, order_type):

        """
        Checks if the pending order price is valid for a given tick and position type. It checks if the pending order price is below the current ask (for buy limit orders) or above the current bid (for sell limit orders) or above the current ask (for buy stop orders) or below the current bid (for sell stop orders).

        Args:
            price (float): The pending order price to validate
            tick (Tick): The current tick information for the symbol
            order_type (int): The MetaTrader 5 pending order type (e.g., BUY_LIMIT, SELL_LIMIT, etc.)

        """

        if order_type == MetaTrader5Constants.ORDER_TYPE_BUY_LIMIT:
            return price < tick.ask
        elif order_type == MetaTrader5Constants.ORDER_TYPE_SELL_LIMIT:
            return price > tick.bid
        elif order_type == MetaTrader5Constants.ORDER_TYPE_BUY_STOP:
            return price > tick.ask
        elif order_type == MetaTrader5Constants.ORDER_TYPE_SELL_STOP:
            return price < tick.bid
        return False

    def is_there_enough_money(self, margin_required: float, free_margin: float) -> bool:

        """
        Checks if there is enough free margin to open a trade with the required margin. It also checks if the margin required is a valid non-negative number.

        Args:
            margin_required (float): The margin required to open the trade
            free_margin (float): The current free margin of the account

        Returns:
            bool: True if there is enough free margin to open the trade and False otherwise
        """

        if margin_required < 0:
            self.logger.warning("Trade validation failed: Cannot calculate margin requirements")
            return False

        # Check free margin
        if margin_required > free_margin:
            self.logger.warning(f'Trade validation failed: Not enough money to open trade. '
                                f'Required: {margin_required:.2f}, '
                                f'Free margin: {free_margin:.2f}')

            return False

        return True