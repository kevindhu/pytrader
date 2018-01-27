from __future__ import division
from binance.client import Client
from binance.enums import *

API_KEY = "i1s87G06vlhZTdKy7z3V0IRRKujhvps4umFTELYqre3awoeD4ZKpzWsCm8O3HklK"
API_SECRET = "mpZGQfH0SraheOvbJZMANJCWapD5xDo0HfbapGGmjm3YCXxsvrFj4a5zVxNOqdoP"
NUM_THREADS = 100


class Trader:
    def __init__(self, chadAlert, logger):
        self.client = Client(API_KEY, API_SECRET, {"timeout": 60})
        self.chadAlert = chadAlert
        self.logger = logger

        # the ticker traded
        self.trading = ""
        self.USDT = 0.0

    def getCurrentUSDT(self):
        self.USDT = self.client.get_asset_balance(asset='USDT')

    # secondCoin = only the coin
    def buyCoin(self, coin, secondCoin, price, percentage):
        if self.trading != coin:
            print("not trading this coin, cannot buy!")
            return

        price = float("%.4g" % price)
        self.getCurrentUSDT()
        totalUSDTquantity = float(self.USDT["free"])
        self.logger.log("WE HAVE {0} AMOUNT OF USDT"
                        .format(totalUSDTquantity))
        USDTquantity = totalUSDTquantity * percentage
        self.logger.log("WE WILL USE {0} AMOUNT OF USDT"
                        .format(USDTquantity))


        secondCoinQuantity = float(self.truncate(USDTquantity /
                                                 self.chadAlert.USDTprices[secondCoin + "USDT"], 5))
        self.logger.log("BUYING {0} AMOUNT OF {1} FOR TRANSFERRING"
                        .format(secondCoinQuantity, secondCoin))

        firstOrder = self.client.order_market_buy(
            symbol=secondCoin + "USDT",
            quantity=secondCoinQuantity)

        coinQuantity = float(self.truncate((secondCoinQuantity / price) * 0.95, 0))

        self.logger.log("LIMIT BUYING {0} OF {1} AT {2}"
                        .format(coinQuantity, coin, str(price)))

        # limit buy the coin
        secondOrder = self.client.order_limit_buy(
            symbol=coin,
            type=ORDER_TYPE_LIMIT,
            timeInForce=TIME_IN_FORCE_GTC,
            quantity=coinQuantity,
            price=str(price))
        return secondOrder

    def sellCoin(self, coin, secondCoin, price, length):
        if self.trading != coin:
            print("not trading this coin, cannot sell!")
            return

        coinAlone = coin.replace(secondCoin, '')
        coinInfo = self.client.get_asset_balance(asset=coinAlone)
        quantity = float(self.truncate(coinInfo["free"], length))

        self.logger.log("SELLING {0} AMOUNT OF {1}"
                        .format(quantity, coin))

        if price:
            price = float("%.4g" % price)
            order = self.client.order_limit_sell(
                symbol=coin,
                type=ORDER_TYPE_LIMIT,
                timeInForce=TIME_IN_FORCE_GTC,
                quantity=quantity,
                price=str(price))
        else:
            order = self.client.order_market_sell(
                symbol=coin,
                quantity=quantity)

        return order

    def cancelOrder(self, coin, orderId):
        self.client.cancel_order(
            symbol=coin,
            orderId=orderId)

    def startTrade(self, coin):
        if self.trading == "":
            self.trading = coin

    def endTrade(self):
        self.trading = ""

    def truncate(self, f, n):
        # Truncates/pads a float f to n decimal places without rounding
        s = '{}'.format(f)
        if 'e' in s or 'E' in s:
            return '{0:.{1}f}'.format(f, n)
        i, p, d = s.partition('.')
        return '.'.join([i, (d + '0' * n)[:n]])
