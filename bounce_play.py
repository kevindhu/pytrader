from __future__ import division
from binance.client import Client
import threading
from threading import Thread
from queue import Queue
import time

API_KEY = ""
API_SECRET = ""
NUM_THREADS = 100


class BouncePlay:
    def __init__(self, coin, chadAlert):
        self.client = Client(API_KEY, API_SECRET, {"timeout": 60})
        self.coin = coin
        self.chadAlert = chadAlert
        self.stage = 0
        self.startTime = 0
        self.firstBuyDone = False
        self.secondBuyDone = False
        self.thirdBuyDone = False
        self.mainBuyOrder = False
        self.mainSellOrder = False

        self.lastKlines = self.client.get_historical_klines(self.coin,
                                                            Client.KLINE_INTERVAL_1HOUR,
                                                            "7 hours ago PT")

        self.run()

    def run(self):
        loops = 0

        # firstKline = first candlestick that is green and larger volume
        firstKline = False
        minVolume = 0.0
        # get the first big green volume
        for kline in self.lastKlines:
            volume = float(kline[5])
            if minVolume == 0 or minVolume > volume:
                minVolume = volume
            elif float(kline[4]) - float(kline[1]) > 0 and volume > minVolume * 3:
                firstKline = kline
                break

        if not firstKline:
            print("Volume did not match parameters: deleting from bounce list")
            self.chadAlert.bouncePlays.remove(self.coin)
            self.chadAlert.bouncePlaying = False
            return

        lowestPrice = float(firstKline[3])
        highestPrice = float(firstKline[2])
        lowestHistDip = highestPrice

        # find highestPrice up to now and lowest dip
        for kline in self.lastKlines:
            localHigh = float(kline[2])
            localLow = float(kline[3])

            if highestPrice < localHigh:
                highestPrice = localHigh
                lowestHistDip = highestPrice

            if lowestHistDip > localLow:
                lowestHistDip = localLow

        lowestDip = lowestHistDip

        if highestPrice - lowestHistDip > (highestPrice - lowestPrice) / 2:
            print("dip already happened, putting {0} back on the runner list".format(self.coin))
            print(str(highestPrice), str(lowestPrice), str(lowestHistDip))
            self.stage = 6
        else:
            print("bounce still occuring, WOO!")
            print("commencing stage 1, starting the bounce play on {0}".format(self.coin))
            self.stage = 1

        while True:
            loops += 1
            price = self.chadAlert.getPrice(self.coin)

            if lowestDip > price:
                lowestDip = price

            # if sell is satisfied
            if self.mainSellOrder and price > self.mainSellOrder["price"]:
                print("GOT OUT OF TRADE AT {0}, cancelling any further bids", self.mainSellOrder["price"])
                # cancel any bids
                if self.mainBuyOrder:
                    self.client.cancel_order(self.mainBuyOrder["orderId"])
                self.stage = 6

            if self.stage == 1:
                if price > highestPrice:
                    highestPrice = price

                    print("new highest price {0}".format(highestPrice))
                    print("maxIncrease {0}".format(highestPrice - lowestPrice))

                # if the price dips more than 25% of the move
                if (highestPrice - lowestDip) > (highestPrice - lowestPrice) / 4:
                    print("commencing stage 2, the price has gone to {0}, 25% dip from the top at {1}".format(lowestDip,
                                                                                                              highestPrice))

                    firstQuantity = self.getQuantity(0.3)
                    secondQuantity = self.getQuantity(0.35)
                    thirdQuantity = self.getQuantity(0.35)

                    firstBuyPrice = (lowestPrice + highestPrice) / 2
                    secondBuyPrice = lowestPrice + ((highestPrice - lowestPrice) * 0.35)
                    thirdBuyPrice = lowestPrice + ((highestPrice - lowestPrice) * 0.25)

                    firstSellPrice = firstBuyPrice + ((highestPrice - lowestDip) * 0.4)
                    secondSellPrice = secondBuyPrice + ((highestPrice - lowestDip) * 0.3)
                    thirdSellPrice = thirdBuyPrice + ((highestPrice - lowestDip) * 0.3)

                    print("WILL TRADE: {0} at {3} - {6}, {1} at {4} - {7}, {2} at {5} - {8}".format(firstQuantity,
                                                                                                    secondQuantity,
                                                                                                    thirdQuantity,
                                                                                                    firstBuyPrice,
                                                                                                    secondBuyPrice,
                                                                                                    thirdBuyPrice,
                                                                                                    firstSellPrice,
                                                                                                    secondSellPrice,
                                                                                                    thirdSellPrice))

                    self.startTime = self.chadAlert.serverTime
                    self.stage = 2

            elif self.stage == 2:
                if self.chadAlert.serverTime - firstKline[0] <= 600:
                    print("bounce has happened too soon, cannot play; will return coin back to runner list")
                    # go to stage 6 - put it back on runner list
                    return

                if not self.firstBuyDone:
                    self.mainBuyOrder = self.client.order_limit_buy(
                        symbol=self.coin,
                        quantity=firstQuantity,
                        price=firstBuyPrice)

                # if now in the trade, go to stage 3
                if price < firstBuyPrice:
                    self.mainSellOrder = self.client.order_limit_sell(
                        symbol=self.coin,
                        quantity=firstQuantity,
                        price=firstSellPrice
                    )

                    self.stage = 3

                    print("commencing stage 3, now in the trade at {0}, will attempt to sell at {1}".
                          format(firstBuyPrice, firstSellPrice))

            elif self.stage == 3:
                if not self.secondBuyDone:
                    self.mainBuyOrder = self.client.order_limit_buy(
                        symbol=self.coin,
                        quantity=secondQuantity,
                        price=secondBuyPrice)

                if price < secondBuyPrice:
                    # cancel previous order sell
                    self.client.cancel_order(symbol=self.coin, orderId=self.mainSellOrder["orderId"])

                    self.mainSellOrder = self.client.order_limit_sell(
                        symbol=self.coin,
                        quantity=firstQuantity + secondQuantity,
                        price=secondSellPrice
                    )

                    print("commencing stage 4, now in the trade at {0}, will attempt to sell at {1}".
                          format(secondBuyPrice, secondSellPrice))

                    self.stage = 4

            elif self.stage == 4:
                if not self.thirdBuyDone:
                    self.mainBuyOrder = self.client.order_limit_buy(
                        symbol=self.coin,
                        quantity=thirdQuantity,
                        price=thirdBuyPrice)

                if price < secondBuyPrice:
                    # cancel previous order sell
                    self.client.cancel_order(symbol=self.coin, orderId=self.mainSellOrder["orderId"])

                    self.mainSellOrder = self.client.order_limit_sell(
                        symbol=self.coin,
                        quantity=firstQuantity + secondQuantity + thirdQuantity,
                        price=thirdSellPrice
                    )
                    print("commencing stage 3, now in the trade at {0}, will attempt to sell at {1}".
                          format(thirdBuyPrice, thirdSellPrice))

                    self.stage = 5

            elif self.stage == 5:
                # if the time has been too long , just get out with 25%
                uptrendTime = firstKline[0] - self.startTime
                downTrendTime = self.chadAlert.serverTime - self.startTime

                if uptrendTime < downTrendTime:
                    quantity = self.mainSellOrder["origQty"]
                    self.client.cancel_order(symbol=self.coin, orderId=self.mainSellOrder["orderId"])

                    smallSellPrice = lowestDip + ((highestPrice - lowestDip) * 0.25)

                    self.mainSellOrder = self.client.order_limit_sell(
                        symbol=self.coin,
                        quantity=quantity,
                        price=smallSellPrice
                    )

                    print("attempting to now get out at {0} instead of {1} "
                          "because trade has taken duration of {2}".format(
                        smallSellPrice, thirdSellPrice, downTrendTime))

            elif self.stage == 6:
                self.chadAlert.addToRunners(
                    {'coin': self.coin, 'low': lowestPrice, 'high': highestPrice, 'time': firstKline[0]})
                print("high: " + str(highestPrice))
                self.chadAlert.bouncePlays.remove(self.coin)
                self.chadAlert.bouncePlaying = False
                return
            time.sleep(1)

    def getQuantity(self, value):
        balance = self.client.get_asset_balance(asset='USDT')

        amount1 = balance * value
        order1 = self.client.order_market_buy(
            symbol='BTCUSDT',
            quantity=amount1)

        quantity = order1
        return quantity
