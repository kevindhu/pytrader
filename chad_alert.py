from __future__ import division
from binance.client import Client
import threading
from threading import Thread
from queue import Queue
import time
from bounce_play_test import BouncePlay
from trader import Trader
from logger import Logger
import operator

API_KEY = ""
API_SECRET = ""
NUM_THREADS = 100


class ChadAlert:
    def __init__(self):
        self.logger = Logger("", None)
        self.trader = Trader(self, self.logger)
        self.workers = []
        self.queue = Queue()
        self.originalBlacklist = {'HSRBTC', 'AMDBTC'}
        self.blacklist = set(self.originalBlacklist)
        self.klines = {}
        self.client = Client(API_KEY, API_SECRET, {"timeout": 60})
        self.runners = {}
        self.serverTime = 0.0
        self.lastClean = 0.0
        self.BTCprices = {}  # BTCprices against BTC
        self.USDTprices = {}
        self.loops = 0
        self.bouncePlayCount = 0

        self.bounceQueue = {}
        self.bouncePlaying = {}
        self.bouncePlayObjs = {}

    def run(self):
        for worker_id in range(NUM_THREADS):
            worker = Thread(target=self.process_queue, args=[worker_id])
            worker.daemon = True
            worker.start()
            self.workers.append(worker)

        time.sleep(1)

        global lock
        lock = threading.Lock()
        self.logger.log("---STARTING CHAD ALERT---")
        self.lastClean = self.client.get_server_time()["serverTime"]

        while True:
            self.loops += 1
            self.serverTime = self.client.get_server_time()["serverTime"]
            allPrices = self.client.get_all_tickers()
            for ticker in allPrices:
                if ticker['symbol'].endswith("BTC"):
                    self.BTCprices[ticker['symbol']] = float(ticker['price'])
                    self.queue.put(ticker)
                if ticker['symbol'].endswith("USDT"):
                    self.USDTprices[ticker['symbol']] = float(ticker['price'])
            # reset after one day
            if self.serverTime - self.lastClean > 8000000:
                self.lastClean = self.serverTime
                self.logger.log("Resetting blacklist")
                self.logger.log("Resetting klines")
                self.blacklist = set(self.originalBlacklist)
                self.klines = {}

    def process_queue(self, worker_id):
        while True:
            if not self.queue.empty():
                ticker = self.queue.get()
                coin = ticker['symbol']
                currPrice = float(ticker['price'])
                self.probe(coin, currPrice)
                self.queue.task_done()

    def getPrice(self, coin):
        return self.BTCprices[coin]

    def probe(self, coin, currPrice):
        try:
            if coin not in self.klines:
                klines = self.client.get_historical_klines(coin,
                                                           Client.KLINE_INTERVAL_15MINUTE,
                                                           "48 hours ago PT")
                with lock:
                    self.klines[coin] = klines

        except TypeError:
            # self.logger.log("TYPEERROR SHIT FOR " + coin)
            return

        minLow = self.getMinLow(self.klines[coin])
        increase = (currPrice - minLow) / minLow

        # add to / edit bounce
        with lock:
            if increase > 0.1 and (coin not in self.bouncePlaying) \
                    and (coin not in self.runners) and coin not in self.blacklist:
                if coin not in self.bounceQueue:
                    self.bounceQueue[coin] = increase
                elif self.bounceQueue[coin] < increase:
                    self.logger.log("{0} going up in bounce queue by {1}".format(coin, increase))
                    self.bounceQueue[coin] = increase

        # check runners to see if you can bounce play them again
        if coin in self.runners:
            if self.serverTime - self.runners[coin]["time"] > 400000000:
                self.logger.log("Taking {0} out of runners, time since start has exceeded 400000000".format(coin))
                self.runners.pop(coin, 0)

            elif currPrice > self.runners[coin]["high"] * 1.1:
                self.logger.log("Price for {0} has gone 10% higher than high at {1}: Adding runner "
                                "back into bounce queue".format(coin, self.runners[coin]["high"]))
                self.bounceQueue[coin] = increase
                self.runners.pop(coin, 0)

        with lock:
            if coin in self.bounceQueue:
                value = self.bounceQueue[coin]
                if self.bouncePlayCount < 10:
                    self.bounceQueue.pop(coin, 0)
                    self.addBouncePlay(coin, value)
                else:
                    sorted_plays = sorted(self.bouncePlaying.items(), key=operator.itemgetter(0))
                    for pair in sorted_plays:
                        currCoin = pair[0]
                        currValue = pair[1]
                        if currCoin not in self.bouncePlayObjs:
                            self.logger.log("Weird Error: bounce play object not found for {0}".format(currCoin))
                            continue

                        stage = self.bouncePlayObjs[currCoin].stage
                        if value > currValue and 0 < stage < 3:
                            self.logger.log("Replacing {0} for {1} in bounce plays ({2} vs {3})"
                                            .format(currCoin, coin, currValue, value))
                            self.bounceQueue[currCoin] = currValue
                            self.bounceQueue.pop(coin, 0)

                            self.removeBouncePlay(currCoin)
                            self.addBouncePlay(coin, value)
                            break

        if coin in self.bouncePlayObjs and not self.bouncePlayObjs[coin].started:
            self.startBouncePlay(coin)

    def getMinLow(self, klines):
        minLow = 100000000.0
        for index in range(0, len(klines) - 1):
            currLow = float(klines[index][3])
            if minLow > currLow:
                minLow = currLow
        return minLow

    def getMaxHigh(self, klines):
        maxHigh = 0
        for index in range(0, len(klines) - 1):
            currHigh = float(klines[index][2])
            if maxHigh < currHigh:
                maxHigh = currHigh
        return maxHigh

    def addBouncePlay(self, coin, value):
        self.logger.log(self.bouncePlaying)
        self.bouncePlayObjs[coin] = BouncePlay(coin, self, self.trader)
        self.bounceQueue.pop(coin, 0)
        self.bouncePlayCount = len(self.bouncePlaying)
        self.logger.log("Playing bounce-play from list: {0}".format(coin))
        self.bouncePlaying[coin] = value

    def removeBouncePlay(self, coin):
        self.bouncePlaying.pop(coin, 0)
        self.bouncePlayObjs.pop(coin, 0)
        self.bouncePlayCount = len(self.bouncePlaying)
        self.logger.log("Deleting current bounce play: {0}".format(coin))
        self.logger.log(self.bouncePlaying)

    def startBouncePlay(self, coin):
        self.bouncePlayObjs[coin].run()

    def addToRunners(self, info):
        # info in the form of {coin, low, high}
        with lock:
            if info["coin"] not in self.runners:
                self.runners[info["coin"]] = info
                self.logger.log("Adding {0} to the runner list".format(info["coin"]))


ChadAlert().run()
