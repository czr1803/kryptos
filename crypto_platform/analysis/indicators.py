import pandas as pd
import numpy as np
import talib as ta
import matplotlib.pyplot as plt

from catalyst.api import record

from logbook import Logger
from crypto_platform.config import TAConfig as CONFIG
from crypto_platform.utils import viz

log = Logger('INDICATOR')


def get_last(arr, name):
    return arr[name][arr[name].index[-1]]


class TAAnalysis(object):
    def __init__(self, context=None, data=None):
        self.context = None
        self.data = None

    def update(self, context, data):
        self.context = context
        self.data = data

    @property
    def prices(self):
        # Get price, open, high, low, close
        return self.data.history(
            self.context.asset,
            bar_count=self.context.BARS,
            fields=['price', 'open', 'high', 'low', 'close', 'volume'],
            frequency='1d')

    @property
    def current_price(self):
        return self.data.current(self.context.asset, 'price')

    @property
    def bbands(self):
        return BBANDS(self.current_price, self.prices.close)

    @property
    def psar(self):
        return PSAR(self.current_price, self.prices.low, self.prices.high)

    @property
    def macd(self):
        return MACD(self.prices)

    @property
    def macdfix(self):
        return MACDFIX(self.prices)

    @property
    def obv(self):
        return OBV(self.prices.close, self.prices.volume)

    @property
    def rsi(self):
        return RSI(self.prices)


class BBANDS(object):
    def __init__(self, price, closes):
        self.price = price
        self.closes = closes

        self.calculate()

    def calculate(self):
        self.upper, self.middle, self.lower = ta.BBANDS(self.closes.as_matrix(), matype=ta.MA_Type.T3)

    def record(self):
        record(upper=self.upper[-1], middle=self.middle[-1], lower=self.lower[-1])

    def plot(self, results, pos):
        y_label = 'BBands'
        viz.plot_metric(results, 'price', pos, label='price', color='black')
        viz.plot_metric(results, 'upper', pos, y_label=y_label, label='upper')
        viz.plot_metric(results, 'middle', pos, y_label=y_label, label='middle')
        viz.plot_metric(results, 'lower', pos, y_label=y_label, label='lower')
        plt.legend()

    @property
    def is_bullish(self):
        print('Comparing {} to {}'.format(self.price, self.upper[-1]))
        if self.price > self.upper[-1]:
            return True
        return False

    @property
    def is_bearish(self):
        if self.price < self.lower[-1]:
            return True
        return False


class PSAR(object):
    def __init__(self, current_price, high, low):
        self.current_price = current_price
        self.calculate(high, low)

    def calculate(self, high, low):
        self.psar = ta.SAR(
            high.as_matrix(),
            low.as_matrix(),
            acceleration=CONFIG.SAR_ACCEL,
            maximum=CONFIG.SAR_MAX)

    def record(self):
        record(psar=self.psar[-1])

    def plot(self, results, pos):
        y_label = 'PSAR'
        viz.plot_metric(results, 'price', pos, label='price', color='black')
        viz.plot_metric(results, 'psar', pos, y_label=y_label, label='psar')
        plt.legend()

    @property
    def is_bullish(self):
        pass

    @property
    def is_bearish(self):
        if self.current_price < self.psar[-1]:
            log.info('Closing position due to PSAR')
            return True
        return False


