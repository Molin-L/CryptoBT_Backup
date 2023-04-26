import numpy as numpy
import pandas as pd

from abc import ABCMeta, abstractmethod
from idl import *
from typing import Callable, Dict, List, Optional, Sequence, Tuple, Type, Union
from _stats import get_backtesting_results

class Strategy(metaclass=ABCMeta):
    def __init__(self, trading_engine, data, params):
        self.trading_engine = trading_engine
        self.data = data
        self.params = params
        self.position = None

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


class _TradingEngine:
    def __init__(self, data, balance, maker_fee, taker_fee, hedge_mode, exclusive_orders):
        self.data = data
        self.balance = balance
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.position = None
        self.pending_orders = []
        self.trades = []
        self.equity = None
        self.hedge_mode = hedge_mode
        self.exclusive_orders = exclusive_orders

    def new_order(self, *,
                  side: Side,
                  size: Optional[float] = None,
                  price: Optional[float] = None,
                  stop: Optional[float] = None,
                  tp: Optional[float] = None,
                  sl: Optional[float] = None,
                  trail: Optional[float] = None,
                  ExecType: Optional[ExecType] = ExecType.TakerFill
                  ):
        # Todo: implement
        pass

    def set_leverage(self, leverage):
        # Todo: implement
        pass

    def handle_execution(self):

        for order in self.pending_orders:
            pass
        self.pending_orders = []

class Order:
    def __init__(self, side: Side,
                 size: Optional[float] = None,
                 price: Optional[float] = None,
                 stop: Optional[float] = None,
                 tp: Optional[float] = None,
                 sl: Optional[float] = None,
                 trail: Optional[float] = None,
                 ExecType: Optional[ExecType] = ExecType.TakerFill):
        self.side = side
        self.size = size
        self.price = price
        self.stop = stop
        self.tp = tp
        self.sl = sl
        self.trail = trail
        self.ExecType = ExecType

        self.OrderStatus = OrderStatus.New

    def cancel(self):
        # Todo: implement
        self.OrderStatus = OrderStatus.Canceled


class Backtest:
    def __init__(self, data: pd.DataFrame,
                 strategy: Type[Strategy],
                 balance: Optional[float] = 1000000,
                 maker_fee: Optional[float] = 0,
                 taker_fee: Optional[float] = 0,
                 hedge_mode: Optional[bool] = False,
                 exclusive_orders: Optional[bool] = False):
        self._results = None
        self.data:pd.DataFrame = data
        self.balance = balance
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.hedge_mode = hedge_mode
        self.exclusive_orders = exclusive_orders

        self._strategy: Type[Strategy] = strategy


    def run(self, **kwargs) -> pd.Series:

        trading_engine = _TradingEngine(self.data, self.balance, self.maker_fee, self.taker_fee, self.hedge_mode, self.exclusive_orders)
        strategy = self._strategy(trading_engine, self.data, kwargs)

        strategy.init()

        for i in range(len(self.data)):
            strategy.data = self.data.iloc[:i]

            strategy.next()
            trading_engine.handle_execution()

        else:
            for trade in trading_engine.trades:
                trade.close()

        self._results = get_backtesting_results(data=self.data, trades=trading_engine.trades, equity=trading_engine.equity)
        return self._results
