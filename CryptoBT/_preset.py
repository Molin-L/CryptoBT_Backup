
from .dto import SymbolConfig

BTCUSDT = SymbolConfig(
    name='BTC-USDT',
    exchange='binance',
    tick_size=0.00001,
    min_trade_amount=0.00001,
    max_trade_amount=130)

symbol_config_map = {
    'BTC-USDT': BTCUSDT
}