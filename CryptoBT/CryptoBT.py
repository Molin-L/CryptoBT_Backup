import copy
import uuid
from abc import ABCMeta, abstractmethod
from typing import Optional, Type, Callable

import pandas as pd
import numpy as np
from itertools import chain

from ._preset import symbol_config_map
from ._stats import get_backtesting_results
from .dto import SymbolConfig
from .idl import *
from ._util import _as_str, _Indicator, _Data, try_


class Strategy(metaclass=ABCMeta):
    def __init__(self, trading_engine, data, params):
        self.trading_engine = trading_engine
        self.data = data
        self.params = params
        self.position = None
        self._indicators = []

    @abstractmethod
    def init(self):
        pass

    @abstractmethod
    def next(self):
        pass

    def buy(self, *,
            size: Optional[float] = None,
            price: Optional[float] = None,
            stop: Optional[float] = None,
            tp: Optional[float] = None,
            sl: Optional[float] = None,
            trail: Optional[float] = None,
            exec_type: Optional[ExecType] = ExecType.TakerFill
            ):
        return self.trading_engine.new_order(side=Side.Buy, size=size, price=price, stop=stop, tp=tp, sl=sl,
                                             trail=trail, exec_type=exec_type)

    def sell(self, *,
             size: Optional[float] = None,
             price: Optional[float] = None,
             stop: Optional[float] = None,
             tp: Optional[float] = None,
             sl: Optional[float] = None,
             trail: Optional[float] = None,
             exec_type: Optional[ExecType] = ExecType.TakerFill
             ):
        return self.trading_engine.new_order(side=Side.Sell, size=size, price=price, stop=stop, tp=tp, sl=sl,
                                             trail=trail, exec_type=exec_type)

    def I(self,  # noqa: E743
          func: Callable, *args,
          name=None, plot=True, overlay=None, color=None, scatter=False,
          **kwargs) -> np.ndarray:
        if name is None:
            params = ','.join(filter(None, map(_as_str, chain(args, kwargs.values()))))
            func_name = _as_str(func)
            name = (f'{func_name}({params})' if params else f'{func_name}')
        else:
            name = name.format(*map(_as_str, args),
                               **dict(zip(kwargs.keys(), map(_as_str, kwargs.values()))))

        try:
            value = func(*args, **kwargs)
        except Exception as e:
            raise RuntimeError(f'Indicator "{name}" error') from e

        if isinstance(value, pd.DataFrame):
            value = value.values.T

        if value is not None:
            value = try_(lambda: np.asarray(value, order='C'), None)
        is_arraylike = bool(value is not None and value.shape)

        # Optionally flip the array if the user returned e.g. `df.values`
        if is_arraylike and np.argmax(value.shape) == 0:
            value = value.T

        if not is_arraylike or not 1 <= value.ndim <= 2 or value.shape[-1] != len(self.data.Close):
            raise ValueError(
                'Indicators must return (optionally a tuple of) numpy.arrays of same '
                f'length as `data` (data shape: {self.data.Close.shape}; indicator "{name}" '
                f'shape: {getattr(value, "shape", "")}, returned value: {value})')

        if plot and overlay is None and np.issubdtype(value.dtype, np.number):
            x = value / self.data.Close
            # By default, overlay if strong majority of indicator values
            # is within 30% of Close
            with np.errstate(invalid='ignore'):
                overlay = ((x < 1.4) & (x > .6)).mean() > .6

        value = _Indicator(value, name=name, plot=plot, overlay=overlay,
                           color=color, scatter=scatter,
                           # _Indicator.s Series accessor uses this:
                           index=self.data.index)
        self._indicators.append(value)
        return value


