from enum import Enum

class ExecType(Enum):
    TakerFill = 1
    MakerFill = 2

class Side(Enum):
    Buy = 1
    Sell = 2

    def opposite(self):
        if self == Side.Buy:
            return Side.Sell
        return Side.Buy

class Position(Enum):
    Long = 1
    Short = 2
    Hedge = 3

class OrderStatus(Enum):
    New = 1
    Created = 2
    TakerFill = 3
    MakerFill = 4
    Canceled = 5
    Rejected = 6
    Expired = 7

class SymbolType(Enum):
    Spot = 1
    Future = 2
    Option = 3

class TradeStatus(Enum):
    Open = 1
    Closed = 2