import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple

class TechnicalEngine:
    """
    Computes technical indicators, chart patterns, support/resistance, Fibonacci levels,
    and a multi-indicator composite score.
    """

    @staticmethod
    def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """
        Computes all standard indicators directly on OHLCV DataFrame using vectorized pandas/numpy.
        """
        if df.empty or len(df) < 20:
            return df

        df = df.copy()
        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]

        # 1. Moving Averages
        df["SMA20"] = close.rolling(window=20).mean()
        df["SMA50"] = close.rolling(window=50).mean()
        df["SMA100"] = close.rolling(window=100).mean()
        df["SMA200"] = close.rolling(window=200).mean()

        df["EMA20"] = close.ewm(span=20, adjust=False).mean()
        df["EMA50"] = close.ewm(span=50, adjust=False).mean()
        df["EMA200"] = close.ewm(span=200, adjust=False).mean()

        # 2. RSI (14)
        delta = close.diff()
        gain = np.where(delta > 0, delta, 0.0)
        loss = np.where(delta < 0, -delta, 0.0)
        avg_gain = pd.Series(gain, index=df.index).rolling(window=14).mean()
        avg_loss = pd.Series(loss, index=df.index).rolling(window=14).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df["RSI"] = (100 - (100 / (1 + rs))).fillna(50.0)

        # 3. MACD (12, 26, 9)
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        df["MACD"] = ema12 - ema26
        df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
        df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

        # 4. Bollinger Bands (20, 2)
        std20 = close.rolling(window=20).std()
        df["BB_Middle"] = df["SMA20"]
        df["BB_Upper"] = df["BB_Middle"] + (2 * std20)
        df["BB_Lower"] = df["BB_Middle"] - (2 * std20)
        df["BB_Width"] = ((df["BB_Upper"] - df["BB_Lower"]) / df["BB_Middle"]) * 100

        # 5. ATR (14)
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["ATR"] = tr.rolling(window=14).mean()

        # 6. Stochastic Oscillator (14, 3, 3)
        low14 = low.rolling(window=14).min()
        high14 = high.rolling(window=14).max()
        df["Stoch_K"] = (((close - low14) / (high14 - low14).replace(0, np.nan)) * 100).fillna(50.0)
        df["Stoch_D"] = df["Stoch_K"].rolling(window=3).mean().fillna(50.0)

        # 7. Volume SMA (20) & OBV
        df["Volume_SMA20"] = volume.rolling(window=20).mean()
        obv = np.where(close > close.shift(1), volume, np.where(close < close.shift(1), -volume, 0.0))
        df["OBV"] = pd.Series(obv, index=df.index).cumsum()

        # 8. VWAP
        typical_price = (high + low + close) / 3
        df["VWAP"] = (typical_price * volume).cumsum() / volume.cumsum().replace(0, np.nan)

        return df

    @staticmethod
    def detect_support_resistance(df: pd.DataFrame, n_levels: int = 5) -> List[float]:
        """
        Detects significant horizontal Support and Resistance levels.
        """
        if df.empty or len(df) < 30:
            return []

        levels = []
        highs = df["High"].values
        lows = df["Low"].values

        # Local extrema detection
        for i in range(5, len(df) - 5):
            # Swing High
            if highs[i] == max(highs[i-5:i+6]):
                levels.append(float(highs[i]))
            # Swing Low
            if lows[i] == min(lows[i-5:i+6]):
                levels.append(float(lows[i]))

        if not levels:
            return []

        # Cluster levels within 1.5% distance
        levels.sort()
        clustered = []
        current_cluster = [levels[0]]

        for l in levels[1:]:
            if (l - current_cluster[-1]) / current_cluster[-1] < 0.018:
                current_cluster.append(l)
            else:
                clustered.append(float(np.mean(current_cluster)))
                current_cluster = [l]
        if current_cluster:
            clustered.append(float(np.mean(current_cluster)))

        current_price = float(df["Close"].iloc[-1])
        # Sort by proximity to current price
        clustered.sort(key=lambda x: abs(x - current_price))
        return [round(x, 2) for x in clustered[:n_levels]]

    @staticmethod
    def calculate_fibonacci_levels(df: pd.DataFrame) -> Dict[str, float]:
        """
        Calculates key Fibonacci retracement levels from the 6-month high and low.
        """
        if df.empty or len(df) < 30:
            return {}

        period_df = df.tail(126) # ~6 months
        high = float(period_df["High"].max())
        low = float(period_df["Low"].min())
        diff = high - low

        return {
            "0.0% (Swing Low)": round(low, 2),
            "23.6%": round(low + 0.236 * diff, 2),
            "38.2%": round(low + 0.382 * diff, 2),
            "50.0%": round(low + 0.500 * diff, 2),
            "61.8% (Golden Pocket)": round(low + 0.618 * diff, 2),
            "78.6%": round(low + 0.786 * diff, 2),
            "100.0% (Swing High)": round(high, 2)
        }

    @staticmethod
    def detect_patterns(df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Detects candlestick patterns on the most recent bars.
        """
        if df.empty or len(df) < 5:
            return []

        patterns = []
        last = df.iloc[-1]
        prev = df.iloc[-2]

        c = last["Close"]
        o = last["Open"]
        h = last["High"]
        l = last["Low"]
        body = abs(c - o)
        total_range = h - l if (h - l) > 0 else 0.001

        # 1. Hammer / Inverted Hammer
        lower_shadow = min(o, c) - l
        upper_shadow = h - max(o, c)
        if lower_shadow > 2.0 * body and upper_shadow < body * 0.5 and (body / total_range) < 0.4:
            patterns.append({
                "pattern": "Hammer",
                "type": "Bullish Reversal",
                "description": "Long lower shadow indicates strong intraday buying support and rejection of lower prices."
            })
        elif upper_shadow > 2.0 * body and lower_shadow < body * 0.5 and (body / total_range) < 0.4:
            patterns.append({
                "pattern": "Inverted Hammer",
                "type": "Bullish Potential",
                "description": "Buyers tested higher prices; potential reversal if confirmed by follow-through volume."
            })

        # 2. Bullish Engulfing
        if prev["Close"] < prev["Open"] and c > o and c >= prev["Open"] and o <= prev["Close"]:
            patterns.append({
                "pattern": "Bullish Engulfing",
                "type": "Bullish Reversal",
                "description": "Current green candle completely engulfs previous red candle body."
            })

        # 3. Bearish Engulfing
        if prev["Close"] > prev["Open"] and c < o and c <= prev["Open"] and o >= prev["Close"]:
            patterns.append({
                "pattern": "Bearish Engulfing",
                "type": "Bearish Reversal",
                "description": "Current red candle completely engulfs previous green candle body."
            })

        # 4. Doji
        if (body / total_range) < 0.10:
            patterns.append({
                "pattern": "Doji",
                "type": "Neutral / Indecision",
                "description": "Opening and closing prices are virtually equal, signaling market indecision."
            })

        return patterns

    @staticmethod
    def analyze(df: pd.DataFrame) -> Dict[str, Any]:
        """
        Full technical analysis suite returning indicators, signals, S/R, Fibonacci,
        candlestick patterns, and composite rating.
        """
        if df.empty or len(df) < 20:
            return {"status": "error", "message": "Insufficient data"}

        df_ind = TechnicalEngine.add_indicators(df)
        last = df_ind.iloc[-1]
        prev = df_ind.iloc[-2] if len(df_ind) >= 2 else last

        cmp = float(last["Close"])
        rsi = float(last.get("RSI", 50.0))
        macd = float(last.get("MACD", 0.0))
        macd_signal = float(last.get("MACD_Signal", 0.0))
        macd_hist = float(last.get("MACD_Hist", 0.0))
        atr = float(last.get("ATR", cmp * 0.02))
        vol = float(last.get("Volume", 0.0))
        vol_sma20 = float(last.get("Volume_SMA20", vol))
        stoch_k = float(last.get("Stoch_K", 50.0))
        stoch_d = float(last.get("Stoch_D", 50.0))

        sma20 = float(last.get("SMA20", cmp))
        sma50 = float(last.get("SMA50", cmp))
        sma100 = float(last.get("SMA100", cmp))
        sma200 = float(last.get("SMA200", cmp))
        ema20 = float(last.get("EMA20", cmp))
        ema50 = float(last.get("EMA50", cmp))

        bb_upper = float(last.get("BB_Upper", cmp * 1.05))
        bb_lower = float(last.get("BB_Lower", cmp * 0.95))
        bb_middle = float(last.get("BB_Middle", cmp))

        # Signals & Scoring
        score = 50.0
        signals = []

        # Trend & Moving Averages
        if cmp > sma200:
            score += 15
            signals.append({"name": "Price > 200 DMA", "type": "Bullish", "weight": "+15", "desc": f"Trading above long-term 200 DMA (₹{sma200:.2f})"})
        else:
            score -= 15
            signals.append({"name": "Price < 200 DMA", "type": "Bearish", "weight": "-15", "desc": f"Trading below long-term 200 DMA (₹{sma200:.2f})"})

        if sma50 > sma200:
            score += 10
            signals.append({"name": "Golden Cross Alignment", "type": "Bullish", "weight": "+10", "desc": "50 DMA above 200 DMA confirming primary uptrend"})
        else:
            score -= 10
            signals.append({"name": "Death Cross Alignment", "type": "Bearish", "weight": "-10", "desc": "50 DMA below 200 DMA indicating long-term correction"})

        if cmp > sma20 > sma50:
            score += 10
            signals.append({"name": "Short-Term Momentum", "type": "Bullish", "weight": "+10", "desc": "Price above 20 & 50 DMA stacked in bullish order"})

        # Momentum (RSI)
        if 45 <= rsi <= 65:
            score += 5
            signals.append({"name": "Healthy RSI", "type": "Bullish", "weight": "+5", "desc": f"RSI at {rsi:.1f} in strong momentum zone"})
        elif rsi < 35:
            score += 8
            signals.append({"name": "Oversold RSI", "type": "Bullish Reversal", "weight": "+8", "desc": f"RSI at {rsi:.1f} in oversold territory"})
        elif rsi > 70:
            score -= 8
            signals.append({"name": "Overbought RSI", "type": "Bearish Warning", "weight": "-8", "desc": f"RSI at {rsi:.1f} in overbought zone"})

        # MACD
        if macd > macd_signal and prev.get("MACD", 0) <= prev.get("MACD_Signal", 0):
            score += 12
            signals.append({"name": "Fresh Bullish MACD Crossover", "type": "Bullish", "weight": "+12", "desc": "MACD line crossed above Signal line"})
        elif macd > macd_signal:
            score += 6
            signals.append({"name": "Bullish MACD Momentum", "type": "Bullish", "weight": "+6", "desc": "MACD above Signal line with positive momentum"})
        else:
            score -= 8
            signals.append({"name": "Bearish MACD Momentum", "type": "Bearish", "weight": "-8", "desc": "MACD below Signal line"})

        # Volume
        if vol > (vol_sma20 * 1.5):
            score += 8
            signals.append({"name": "High Volume Expansion", "type": "Bullish", "weight": "+8", "desc": f"Volume {vol/vol_sma20:.1f}x higher than 20-day average"})

        # Rating Normalization
        final_score = max(10, min(95, round(score)))
        if final_score >= 80:
            rating = "Strong Buy"
            rating_color = "emerald"
        elif final_score >= 65:
            rating = "Buy"
            rating_color = "green"
        elif final_score >= 45:
            rating = "Neutral"
            rating_color = "amber"
        elif final_score >= 30:
            rating = "Sell"
            rating_color = "rose"
        else:
            rating = "Strong Sell"
            rating_color = "red"

        # S/R & Fibonacci
        sr_levels = TechnicalEngine.detect_support_resistance(df)
        fib_levels = TechnicalEngine.calculate_fibonacci_levels(df)
        from app.services.technical_patterns import detect_all_patterns
        pattern_sets = detect_all_patterns(df)

        # Target & Stop Loss Calculation
        nearest_resistance = next((l for l in sorted(sr_levels) if l > cmp * 1.01), cmp + (2 * atr))
        nearest_support = next((l for l in sorted(sr_levels, reverse=True) if l < cmp * 0.99), cmp - (1.5 * atr))

        return {
            "current_price": cmp,
            "technical_score": final_score,
            "overall_rating": rating,
            "rating_color": rating_color,
            "indicators": {
                "rsi_14": round(rsi, 2),
                "macd": round(macd, 2),
                "macd_signal": round(macd_signal, 2),
                "macd_hist": round(macd_hist, 2),
                "atr_14": round(atr, 2),
                "stoch_k": round(stoch_k, 2),
                "stoch_d": round(stoch_d, 2),
                "sma_20": round(sma20, 2),
                "sma_50": round(sma50, 2),
                "sma_100": round(sma100, 2),
                "sma_200": round(sma200, 2),
                "ema_20": round(ema20, 2),
                "ema_50": round(ema50, 2),
                "bb_upper": round(bb_upper, 2),
                "bb_middle": round(bb_middle, 2),
                "bb_lower": round(bb_lower, 2),
                "volume": vol,
                "avg_volume_20d": vol_sma20
            },
            "signals": signals,
            "support_resistance_levels": sr_levels,
            "nearest_support": round(nearest_support, 2),
            "nearest_resistance": round(nearest_resistance, 2),
            "fibonacci_levels": fib_levels,
            "candlestick_patterns": pattern_sets["candlestick"],
            "chart_patterns": pattern_sets["chart"],
        }