class _TradingEngine:
    def __init__(self, data, balance, maker_fee, taker_fee, hedge_mode, exclusive_orders, symbol: str = "BTC-USDT"):
        self.symbol = symbol
        self.data = data
        self.init_balance = balance
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        buy_position = Position(symbol=self.symbol)
        sell_position = Position(symbol=self.symbol)
        self.position = {
            Side.Buy: buy_position, Side.Sell: sell_position
        }
        self.pending_orders = []  # Store new order and created order
        self.trades = []

        self.equity = balance
        self.equitys = [self.equity]
        self.hedge_mode = hedge_mode
        self.exclusive_orders = exclusive_orders

        self.symbol_config: SymbolConfig = symbol_config_map[symbol]
        self.leverage = 1.0

        self._i = 0

    def new_order(self, *,
                  side: Side,
                  size: float = None,
                  price: Optional[float] = None,
                  stop: Optional[float] = None,
                  tp: Optional[float] = None,
                  sl: Optional[float] = None,
                  trail: Optional[float] = None,
                  exec_type: Optional[ExecType] = ExecType.TakerFill
                  ):
        i = self._i = len(self.data) - 1
        if price <= 0 or (size != None and size <= 0):
            return None
        # Todo: Implement exclusive orders
        if size is None:
            size = self.equity / price
        size = self._verify_order_size(size)
        if price is None:
            # Market order
            price = self.data[i].open
        if size * price > self.equity:
            return None
        self.equity -= size * price
        order = Order(side=side, size=size, price=price, stop=stop, tp=tp, sl=sl, trail=trail, exec_type=exec_type)
        self.pending_orders.append(order)
        return order

    def set_leverage(self, leverage):
        # Todo: implement
        pass

    def handle_execution(self):
        i = self._i = len(self.data) - 1

        current_data = self.data.iloc[i]

        current_price = current_data.Close
        for order in self.pending_orders:
            if current_data.Low <= order.price <= current_data.High:
                # Order price hit
                if order.reduce_only:
                    # Close Position
                    pnl = self.position[order.side.opposite()].close(current_price, order.size)

                    # Return equity
                    self.equity += pnl

                    # Record trade
                    self._close_prev_trades(order)
                else:
                    # Open Position
                    if self.position[order.side].size == 0:
                        self.position[order.side].open_with_order(order)
                    self.trades.append(Trade(symbol=self.symbol, size=order.size, entry_price=order.price,
                                             side=order.side, time=i))

                # The order of tpsl will only be placed after the parent order is filled
                if order.tp and ((order.side == Side.Buy and order.tp >= current_data.Low) or (
                        order.side == Side.Sell and order.tp <= current_data.High)):
                    tp_order = self.new_order(side=order.side.opposite(), size=order.size, price=order.tp)
                    tp_order.parent_order_id = order.order_id
                    tp_order.reduce_only = True
                    self.pending_orders.append(tp_order)
                if order.sl and ((order.side == Side.Buy and order.sl <= current_data.Hig) or (
                        order.side == Side.Sell and order.sl >= current_data.Low)):
                    sl_order = self.new_order(side=order.side.opposite(), size=order.size, price=order.sl)
                    sl_order.parent_order_id = order.order_id
                    sl_order.reduce_only = True
                    self.pending_orders.append(sl_order)

                self.pending_orders.remove(order)
            else:
                # Post only
                order.OrderStatus = OrderStatus.Created

        self.pending_orders = []
        self.equitys.append(self.equity)

    def _verify_order_size(self, origin_size: float) -> float:
        result = int(origin_size / self.symbol_config.tick_size) * self.symbol_config.tick_size
        if result > self.symbol_config.max_order_size:
            result = self.symbol_config.max_order_size
        return result

    def _close_prev_trades(self, close_order):
        for trade in reversed(self.trades):
            if trade.trade_status == TradeStatus.Open and trade.side == close_order.side.opposite():
                trade.trade_status = TradeStatus.Closed

                remain_trade = trade.close(close_order)
                if remain_trade is not None:
                    self.trades.append(remain_trade)


