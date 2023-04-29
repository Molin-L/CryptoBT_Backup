from typing import Optional
from .idl import SymbolType


class SymbolConfig:
    def __init__(self, name: str, exchange: str = "binance", symbol_type: SymbolType = SymbolType.Future,
                 tick_size: float = 0.00001, min_trade_amount: float = 0.00001, max_trade_amount: float = 130, is_active: bool = True):
        self.is_active = is_active
        self.name = name
        self.exchange = exchange
        self.symbol_type = symbol_type
        self.tick_size = tick_size
        self.min_order_size = min_trade_amount
        self.max_order_size = max_trade_amount
        self.is_active = is_active

    def __str__(self):
        return f"Symbol({self.name}, {self.type})"

    def __repr__(self):
        return self.__str__()