class MACD(object):

    def __init__(self, prices):
        self.closes = prices.close
        self.results = pd.DataFrame(index=prices)

        self.calculate()

    def calculate(self):

        self.macd, self.macd_signal, self.macd_hist = ta.MACD(
            self.closes.as_matrix(), fastperiod=CONFIG.MACD_FAST,
            slowperiod=CONFIG.MACD_SLOW, signalperiod=CONFIG.MACD_SIGNAL)

        self.results['macd'] = self.macd
        self.results['macd_signal'] = self.macd_signal

        self.macd_test = np.where((self.results.macd > self.results.macd_signal), 1, 0)

    def record(self):
        record(macd=self.macd[-1], macd_signal=self.macd_signal[-1],
               macd_hist=self.macd_hist[-1], macd_test=self.macd_test[-1])

    def plot(self, results, pos):
        y_label = 'MACD'
        viz.plot_metric(results, 'macd', pos, y_label=y_label, label='macd')
        viz.plot_metric(results, 'macd_signal', pos, y_label=y_label, label='macd_signal')
        viz.plot_metric(results, 'macd_hist', pos, y_label=y_label, label='macd_hist')
        viz.plot_buy_sells(results, pos, y_val='macd')

        plt.legend()

    @property
    def is_bullish(self):
        return self.macd_test[-1] == 1

    @property
    def is_bearish(self):
        return self.macd_test[-1] == 0


class MACDFIX(MACD):

    def __init__(self, prices):
        super(MACDFIX, self).__init__(prices)

    def calculate(self):
        self.macd, self.macd_signal, self.macd_hist = ta.MACDFIX(
            self.closes.as_matrix(), signalperiod=CONFIG.MACD_SIGNAL)

        self.results['macd'] = self.macd
        self.results['macd_signal'] = self.macd_signal

        self.macd_test = np.where((self.results.macd > self.results.macd_signal), 1, 0)


class OBV(object):
    def __init__(self, close, volume):
        super(OBV, self).__init__()
        self.close = close
        self.volume = volume
        self.calculate()

    def calculate(self):
        self.obv = ta.OBV(
            self.close.as_matrix(),
            self.volume.as_matrix()
        )

    def record(self):
        record(obv=self.obv[-1])

    def plot(self, results, pos):
        y_label = 'OBV'
        viz.plot_metric(results, 'obv', pos, y_label=y_label, label='obv')
        viz.plot_buy_sells(results, pos, y_val='macd')

        plt.legend()

    @property
    def is_bullish(self):
        return self.obv[-1] > self.obv[-2]

    @property
    def is_bearish(self):
        return self.obv[-1] < self.obv[-2]


class RSI(object):
    def __init__(self, prices):
        super(RSI, self).__init__()
        self.prices = prices

    def record(self):
        record(rsi=self.rsi[-1], overbought=self.overbought, oversold=self.oversold)

    def plot(self, results, pos):
        y_label = 'RSI'
        ax = viz.plot_metric(results, 'rsi', pos, y_label=y_label, label='rsi')

        overbought_line = [CONFIG.RSI_OVER_BOUGHT for i in results.index]
        oversold_line = [CONFIG.RSI_OVER_SOLD for i in results.index]
        ax.plot(results.index, overbought_line)
        ax.plot(results.index, oversold_line)

        overboughts = results[results['overbought']]
        oversolds = results[results['oversold']]
        viz.plot_points(overboughts, pos, y_val='rsi', color='red', label='overbought')
        viz.plot_points(oversolds, pos, y_val='rsi', label='oversold')

        plt.legend()

    @property
    def rsi(self):
        return ta.RSI(self.prices.close.as_matrix(), CONFIG.RSI_PERIOD)


    @property
    def overbought(self):
        # RSI OVER BOUGHT & Decreasing
        return self.rsi[-2] >= CONFIG.RSI_OVER_BOUGHT and self.rsi[-1] < CONFIG.RSI_OVER_BOUGHT


    @property
    def oversold(self):
        # RSI OVER SOLD & Increasing
        return self.rsi[-2] <= CONFIG.RSI_OVER_SOLD and self.rsi[-1] > CONFIG.RSI_OVER_SOLD


    @property
    def is_bullish(self):
        print(self.rsi[-1], self.rsi[-1])
        return self.rsi[-2] <= CONFIG.RSI_OVER_SOLD and self.rsi[-1] > CONFIG.RSI_OVER_SOLD

    @property
    def is_bearish(self):
        print(self.rsi[-1], self.rsi[-1])
        return self.rsi[-2] >= CONFIG.RSI_OVER_BOUGHT and self.rsi[-1] < CONFIG.RSI_OVER_BOUGHT

    @property
    def sma_rsi(self):
        return ta.SMA(self.rsi.as_matrix(), CONFIG.RSI_AVG_PERIOD)

    @property
    def sma_fast(self):
        close = self.get_fields('close')
        self.results['sma_fast'] = ta.SMA(close.as_matrix(), CONFIG.SMA_FAST)
        return self.results['sma_fast']

    @property
    def sma_slow(self):
        return ta.SMA(close.as_matrix(), CONFIG.SMA_SLOW)

    @property
    def sma_test(self):
        return np.where(self.sma_fast > self.sma_slow, 1, 0)


