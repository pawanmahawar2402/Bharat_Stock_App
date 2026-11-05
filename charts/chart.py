# import yfinance as yf
# import pandas as pd
# import numpy as np
# import matplotlib.pyplot as plt
# import mplfinance as mpf
# from io import BytesIO
# from PIL import Image

# # --------------------------------------
# # Stock Mapping
# # --------------------------------------
# STOCK_MAPPING = {
#     "Reliance Industries": "RELIANCE.NS",
#     "HDFC Bank": "HDFCBANK.NS",
#     "Infosys": "INFY.NS",
#     "State Bank of India": "SBIN.NS",
#     "ICICI Bank": "ICICIBANK.NS",
#     "Tata Consultancy Services": "TCS.NS",
#     "Bharti Airtel": "BHARTIARTL.NS",
#     "Kotak Mahindra Bank": "KOTAKBANK.NS",
#     "Axis Bank": "AXISBANK.NS",
#     "Larsen & Toubro": "LT.NS",
#     "Bajaj Finance": "BAJFINANCE.NS",
#     "ITC": "ITC.NS",
#     "Hindustan Unilever": "HINDUNILVR.NS",
#     "Maruti Suzuki": "MARUTI.NS",
#     "Mahindra & Mahindra": "M&M.NS",
#     "Adani Enterprises": "ADANIENT.NS",
#     "Adani Ports & SEZ": "ADANIPORTS.NS",
#     "Tata Steel": "TATASTEEL.NS",
#     "JSW Steel": "JSWSTEEL.NS",
#     "UltraTech Cement": "ULTRACEMCO.NS",
#     "Sun Pharmaceutical": "SUNPHARMA.NS",
#     "Dr. Reddy's Laboratories": "DRREDDY.NS",
#     "Divi's Laboratories": "DIVISLAB.NS",
#     "Cipla": "CIPLA.NS",
#     "Wipro": "WIPRO.NS",
#     "Tech Mahindra": "TECHM.NS",
#     "HCL Technologies": "HCLTECH.NS",
#     "Nestle India": "NESTLEIND.NS",
#     "Britannia Industries": "BRITANNIA.NS",
#     "Eicher Motors": "EICHERMOT.NS",
#     "Bajaj Auto": "BAJAJ-AUTO.NS",
#     "Tata Motors": "TATAMOTORS.NS",
#     "Grasim Industries": "GRASIM.NS",
#     "Hindalco Industries": "HINDALCO.NS",
#     "Coal India": "COALINDIA.NS",
#     "NTPC": "NTPC.NS",
#     "Power Grid Corporation": "POWERGRID.NS",
#     "SBI Life Insurance": "SBILIFE.NS",
#     "Zee Entertainment": "ZEEL.NS"
# }

# # --------------------------------------
# # Resolve friendly name to ticker
# # --------------------------------------
# def resolve_symbol(stock_name_or_symbol):
#     return STOCK_MAPPING.get(stock_name_or_symbol, stock_name_or_symbol)

# # --------------------------------------
# # Fetch stock data
# # --------------------------------------
# def fetch_stock_data(symbol, period="6mo", interval="1d"):
#     df = yf.download(symbol, period=period, interval=interval, progress=False)
#     if df.empty:
#         raise ValueError(f"No data fetched for {symbol}")

#     # Reset MultiIndex columns (sometimes yfinance gives them)
#     df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]

#     # Keep only OHLCV
#     required_cols = ["Open", "High", "Low", "Close", "Volume"]
#     df = df[required_cols]

#     # Ensure datetime index
#     df.index = pd.to_datetime(df.index)

#     # Ensure numeric
#     for col in required_cols:
#         df[col] = pd.to_numeric(df[col], errors="coerce")

#     df = df.dropna(subset=["Open", "High", "Low", "Close"])

#     return df

# # --------------------------------------
# # Add indicators
# # --------------------------------------
# def add_indicators(df):
#     # Moving Averages
#     df["SMA20"] = df["Close"].rolling(20).mean()
#     df["SMA50"] = df["Close"].rolling(50).mean()

#     # RSI
#     df["RSI"] = compute_rsi(df["Close"])

#     # MACD
#     short_ema = df["Close"].ewm(span=12, adjust=False).mean()
#     long_ema = df["Close"].ewm(span=26, adjust=False).mean()
#     df["MACD"] = short_ema - long_ema
#     df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
#     df["MACD_Hist"] = df["MACD"] - df["Signal"]

#     # Bollinger Bands
#     rolling_mean = df["Close"].rolling(20).mean()
#     rolling_std = df["Close"].rolling(20).std()
#     df["BB_Upper"] = rolling_mean + (rolling_std * 2)
#     df["BB_Lower"] = rolling_mean - (rolling_std * 2)

#     return df


# def compute_rsi(series, period=14):
#     delta = series.diff()
#     gain = np.where(delta > 0, delta, 0)
#     loss = np.where(delta < 0, -delta, 0)
#     avg_gain = pd.Series(gain).rolling(period).mean()
#     avg_loss = pd.Series(loss).rolling(period).mean()
#     rs = avg_gain / avg_loss.replace(0, np.nan)
#     rsi = 100 - (100 / (1 + rs))
#     return rsi.fillna(50)   # neutral default

