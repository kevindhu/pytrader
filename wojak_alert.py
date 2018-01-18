from __future__ import division
from binance.client import Client
import threading
from threading import Thread
from queue import Queue
import time
import datetime

API_KEY = ""
API_SECRET = ""
NUM_THREADS = 100

COINS = ["ADABTC", "ADXBTC", "AIONBTC", "AMBBTC", "APPCBTC", "ARKBTC", "ARNBTC", "ASTBTC", "BATBTC", "BCCBTC",
         "BCDBTC", "BCPTBTC"
         ]


class WojakAlert:
    def __init__(self):
        self.workers = []
        self.queue = Queue()
        self.twoHourWojak = set()
        self.tenMinWojak = set()
        self.hourKlines = {}
        self.tenMinKlines = {}
        self.client = Client(API_KEY, API_SECRET, {"timeout": 60})

    def run(self):
        loops = 0
        for worker_id in range(NUM_THREADS):
            worker = Thread(target=self.process_queue, args=[worker_id])
            worker.daemon = True
            worker.start()
            self.workers.append(worker)

        time.sleep(1)

        global lock
        lock = threading.Lock()

        while True:
            loops += 1
            allPrices = self.client.get_all_tickers()
            for ticker in allPrices:
                if ticker['symbol'].endswith("BTC"):
                    self.queue.put(ticker)

            # resets every 100 loops
            if loops % 100 == 0:
                print("RESETTING SETS")
                self.twoHourWojak = set()
                self.tenMinWojak = set()
            time.sleep(5)

            # print(len(self.tenMinKlines))

    def process_queue(self, worker_id):
        print("Started worker thread: %s" % worker_id)
        while True:
            if not self.queue.empty():
                ticker = self.queue.get()
                coin = ticker['symbol']
                currPrice = float(ticker['price'])
                self.probe(coin, currPrice)
                self.queue.task_done()

    def probe(self, coin, currPrice):
        TIME_SCALE = "2 hours ago"

        try:
            # updates every 60 minutes
            if coin not in self.hourKlines:
                newHourKlines = self.client.get_historical_klines(coin,
                                                                  Client.KLINE_INTERVAL_1HOUR,
                                                                  "2 hours ago PT")
                with lock:
                    self.hourKlines[coin] = newHourKlines

            # update every 10 minutes
            if coin not in self.tenMinKlines:
                newTenMinKlines = self.client.get_historical_klines(coin,
                                                                    Client.KLINE_INTERVAL_5MINUTE,
                                                                    "10 minutes ago PT")
                with lock:
                    self.tenMinKlines[coin] = newTenMinKlines

        except TypeError:
            # print("TYPEERROR SHIT FOR " + coin + " in " + TIME_SCALE)
            return

        hourMaxHigh = self.getMaxHigh(self.hourKlines[coin])
        tenMinMaxHigh = self.getMaxHigh(self.tenMinKlines[coin])

        hourDecrease = (hourMaxHigh - currPrice) / hourMaxHigh
        tenMinDecrease = (tenMinMaxHigh - currPrice) / tenMinMaxHigh

        if hourDecrease > 0.1 and (coin not in self.twoHourWojak):
            print("OOF! THE PRICE FOR {0} has dropped {1}% in the past two hours! (price : {2})"
                  .format(coin, str(hourDecrease * 100), str(currPrice)))
            self.twoHourWojak.add(coin)

        if tenMinDecrease > 0.05 and (coin not in self.tenMinWojak):
            print("OUCHIES! THE PRICE FOR {0} has dropped {1}% in the past ten minutes! (price : {2})"
                  .format(coin, str(tenMinDecrease * 100), str(currPrice)))
            self.tenMinWojak.add(coin)

    def getMaxHigh(self, klines):
        maxHigh = -1.0
        for index in range(0, len(klines) - 1):
            currHigh = float(klines[index][2])
            if maxHigh < currHigh:
                maxHigh = currHigh
        return maxHigh


WojakAlert().run()
