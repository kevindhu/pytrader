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
                                                                  "5 hours ago PT")
                with lock:
                    self.hourKlines[coin] = newHourKlines

        except TypeError:
            # self.logger.log("TYPEERROR SHIT FOR " + coin + " in " + TIME_SCALE)
            return

        hourMinLow = self.getMinLow(self.hourKlines[coin])
        hourIncrease = (currPrice - hourMinLow) / hourMinLow

        # add to / edit bounce
        if hourIncrease > 0.1 and (coin not in self.bounceQueue) and (coin not in self.bouncePlaying) and (
                coin not in self.runners) \
                and coin not in self.blacklist:
            with lock:
                self.logger.log("adding {0} to bounce list".format(coin))
                self.bounceQueue[coin] = hourIncrease

        if coin in self.bounceQueue and self.bounceQueue[coin] < hourIncrease:
            self.bounceQueue[coin] = hourIncrease

        # check runners to see if you can bounce play them again
        if coin in self.runners:
            price = self.prices[coin]

            if self.serverTime - self.runners[coin]["time"] > 106400000:
                self.logger.log("Too long, taking {0} out of runners".format(coin))
                self.runners.pop(coin, 0)

            elif price > self.runners[coin]["high"]:
                self.logger.log("Adding runner back into bounceQueue list")
                self.bounceQueue[coin] = hourIncrease
                self.runners.pop(coin, 0)

        if coin in self.bounceQueue and (coin not in self.bouncePlaying):
            sorted_plays = sorted(self.bouncePlaying.items(), key=operator.itemgetter(0))
            if self.bouncePlayCount < 5:
                self.addBouncePlay(coin)

            # add weak coin to bounce queue again
            else:
                for pair in sorted_plays:
                    currCoin = pair[0]
                    value = pair[1]
                    if self.bounceQueue[coin] > value and self.bouncePlayObjs[currCoin].stage < 3:
                        with lock:
                            self.bounceQueue[currCoin] = self.bouncePlaying[currCoin]
                            self.removeBouncePlay(currCoin)
                            self.addBouncePlay(coin)
                            self.logger.log("REPLACED {0} for {1} in bounce plays".format(currCoin, coin))
                        break

    def getMinLow(self, klines):
        minLow = 100000000.0
        for index in range(0, len(klines) - 1):
            currLow = float(klines[index][3])
            if minLow > currLow:
                minLow = currLow
        return minLow

    def addBouncePlay(self, coin):
        self.bouncePlaying[coin] = self.bounceQueue[coin]
        self.bounceQueue.pop(coin, 0)
        self.logger.log("Playing bounce-play from list: {0}".format(coin))
        bouncePlay = BouncePlay(coin, self)
        self.bouncePlayObjs[coin] = bouncePlay
        self.bouncePlayCount += 1

    def removeBouncePlay(self, coin):
        self.bouncePlaying.pop(coin, 0)
        self.bouncePlayObjs.pop(coin, 0)
        self.logger.log("Deleting current bounce play: {0}".format(coin))
        self.bouncePlayCount -= 1

    def addToRunners(self, info):
        # info in the form of {coin, low, high}
        with lock:
            if info["coin"] not in self.runners:
                self.runners[info["coin"]] = info
                self.logger.log("adding {0} to the runner list".format(info["coin"]))


ChadAlert().run()
