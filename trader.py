from __future__ import division
from binance.client import Client
from binance.enums import *

API_KEY = ""
API_SECRET = ""
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
            print("NOT TRADING {0}, CANNOT BUY!".format(coin))
            return

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

        try:
            firstOrder = self.client.order_market_buy(
                symbol=secondCoin + "USDT",
                quantity=secondCoinQuantity)
        except Exception as e:
            self.logger.log(str(e))

        price = "%.4g" % price
        price = '{:.8f}'.format(float(price))

        coinQuantity = float(self.truncate((secondCoinQuantity / float(price)) * 0.95, 0))

        self.logger.log("LIMIT BUYING {0} OF {1} AT {2}"
                        .format(coinQuantity, coin, price))

        # limit buy the coin
        try:
            secondOrder = self.client.order_limit_buy(
                symbol=coin,
                type=ORDER_TYPE_LIMIT,
                timeInForce=TIME_IN_FORCE_GTC,
                quantity=coinQuantity,
                price=price)
        except Exception as e:
            self.logger.log(str(e))
            secondOrder = None
        return secondOrder

    # permission = extra permission for trading
    def sellCoin(self, coin, secondCoin, price, length, permission):
        if self.trading != coin and not permission:
            print("NOT TRADING {0}, CANNOT SELL!".format(coin))
            return

        coinAlone = coin.replace(secondCoin, '')
        coinInfo = self.client.get_asset_balance(asset=coinAlone)
        quantity = float(self.truncate(coinInfo["free"], length))
        try:
            if price:
                price = "%.4g" % price
                price = '{:.8f}'.format(float(price))
                self.logger.log("SELLING {0} AMOUNT OF {1} AT {2}"
                                .format(quantity, coin, price))

                order = self.client.order_limit_sell(
                    symbol=coin,
                    type=ORDER_TYPE_LIMIT,
                    timeInForce=TIME_IN_FORCE_GTC,
                    quantity=quantity,
                    price=price)
            else:
                self.logger.log("SELLING {0} AMOUNT OF {1} FOR MARKET"
                                .format(quantity, coin))

                order = self.client.order_market_sell(
                    symbol=coin,
                    quantity=quantity)
        except Exception as e:
            self.logger.log(str(e))
            order = None
        return order

    def cancelOrder(self, coin, orderId):
        self.logger.log("CANCEL ORDER #{0} FOR {1}"
                        .format(orderId, coin))

        try:
            self.client.cancel_order(
                symbol=coin,
                orderId=orderId)
        except Exception as e:
            self.logger.log(str(e))

    def startTrade(self, coin):
        if self.trading == "":
            self.trading = coin
            self.logger.log("NOW TRADING {0} FOR REAL MONEY".format(coin))

    def endTrade(self):
        self.trading = ""
        self.logger.log("STOPPED TRADE FOR REAL MONEY")

    def truncate(self, f, n):
        # Truncates/pads a float f to n decimal places without rounding
        s = '{}'.format(f)
        if 'e' in s or 'E' in s:
            return '{0:.{1}f}'.format(f, n)
        i, p, d = s.partition('.')
        return '.'.join([i, (d + '0' * n)[:n]])
