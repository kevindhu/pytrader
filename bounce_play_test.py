from __future__ import division
from binance.client import Client
from logger import Logger
import time

API_KEY = ""
API_SECRET = ""
NUM_THREADS = 100


class BouncePlay:
    def __init__(self, coin, chadAlert):
        self.logger = Logger("", coin)
        self.logreceipt = Logger("", coin + "receipt")
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
        self.firstDeduction = False
        self.secondDeduction = False

        self.lastKlines = self.client.get_historical_klines(self.coin,
                                                            Client.KLINE_INTERVAL_15MINUTE,
                                                            "24 hours ago PT")

        self.run()

    def run(self):
        loops = 0
        self.logger.log("-------------------------------------------------------")
        # firstKline = first candlestick that is green and larger volume
        firstKline = False
        minVolume = 0.0
        lowestPrice = 100000
        # get the first green candle with lowest price and large enough volume
        for kline in self.lastKlines:
            volume = float(kline[5])
            if minVolume == 0 or minVolume > volume:
                minVolume = volume
        for kline in self.lastKlines:
            volume = float(kline[5])
            if (volume > minVolume * 2) and lowestPrice > float(kline[3]):
                lowestPrice = float(kline[3])
                # self.logger.log("LOWEST PRICE: " + str(lowestPrice))
                firstKline = kline

        ticker = self.client.get_ticker(symbol=self.coin)
        volume = float(ticker["volume"]) * float(ticker["lastPrice"])
        if not firstKline or volume < 100:
            self.logger.log("Volume ({0} BTC) did not match parameters: deleting from bounce list, "
                            "adding to blacklist".format(volume))
            self.chadAlert.bouncePlaying.remove(self.coin)
            self.chadAlert.bouncePlayCount -= 1
            self.chadAlert.blacklist.add(self.coin)
            return

        highestPrice = float(firstKline[2])
        lowestHistDip = highestPrice

        # find highestPrice up to now and lowest dip
        for kline in self.lastKlines:
            localHigh = float(kline[2])
            localLow = float(kline[3])
            open = float(kline[1])
            close = float(kline[4])

            if highestPrice < localHigh:
                highestPrice = localHigh
                lowestHistDip = localHigh

            if open > close and lowestHistDip > localLow:
                lowestHistDip = localLow

        lowestDip = lowestHistDip

        self.logger.log(
            "{3}: high, low, lowestDip: {0}, {1}, {2}".format(highestPrice, lowestPrice, lowestDip, self.coin))
        if highestPrice - lowestHistDip > (highestPrice - lowestPrice) * 0.4:
            self.logger.log("dip already happened, putting {0} back on the runner list".format(self.coin))
            self.stage = 6
        else:
            self.logger.log("-------commencing stage 1, starting the bounce play on {0}------".format(self.coin))
            self.stage = 1

        while True:
            loops += 1
            price = self.chadAlert.getPrice(self.coin)

            if lowestDip > price:
                lowestDip = price

            # if sell is satisfied
            if self.mainSellOrder and price > self.mainSellOrder:
                self.logger.log("--------GOT OUT OF TRADE AT {0} for {1}, cancelling any further bids--------".format(
                    self.mainSellOrder, self.coin))
                # cancel any bids
                # self.client.cancel_order(self.mainBuyOrder["orderId"])
                self.logreceipt.log("SOLD AT {0}".format(self.mainSellOrder))
                self.stage = 6

            if self.stage == 1:
                if price > highestPrice:
                    highestPrice = price

                    self.logger.log("new highest price {0}".format(highestPrice))
                    self.logger.log("maxIncrease {0}".format(highestPrice - lowestPrice))

                # if the price dips more than 25% of the move
                percentage = ((highestPrice - price) / (highestPrice - lowestPrice)) * 100
                if percentage > 15:
                    self.logger.log(
                        "---------commencing stage 2 on {4}, the price has gone to {0}, "
                        "{3}% dip from the top at {1} and bottom at {2}-----------"
                            .format(price, highestPrice, lowestPrice, percentage, self.coin))

                    firstBuyPrice = lowestPrice + ((highestPrice - lowestPrice) * 0.75)
                    secondBuyPrice = lowestPrice + ((highestPrice - lowestPrice) * 0.6)
                    thirdBuyPrice = lowestPrice + ((highestPrice - lowestPrice) * 0.5)

                    firstSellPrice = firstBuyPrice + ((highestPrice - firstBuyPrice) * 0.15)
                    secondSellPrice = secondBuyPrice + ((highestPrice - secondBuyPrice) * 0.2)
                    thirdSellPrice = thirdBuyPrice + ((highestPrice - thirdBuyPrice) * 0.3)

                    self.mainBuyOrder = firstBuyPrice

                    self.logger.log("WILL TRADE: at {0} - {3}, {1} - {4}, {2} - {5}".format(
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
                    self.logger.log("bounce has happened too soon, cannot play; will return coin back to runner list")
                    # go to stage 6 - put it back on runner list
                    return

                # if now in the trade, go to stage 3
                if price < firstBuyPrice:
                    self.stage = 3
                    self.logger.log(
                        "-------commencing stage 3, now in the trade at {0}, will attempt to sell at {1}----------".
                            format(firstBuyPrice, firstSellPrice))
                    self.logreceipt.log("BOUGHT AT {0}".format(firstBuyPrice, self.coin))
                    self.mainBuyOrder = secondBuyPrice
                    self.mainSellOrder = firstSellPrice


            elif self.stage == 3:
                if price < secondBuyPrice:
                    # cancel previous order sell
                    self.logger.log(
                        "------commencing stage 4, now in the trade at {0}, will attempt to sell at {1}---------".
                            format(secondBuyPrice, secondSellPrice))
                    self.logreceipt.log("BOUGHT AT {0}".format(secondBuyPrice, self.coin))
                    self.mainBuyOrder = thirdBuyPrice
                    self.mainSellOrder = secondSellPrice
                    self.stage = 4

            elif self.stage == 4:
                if price < secondBuyPrice:
                    # cancel previous order sell
                    self.logger.log(
                        "-------commencing stage 5, now in the trade at {0}, will attempt to sell at {1}-------".
                            format(thirdBuyPrice, thirdSellPrice))
                    self.logreceipt.log("BOUGHT AT {0}".format(thirdBuyPrice))
                    self.mainBuyOrder = False
                    self.mainSellOrder = thirdBuyPrice
                    self.stage = 5

            elif self.stage == 5:
                # if the time has been too long , just get out with 25%
                uptrendTime = firstKline[0] - self.startTime
                downTrendTime = self.chadAlert.serverTime - self.startTime

                if uptrendTime < downTrendTime and not self.firstDeduction:
                    self.firstDeduction = True
                    smallSellPrice = lowestDip + ((highestPrice - lowestDip) * 0.15)

                    self.logger.log("attempting to now get out at {0} instead of {1} "
                                    "because trade has taken duration of {2}".format(
                        smallSellPrice, thirdSellPrice, downTrendTime))
                    self.mainSellOrder = smallSellPrice

                if uptrendTime * 1.2 < downTrendTime and not self.secondDeduction:
                    self.secondDeduction = True
                    smallSellPrice = lowestDip + ((highestPrice - lowestDip) * 0.1)
                    self.logger.log("attempting to now get out at {0} instead of {1} "
                                    "because trade has taken duration of {2}".format(
                        smallSellPrice, thirdSellPrice, downTrendTime))
                    self.mainSellOrder = smallSellPrice

            elif self.stage == 6:
                self.chadAlert.addToRunners(
                    {'coin': self.coin, 'low': lowestPrice, 'high': highestPrice, 'time': firstKline[0]})
                self.chadAlert.bouncePlayCount -= 1
                return
            time.sleep(1)
