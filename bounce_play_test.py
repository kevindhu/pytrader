from __future__ import division
from binance.client import Client
from logger import Logger
import time

API_KEY = ""
API_SECRET = ""
NUM_THREADS = 100

flag = False


class BouncePlay:
    def __init__(self, coin, chadAlert, trader):
        self.logger = Logger(coin)
        self.logreceipt = Logger(coin + "receipt")
        self.client = Client(API_KEY, API_SECRET, {"timeout": 60})
        self.coin = coin
        self.chadAlert = chadAlert
        self.trader = trader
        self.stage = 0
        self.startTime = 0
        self.started = False
        self.firstBuyDone = False
        self.secondBuyDone = False
        self.thirdBuyDone = False

        self.mainBuyOrder = False
        self.mainSellOrder = False

        self.mainBought = False
        self.mainBuyPrice = False
        self.mainSellPrice = False
        self.firstDeduction = False
        self.secondDeduction = False

        try:
            self.lastKlines = self.client.get_historical_klines(self.coin,
                                                                Client.KLINE_INTERVAL_15MINUTE,
                                                                "30 hours ago PT")
        except Exception as e:
            self.logger.log("weird error initializing lastKlines for {0}, retrying".format(self.coin))
            time.sleep(5)
            self.lastKlines = self.client.get_historical_klines(self.coin,
                                                                Client.KLINE_INTERVAL_15MINUTE,
                                                                "30 hours ago PT")

    def run(self):
        self.started = True
        loops = 0
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
            self.logger.log("{1} STAGE 0: Volume ({0} BTC) did not match parameters: deleting from bounce list, "
                            "adding to blacklist".format(volume, self.coin))
            self.chadAlert.removeBouncePlay(self.coin)
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
            "{3} STAGE 0: HIGH, LOW, LOWESTDIP - {0}, {1}, {2}".format(highestPrice, lowestPrice, lowestDip, self.coin))
        if highestPrice - lowestHistDip > (highestPrice - lowestPrice) * 0.5:
            self.logger.log("{0} STAGE 0: DIP OCCURED BEFORE".format(self.coin))
            self.stage = 6
        else:
            self.logger.log("{0} STAGE 1: STARTING VALID TRADE".format(self.coin))
            self.stage = 1

        while True:
            if self.coin not in self.chadAlert.bouncePlaying:
                self.logger.log("{0} STAGE {1}: CHAD ALERT FOR {0} STOPPED US BECAUSE "
                                "A BETTER COIN WAS PLAYABLE!".format(self.coin, self.stage))
                return

            loops += 1
            price = self.chadAlert.getPrice(self.coin)

            if lowestDip > price:
                lowestDip = price

            # if sell is satisfied
            if self.mainSellPrice and price > self.mainSellPrice:
                self.logger.log("--------GOT OUT OF TRADE AT {0} for {1}, cancelling any further bids-------".format(
                    self.mainSellPrice, self.coin))

                # sell to USDT
                self.trySell("BTC", "USDT", None)
                if self.mainBuyOrder:
                    self.tryCancel(self.coin, self.mainBuyOrder["orderId"])
                profit = 1000 * (self.mainSellPrice / self.mainBought - 1)
                self.logreceipt.log("SOLD AT {0} for ${1} profit".format(self.mainSellPrice, profit))

                # end the trade!
                if self.trader.trading == self.coin:
                    self.logger.log("-------- STOPPING TRADE FOR {0} WITH REAL MONEY --------".format(self.coin))
                self.tryEndTrade()

                self.stage = 6

            if self.stage == 1:
                if price > highestPrice:
                    highestPrice = price
                    self.logger.log("{1} STAGE 1: NEW HIGH {0}, INCREASED {2}"
                                    .format(highestPrice, self.coin, highestPrice - lowestPrice))

                # if the price dips more than 40% of the move
                percentage = ((highestPrice - price) / (highestPrice - lowestPrice)) * 100
                if percentage > 40:
                    self.logger.log(
                        "{4} STAGE 2: PRICE AT {0}, {3}% DIP FROM TOP {1} AND BOTTOM {2}"
                            .format(price, highestPrice, lowestPrice, percentage, self.coin))

                    firstBuyPrice = lowestPrice + ((highestPrice - lowestPrice) * 0.52)
                    secondBuyPrice = lowestPrice + ((highestPrice - lowestPrice) * 0.4)
                    thirdBuyPrice = lowestPrice + ((highestPrice - lowestPrice) * 0.3)

                    firstSellPrice = firstBuyPrice + ((highestPrice - firstBuyPrice) * 0.3)
                    secondSellPrice = secondBuyPrice + ((highestPrice - secondBuyPrice) * 0.35)
                    thirdSellPrice = thirdBuyPrice + ((highestPrice - thirdBuyPrice) * 0.4)

                    # starting trade!
                    self.tryStartTrade()

                    self.logger.log("{6} STAGE 2: WILL TRADE FROM {0} - {3}, {1} - {4}, {2} - {5}".format(
                        firstBuyPrice,
                        secondBuyPrice,
                        thirdBuyPrice,
                        firstSellPrice,
                        secondSellPrice,
                        thirdSellPrice, self.coin))

                    if self.trader.trading == self.coin:
                        self.logger.log("-------- NOW TRADING {0} WITH REAL MONEY --------".format(self.coin))

                    self.mainBuyPrice = firstBuyPrice
                    self.mainBuyOrder = self.tryBuy("BTC", self.mainBuyPrice, 0.33)



                    self.startTime = self.chadAlert.serverTime
                    self.stage = 2

            elif self.stage == 2:
                if self.chadAlert.serverTime - firstKline[0] <= 600:
                    self.logger.log("{0} STAGE 2: BOUNCE HAPPENED TOO QUICKLY, STOPPING TRADE".format(self.coin))
                    # go to stage 6 - put it back on runner list
                    self.stage = 6
                    return

                if price - lowestDip > (highestPrice - lowestPrice) * 0.3:
                    self.logger.log("{0} STAGE 2: BOUNCE JUST HAPPENED, STOPPING TRADE".format(self.coin))
                    self.stage = 6

                # if now in the trade, go to stage 3
                if price < firstBuyPrice:
                    self.stage = 3
                    self.logger.log(
                        "{2} STAGE 3: IN AT {0}, ATTEMPTED SELL AT {1}".format(firstBuyPrice, firstSellPrice,
                                                                               self.coin))e
                    self.logreceipt.log("BOUGHT AT {0}".format(firstBuyPrice, self.coin))
                    self.mainBought = self.mainBuyPrice
                    self.mainBuyPrice = secondBuyPrice
                    self.mainBuyOrder = self.tryBuy("BTC", self.mainBuyPrice, 0.5)
                    self.mainSellPrice = firstSellPrice
                    self.mainSellOrder = self.trySell(self.coin, "BTC", self.mainSellPrice)


            elif self.stage == 3:
                if price < secondBuyPrice:
                    # TODO: cancel previous order sell
                    self.logger.log(
                        "{2} STAGE 4: IN AT {0}, ATTEMPTED SELL AT {1}".format(secondBuyPrice, secondSellPrice,
                                                                               self.coin))
                    self.logreceipt.log("BOUGHT AT {0}".format(secondBuyPrice, self.coin))
                    self.mainBought = (self.mainBuyPrice + self.mainBought) / 2

                    # cancel previous sell
                    self.tryCancel(self.coin, self.mainSellOrder["orderId"])

                    self.mainBuyPrice = thirdBuyPrice
                    self.mainBuyOrder = self.tryBuy("BTC", self.mainBuyPrice, 1)
                    self.mainSellPrice = secondSellPrice
                    self.mainSellOrder = self.trySell(self.coin, "BTC", self.mainSellPrice)
                    self.stage = 4

            elif self.stage == 4:
                if price < thirdBuyPrice:
                    self.logger.log(
                        "{2} STAGE 5: IN AT {0}, ATTEMPTED SELL AT {1}".format(thirdBuyPrice, thirdSellPrice,
                                                                               self.coin))
                    self.logreceipt.log("BOUGHT AT {0}".format(thirdBuyPrice))
                    self.mainBought = (self.mainBuyPrice + self.mainBought) / 2

                    # cancel previous sell
                    self.tryCancel(self.coin, self.mainSellOrder["orderId"])

                    self.mainBuyPrice = False
                    self.mainBuyOrder = False
                    self.mainSellPrice = thirdSellPrice
                    self.mainSellOrder = self.trySell(self.coin, "BTC", self.mainSellPrice)
                    self.stage = 5

            elif self.stage == 5:
                # if the time has been too long , just get out with 25%
                uptrendTime = self.startTime - firstKline[0]
                downTrendTime = self.chadAlert.serverTime - self.startTime

                if uptrendTime < downTrendTime and not self.firstDeduction:
                    self.firstDeduction = True
                    self.tryCancel(self.coin, self.mainSellOrder["orderId"])

                    smallSellPrice = thirdBuyPrice + ((highestPrice - thirdBuyPrice) * 0.3)
                    self.logger.log("{3} STAGE 5: ATTEMPT TO NOW SELL AT {0} INSTEAD OF {1} - DURATION OF {2}".format(
                        smallSellPrice, self.mainSellPrice, downTrendTime, self.coin))
                    self.mainSellPrice = smallSellPrice
                    self.mainSellOrder = self.trySell(self.coin, "BTC", self.mainSellPrice)

                if uptrendTime * 1.5 < downTrendTime and not self.secondDeduction:
                    self.secondDeduction = True
                    self.tryCancel(self.coin, self.mainSellOrder["orderId"])

                    smallSellPrice = thirdBuyPrice + ((highestPrice - thirdBuyPrice) * 0.25)
                    self.logger.log("{3} STAGE 5: ATTEMPT TO NOW SELL AT {0} INSTEAD OF {1} - DURATION OF {2}".format(
                        smallSellPrice, self.mainSellPrice, downTrendTime, self.coin))
                    self.mainSellPrice = smallSellPrice
                    self.mainSellOrder = self.trySell(self.coin, "BTC", self.mainSellPrice)

            elif self.stage == 6:
                self.logger.log("{0} STAGE 6: ADDING {0} TO RUNNER LIST".format(self.coin))
                self.chadAlert.addToRunners(
                    {'coin': self.coin, 'low': lowestPrice, 'high': highestPrice, 'time': firstKline[0]})
                self.chadAlert.removeBouncePlay(self.coin)
                return
            time.sleep(1)

    def tryBuy(self, secondCoin, price, percentage):
        order = None
        if self.trader.trading == self.coin:
            order = self.trader.buyCoin(self.coin, secondCoin, price, percentage)
        return order

    def trySell(self, coin, secondCoin, price):
        order = None
        if self.trader.trading == self.coin:
            order = self.trader.sellCoin(coin, secondCoin, price)
        return order

    def tryCancel(self, coin, id):
        order = None
        if self.trader.trading == self.coin:
            order = self.trader.cancelOrder(coin, id)
        return order

    def tryStartTrade(self):
        if self.trader.trading == "":
            self.trader.startTrade(self.coin)

    def tryEndTrade(self):
        if self.trader.trading == self.coin:
            self.trader.endTrade()
