import datetime
import os


class Logger:
    def __init__(self, name):
        self.name = name

    def log(self, text):
        print(text)
        date = datetime.datetime.now()
        if self.name != "":
            if self.name.endswith("receipt"):
                dir = "logs/{0}-{1}/receipts/{2}.txt".format(str(date.month), str(date.day), self.name)
                file = "logs/{0}-{1}/receipts/".format(str(date.month), str(date.day))
            else:
                dir = "logs/{0}-{1}/{2}.txt".format(str(date.month), str(date.day), self.name)
                file = "logs/{0}-{1}/".format(str(date.month), str(date.day))
            if not os.path.exists(file):
                os.makedirs(file)
        else:
            dir = "logs/{0}-{1}-{2}.txt".format(str(date.month), str(date.day), str(date.hour))
        timestamp = datetime.datetime.now()

        with open(dir, 'a') as f:
            f.write("{0}: {1}\n".format(timestamp, text))
            f.close()
