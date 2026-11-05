
from yahooquery import Screener
import csv
s = Screener()
d = s.get_screeners(["all_cryptocurrencies", "day_gainers"]) # Wait, yahooquery screeners for country, or we can use the top lists

