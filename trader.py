from __future__ import division
from binance.client import Client
from binance.enums import *
import threading
from threading import Thread
from queue import Queue
import time

API_KEY = "i1s87G06vlhZTdKy7z3V0IRRKujhvps4umFTELYqre3awoeD4ZKpzWsCm8O3HklK"
API_SECRET = "mpZGQfH0SraheOvbJZMANJCWapD5xDo0HfbapGGmjm3YCXxsvrFj4a5zVxNOqdoP"
NUM_THREADS = 100


class Trader:
    def __init__(self, chadAlert):
        self.client = Client(API_KEY, API_SECRET, {"timeout": 60})
        self.chadAlert = chadAlert

        # the ticker traded
        self.trading = ""
        self.USDT = self.client.get_asset_balance(asset='USDT')

    def getCurrentUSDT(self):
        self.USDT = self.client.get_asset_balance(asset='USDT')

    # secondCoin = something that can be traded for USDT
    def buyCoin(self, coin, secondCoin, price, percentage):
        if self.trading != coin:
            print("not trading this coin, cannot buy!")
            return

        self.getCurrentUSDT()
        USDTquantity = float(self.USDT["free"]) * percentage
        secondCoinQuantity = USDTquantity / self.chadAlert.prices[secondCoin]

        firstOrder = self.client.order_market_buy(
            symbol=secondCoin,
            quantity=secondCoinQuantity)

        coinQuantity = secondCoinQuantity / price
        # limit buy the coin
        secondOrder = self.client.order_limit_buy(
            symbol=coin + secondCoin,
            type=ORDER_TYPE_LIMIT,
            timeInForce=TIME_IN_FORCE_GTC,
            quantity=coinQuantity,
            price=str(price))
        return secondOrder

    def sellCoin(self, coin, secondCoin, price):
        if self.trading != coin:
            print("not trading this coin, cannot sell!")
            return
        coinInfo = self.client.get_asset_balance(asset=coin)
        quantity = coinInfo["free"]

        if not price:
            order = self.client.order_market_sell(
                symbol=coin + secondCoin,
                quantity=quantity)
        else:
            order = self.client.order_limit_sell(
                symbol=coin + secondCoin,
                type=ORDER_TYPE_LIMIT,
                timeInForce=TIME_IN_FORCE_GTC,
                quantity=quantity,
                price=str(price))

        return order

    def cancelOrder(self, coin, id):
        self.client.cancel_order(
            symbol=coin,
            orderId=id)

    def startTrade(self, coin):
        if self.trading == "":
            self.trading = coin

    def endTrade(self):
        self.trading = ""