# # --------------------------------------
# # Detect patterns
# # --------------------------------------
# def detect_hammer(df):
#     hammers = []
#     for i in range(1, len(df)):
#         o, h, l, c = df.iloc[i][["Open", "High", "Low", "Close"]]
#         body = abs(c - o)
#         lower_shadow = o - l if c >= o else c - l
#         upper_shadow = h - c if c >= o else h - o
#         if body < (h - l) * 0.3 and lower_shadow > body * 2 and upper_shadow < body:
#             hammers.append(df.index[i])
#     return hammers

# def detect_doji(df):
#     dojis = []
#     for i in range(len(df)):
#         o, c, h, l = df.iloc[i][["Open", "Close", "High", "Low"]]
#         if abs(c - o) <= (h - l) * 0.1:
#             dojis.append(df.index[i])
#     return dojis

# def detect_bullish_engulfing(df):
#     engulfs = []
#     for i in range(1, len(df)):
#         o1, c1 = df.iloc[i-1][["Open", "Close"]]
#         o2, c2 = df.iloc[i][["Open", "Close"]]
#         if c1 < o1 and c2 > o2 and c2 >= o1 and o2 <= c1:
#             engulfs.append(df.index[i])
#     return engulfs

# def detect_bearish_engulfing(df):
#     engulfs = []
#     for i in range(1, len(df)):
#         o1, c1 = df.iloc[i-1][["Open", "Close"]]
#         o2, c2 = df.iloc[i][["Open", "Close"]]
#         if c1 > o1 and c2 < o2 and c2 <= o1 and o2 >= c1:
#             engulfs.append(df.index[i])
#     return engulfs

# # --------------------------------------
# # Pattern detection map
# # --------------------------------------
# PATTERN_FUNCTIONS = {
#     "hammer": detect_hammer,
#     "doji": detect_doji,
#     "bullish_engulfing": detect_bullish_engulfing,
#     "bearish_engulfing": detect_bearish_engulfing,
# }

# # --------------------------------------
# # Chart with patterns + labels
# # --------------------------------------
# def generate_pattern_chart(df, patterns):
#     pattern_indices = {}
#     for p in patterns:
#         if p in PATTERN_FUNCTIONS:
#             pattern_indices[p] = PATTERN_FUNCTIONS[p](df)

#     # ✅ use mplfinance with returnfig=True
#     fig, axlist = mpf.plot(
#         df,
#         type="candle",
#         style="yahoo",
#         show_nontrading=True,
#         returnfig=True,
#         figsize=(12, 6),
#     )
#     ax = axlist[0]   # main candle axis

#     colors = {
#         "hammer": "green",
#         "doji": "blue",
#         "bullish_engulfing": "lime",
#         "bearish_engulfing": "red",
#     }

#     # ✅ Label only selected patterns
#     for p, idxs in pattern_indices.items():
#         if not idxs:
#             continue
#         for dt in idxs:
#             if dt not in df.index:
#                 continue
#             price = df.at[dt, "Close"]

#             # Marker
#             ax.plot([dt], [price], marker="*", color=colors.get(p, "black"), markersize=14)

#             # Label above candle
#             ax.text(
#                 dt, price * 1.02,
#                 p.replace("_", " ").title(),
#                 fontsize=9,
#                 color=colors.get(p, "black"),
#                 ha="center", va="bottom",
#                 bbox=dict(facecolor="white", alpha=0.6, edgecolor="none")
#             )

#     buf = BytesIO()
#     fig.savefig(buf, format="png", bbox_inches="tight")
#     plt.close(fig)
#     buf.seek(0)
#     img = Image.open(buf)
#     return img, pattern_indices

# # --------------------------------------
# # Indicator Summary
# # --------------------------------------
# def calculate_indicators(df):
#     signals = []
#     if df["SMA20"].iloc[-1] > df["SMA50"].iloc[-1]:
#         signals.append("Bullish: SMA20 above SMA50")
#     else:
#         signals.append("Bearish: SMA20 below SMA50")
#     if df["RSI"].iloc[-1] > 70:
#         signals.append("Overbought (RSI > 70)")
#     elif df["RSI"].iloc[-1] < 30:
#         signals.append("Oversold (RSI < 30)")
#     return signals

# # --------------------------------------
# # Main function
# # --------------------------------------
# def get_chart_with_patterns_and_indicators(stock_name_or_symbol, patterns=None,
#                                            period="6mo", interval="1d"):
#     symbol = resolve_symbol(stock_name_or_symbol)
#     df = fetch_stock_data(symbol, period=period, interval=interval)
#     df = df.sort_index()
#     df = df[~df.index.duplicated(keep="last")]

#     if len(df) < 2:
#         raise ValueError("Not enough data to create chart")

#     if patterns is None:
#         patterns = ["hammer", "doji", "bullish_engulfing", "bearish_engulfing"]

#     img, indices = generate_pattern_chart(df, patterns)

#     summary = []
#     for p in patterns:
#         dates = [str(d.date()) for d in indices.get(p, [])]
#         if dates:
#             summary.append(f"{p}: {dates}")

#     summary.extend(calculate_indicators(add_indicators(df)))

#     if not summary:
#         summary = ["No significant candlestick pattern or signal detected."]

#     return img, "\n".join(summary)


# # --------------------------------------
# # Example Usage
# # --------------------------------------
# if __name__ == "__main__":
#     stock = "Bharti Airtel"
#     patterns = ["hammer", "doji", "bullish_engulfing", "bearish_engulfing"]
#     chart, summary = get_chart_with_patterns_and_indicators(stock, patterns)
#     chart.show()
#     print(summary)
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import mplfinance as mpf
from io import BytesIO
from PIL import Image

