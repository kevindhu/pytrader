import datetime
import os


class Logger:
    def __init__(self, name, coin):
        self.name = name
        self.coin = coin

    def log(self, text):
        print(text)
        date = datetime.datetime.now()
        if self.coin != "":
            dir = "logs/{0}-{1}/{2}.txt".format(str(date.month), str(date.day), self.coin)
            file = "logs/{0}-{1}/".format(str(date.month), str(date.day))
            if not os.path.exists(file):
                os.makedirs(file)
        else:
            dir = "logs/{0}-{1}-{2}.txt".format(str(date.month), str(date.day), str(date.hour))
        timestamp = datetime.datetime.now()

        with open(dir, 'a') as f:
            f.write("{0}: {1}\n".format(timestamp, text))
            f.close()
