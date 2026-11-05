import yfinance as yf
from crewai.tools import tool
import requests

@tool("Fundamental Analysis Tool")
def get_fundamental_ratios(stock_symbol: str) -> str:
    """
    Retrieves key fundamental ratios and financial metrics for a given stock symbol using Yahoo Finance.
    Retrieved metrics include P/E, PEG, P/B, ROE, Debt/Equity, and Dividend Yield.

    Parameters:
        stock_symbol (str): The ticker symbol of the stock (e.g., AAPL, RELIANCE.NS).

    Returns:
        str: A formatted summary of the fundamental ratios.
    """
    try:
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
        
        # Pre-warm Step: Fetch a small amount of history to "wake up" the session cookies
        stock.history(period="1d")
        
        info = stock.info
        
        # Fallback for Indian tickers: If info is empty, try to get basic data from chart metadata
        if not info or len(info) < 5:
            try:
                import json
                import urllib.request
                url = f"https://query2.finance.yahoo.com/v8/finance/chart/{stock_symbol}?range=1d&interval=1d"
                req = urllib.request.Request(url, headers=session.headers)
                with urllib.request.urlopen(req, timeout=5) as response:
                    res_data = json.loads(response.read().decode())['chart']['result'][0]['meta']
                    info = {
                        "marketCap": res_data.get("marketCap", "N/A"),
                        "trailingPE": res_data.get("trailingPE", "N/A"),
                        "forwardPE": res_data.get("forwardPE", "N/A"),
                        "regularMarketPrice": res_data.get("regularMarketPrice", "N/A"),
                        "currency": res_data.get("currency", "INR")
                    }
            except:
                pass

        # Safe extraction with default "N/A"
        pe_ratio = info.get("trailingPE", "N/A")
        forward_pe = info.get("forwardPE", "N/A")
        peg_ratio = info.get("pegRatio", "N/A")
        pb_ratio = info.get("priceToBook", "N/A")
        roe = info.get("returnOnEquity", "N/A")
        debt_to_equity = info.get("debtToEquity", "N/A")
        dividend_yield = info.get("dividendYield", "N/A")
        market_cap = info.get("marketCap", "N/A")
        beta = info.get("beta", "N/A")
        fifty_two_week_high = info.get("fiftyTwoWeekHigh", "N/A")
        fifty_two_week_low = info.get("fiftyTwoWeekLow", "N/A")

        # Formatting values if they are numbers
        if isinstance(roe, (int, float)):
            roe = f"{roe * 100:.2f}%"
        if isinstance(dividend_yield, (int, float)):
            dividend_yield = f"{dividend_yield * 100:.2f}%"
        if isinstance(market_cap, (int, float)):
            market_cap = f"{market_cap / 1e9:.2f}B"

        return (
            f"Fundamental Ratios for {stock_symbol.upper()}:\n"
            f"- Market Cap: {market_cap}\n"
            f"- P/E Ratio (Trailing): {pe_ratio}\n"
            f"- Forward P/E: {forward_pe}\n"
            f"- PEG Ratio: {peg_ratio}\n"
            f"- P/B Ratio: {pb_ratio}\n"
            f"- ROE: {roe}\n"
            f"- Debt/Equity: {debt_to_equity}\n"
            f"- Dividend Yield: {dividend_yield}\n"
            f"- Beta: {beta}\n"
            f"- 52-Week High: {fifty_two_week_high}\n"
            f"- 52-Week Low: {fifty_two_week_low}\n"
        )
    except Exception as e:
        return f"Error fetching fundamentals for {stock_symbol}: {e}"