# --------------------------------------
# Stock Mapping
# --------------------------------------
STOCK_MAPPING = {
    "Reliance Industries": "RELIANCE.NS",
    "HDFC Bank": "HDFCBANK.NS",
    "Infosys": "INFY.NS",
    "State Bank of India": "SBIN.NS",
    "ICICI Bank": "ICICIBANK.NS",
    "Tata Consultancy Services": "TCS.NS",
    "Bharti Airtel": "BHARTIARTL.NS",
    "Kotak Mahindra Bank": "KOTAKBANK.NS",
    "Axis Bank": "AXISBANK.NS",
    "Larsen & Toubro": "LT.NS",
    "Bajaj Finance": "BAJFINANCE.NS",
    "ITC": "ITC.NS",
    "Hindustan Unilever": "HINDUNILVR.NS",
    "Maruti Suzuki": "MARUTI.NS",
    "Mahindra & Mahindra": "M&M.NS",
    "Adani Enterprises": "ADANIENT.NS",
    "Adani Ports & SEZ": "ADANIPORTS.NS",
    "Tata Steel": "TATASTEEL.NS",
    "JSW Steel": "JSWSTEEL.NS",
    "UltraTech Cement": "ULTRACEMCO.NS",
    "Sun Pharmaceutical": "SUNPHARMA.NS",
    "Dr. Reddy's Laboratories": "DRREDDY.NS",
    "Divi's Laboratories": "DIVISLAB.NS",
    "Cipla": "CIPLA.NS",
    "Wipro": "WIPRO.NS",
    "Tech Mahindra": "TECHM.NS",
    "HCL Technologies": "HCLTECH.NS",
    "Nestle India": "NESTLEIND.NS",
    "Britannia Industries": "BRITANNIA.NS",
    "Eicher Motors": "EICHERMOT.NS",
    "Bajaj Auto": "BAJAJ-AUTO.NS",
    "Tata Motors": "TATAMOTORS.NS",
    "Grasim Industries": "GRASIM.NS",
    "Hindalco Industries": "HINDALCO.NS",
    "Coal India": "COALINDIA.NS",
    "NTPC": "NTPC.NS",
    "Power Grid Corporation": "POWERGRID.NS",
    "SBI Life Insurance": "SBILIFE.NS",
    "Zee Entertainment": "ZEEL.NS"
}

# --------------------------------------
# Resolve friendly name to ticker
# --------------------------------------
def resolve_symbol(stock_name_or_symbol):
    return STOCK_MAPPING.get(stock_name_or_symbol, stock_name_or_symbol)

# --------------------------------------
# Fetch stock data
# --------------------------------------
def fetch_stock_data(symbol, period="6mo", interval="1d"):
    import time
    import requests
    import urllib.request
    import json
    
    # Pure REST Fallback to bypass Strict yfinance Blocking on Hugging Face Data Centers
    def raw_yahoo_fetch(sym, per, inv):
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?range={per}&interval={inv}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
        result = data['chart']['result'][0]
        df = pd.DataFrame(result['indicators']['quote'][0])
        df.index = pd.to_datetime(result['timestamp'], unit='s')
        
        # Rename columns to match yfinance format exactly
        df = df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'})
        return df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()

    df = pd.DataFrame()
    for attempt in range(3):
        # Try 1: Pure REST JSON API directly hitting Yahoo server
        try:
            df = raw_yahoo_fetch(symbol, period, interval)
            if not df.empty: break
        except Exception:
            pass

        # Try 2: yf.Ticker().history()
        try:
            df = yf.Ticker(symbol).history(period=period, interval=interval)
            if not df.empty: break
        except Exception:
            pass

        if attempt < 2:
            time.sleep(1)

    if df.empty:
        raise ValueError(f"No data fetched for {symbol}")

    df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
    required_cols = ["Open", "High", "Low", "Close", "Volume"]
    df = df[[c for c in required_cols if c in df.columns]]
    df.index = pd.to_datetime(df.index)

    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    return df

# --------------------------------------
# Add indicators
# --------------------------------------
def add_indicators(df):
    # Moving Averages
    df["SMA20"] = df["Close"].rolling(20).mean()
    df["SMA50"] = df["Close"].rolling(50).mean()
    
    # EMA
    df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()

    # RSI
    df["RSI"] = compute_rsi(df["Close"])

    # MACD
    short_ema = df["Close"].ewm(span=12, adjust=False).mean()
    long_ema = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = short_ema - long_ema
    df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["Signal"]

    # Bollinger Bands
    rolling_mean = df["Close"].rolling(20).mean()
    rolling_std = df["Close"].rolling(20).std()
    df["BB_Upper"] = rolling_mean + (rolling_std * 2)
    df["BB_Lower"] = rolling_mean - (rolling_std * 2)
    
    # ATR (Average True Range)
    df["ATR"] = compute_atr(df)
    
    # Stochastic Oscillator
    df = compute_stochastic(df)

    return df


