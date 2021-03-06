from __future__ import division
from binance.client import Client
from logger import Logger
import time

API_KEY = "i1s87G06vlhZTdKy7z3V0IRRKujhvps4umFTELYqre3awoeD4ZKpzWsCm8O3HklK"
API_SECRET = "mpZGQfH0SraheOvbJZMANJCWapD5xDo0HfbapGGmjm3YCXxsvrFj4a5zVxNOqdoP"
NUM_THREADS = 100

BUY_PERC = (0.33, 0.5, 0.95)

BUYS_A = (0.52, 0.4, 0.3)
SELLS_A = (0.3, 0.28, 0.25, 0.22, 0.18)

BUYS_B = (0.3, 0.2, 0.15)
SELLS_B = (0.2, 0.23, 0.23, 0.17, 0.15)

TIMER_A = 108000000
TIMER_B = 208000000

flag = False


class BouncePlay:
    def __init__(self, coin, chadAlert, trader):
        self.logger = Logger(coin, self)
        self.logreceipt = Logger(coin + "receipt", None)
        self.client = Client(API_KEY, API_SECRET, {"timeout": 60})
        self.coin = coin
        self.chadAlert = chadAlert
        self.trader = trader
        self.stage = 0
        self.startTime = 0
        self.startWatchingTime = 0
        self.started = False

        self.mainBuyOrder = None
        self.mainSellOrder = None

        self.mainBought = False
        self.mainBuyPrice = False
        self.mainSellPrice = False
        self.firstDeduction = False
        self.secondDeduction = False

        try:
            self.lastKlines = self.client.get_historical_klines(self.coin,
                                                                Client.KLINE_INTERVAL_15MINUTE,
                                                                "100 hours ago PT")
        except Exception as e:
            self.logger.log("weird error initializing lastKlines for {0}, retrying".format(self.coin))
            time.sleep(5)
            self.lastKlines = self.client.get_historical_klines(self.coin,
                                                                Client.KLINE_INTERVAL_15MINUTE,
                                                                "100 hours ago PT")

    def run(self):
        self.started = True
        loops = 0
        # get the first green candle with lowest price and large enough volume

        ticker = self.client.get_ticker(symbol=self.coin)

        firstKline = None
        minVolume = 0.0
        lowestPrice = 9999999
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

        highestPrice = float(firstKline[2])
        lowestHistDip = highestPrice
        highTime = firstKline[0]

        # find highestPrice up to now and lowest dip
        for kline in self.lastKlines:
            currTime = float(kline[0])
            localHigh = float(kline[2])
            localLow = float(kline[3])
            open = float(kline[1])
            close = float(kline[4])

            if highestPrice < localHigh:
                highestPrice = localHigh
                lowestHistDip = localHigh
                highTime = currTime

            if open > close and lowestHistDip > localLow:
                lowestHistDip = localLow

        lowestDip = lowestHistDip

        self.logger.log(
            "HIGH, LOW, LOWESTDIP - {0}, {1}, {2}".format(highestPrice, lowestPrice, lowestDip))

        volume = float(ticker["volume"]) * float(ticker["lastPrice"])

        buys = BUYS_A
        sells = SELLS_A
        timer = TIMER_A
        if 500 < volume < 1000:
            buys = BUYS_B
            sells = SELLS_B
            timer = TIMER_B
            self.logger.log("PLAYING MORE CAUTIOUSLY, VOLUME IS ONLY {0}".format(volume))
        if volume < 500:
            self.logger.log("VOLUME ({0} BTC) DID NOT MATCH PARAMETERS, STOPPING PLAY".format(volume))
            self.stage = 6
        elif highestPrice - lowestHistDip > (highestPrice - lowestPrice) * buys[0]:
            self.logger.log("DIP ALREADY HAPPENED (DROPPED MORE THAN 50% FROM HIGH)".format(self.coin))
            self.stage = 6
        else:
            self.stage = 1
            self.logger.log("STARTING VALID TRADE".format(self.coin))
            self.startWatchingTime = self.chadAlert.serverTime

        while True:
            if self.coin not in self.chadAlert.bouncePlaying or self.stage == 7:
                self.logger.log(
                    "CHAD ALERT NO LONGER HAS {0} IN BOUNCE PLAYS!".format(self.coin, self.stage))
                self.revertBack()
                return

            loops += 1
            price = self.chadAlert.getPrice(self.coin)

            if lowestDip > price:
                lowestDip = price

            # if sell is satisfied
            if self.mainSellPrice and price > self.mainSellPrice:
                if self.mainSellOrder:
                    orderStatus = self.client.get_order(symbol=self.coin, orderId=self.mainSellOrder["orderId"])
                    if orderStatus["status"] != "FILLED" or orderStatus["status"] != "CANCELED":
                        self.logger.log("NOT DONE EXECUTING SELL, RETRYING (ORDER STATUS: {0})"
                                        .format(orderStatus["status"]))
                        continue
                self.logger.log("--------GOT OUT OF TRADE AT {0} for {1}, cancelling any further bids-------".format(
                    self.mainSellPrice, self.coin))
                self.mainSellOrder = None

                profit = 1000 * (self.mainSellPrice / self.mainBought - 1)
                self.logreceipt.log("SOLD {2} AT {0} for ${1} profit".format(self.mainSellPrice, profit, self.coin))

                # end the trade!
                if self.trader.trading == self.coin:
                    self.logger.log("-------- STOPPING TRADE FOR {0} WITH REAL MONEY --------".format(self.coin))
                self.stage = 6

            if self.chadAlert.serverTime - highTime > timer and self.stage < 3:
                self.logger.log(
                    "DROP HAPPENED TOO SLOW, (OVER {0} MILLISECONDS), PUTTING BACK ON RUNNER LIST".format(timer))
                self.stage = 6
                continue

            if self.chadAlert.serverTime - self.startWatchingTime > 86400000 and self.stage == 1:
                self.logger.log(
                    "DROP HAPPENED TOO SLOW, (OVER {0} MILLISECONDS), PUTTING BACK ON RUNNER LIST".format(timer))
                self.stage = 6
                continue

            if self.stage == 1:
                if price > highestPrice * 1.1:
                    self.logger.log("PRICE WENT TOO HIGH TOO QUICKLY, PROBABLY FAT FINGER, FROM {0} TO {1}"
                                    .format(price, highestPrice))
                    self.stage = 6
                    continue
                if price > highestPrice:
                    highestPrice = price
                    highTime = self.chadAlert.serverTime
                    self.logger.log("NEW HIGH {0}, INCREASED {2}"
                                    .format(highestPrice, self.coin, highestPrice - lowestPrice))

                # if the price dips more than 40% of the move
                percentage = ((highestPrice - price) / (highestPrice - lowestPrice)) * 100
                if percentage > 30:
                    self.stage = 1.5
                    firstBuyPrice = lowestPrice + ((highestPrice - lowestPrice) * buys[0])
                    secondBuyPrice = lowestPrice + ((highestPrice - lowestPrice) * buys[1])
                    thirdBuyPrice = lowestPrice + ((highestPrice - lowestPrice) * buys[2])

                    firstSellPrice = firstBuyPrice + ((highestPrice - firstBuyPrice) * sells[0])
                    secondSellPrice = secondBuyPrice + ((highestPrice - secondBuyPrice) * sells[1])
                    thirdSellPrice = thirdBuyPrice + ((highestPrice - thirdBuyPrice) * sells[2])
                    self.logger.log("LOOKING INTO TRADE FROM {0} - {3}, {1} - {4}, {2} - {5}".format(
                        firstBuyPrice,
                        secondBuyPrice,
                        thirdBuyPrice,
                        firstSellPrice,
                        secondSellPrice,
                        thirdSellPrice, self.coin))

            elif self.stage == 1.5:
                if price > highestPrice:
                    self.logger.log("PRICE ({0}) WENT HIGHER THAN HIGH, REVERTING BACK TO STAGE 1".format(price))
                    self.stage = 1
                    continue

                percentage = ((highestPrice - price) / (highestPrice - lowestPrice)) * 100
                if percentage >= 47.9:
                    self.stage = 2
                    self.logger.log(
                        "PRICE AT {0}, {3}% DIP FROM TOP {1} AND BOTTOM {2}"
                            .format(price, highestPrice, lowestPrice, percentage, self.coin))

                    self.logger.log("WILL TRADE FROM {0} - {3}, {1} - {4}, {2} - {5}".format(
                        firstBuyPrice,
                        secondBuyPrice,
                        thirdBuyPrice,
                        firstSellPrice,
                        secondSellPrice,
                        thirdSellPrice, self.coin))

                    self.mainBuyPrice = firstBuyPrice
                    self.mainBuyOrder = self.tryBuy("BTC", self.mainBuyPrice, BUY_PERC[0])
                    self.startTime = self.chadAlert.serverTime

            elif self.stage == 2:
                if self.chadAlert.serverTime - firstKline[0] <= 3600000:
                    self.logger.log("BOUNCE HAPPENED TOO QUICKLY, PUTTING BACK ON RUNNER LIST".format(self.coin))
                    self.stage = 6
                    continue

                if price < firstBuyPrice:
                    if self.mainBuyOrder:
                        orderStatus = self.client.get_order(symbol=self.coin, orderId=self.mainBuyOrder["orderId"])
                        if orderStatus["status"] != "FILLED":
                            self.logger.log(
                                "NOT DONE EXECUTING BUY FOR STAGE 2, RETRYING".format(self.coin))
                            continue

                    self.stage = 2.5
                    self.logger.log(
                        "IN AT {0}, ATTEMPTED SELL AT {1}".format(firstBuyPrice, firstSellPrice,
                                                                  self.coin))
                    self.logreceipt.log("BOUGHT {1} AT {0}".format(firstBuyPrice, self.coin))
                    self.mainBought = self.mainBuyPrice
                    self.mainSellPrice = firstSellPrice
                    self.mainSellOrder = self.trySell(self.coin, "BTC", self.mainSellPrice, 0, False)

            elif self.stage == 2.5:
                if price < secondBuyPrice * 1.02:
                    self.stage = 3
                    self.mainBuyPrice = secondBuyPrice
                    self.mainBuyOrder = self.tryBuy("BTC", self.mainBuyPrice, BUY_PERC[1])
                    self.logger.log("ATTEMPTING TO BUY AT {0}".format(self.mainBuyPrice))

            elif self.stage == 3:
                if price < secondBuyPrice:
                    if self.mainBuyOrder:
                        orderStatus = self.client.get_order(symbol=self.coin, orderId=self.mainBuyOrder["orderId"])
                        if orderStatus["status"] != "FILLED":
                            self.logger.log(
                                "NOT DONE EXECUTING BID FOR STAGE 3, RETRYING".format(self.coin))
                            continue
                    self.stage = 3.5
                    self.logger.log(
                        "ALSO IN AT {0}, ATTEMPTED SELL AT {1}".format(secondBuyPrice, secondSellPrice,
                                                                       self.coin))
                    self.logreceipt.log("BOUGHT {1} AT {0}".format(secondBuyPrice, self.coin))
                    self.mainBought = (self.mainBuyPrice + self.mainBought) / 2

                    # cancel previous sell
                    self.tryCancel(self.coin, self.mainSellOrder)
                    self.mainSellPrice = secondSellPrice
                    self.mainSellOrder = self.trySell(self.coin, "BTC", self.mainSellPrice, 0, False)

            elif self.stage == 3.5:
                if price < thirdBuyPrice * 1.02:
                    self.stage = 4
                    self.mainBuyPrice = thirdBuyPrice
                    self.mainBuyOrder = self.tryBuy("BTC", self.mainBuyPrice, BUY_PERC[2])
                    self.logger.log("ATTEMPTING TO BUY AT {0}".format(self.mainBuyPrice))

            elif self.stage == 4:
                if price < thirdBuyPrice:
                    if self.mainBuyOrder:
                        orderStatus = self.client.get_order(symbol=self.coin, orderId=self.mainBuyOrder["orderId"])
                        if orderStatus["status"] != "FILLED":
                            self.logger.log(
                                "NOT DONE EXECUTING BID FOR STAGE 4, RETRYING".format(self.coin))
                            continue
                    self.stage = 5
                    self.logger.log(
                        "IN AT {0}, ATTEMPTED SELL AT {1}".format(thirdBuyPrice, thirdSellPrice,
                                                                  self.coin))
                    self.logreceipt.log("BOUGHT {1} AT {0}".format(thirdBuyPrice, self.coin))
                    self.mainBought = (self.mainBuyPrice + self.mainBought) / 2

                    # cancel previous sell
                    self.tryCancel(self.coin, self.mainSellOrder)
                    self.mainBuyPrice = False
                    self.mainBuyOrder = None
                    self.mainSellPrice = thirdSellPrice
                    self.mainSellOrder = self.trySell(self.coin, "BTC", self.mainSellPrice, 0, False)

            elif self.stage == 5:
                uptrendTime = self.startTime - firstKline[0]
                downTrendTime = self.chadAlert.serverTime - self.startTime

                if uptrendTime < downTrendTime and not self.firstDeduction:
                    self.firstDeduction = True
                    self.tryCancel(self.coin, self.mainSellOrder)

                    smallSellPrice = thirdBuyPrice + ((highestPrice - thirdBuyPrice) * sells[3])
                    self.logger.log("ATTEMPT TO NOW SELL AT {0} INSTEAD OF {1} - DURATION OF {2}".format(
                        smallSellPrice, self.mainSellPrice, downTrendTime, self.coin))
                    self.mainSellPrice = smallSellPrice
                    self.mainSellOrder = self.trySell(self.coin, "BTC", self.mainSellPrice, 0, False)

                if uptrendTime * 1.5 < downTrendTime and not self.secondDeduction:
                    self.secondDeduction = True
                    self.tryCancel(self.coin, self.mainSellOrder)

                    smallSellPrice = thirdBuyPrice + ((highestPrice - thirdBuyPrice) * sells[4])
                    self.logger.log("ATTEMPT TO NOW SELL AT {0} INSTEAD OF {1} - DURATION OF {2}".format(
                        smallSellPrice, self.mainSellPrice, downTrendTime, self.coin))
                    self.mainSellPrice = smallSellPrice
                    self.mainSellOrder = self.trySell(self.coin, "BTC", self.mainSellPrice, 0, False)

            elif self.stage == 6:
                self.logger.log("ADDING {0} TO RUNNER LIST".format(self.coin))
                self.chadAlert.addToRunners(
                    {'coin': self.coin, 'low': lowestPrice, 'high': highestPrice, 'time': firstKline[0]})
                self.chadAlert.removeBouncePlay(self.coin)
                self.stage = 7
            time.sleep(1)

    def tryBuy(self, secondCoin, price, percentage):
        order = None
        if self.trader.trading == "":
            self.tryStartTrade()

        if self.trader.trading == self.coin:
            order = self.trader.buyCoin(self.coin, secondCoin, price, percentage)
        else:
            self.logger.log("NOT TRADING {0} BECAUSE CURRENTLY TRADING {2}".format(self.coin, self.stage,
                                                                                   self.trader.trading))
        return order

    def trySell(self, coin, secondCoin, price, length, permission):
        order = None
        if self.trader.trading == self.coin or permission:
            order = self.trader.sellCoin(coin, secondCoin, price, length, permission)
        return order

    def tryCancel(self, coin, order):
        if self.trader.trading == self.coin:
            cancel = self.trader.cancelOrder(coin, order["orderId"])

    def tryStartTrade(self):
        if self.trader.trading == "":
            self.trader.startTrade(self.coin)
        if self.trader.trading == self.coin:
            self.logger.log("-------- NOW TRADING {0} FOR REAL MONEY --------".format(self.coin))

    def tryEndTrade(self):
        if self.trader.trading == self.coin:
            self.trader.endTrade()
            if self.trader.trading != self.coin:
                self.logger.log("-------- ENDED TRADE WITH {0} FOR REAL MONEY --------".format(self.coin))

    def revertBack(self):
        if self.mainBuyOrder:
            self.tryCancel(self.coin, self.mainBuyOrder)
        if self.mainSellOrder:
            self.trySell(self.coin, "BTC", None, 0, False)
        if self.trader.trading == self.coin:
            self.logger.log("SELLING REMAINING BITOIN BACK INTO USDT")
            self.trySell("BTCUSDT", "USDT", None, 5, True)
        self.tryEndTrade()