class Position:
    def __init__(self, symbol: str = "BTC-USDT", size: float = 0, entry_price: float = 0,
                 side: Side = Side.Buy,
                 time: int = 0):
        self.symbol = symbol
        self.size = size
        self.entry_price = entry_price
        self.side = side
        self.time = time

    def open_with_order(self, order):
        assert order.side == self.side
        if self.size == 0:
            self.entry_price = order.price
        else:
            self.entry_price = order.price * order.size / (self.size + order.size) + self.entry_price * self.size / (
                    self.size + order.size)
        self.size += order.size

    def get_pnl(self, price: float, size: float = None) -> float:
        if size is None:
            size = self.size
        if self.side == Side.Buy:
            return (price - self.entry_price) * size
        else:
            return (self.entry_price - price) * size

    def close(self, price: float, size: float = None):
        if size is None or size > self.size:
            size = self.size
        result = self.get_pnl(price)

        self.size -= size

        return result


class Order:
    def __init__(self, side: Side,
                 size: Optional[float] = None,
                 price: Optional[float] = None,
                 stop: Optional[float] = None,
                 tp: Optional[float] = None,
                 sl: Optional[float] = None,
                 trail: Optional[float] = None,
                 create_time: Optional[int] = None,
                 exec_type: Optional[ExecType] = ExecType.TakerFill,
                 parent_order_id: Optional[uuid.UUID] = None,
                 reduce_only: Optional[bool] = False
                 ):
        self.side = side
        self.size = size
        self.price = price
        self.stop = stop
        self.tp = tp
        self.sl = sl
        self.trail = trail
        self.create_time = create_time
        self.exec_type = exec_type
        self.exec_time = None

        self.OrderStatus = OrderStatus.New
        self.order_id = uuid.uuid4()
        self.parent_order_id = parent_order_id
        self.reduce_only = reduce_only

    def cancel(self):
        # Todo: implement
        self.OrderStatus = OrderStatus.Canceled


class Trade:

    def __init__(self, symbol: str = "BTC-USDT", size: float = 0, entry_price: float = 0,
                 side: Side = Side.Buy,
                 entry_order_id: Optional[uuid.UUID] = None,
                 time: int = 0):
        self.symbol = symbol
        self.size = size
        self.entry_price = entry_price
        self.entry_size = size
        self.exit_price = 0
        self.side = side
        self.entry_order_id = entry_order_id
        self.entry_time = time
        self.exit_time = None
        self.exit_size = None
        self.exit_order_id = None
        self.trade_status = TradeStatus.Open

    def __copy__(self):
        copy_obj = Trade(symbol=self.symbol, size=self.size, entry_price=self.entry_price, side=self.side,
                         entry_order_id=self.entry_order_id, time=self.entry_time)
        return copy_obj

    def close(self, order: Order):
        remain_trade = None
        remain_size = order.size - self.size
        self.exit_size = order.size
        self.exit_price = order.price
        self.exit_time = order.exec_time
        self.exit_order_id = order.order_id

        if remain_size < 0:
            remain_trade = copy.deepcopy(self)
            remain_trade.size = -remain_size
            order.size = 0

        self.trade_status = TradeStatus.Closed

        return remain_trade


class Backtest:
    def __init__(self, data: pd.DataFrame,
                 strategy: Type[Strategy],
                 balance: Optional[float] = 1000000,
                 maker_fee: Optional[float] = 0,
                 taker_fee: Optional[float] = 0,
                 hedge_mode: Optional[bool] = False,
                 exclusive_orders: Optional[bool] = False):
        self._results = None

        self.balance = balance
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.hedge_mode = hedge_mode
        self.exclusive_orders = exclusive_orders

        self._strategy: Type[Strategy] = strategy
        self.data: pd.DataFrame = data
        self.data.columns = map(lambda x: x.lower().capitalize(), self.data.columns)

    def run(self, **kwargs) -> pd.Series:

        trading_engine = _TradingEngine(self.data, self.balance, self.maker_fee, self.taker_fee, self.hedge_mode,
                                        self.exclusive_orders)
        strategy = self._strategy(trading_engine, self.data, kwargs)

        strategy.init()

        for i in range(len(self.data)):
            strategy.data = self.data.iloc[:i]

            strategy.next()
            trading_engine.handle_execution()

        else:
            for trade in trading_engine.trades:
                trade.close()

        self._results = get_backtesting_results(data=self.data, trades=trading_engine.trades,
                                                equity=trading_engine.equitys)
        return self._results
