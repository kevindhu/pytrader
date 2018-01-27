import datetime
import os


class Logger:
    def __init__(self, name):
        self.name = name

    def log(self, text):
        # only for the console
        print(text)
        timestamp = datetime.datetime.now()
        date = datetime.datetime.now()
        month = str(date.month)
        day = str(date.day)
        hour = str(date.hour)
        directory = "logs/{0}-{1}-{2}.txt".format(month, day, hour)
        directory2 = None

        if self.name != "":
            if self.name.endswith("receipt"):
                directory2 = "logs/{0}-{1}/receipts/{2}.txt".format(month, day, self.name)
                file = "logs/{0}-{1}/receipts/".format(month, day)
            else:
                directory2 = "logs/{0}-{1}/{2}.txt".format(month, day, self.name)
                file = "logs/{0}-{1}/".format(month, day)
            if not os.path.exists(file):
                os.makedirs(file)

        with open(directory, 'a') as f:
            f.write("{0}: {1}\n".format(timestamp, text))
            f.close()

        if directory2:
            with open(directory2, 'a') as f:
                f.write("{0}: {1}\n".format(timestamp, text))
                f.close()
