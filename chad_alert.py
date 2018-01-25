from __future__ import division
from binance.client import Client
import threading
from threading import Thread
from queue import Queue
import time
from bounce_play_test import BouncePlay
from logger import Logger
import operator

API_KEY = ""
API_SECRET = ""
NUM_THREADS = 100


class ChadAlert:
    def __init__(self):
        self.logger = Logger("ChadAlert", "")
        self.workers = []
        self.queue = Queue()
        self.hourKlines = {}
        self.client = Client(API_KEY, API_SECRET, {"timeout": 60})
        self.blacklist = set()
        self.runners = {}
        self.serverTime = 0.0
        self.prices = {}
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

        allPrices = self.client.get_all_tickers()
        self.logger.log("STARTED CHAD ALERT ----------------------------"
                        "------------------------------------------------")

        while True:
            self.loops += 1
            self.serverTime = self.client.get_server_time()["serverTime"]
            allPrices = self.client.get_all_tickers()
            for ticker in allPrices:
                if ticker['symbol'].endswith("BTC"):
                    self.prices[ticker['symbol']] = float(ticker['price'])
                    self.queue.put(ticker)

            if self.loops % 4000 == 0:
                self.logger.log("resetting blacklist")

    def process_queue(self, worker_id):
        while True:
            if not self.queue.empty():
                ticker = self.queue.get()
                coin = ticker['symbol']
                currPrice = float(ticker['price'])
                self.probe(coin, currPrice)
                self.queue.task_done()

    def getPrice(self, coin):
        return self.prices[coin]

    def probe(self, coin, currPrice):
        TIME_SCALE = "2 hours ago"

        try:
            # updates every 60 minutes
            if coin not in self.hourKlines:
                # self.logger.log("2 HR CALLING " + coin)
                newHourKlines = self.client.get_historical_klines(coin,
                                                                  Client.KLINE_INTERVAL_15MINUTE,
                                                                  "10 hours ago PT")
                with lock:
                    self.hourKlines[coin] = newHourKlines

        except TypeError:
            # self.logger.log("TYPEERROR SHIT FOR " + coin + " in " + TIME_SCALE)
            return

        hourMinLow = self.getMinLow(self.hourKlines[coin])
        hourMaxHigh = self.getMaxHigh(self.hourKlines[coin])
        hourIncrease = (hourMaxHigh - hourMinLow) / hourMinLow

        # add to / edit bounce
        with lock:
            if hourIncrease > 0.1 and (coin not in self.bounceQueue) and (coin not in self.bouncePlaying) \
                    and (coin not in self.runners) and coin not in self.blacklist:
                self.logger.log("adding {0} to bounce queue".format(coin))
                self.bounceQueue[coin] = hourIncrease

        if coin in self.bounceQueue and self.bounceQueue[coin] < hourIncrease:
            self.bounceQueue[coin] = hourIncrease

        # check runners to see if you can bounce play them again
        if coin in self.runners:
            price = self.prices[coin]

            if self.serverTime - self.runners[coin]["time"] > 150000000:
                self.logger.log("Too long, taking {0} out of runners".format(coin))
                self.runners.pop(coin, 0)

            elif price > self.runners[coin]["high"]:
                self.logger.log("Adding runner back into bounce queue")
                self.bounceQueue[coin] = hourIncrease
                self.runners.pop(coin, 0)

        with lock:
            if coin in self.bounceQueue:
                value = self.bounceQueue[coin]
                if self.bouncePlayCount < 5:
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
                            self.bounceQueue[currCoin] = currValue
                            self.bounceQueue.pop(coin, 0)

                            self.removeBouncePlay(currCoin)
                            self.addBouncePlay(coin, value)
                            self.logger.log("REPLACED {0} for {1} in bounce plays ({2} vs {3})"
                                            .format(currCoin, coin, currValue, value))
                            break

        # TODO: STOP RERUNNING
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
        self.logger.log("Playing bounce-play from list: {0}".format(coin))
        self.logger.log("BOUNCE PLAY COUNT IS NOW {0}".format(self.bouncePlayCount))
        self.bouncePlayObjs[coin] = BouncePlay(coin, self)
        self.bouncePlaying[coin] = value
        self.bounceQueue.pop(coin, 0)
        self.bouncePlayCount = len(self.bouncePlaying)

    def removeBouncePlay(self, coin):
        self.bouncePlaying.pop(coin, 0)
        self.bouncePlayObjs.pop(coin, 0)
        self.bouncePlayCount = len(self.bouncePlaying)
        self.logger.log("Deleting current bounce play: {0}".format(coin))
        self.logger.log("BOUNCE PLAY COUNT IS NOW {0}".format(self.bouncePlayCount))

    def startBouncePlay(self, coin):
        self.bouncePlayObjs[coin].run()

    def addToRunners(self, info):
        # info in the form of {coin, low, high}
        with lock:
            if info["coin"] not in self.runners:
                self.runners[info["coin"]] = info
                self.logger.log("adding {0} to the runner list".format(info["coin"]))


ChadAlert().run()
