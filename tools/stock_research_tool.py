import yfinance as yf
from crewai.tools import tool
import requests


@tool("Live Stock Information Tool")
def get_stock_price(stock_symbol: str) -> str:
    """
    Retrieves the latest stock price and other relevant info for a given stock symbol using Yahoo Finance.

    Parameters:
        stock_symbol (str): The ticker symbol of the stock (e.g., AAPL, TSLA, MSFT).

    Returns:
        str: A summary of the stock's current price, daily change, and other key data.
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.1.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://finance.yahoo.com/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    })
    stock = yf.Ticker(stock_symbol, session=session)
    
    # Pre-warm Step
    stock.history(period="1d", interval="1d")
    
    info = stock.info

    current_price = info.get("regularMarketPrice")
    change = info.get("regularMarketChange")
    change_percent = info.get("regularMarketChangePercent")
    currency = info.get("currency", "INR")

    if current_price is None:
        return f"Could not fetch price for {stock_symbol}. Please check the symbol."

    return (
        f"Stock: {stock_symbol.upper()}\n"
        f"Price: {current_price} {currency}\n"
        f"Change: {change} ({round(change_percent, 2)}%)"
    )
