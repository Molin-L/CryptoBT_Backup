from enum import Enum

class ExecType(Enum):
    TakerFill = 1
    MakerFill = 2

class Side(Enum):
    Buy = 1
    Sell = 2

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
