from __future__ import division
from binance.client import Client
import time

API_KEY = ""
API_SECRET = ""


class FindBases:
    def __init__(self, coin):
        self.client = Client(API_KEY, API_SECRET, {"timeout": 60})
        start = time.time()
        self.klines = self.client.get_historical_klines(coin, Client.KLINE_INTERVAL_1HOUR, "8 days ago",
                                                        "now")
        end = time.time()
        print("LATENCY: " + str(end - start))

    def run(self):
        bases = []
        for index in range(0, len(self.klines) - 1):
            if self.isBase(index, self.klines, 5):
                currDate = self.klines[index][0]
                currBase = min(float(self.klines[index][4]), float(self.klines[index][1]))
                currBase = (currBase + float(self.klines[index][3])) / 2
                bases.append([currDate, currBase])

        for base in bases:
            print(base)

    def isBase(self, index, chart, hours):
        curr = chart[index]
        prev = chart[index - 1]

        # find if curr low is lower than previous candle's low
        isBottom = float(curr[3]) < float(prev[3])

        # find if next few hours' high is 10-30% higher than the candle's low
        maxHigh = -1.0
        for i in range(0, hours):
            if index + i + 1 >= len(chart):
                continue
            currCandle = chart[index + i + 1]
            currHigh = float(currCandle[2])
            if maxHigh < currHigh:
                maxHigh = currHigh

        # print("MAXHIGH:" + str(maxHigh))

        hasJump = (maxHigh / float(curr[3])) > 1.07
        return hasJump & isBottom


while True:
    FindBases("REQBTC").run()
