from __future__ import division
from binance.client import Client
import threading
from threading import Thread
from queue import Queue
import time
from bounce_play_test import BouncePlay
from logger import Logger

API_KEY = ""
API_SECRET = ""
NUM_THREADS = 100


class ChadAlert:
    def __init__(self):
        self.logger = Logger("ChadAlert")
        self.workers = []
        self.queue = Queue()
        self.fiveHourChad = set()
        self.tenMinChad = set()
        self.hourKlines = {}
        self.tenMinKlines = {}
        self.client = Client(API_KEY, API_SECRET, {"timeout": 60})
        self.bouncePlays = set()
        self.blacklist = set()
        self.bouncePlaying = False
        self.runners = {}
        self.serverTime = 0.0
        self.prices = {}
        self.loops = 0

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
        self.logger.log("----------------------------------------------------------------------------")

        while True:
            self.loops += 1
            self.serverTime = self.client.get_server_time()["serverTime"]
            allPrices = self.client.get_all_tickers()
            for ticker in allPrices:
                if ticker['symbol'].endswith("BTC"):
                    self.prices[ticker['symbol']] = float(ticker['price'])
                    self.queue.put(ticker)

            # resets every 100 loops
            if self.loops % 100 == 0:
                self.logger.log("RESETTING SETS")
                self.fiveHourChad = set()
                self.tenMinChad = set()
            time.sleep(5)

            if self.loops % 4000 == 0:
                self.logger.log("resetting blacklist")

            # self.logger.log(len(self.tenMinKlines))

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
                                                                  Client.KLINE_INTERVAL_1HOUR,
                                                                  "5 hours ago PT")
                with lock:
                    self.hourKlines[coin] = newHourKlines

            # update every 10 minutes
            if coin not in self.tenMinKlines:
                # self.logger.log("10 MIN CALLING " + coin)
                newTenMinKlines = self.client.get_historical_klines(coin,
                                                                    Client.KLINE_INTERVAL_5MINUTE,
                                                                    "10 minutes ago PT")
                with lock:
                    self.tenMinKlines[coin] = newTenMinKlines

        except TypeError:
            # self.logger.log("TYPEERROR SHIT FOR " + coin + " in " + TIME_SCALE)
            return

        hourMinLow = self.getMinLow(self.hourKlines[coin])
        tenMinMinLow = self.getMinLow(self.tenMinKlines[coin])

        hourIncrease = (currPrice - hourMinLow) / hourMinLow
        tenMinIncrease = (currPrice - tenMinMinLow) / tenMinMinLow

        if hourIncrease > 0.1 and (coin not in self.fiveHourChad):
            # self.logger.log("NICE! THE PRICE FOR {0} has CHADSTEPPED {1}% in the past five hours! (price : {2})".
            # format(coin, str(hourIncrease * 100), str(currPrice)))
            self.fiveHourChad.add(coin)

        if hourIncrease > 0.1 and (coin not in self.bouncePlays) and \
                (coin not in self.runners) and (coin not in self.blacklist):
            self.logger.log("adding {0} to bounce list".format(coin))
            self.bouncePlays.add(coin)

        # check runners to see if you can bounce play them again
        if coin in self.runners:
            price = self.prices[coin]

            if self.serverTime - self.runners[coin]["time"] > 1000000:
                self.logger.log("Too long, taking coin out of runners")
                self.runners.pop(coin, 0)

            elif price > self.runners[coin]["high"]:
                self.logger.log("Adding runner back into bouncePlay list")
                self.bouncePlays.add(coin)
                self.runners.pop(coin, 0)

        if coin in self.bouncePlays and not self.bouncePlaying:
            self.logger.log("Playing bounce-play from list: {0}".format(coin))
            self.bouncePlaying = True
            bouncePlay = BouncePlay(coin, self)

        if tenMinIncrease > 0.07 and (coin not in self.tenMinChad):
            self.logger.log("YOOO! THE PRICE FOR {0} has CHADSTEPPED {1}% in the past ten minutes! (price : {2})"
                  .format(coin, str(tenMinIncrease * 100), str(currPrice)))
            self.tenMinChad.add(coin)

    def getMinLow(self, klines):
        minLow = 100000000.0
        for index in range(0, len(klines) - 1):
            currLow = float(klines[index][3])
            if minLow > currLow:
                minLow = currLow
        return minLow

    def addToRunners(self, info):
        # info in the form of {coin, low, high}
        with lock:
            if info["coin"] not in self.runners:
                self.runners[info["coin"]] = info


ChadAlert().run()