# def stoch(prices, df):
#     df['stoch_k'], df['stoch_d'] = ta.STOCH(
#         prices.high.as_matrix(), prices.low.as_matrix(),
#         prices.close.as_matrix(), slowk_period=CONFIG.STOCH_K,
#         slowd_period=CONFIG.STOCH_D)

#     # Stochastics OVER BOUGHT & Decreasing
#     df['stoch_over_bought'] = np.where(
#         (df.stoch_k > CONFIG.STOCH_OVER_BOUGHT) & (
#             df.stoch_k > df.stoch_k.shift(1)), 1, 0)

#     # Stochastics OVER SOLD & Increasing
#     df['stoch_over_sold'] = np.where(
#         (df.stoch_k < CONFIG.STOCH_OVER_SOLD) & (
#             df.stoch_k > df.stoch_k.shift(1)), 1, 0)

#     # Stochastics %K %D
#     # %K = (Current Close - Lowest Low)/(Highest High - Lowest Low) * 100
#     # %D = 3-day SMA of %K
#     df['stoch_k'], df['stoch_d'] = ta.STOCH(
#         prices.high.as_matrix(), prices.low.as_matrix(),
#         prices.close.as_matrix(), slowk_period=CONFIG.STOCH_K,
#         slowd_period=CONFIG.STOCH_D)

#     # Stochastics OVER BOUGHT & Decreasing
#     df['stoch_over_bought'] = np.where(
#         (df.stoch_k > CONFIG.STOCH_OVER_BOUGHT) & (
#             df.stoch_k > df.stoch_k.shift(1)), 1, 0)

#     # Stochastics OVER SOLD & Increasing
#     df['stoch_over_sold'] = np.where(
#         (df.stoch_k < CONFIG.STOCH_OVER_SOLD) & (
#             df.stoch_k > df.stoch_k.shift(1)), 1, 0)


# def stoch_rsi(prices, df):
#     df['fast_k'], df['fast_d'] = ta.STOCHRSI(
#         prices.close.as_matrix(),
#         timeperiod=CONFIG.TIMEPERIOD,
#         fastk_period=CONFIG.FASTK_PERIOD,
#         fastd_period=CONFIG.FASTD_PERIOD,
#         fastd_matype=CONFIG.FASTD_MATYPE)

#     # Stochastics %K %D
#     # %K = (Current Close - Lowest Low)/(Highest High - Lowest Low) * 100
#     # %D = 3-day SMA of %K
#     # df['stoch_k'], df['stoch_d'] = ta.STOCHRSI(
#     #     prices.high.as_matrix(), prices.low.as_matrix(),
#     #     prices.close.as_matrix(), slowk_period=CONFIG.STOCH_K,
#     #     slowd_period=CONFIG.STOCH_D)

#     # Stochastics OVER BOUGHT & Decreasing
#     df['stoch_over_bought'] = np.where(
#         (df.fast_k > CONFIG.STOCH_OVER_BOUGHT) & (
#             df.fast_k > df.fast_k.shift(1)), 1, 0)

#     # Stochastics OVER SOLD & Increasing
#     df['stoch_over_sold'] = np.where(
#         (df.fast_k < CONFIG.STOCH_OVER_SOLD) & (
#             df.fast_k > df.fast_k.shift(1)), 1, 0)