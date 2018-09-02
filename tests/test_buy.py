from binance.client import Client
from binance.enums import *

API_KEY = "i1s87G06vlhZTdKy7z3V0IRRKujhvps4umFTELYqre3awoeD4ZKpzWsCm8O3HklK"
API_SECRET = "mpZGQfH0SraheOvbJZMANJCWapD5xDo0HfbapGGmjm3YCXxsvrFj4a5zVxNOqdoP"
NUM_THREADS = 100


def truncate(f, n):
    # Truncates/pads a float f to n decimal places without rounding
    s = '{}'.format(f)
    if 'e' in s or 'E' in s:
        return '{0:.{1}f}'.format(f, n)
    i, p, d = s.partition('.')
    return '.'.join([i, (d + '0' * n)[:n]])


client = Client(API_KEY, API_SECRET, {"timeout": 60})

price = 0.001655552113213123
price = "%.4g" % price
newPrice = '{:.8f}'.format(float(price))
print(newPrice)

print("BUYING BTGBTC AT {0}", newPrice)

secondOrder = client.create_test_order(
    symbol="BTGBTC",
    side=Client.SIDE_BUY,
    type=ORDER_TYPE_LIMIT,
    timeInForce=TIME_IN_FORCE_GTC,
    quantity=1000,
    price=newPrice)