def compute_rsi(series, period=14):
    delta = series.diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = pd.Series(gain).rolling(period).mean()
    avg_loss = pd.Series(loss).rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def compute_atr(df, period=14):
    high_low = df["High"] - df["Low"]
    high_close = np.abs(df["High"] - df["Close"].shift())
    low_close = np.abs(df["Low"] - df["Close"].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    return true_range.rolling(period).mean()

def compute_stochastic(df, period=14, k_period=3, d_period=3):
    low_min = df["Low"].rolling(period).min()
    high_max = df["High"].rolling(period).max()
    df["%K"] = 100 * ((df["Close"] - low_min) / (high_max - low_min))
    df["%D"] = df["%K"].rolling(d_period).mean()
    return df

# --------------------------------------
# Candlestick patterns
# --------------------------------------
def detect_hammer(df):
    hammers = []
    for i in range(1, len(df)):
        o, h, l, c = df.iloc[i][["Open", "High", "Low", "Close"]]
        body = abs(c - o)
        lower_shadow = o - l if c >= o else c - l
        upper_shadow = h - c if c >= o else h - o
        if body < (h - l) * 0.3 and lower_shadow > body * 2 and upper_shadow < body:
            hammers.append(df.index[i])
    return hammers

def detect_inverted_hammer(df):
    patterns = []
    for i in range(1, len(df)):
        o, h, l, c = df.iloc[i][["Open", "High", "Low", "Close"]]
        body = abs(c - o)
        lower_shadow = o - l if c >= o else c - l
        upper_shadow = h - c if c >= o else h - o
        if body < (h - l) * 0.3 and upper_shadow > body * 2 and lower_shadow < body:
            patterns.append(df.index[i])
    return patterns

def detect_bullish_engulfing(df):
    engulfs = []
    for i in range(1, len(df)):
        o1, c1 = df.iloc[i-1][["Open", "Close"]]
        o2, c2 = df.iloc[i][["Open", "Close"]]
        if c1 < o1 and c2 > o2 and c2 >= o1 and o2 <= c1:
            engulfs.append(df.index[i])
    return engulfs

def detect_bearish_engulfing(df):
    engulfs = []
    for i in range(1, len(df)):
        o1, c1 = df.iloc[i-1][["Open", "Close"]]
        o2, c2 = df.iloc[i][["Open", "Close"]]
        if c1 > o1 and c2 < o2 and c2 <= o1 and o2 >= c1:
            engulfs.append(df.index[i])
    return engulfs

# --------------------------------------
# Breakout patterns
# --------------------------------------
def find_pivots(series, window=5):
    """
    Finds local peaks (highs) and troughs (lows).
    Returns two series: highs and lows, with NaN where not a pivot.
    """
    rollup = series.rolling(window, center=True)
    maxs = rollup.max()
    mins = rollup.min()
    
    is_max = series == maxs
    is_min = series == mins
    
    return is_max, is_min

def detect_head_and_shoulders(df):
    # Bearish Reversal Pattern
    patterns = []
    if len(df) < 50: return patterns
    
    # Simple logic using 3 peaks
    # Left Shoulder < Head > Right Shoulder
    # Check last 60 days
    subset = df.iloc[-60:]
    highs = subset["High"]
    
    # Get local maxima with window 5
    is_peak, _ = find_pivots(highs, window=5)
    peaks = subset[is_peak]
    
    if len(peaks) >= 3:
        # Check last 3 peaks
        p1, p2, p3 = peaks.iloc[-3]["High"], peaks.iloc[-2]["High"], peaks.iloc[-1]["High"]
        d1, d2, d3 = peaks.index[-3], peaks.index[-2], peaks.index[-1]
        
        # Head (p2) must be highest
        # Shoulders (p1, p3) roughly equal lower than head
        if p2 > p1 and p2 > p3:
            # Check shoulder symmetry (within 10%)
            if abs(p1 - p3) / p1 < 0.1:
               patterns.append(d3) # Mark the completion (Right Shoulder)
               
    return patterns

def detect_inverse_head_and_shoulders(df):
    # Bullish Reversal Pattern
    patterns = []
    if len(df) < 50: return patterns
    
    subset = df.iloc[-60:]
    lows = subset["Low"]
    
    _, is_trough = find_pivots(lows, window=5)
    troughs = subset[is_trough]
    
    if len(troughs) >= 3:
        t1, t2, t3 = troughs.iloc[-3]["Low"], troughs.iloc[-2]["Low"], troughs.iloc[-1]["Low"]
        d3 = troughs.index[-1]
        
        # Head (t2) lowest
        if t2 < t1 and t2 < t3:
             if abs(t1 - t3) / t1 < 0.1:
                 patterns.append(d3)
                 
    return patterns

def detect_cup_and_handle(df):
    # Bullish Continuation
    if len(df) < 50: return []
    
    # Rough approximation: U-shape followed by small drop
    # We look for price being near 50-day high after a U-recovery
    current_close = df["Close"].iloc[-1]
    high_50 = df["High"].tail(50).max()
    
    if current_close >= high_50 * 0.95:
        # Check if we were low recently (the cup bottom)
        min_50 = df["Low"].tail(50).min()
        if min_50 < high_50 * 0.8:
            # Simple check passed
            return [df.index[-1]]
    return []

def detect_double_top(df):
    patterns = []
    if len(df) < 40: return patterns
    
    subset = df.iloc[-40:]
    is_peak, _ = find_pivots(subset["High"], window=5)
    peaks = subset[is_peak]
    
    if len(peaks) >= 2:
        p1 = peaks.iloc[-2]["High"]
        p2 = peaks.iloc[-1]["High"]
        d2 = peaks.index[-1]
        
        # Peaks roughly equal
        if abs(p1 - p2) / p1 < 0.03: # 3% tolerance
            patterns.append(d2)
            
    return patterns

def detect_double_bottom(df):
    patterns = []
    if len(df) < 40: return patterns
    
    subset = df.iloc[-40:]
    _, is_trough = find_pivots(subset["Low"], window=5)
    troughs = subset[is_trough]
    
    if len(troughs) >= 2:
        t1 = troughs.iloc[-2]["Low"]
        t2 = troughs.iloc[-1]["Low"]
        d2 = troughs.index[-1]
        
        # Troughs roughly equal
        if abs(t1 - t2) / t1 < 0.03:
             patterns.append(d2)
             
    return patterns

def detect_triangle_breakout(df):
    # Generic triangle consolidation
    return []

def detect_ascending_triangle(df):
    # Flat top, higher lows
    if len(df) < 30: return []
    
    subset = df.iloc[-30:]
    is_peak, is_trough = find_pivots(subset["Close"], window=3)
    
    peaks = subset[is_peak]
    troughs = subset[is_trough]
    
    if len(peaks) >= 2 and len(troughs) >= 2:
        last_peaks = peaks["Close"].tail(3)
        last_troughs = troughs["Close"].tail(3)
        
        # Check flat top (low variance in peaks)
        peak_var = last_peaks.std() / last_peaks.mean()
        
        # Check ascending lows (slope > 0)
        # Simple Logic: last trough > previous trough
        ascending = True
        for i in range(1, len(last_troughs)):
            if last_troughs.iloc[i] <= last_troughs.iloc[i-1]:
                ascending = False
        
        if peak_var < 0.02 and ascending:
            return [df.index[-1]]
            
    return []

def detect_descending_triangle(df):
    # Flat bottom, lower highs
    if len(df) < 30: return []
    
    subset = df.iloc[-30:]
    is_peak, is_trough = find_pivots(subset["Close"], window=3)
    
    peaks = subset[is_peak]
    troughs = subset[is_trough]
    
    if len(peaks) >= 2 and len(troughs) >= 2:
        last_peaks = peaks["Close"].tail(3)
        last_troughs = troughs["Close"].tail(3)
        
        # Check flat bottom (low variance in troughs)
        trough_var = last_troughs.std() / last_troughs.mean()
        
        # Check descending highs
        descending = True
        for i in range(1, len(last_peaks)):
            if last_peaks.iloc[i] >= last_peaks.iloc[i-1]:
                descending = False
                
        if trough_var < 0.02 and descending:
            return [df.index[-1]]
            
    return []

def detect_symmetrical_triangle(df):
    # Lower highs AND higher lows
    if len(df) < 30: return []
    
    subset = df.iloc[-30:]
    is_peak, is_trough = find_pivots(subset["Close"], window=3)
    
    last_peaks = subset[is_peak]["Close"].tail(3)
    last_troughs = subset[is_trough]["Close"].tail(3)
    
    if len(last_peaks) < 2 or len(last_troughs) < 2: return []

    descending_highs = True
    for i in range(1, len(last_peaks)):
        if last_peaks.iloc[i] >= last_peaks.iloc[i-1]: descending_highs = False
        
    ascending_lows = True
    for i in range(1, len(last_troughs)):
         if last_troughs.iloc[i] <= last_troughs.iloc[i-1]: ascending_lows = False
         
    if descending_highs and ascending_lows:
        return [df.index[-1]]
        
    return []

# --------------------------------------
# Pattern detection map
# --------------------------------------
PATTERN_FUNCTIONS = {
    "hammer": detect_hammer,
    "inverted_hammer": detect_inverted_hammer,
    "bullish_engulfing": detect_bullish_engulfing,
    "bearish_engulfing": detect_bearish_engulfing,
    
    "head_and_shoulders": detect_head_and_shoulders,
    "inverse_head_and_shoulders": detect_inverse_head_and_shoulders,
    "cup_and_handle": detect_cup_and_handle,
    "double_top": detect_double_top,
    "double_bottom": detect_double_bottom,
    "ascending_triangle": detect_ascending_triangle,
    "descending_triangle": detect_descending_triangle,
    "symmetrical_triangle": detect_symmetrical_triangle,
}

# --------------------------------------
# Trendlines & Support/Resistance
# --------------------------------------
def detect_support_resistance(df, window=5):
    """
    Identifies Support and Resistance levels based on pivot points.
    Returns a list of price levels.
    """
    if len(df) < 50: return []
    
    # Use find_pivots from earlier
    highs = df["High"]
    lows = df["Low"]
    
    is_peak, _ = find_pivots(highs, window)
    _, is_trough = find_pivots(lows, window)
    
    peaks = highs[is_peak].tolist()
    troughs = lows[is_trough].tolist()
    
    levels = peaks + troughs
    # Simple clustering: If levels are within 1.5% of each other, merge them (take mean)
    levels.sort()
    
    merged_levels = []
    if not levels: return []
    
    current_group = [levels[0]]
    
    for i in range(1, len(levels)):
        if levels[i] <= current_group[0] * 1.015: # 1.5% tolerance
            current_group.append(levels[i])
        else:
            merged_levels.append(sum(current_group) / len(current_group))
            current_group = [levels[i]]
    merged_levels.append(sum(current_group) / len(current_group))
    
    # Filter to only keep levels clearly near current price (e.g. within 15% to avoid clutter)
    current_price = df["Close"].iloc[-1]
    relevant_levels = [l for l in merged_levels if 0.85 * current_price <= l <= 1.15 * current_price]
    
    # Limit to top 5 strongest (most touches - here we just simulated average, 
    # but for simplicity we take a subset to avoid chart spam)
    return relevant_levels[:5]

def detect_trendlines(df):
    """
    Connects recent major highs (Resist Trend) and lows (Support Trend).
    Returns a list of tuples: [(start_date, start_price), (end_date, end_price)]
    """
    # Simply draw lines connecting the last two major pivots
    tlines = []
    if len(df) < 60: return tlines
    
    # Uptrend Support Line (Higher Lows)
    # Find last 3 major lows in last 60 periods
    is_peak, is_trough = find_pivots(df["Low"], window=10)
    # Get last 3 True indices
    trough_mask = is_trough.iloc[-60:]
    trough_indices = df.index[-60:][trough_mask]
    
    if len(trough_indices) >= 2:
        # Get values
        t1_idx = trough_indices[-2]
        t2_idx = trough_indices[-1]
        t1_val = float(df.at[t1_idx, "Low"])
        t2_val = float(df.at[t2_idx, "Low"])
        
        # Check if ascending
        if t2_val > t1_val:
             tlines.append([(t1_idx, t1_val), (t2_idx, t2_val)])

    # Downtrend Resistance Line (Lower Highs)
    is_peak, _ = find_pivots(df["High"], window=10)
    peak_mask = is_peak.iloc[-60:]
    peak_indices = df.index[-60:][peak_mask]

    if len(peak_indices) >= 2:
        p1_idx = peak_indices[-2]
        p2_idx = peak_indices[-1]
        p1_val = float(df.at[p1_idx, "High"])
        p2_val = float(df.at[p2_idx, "High"])
        
        # Check if descending
        if p2_val < p1_val:
            tlines.append([(p1_idx, p1_val), (p2_idx, p2_val)])
            
    return tlines

# --------------------------------------
# Chart with patterns
# --------------------------------------
def generate_pattern_chart(df, patterns):
    pattern_indices = {}
    for p in patterns:
        if p in PATTERN_FUNCTIONS:
            pattern_indices[p] = PATTERN_FUNCTIONS[p](df)

    # Detect S/R and Trendlines
    sr_levels = detect_support_resistance(df)
    trend_data = detect_trendlines(df) # List of [(d1, p1), (d2, p2)]

    # Filter patterns to only show RECENT ones (last 30 candles) to reduce clutter & focus on current price action
    # The user specifically asked to "Show relevant chart patterns that will determine target price"
    filtered_pattern_indices = {}
    cutoff_date = df.index[-30] if len(df) > 30 else df.index[0]

    for p, idxs in pattern_indices.items():
        # Keep only indices >= cutoff_date
        recent = [d for d in idxs if d >= cutoff_date]
        if recent:
            filtered_pattern_indices[p] = recent

    # Prepare MPF arguments
    plot_kwargs = {}
    
    # S/R Lines (Horizontal)
    if sr_levels:
        plot_kwargs['hlines'] = dict(hlines=sr_levels, colors=['gray']*len(sr_levels), linestyle='-.', linewidths=0.8, alpha=0.5)

    # Trendlines (Use alines for arbitrary disconnected lines)
    if trend_data:
        plot_kwargs['alines'] = dict(alines=trend_data, colors='blue', linewidths=1.5, alpha=0.7)

    fig, axlist = mpf.plot(
        df, type="candle", style="yahoo",
        show_nontrading=True, returnfig=True, figsize=(12, 6),
        **plot_kwargs
    )
    ax = axlist[0]

    colors = {
        "hammer": "green",
        "inverted_hammer": "green",
        "bullish_engulfing": "lime",
        "bearish_engulfing": "red",
        "head_and_shoulders": "red",
        "inverse_head_and_shoulders": "green",
        "cup_and_handle": "gold",
        "double_top": "darkred",
        "double_bottom": "darkgreen",
        "ascending_triangle": "cyan",
        "descending_triangle": "magenta",
        "symmetrical_triangle": "blue",
    }

    # Use filtered_pattern_indices for plotting
    for p, idxs in filtered_pattern_indices.items():
        if not idxs:
            continue
        for dt in idxs:
            if dt not in df.index:
                continue
            price = df.at[dt, "Close"]
            ax.plot([dt], [price], marker="*", color=colors.get(p, "black"), markersize=14)
            ax.text(
                dt, price * 1.02,
                p.replace("_", " ").title(),
                fontsize=9, color=colors.get(p, "black"),
                ha="center", va="bottom",
                bbox=dict(facecolor="white", alpha=0.6, edgecolor="none")
            )
            
    # Add Legend or Annotation for S/R
    # Since S/R lines are auto-drawn, we just leave them as dashed gray lines
    
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    img = Image.open(buf)
    return img, pattern_indices, sr_levels, trend_data 

# --------------------------------------
# Indicator Summary
# --------------------------------------
def compute_rs_rating_and_weekly(symbol, df_daily):
    alerts = []
    try:
        df_weekly = yf.download(symbol, period="2y", interval="1wk", progress=False)
        if not df_weekly.empty:
            df_weekly.columns = [col[0] if isinstance(col, tuple) else col for col in df_weekly.columns]
            df_weekly["EMA_Weekly"] = df_weekly["Close"].ewm(span=10, adjust=False).mean()
            last_weekly_close = df_weekly["Close"].iloc[-1]
            last_weekly_ema = df_weekly["EMA_Weekly"].iloc[-1]
            alerts.append(f"EMA Weekly (10-Wk): {last_weekly_ema:.2f}")
            
            if len(df_weekly) >= 10:
                past_high = df_weekly["High"].iloc[-10:-1].max()
                if last_weekly_close > past_high:
                    alerts.append(f"Weekly Break Out: Yes (Crossed {past_high:.2f})")
                else:
                    alerts.append(f"Weekly Break Out: No (Resistance at {past_high:.2f})")
    except Exception:
        pass

    try:
        nifty = yf.download("^NSEI", period="1y", interval="1d", progress=False)
        if not nifty.empty and not df_daily.empty and len(df_daily) >= 200:
            nifty.columns = [col[0] if isinstance(col, tuple) else col for col in nifty.columns]
            stock_ret = (df_daily["Close"].iloc[-1] - df_daily["Close"].iloc[-200]) / df_daily["Close"].iloc[-200]
            nifty_ret = (nifty["Close"].iloc[-1] - nifty["Close"].iloc[-200]) / nifty["Close"].iloc[-200]
            diff = stock_ret - nifty_ret
            # Proxy RS rating
            rs_rating = min(99, max(1, int(50 + (diff * 100))))
            alerts.append(f"RS Rating: {rs_rating}")
        else:
            alerts.append("RS Rating: N/A")
    except Exception:
        alerts.append("RS Rating: N/A")
        
    return alerts

def get_stock_fundamentals_and_news(symbol):
    fundamentals = {
        "Market Cap": "N/A",
        "Trailing P/E": "N/A",
        "Forward P/E": "N/A",
        "Price to Book (P/B)": "N/A",
        "Dividend Yield": "N/A",
        "Debt to Equity": "N/A"
    }
    recent_news = []
    recent_actions = []

    try:
        import requests
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.1.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://finance.yahoo.com/",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        })
        
        stock = yf.Ticker(symbol, session=session)
        
        # 1. Fundamentals
        try:
            # Pre-warm Step: Fetch a small amount of history to "wake up" the session cookies
            stock.history(period="1d") 
            
            info = stock.info
            # Fallback for Indian tickers: If info is empty, try to get basic data from chart metadata
            if not info or len(info) < 5:
                try:
                    import json
                    import urllib.request
                    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?range=1d&interval=1d"
                    req = urllib.request.Request(url, headers=session.headers)
                    with urllib.request.urlopen(req, timeout=5) as response:
                        res_data = json.loads(response.read().decode())['chart']['result'][0]['meta']
                        # Map what we can from metadata
                        info = {
                            "marketCap": res_data.get("marketCap", info.get("marketCap", "N/A")),
                            "trailingPE": res_data.get("trailingPE", info.get("trailingPE", "N/A")),
                            "forwardPE": res_data.get("forwardPE", info.get("forwardPE", "N/A")),
                            "regularMarketPrice": res_data.get("regularMarketPrice", info.get("regularMarketPrice", "N/A")),
                            "currency": res_data.get("currency", "INR")
                        }
                except:
                    pass

            if info:
                fundamentals = {
                    "Market Cap": info.get("marketCap", "N/A"),
                    "Trailing P/E": info.get("trailingPE", "N/A"),
                    "Forward P/E": info.get("forwardPE", "N/A"),
                    "Price to Book (P/B)": info.get("priceToBook", "N/A"),
                    "Dividend Yield": info.get("dividendYield", "N/A"),
                    "Debt to Equity": info.get("debtToEquity", "N/A")
                }
        except Exception as e:
            print(f"Fundamentals fetch failed: {e}")

        # 2. News (Google News fallback)
        try:
            import urllib.request
            import urllib.parse
            import xml.etree.ElementTree as ET
            from contextlib import closing
            
            clean_name = symbol.replace('.NS', '').replace('.BO', '')
            query = urllib.parse.quote(f"{clean_name} stock news India")
            url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
            
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with closing(urllib.request.urlopen(req, timeout=5)) as response:
                xml_data = response.read()
            
            root = ET.fromstring(xml_data)
            items = root.findall('.//item')
            for item in items[:5]:
                title_elem = item.find('title')
                link_elem = item.find('link')
                pub_elem = item.find('pubDate')
                
                title = title_elem.text if title_elem is not None else "No Title"
                link = link_elem.text if link_elem is not None else "#"
                pubDate = pub_elem.text if pub_elem is not None else ""
                
                if '-' in title:
                    title = "-".join(title.split('-')[:-1]).strip()
                    
                date_str = pubDate[:16] if pubDate else ""
                recent_news.append(f"- [{title}]({link}) ({date_str})")
        except Exception as e:
            recent_news.append(f"⚠️ Could not fetch recent news: {e}")
                
        # 3. Actions
        try:
            actions = stock.get_actions()
            if actions is not None and not actions.empty:
                last_actions = actions.tail(5)
                for date, row in last_actions.iterrows():
                    action_desc = []
                    if row.get("Dividends", 0) > 0:
                        action_desc.append(f"Dividend: {row['Dividends']}")
                    if row.get("Stock Splits", 0) > 0:
                        action_desc.append(f"Split: {row['Stock Splits']}")
                    if action_desc:
                        recent_actions.append(f"- {date.date()}: " + " | ".join(action_desc))
        except Exception as e:
            pass

    except Exception as e:
        print(f"Overall stock init failed: {e}")

    return fundamentals, recent_news, recent_actions

def calculate_indicators(df, symbol=None):
    signals = []
    current = df.iloc[-1]
    
    signals.append(f"Current Price: {current['Close']:.2f}")
    signals.append(f"Volume: {current['Volume']:,.0f}")
    
    # MA Crossovers
    if current["SMA20"] > current["SMA50"]:
        signals.append("Bullish: SMA20 > SMA50")
    else:
        signals.append("Bearish: SMA20 < SMA50")
        
    signals.append(f"EMA Daily (20-D): {current['EMA20']:.2f}")
    signals.append(f"EMA Daily (50-D): {current['EMA50']:.2f}")
    
    if current["EMA20"] > current["EMA50"]:
        signals.append("Bullish: EMA20 > EMA50")
    
    # RSI
    signals.append(f"RSI: {current['RSI']:.2f}")
    if current["RSI"] > 70:
        signals.append(f"Overbought (RSI: {current['RSI']:.2f})")
    elif current["RSI"] < 30:
        signals.append(f"Oversold (RSI: {current['RSI']:.2f})")
    else:
        signals.append(f"Neutral RSI ({current['RSI']:.2f})")
        
    # MACD
    if current["MACD"] > current["Signal"]:
        signals.append("Bullish: MACD > Signal Line")
    else:
        signals.append("Bearish: MACD < Signal Line")
        
    # Stochastic
    if current["%K"] > 80:
        signals.append("Overbought Stochastic (>80)")
    elif current["%K"] < 20:
        signals.append("Oversold Stochastic (<20)")
        
    # Bollinger Bands
    if current["Close"] > current["BB_Upper"]:
        signals.append("Price above Upper Bollinger Band")
    elif current["Close"] < current["BB_Lower"]:
        signals.append("Price below Lower Bollinger Band")
        
    if symbol:
        signals.extend(compute_rs_rating_and_weekly(symbol, df))
        
    return signals

# --------------------------------------
# Target price calculation
# --------------------------------------
def calculate_target_price(df, pattern_indices, sr_levels):
    targets = []
    last_close = df["Close"].iloc[-1]
    
    # S/R Targets
    # Next Resistance = Lowest S/R level above price
    resistances = [l for l in sr_levels if l > last_close * 1.01]
    if resistances:
         targets.append(f"Approaching Resistance Level: {min(resistances):.2f}")
         
    # Next Support = Highest S/R level below price
    supports = [l for l in sr_levels if l < last_close * 0.99]
    if supports:
         targets.append(f"Approaching Support Level: {max(supports):.2f}")

    # Simple ATR based targets for basic patterns
    atr = df["ATR"].iloc[-1]
    
    # Iterate through detected patterns at the *latest* candlestick
    latest_date = df.index[-1]
    
    detected_on_last_candle = []
    for p, idxs in pattern_indices.items():
        # Check if detected recently (last 3 days)
        recent_idxs = [d for d in idxs if d >= df.index[-3]]
        if recent_idxs:
            detected_on_last_candle.append(p)
            
    for p in detected_on_last_candle:
        if "bullish" in p or p == "hammer" or p == "inverted_hammer" or p == "double_bottom" or p== "cup_and_handle" or p == "inverse_head_and_shoulders":
            target = last_close + (2 * atr)
            stop_loss = last_close - (1 * atr)
            targets.append(f"Pattern '{p}': Target {target:.2f}, Stop Loss {stop_loss:.2f}")
        elif "bearish" in p or p == "double_top" or p == "head_and_shoulders":
            target = last_close - (2 * atr)
            stop_loss = last_close + (1 * atr)
            targets.append(f"Pattern '{p}': Target {target:.2f}, Stop Loss {stop_loss:.2f}")

    if not targets:
        # Fallback trend following target
        if df["SMA20"].iloc[-1] > df["SMA50"].iloc[-1]:
             targets.append(f"Trend Bullish: ST Target {last_close + atr:.2f}")
        else:
             targets.append(f"Trend Bearish: ST Target {last_close - atr:.2f}")

    return targets

# --------------------------------------
# Main function
# --------------------------------------
def get_chart_with_patterns_and_indicators(stock_name_or_symbol, patterns=None,
                                           period="6mo", interval="1d"):
    symbol = resolve_symbol(stock_name_or_symbol)
    df = fetch_stock_data(symbol, period=period, interval=interval)
    df = df.sort_index()
    # remove duplicates
    df = df[~df.index.duplicated(keep="last")]

    if len(df) < 50:
        raise ValueError("Not enough data to calculate advanced indicators (need >50 candles)")

    if patterns is None:
        patterns = list(PATTERN_FUNCTIONS.keys())

    # Add indicators first so we can use them if needed
    df = add_indicators(df)

    img, indices, sr_levels, trends = generate_pattern_chart(df, patterns)

    summary = []
    # Only list patterns detected in the last 3 candles to be relevant
    recent_patterns = []
    for p, idxs in indices.items():
        if not idxs: continue
        # filters dates within last 5 periods
        recent_dates = [d for d in idxs if d >= df.index[-5]]
        if recent_dates:
             recent_patterns.append(f"{p} detected on {[str(d.date()) for d in recent_dates]}")

    if recent_patterns:
        summary.append("🔎 RECENT PATTERNS:")
        summary.extend(recent_patterns)
    else:
        summary.append("🔎 No recent patterns detected.")
    
    if sr_levels:
        summary.append(f"\n🧱 Key Level (S/R): {[f'{x:.1f}' for x in sr_levels]}")
        
    if trends:
        summary.append(f"\n📈 Trendlines Detected: {len(trends)}")

    summary.append("\n📊 INDICATOR SIGNALS:")
    summary.extend(calculate_indicators(df, symbol=symbol))
    
    summary.append("\n🎯 TARGETS (ATR & S/R Based):")
    summary.extend(calculate_target_price(df, indices, sr_levels))

    fund_dict, news_list, actions_list = get_stock_fundamentals_and_news(symbol)

    return img, "\n".join(summary), fund_dict, news_list, actions_list
# Force upload 1