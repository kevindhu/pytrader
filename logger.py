import datetime


class Logger:
    def __init__(self, name):
        self.name = name

    def log(self, text):
        print(text)
        date = datetime.datetime.now()
        file = "logs/{0}-{1}-{2}.txt".format(str(date.month), str(date.day), str(date.hour))
        timestamp = datetime.datetime.now()
        with open(file, 'a') as f:
            f.write("{0}: {1} - {2}\n".format(timestamp, self.name, text))
            f.close()
