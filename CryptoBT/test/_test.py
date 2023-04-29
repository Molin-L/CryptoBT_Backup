import unittest
import warnings
from unittest import TestCase
from CryptoBT import Strategy, Backtest
from CryptoBT.lib import crossover
from CryptoBT.test import BTCUSDT, SMA

class SMAStrategy(Strategy):
    # NOTE: These values are also used on the website!
    fast = 10
    slow = 30

    def init(self):
        self.sma1 = self.I(SMA, self.data.Close, self.fast)
        self.sma2 = self.I(SMA, self.data.Close, self.slow)

    def next(self):
        if crossover(self.sma1, self.sma2):
            self.position.close()
            self.buy()
        elif crossover(self.sma2, self.sma1):
            self.position.close()
            self.sell()

class TestBacktest(TestCase):

    def test_backtest(self):
        bt = Backtest(BTCUSDT, SMAStrategy)
        bt.run()

if __name__ == '__main__':
    warnings.filterwarnings('error')
    unittest.main()