from __future__ import division
from binance.client import Client
import threading
from threading import Thread
from queue import Queue
import time
from logger import Logger
import discord
import asyncio

client = discord.Client()

API_KEY = ""
API_SECRET = ""
NUM_THREADS = 100

stopped = False


def truncate(f, n):
    # Truncates/pads a float f to n decimal places without rounding
    s = '{}'.format(f)
    if 'e' in s or 'E' in s:
        return '{0:.{1}f}'.format(f, n)
    i, p, d = s.partition('.')
    return '.'.join([i, (d + '0' * n)[:n]])


@client.event
async def on_ready():
    print("LOGGED IN AS")
    print(client.user.name)
    print(client.user.id)


@client.event
async def on_message(message):
    global stopped
    channel = message.channel
    if message.content.startswith("info"):
        await client.send_message(channel, "start, stop, hi")
    elif message.content.startswith("hi"):
        await client.send_message(channel, "sup beta, still a virgin? LOL")
    elif message.content.startswith("stop"):
        stopped = True
        await client.send_message(channel, "**CHAD ATTEMPTING TO STOP**")
    elif message.content.startswith("start"):
        stopped = False
        await client.send_message(channel, "**CHAD IS AWAKE**")
        chadAlert = ChadAlert()
        try:
            while not stopped:
                chadAlert.run()
                await asyncio.sleep(20)
                for message in chadAlert.messages:
                    await client.send_message(channel, message)
                    await asyncio.sleep(0.5)
                chadAlert.messages = set()
                await asyncio.sleep(2)
            await client.send_message(channel, "**CHAD IS SLEEP**")
        except Exception as e:
            await client.send_message(channel, "**ERROR, CHAD IS SLEEP**")


class ChadAlert:
    def __init__(self):
        self.messages = set()
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

        for worker_id in range(NUM_THREADS):
            worker = Thread(target=self.process_queue, args=[worker_id])
            worker.daemon = True
            worker.start()
            self.workers.append(worker)

    def run(self):
        global lock
        lock = threading.Lock()

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

        if self.loops % 4000 == 0:
            self.logger.log("resetting blacklist")

        # self.logger.log(len(self.tenMinKlines))

    def process_queue(self, worker_id):
        while True:
            ticker = self.queue.get()
            coin = ticker['symbol']
            currPrice = float(ticker['price'])
            self.probe(coin, currPrice)
            self.queue.task_done()

    def getPrice(self, coin):
        return self.prices[coin]

    def probe(self, coin, currPrice):
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
            self.messages.add(
                "**{0}** stepped **{1}%** - 5 hours (price : {2})".
                    format(coin, str(truncate(hourIncrease * 100, 1)), str(currPrice)))
            self.fiveHourChad.add(coin)

        if tenMinIncrease > 0.07 and (coin not in self.tenMinChad):
            self.messages.add(
                "__**{0}** CHADSTEPPED **{1}%** - 10 mins (price : {2})__".
                    format(coin, str(truncate(hourIncrease * 100, 1)), str(currPrice)))
            self.tenMinChad.add(coin)

    def getMinLow(self, klines):
        minLow = 100000000.0
        for index in range(0, len(klines) - 1):
            currLow = float(klines[index][3])
            if minLow > currLow:
                minLow = currLow
        return minLow


try:
    client.run("NDAzNTA2NjUwMTg4NjExNjA0.DUISgQ.uDgcGkmjAjJWavtldiRVQkU31Ak")
except  Exception as e:
    print("OOPSIES! I CRASHED!")
