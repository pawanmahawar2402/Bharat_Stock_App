from dotenv import load_dotenv
from crew import stock_crew
import gradio as gr
import random, time
from charts.chart import get_chart_with_patterns_and_indicators, fetch_stock_data, add_indicators
# ---- Patch for Gradio 4.44.0 bug on HF Spaces (Safe for 5.x) ----
try:
    import gradio_client.utils as _gc_utils
    import yfinance as yf
    yf.set_tz_cache_location("/tmp/yfinance_cache")
    
    if hasattr(_gc_utils, "_json_schema_to_python_type"):
        _original_json_schema = _gc_utils._json_schema_to_python_type
        def _patched_json_schema(schema, defs=None):
            if not isinstance(schema, dict):
                return "any"
            return _original_json_schema(schema, defs)
        _gc_utils._json_schema_to_python_type = _patched_json_schema

    if hasattr(_gc_utils, "json_schema_to_python_type"):
        _original_json_schema_top = _gc_utils.json_schema_to_python_type
        def _patched_json_schema_top(schema):
            if not isinstance(schema, dict):
                return "any"
            return _original_json_schema_top(schema)
        _gc_utils.json_schema_to_python_type = _patched_json_schema_top
except Exception as e:
    print(f"Gradio patch skipped: {e}")
# ---- End patch ----

load_dotenv()

# -------------------------------
# Stock Mapping
# -------------------------------
import csv
import os

# -------------------------------
# Stock Mapping (Loaded from Yahoo Screener / CSV)
# -------------------------------
def load_all_stocks():
    # To avoid the 401 error on Hugging Face, we use a robust hardcoded list of major Indian stocks
    # This is much faster and bypasses Yahoo's screener blocking.
    mapping = {
        "Reliance Industries": "RELIANCE.NS",
        "TCS": "TCS.NS",
        "HDFC Bank": "HDFCBANK.NS",
        "Infosys": "INFY.NS",
        "ICICI Bank": "ICICIBANK.NS",
        "State Bank of India": "SBIN.NS",
        "Bharti Airtel": "BHARTIARTL.NS",
        "ITC": "ITC.NS",
        "Larsen & Toubro": "LT.NS",
        "Kotak Mahindra Bank": "KOTAKBANK.NS",
        "Axis Bank": "AXISBANK.NS",
        "Adani Enterprises": "ADANIENT.NS",
        "Sun Pharmaceutical": "SUNPHARMA.NS",
        "Maruti Suzuki": "MARUTI.NS",
        "Tata Motors": "TATAMOTORS.NS",
        "Bajaj Finance": "BAJFINANCE.NS",
        "Hindustan Unilever": "HINDUNILVR.NS",
        "Mahindra & Mahindra": "M&M.NS",
        "Wipro": "WIPRO.NS",
        "NTPC": "NTPC.NS",
        "HCL Technologies": "HCLTECH.NS",
        "Power Grid": "POWERGRID.NS",
        "Asian Paints": "ASIANPAINT.NS",
        "Titan Company": "TITAN.NS",
        "Bajaj Finserv": "BAJAJFINSV.NS",
        "UltraTech Cement": "ULTRACEMCO.NS",
        "JSW Steel": "JSWSTEEL.NS",
        "Tata Steel": "TATASTEEL.NS",
        "Grasim Industries": "GRASIM.NS",
        "Hindalco": "HINDALCO.NS",
        "Bajaj Auto": "BAJAJ-AUTO.NS",
        "Nestle India": "NESTLEIND.NS",
        "Tech Mahindra": "TECHM.NS",
        "Coal India": "COALINDIA.NS",
        "Adani Ports": "ADANIPORTS.NS",
        "Britannia": "BRITANNIA.NS",
        "Eicher Motors": "EICHERMOT.NS",
        "Dr. Reddy's": "DRREDDY.NS",
        "Cipla": "CIPLA.NS",
        "Zomato": "ZOMATO.NS",
        "Aurobindo Pharma": "AUROPHARMA.NS",
        "Apollo Hospitals": "APOLLOHOSP.NS",
        "Bharat Petroleum": "BPCL.NS",
        "Oil & Natural Gas": "ONGC.NS",
        "Hero MotoCorp": "HEROMOTOCO.NS",
        "Varun Beverages": "VBL.NS",
        "DLF Limited": "DLF.NS",
        "Yes Bank": "YESBANK.NS",
        "Federal Bank": "FEDERALBANK.NS"
    }
    return mapping

STOCK_MAPPING = load_all_stocks()

# -------------------------------
# Pattern choices (updated with breakout patterns)
# -------------------------------
PATTERN_CHOICES = [
    "hammer",
    "inverted_hammer",
    "bullish_engulfing",
    "bearish_engulfing",
    "head_and_shoulders",
    "inverse_head_and_shoulders",
    "double_top",
    "double_bottom",
    "cup_and_handle",
    "ascending_triangle",
    "descending_triangle",
    "symmetrical_triangle"
]

# -------------------------------
# CrewAI Safe Run with retries
# -------------------------------
CACHE = {}

def safe_stock_crew_run(stock, patterns_context=None, technical_indicators=None, fundamentals_context=None, news_context=None, actions_context=None):
    # Create a unique key for caching that includes context
    cache_key = f"{stock}_{patterns_context}_{technical_indicators}"
    if cache_key in CACHE:
        return CACHE[cache_key]

    inputs = {
        "stock": stock,
        "patterns_context": patterns_context or "No specific patterns detected.",
        "technical_indicators_context": technical_indicators or "No specific indicators provided.",
        "fundamentals_context": fundamentals_context or "No fundamentals available.",
        "news_context": news_context or "No recent news.",
        "actions_context": actions_context or "No recent corporate actions."
    }

    retries = 3
    for attempt in range(retries):
        try:
            result = stock_crew.kickoff(inputs=inputs)
            CACHE[cache_key] = result
            return result
        except Exception as e:
            if "429" in str(e):
                import random, time
                wait_time = (2 ** attempt) + random.random()
                print(f"⚠️ Rate limit hit. Retrying in {wait_time:.2f} seconds...")
                time.sleep(wait_time)
            else:
                raise
    raise RuntimeError("❌ Failed after retries due to API rate limit.")

# -------------------------------
# Resolver
# -------------------------------
def resolve_symbol(stock_name_or_symbol) -> str:
    if stock_name_or_symbol is None:
        raise ValueError("Stock name cannot be None")
    
    # Handle list input from Gradio
    if isinstance(stock_name_or_symbol, list):
        stock_name_or_symbol = stock_name_or_symbol[0]
        
    query = str(stock_name_or_symbol).strip()
    if not query:
        raise ValueError("Empty stock name provided")

    # 1. Check if it's our composite format "Name | Ticker"
    if " | " in query:
        return query.split(" | ")[-1]
        
    query_lower = query.lower()

    # 2. Exact Match Check (Case-insensitive)
    for name, ticker in STOCK_MAPPING.items():
        if query_lower == name.lower() or query_lower == ticker.lower().replace(".ns", "").replace(".bo", ""):
            return ticker

    # 3. Fuzzy/Partial Match Check
    for name, ticker in STOCK_MAPPING.items():
        if query_lower in name.lower() or query_lower in ticker.lower():
            return ticker

    # 4. Dynamic Live Yahoo Finance Search for ANY missing NSE/BSE stock
    import urllib.request, urllib.parse, json
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(query)}&quotesCount=5&country=IN"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            quotes = data.get("quotes", [])
            for q in quotes:
                sym = q.get("symbol", "")
                if sym.endswith(".NS") or sym.endswith(".BO"):
                    return sym
    except Exception as e:
        print(f"Yahoo Search Fallback failed: {e}")

    # 5. Final Fallback: Assume it's a direct symbol
    symbol = query.upper().replace(" ", "")
    if "." not in symbol:
        symbol = f"{symbol}.NS"
        
    return symbol

# -------------------------------
# Query function
# -------------------------------
def query_stock(stock_name, period: str, interval: str):
    symbol = resolve_symbol(stock_name)

    # 1. Get Chart & Technicals FIRST (so we can pass findings to the Agent)
    try:
        chart_img, technical_summary, fund_dict, news_list, actions_list = get_chart_with_patterns_and_indicators(
            symbol, patterns=None, period=period, interval=interval
        )
    except Exception as e:
        return f"❌ Chart/Technical Error for '{stock_name}': {e}", None, None

    fund_str = "\n".join([f"- **{k}**: {v}" for k, v in fund_dict.items()]) if fund_dict else "N/A"
    news_str = "\n".join(news_list) if news_list else "No recent news."
    actions_str = "\n".join(actions_list) if actions_list else "No recent corporate actions."

    # 2. Run CrewAI Agent with Context
    try:
        # Pass the technical and fundamental contexts to the agent
        result = safe_stock_crew_run(
            stock=symbol, 
            patterns_context=technical_summary,
            technical_indicators=technical_summary,
            fundamentals_context=fund_str,
            news_context=news_str,
            actions_context=actions_str
        )
    except Exception as e:
        result = f"❌ CrewAI Error for '{stock_name}': {e}"

    # 3. Format Final Output
    final_report = f"""
# 🚀 AI Trade Analysis & Reasoning
**Stock**: {stock_name} ({symbol})

### 🏢 Company Fundamentals
{fund_str}

### 📰 Recent Announcements & News
{news_str}

### 📅 Corporate Actions
{actions_str}

---
### 🤖 AI Agent Report
{result}
"""

    return final_report, chart_img, technical_summary

# -------------------------------
# UI Utilities
# -------------------------------
def get_market_triggers():
    import yfinance as yf
    import urllib.request
    import urllib.parse
    import xml.etree.ElementTree as ET
    from contextlib import closing
    
    # 1. Fetch Global/Macro Indicators
    tickers = {
        "NIFTY 50": "^NSEI",
        "SENSEX": "^BSESN",
        "INDIA VIX": "^INDIAVIX",
        "Gold": "GC=F",
        "Crude Oil": "CL=F",
        "USD/INR": "INR=X"
    }
    
    nifty_val = "N/A"
    vix_val = "21.00" 
    vix_number = 21.0
    
    macro_table = []
    
    try:
        import json
        def raw_fetch(sym):
            try:
                url = f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
                with urllib.request.urlopen(req, timeout=3) as response:
                    res = json.loads(response.read().decode())['chart']['result'][0]
                    df = pd.DataFrame(res['indicators']['quote'][0])
                    df.index = pd.to_datetime(res['timestamp'], unit='s')
                    return df.dropna()
            except Exception:
                return pd.DataFrame()
                
        for name, ticker in tickers.items():
            df = raw_fetch(ticker)
            if not df.empty and "close" in df.columns:
                valid_closes = df["close"].dropna()
                if len(valid_closes) >= 2:
                    current = float(valid_closes.iloc[-1])
                    prev = float(valid_closes.iloc[-2])
                    change = ((current - prev) / prev) * 100
                    
                    if ticker == "^NSEI":
                        nifty_val = f"{current:,.0f}"
                    elif ticker == "^INDIAVIX":
                        vix_val = f"{current:.2f}"
                        vix_number = current
                        
                    # Logic for Impact text
                    if name in ["INDIA VIX", "Crude Oil", "USD/INR"]:
                        if change > 1.0:
                            impact = "🔴 Bearish for India (Rising)"
                        elif change < -1.0:
                            impact = "🟢 Bullish (Falling)"
                        else:
                            impact = "🟡 Neutral / Watch"
                    else:
                        if change > 0.5:
                            impact = "🟢 Positive momentum"
                        elif change < -0.5:
                            impact = "🔴 Bearish / Correction"
                        else:
                            impact = "🟡 Consolidation"
                            
                    macro_table.append(f"| **{name}** at {current:.2f} | {impact} |")
    except Exception:
        pass
        
    # 2. Fetch Daily Broad News via RSS
    try:
        query = urllib.parse.quote("Indian stock market economy news when:7d")
        url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with closing(urllib.request.urlopen(req, timeout=5)) as response:
            xml_data = response.read()
        
        root = ET.fromstring(xml_data)
        items = root.findall('.//item')
        
        for item in items[:4]:
            title = item.find('title')
            link = item.find('link')
            
            title_text = title.text if title is not None else "No Title"
            link_text = link.text if link is not None else "#"
            
            if '-' in title_text:
                title_text = "-".join(title_text.split('-')[:-1]).strip()
                
            # Heuristic impact determination based on keywords
            lower_title = title_text.lower()
            if any(w in lower_title for w in ["plunge", "fall", "crash", "bear", "selloff", "worry", "inflation", "down"]):
                impact = "🔴 Negative / Bearish"
            elif any(w in lower_title for w in ["surge", "record", "jump", "bull", "rally", "growth", "up"]):
                impact = "🟢 Positive catalyst"
            else:
                impact = "🟡 Watch level"
                
            macro_table.append(f"| **News:** [{title_text}]({link_text}) | {impact} |")
    except Exception:
        pass

    # Fallback if empty
    if not macro_table:
        macro_table = [
            "| **Macro Data** | 🟡 Awaiting update |",
            "| **Indian Markets News** | 🟡 Fetching delayed |"
        ]

    table_rows = "\n".join(macro_table)
    
    # 3. Dynamic "What this means for you" context
    # If VIX is high, suggest caution
    vix_advice = "Consider phased deployment into quality large-caps rather than deploying all at once given elevated volatility."
    if vix_number < 15:
        vix_advice = "Market volatility is relatively low. Consider systematically accumulating fundamentally strong stocks."
    elif vix_number > 20:
        vix_advice = "Market is highly volatile. Avoid leveraged/intraday positions and hold cash for deep corrections."

    return f"""
### 🚨 Broad Market & Economic Triggers

| Trigger / Indicator | General Impact |
| :--- | :--- |
{table_rows}

---
### 💡 Broad Market Outlook

**Current Market State**: Benchmark Nifty 50 is trading around **{nifty_val}** with the India VIX at **{vix_val}**. 

**Capital Deployment Strategy**: {vix_advice}

**Near-term outlook**: Track key global macro indicators and upcoming structural policy announcements. Monitor sector rotations driven by quarterly earnings. Ensure your portfolio allocation matches your risk appetite and maintain strict stop-losses in this environment.
"""

def get_potential_stocks():
    import yfinance as yf
    import pandas as pd
    import urllib.request
    import urllib.parse
    import xml.etree.ElementTree as ET
    from contextlib import closing
    
    # Expanded list of high-liquidity stocks
    tickers = {
        "Reliance Industries": "RELIANCE.NS",
        "HDFC Bank": "HDFCBANK.NS",
        "TCS": "TCS.NS",
        "Infosys": "INFY.NS",
        "ICICI Bank": "ICICIBANK.NS",
        "SBI": "SBIN.NS",
        "Bharti Airtel": "BHARTIARTL.NS",
        "ITC": "ITC.NS",
        "L&T": "LT.NS",
        "Kotak Bank": "KOTAKBANK.NS",
        "Axis Bank": "AXISBANK.NS",
        "Sun Pharma": "SUNPHARMA.NS",
        "Maruti Suzuki": "MARUTI.NS",
        "Tata Motors": "TATAMOTORS.NS",
        "Mahindra & M": "M&M.NS",
        "NTPC": "NTPC.NS",
        "Power Grid": "POWERGRID.NS"
    }
    
    # We also need Nifty benchmark for relative strength and VIX for Macro
    symbols = list(tickers.values()) + ["^NSEI", "^INDIAVIX"]
    suggestions = []
    
    # 1. Broad Catalyst News Scan (Fast 1-request scan)
    positive_news_stocks = []
    try:
        query = urllib.parse.quote("Indian stocks buy target upgrade surge when:3d")
        url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with closing(urllib.request.urlopen(req, timeout=3)) as response:
            xml_data = response.read()
        root = ET.fromstring(xml_data)
        for item in root.findall('.//item')[:15]:
            title_text = item.find('title').text.lower() if item.find('title') is not None else ""
            for name, sym in tickers.items():
                first_word = name.lower().split()[0]
                if first_word in title_text or sym.replace(".NS", "").lower() in title_text:
                    positive_news_stocks.append(sym)
    except Exception:
        pass
    
    try:
        import json
        def raw_fetch(sym):
            try:
                url = f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?range=3mo&interval=1d"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
                with urllib.request.urlopen(req, timeout=3) as response:
                    res = json.loads(response.read().decode())['chart']['result'][0]
                    df = pd.DataFrame(res['indicators']['quote'][0])
                    df.index = pd.to_datetime(res['timestamp'], unit='s')
                    return df.dropna()
            except Exception:
                return pd.DataFrame()

        # Baseline Nifty return & Macro VIX
        nifty_ret = 0
        vix_val = 15.0
        
        vix_df = raw_fetch("^INDIAVIX")
        if not vix_df.empty and 'close' in vix_df.columns:
            vix_val = float(vix_df['close'].iloc[-1])
            
        nifty_df = raw_fetch("^NSEI")
        if not nifty_df.empty and 'close' in nifty_df.columns:
            n_series = nifty_df['close']
            if len(n_series) > 20:
                nifty_ret = (n_series.iloc[-1] - n_series.iloc[-20]) / n_series.iloc[-20]
        
        for name, sym in tickers.items():
            try:
                df = raw_fetch(sym)
                if not df.empty and 'close' in df.columns and 'volume' in df.columns:
                    c_series = df['close']
                    v_series = df['volume']
                    
                    if len(c_series) < 50:
                        continue
                        
                    current_price = float(c_series.iloc[-1])
                    prev_price = float(c_series.iloc[-20]) if len(c_series) > 20 else current_price
                    stock_ret = (current_price - prev_price) / prev_price
                    
                    sma20 = float(c_series.rolling(20).mean().iloc[-1])
                    sma50 = float(c_series.rolling(50).mean().iloc[-1])
                    
                    avg_vol = float(v_series.rolling(10).mean().iloc[-1])
                    curr_vol = float(v_series.iloc[-1])
                    
                    # RSI
                    delta = c_series.diff()
                    gain = delta.where(delta > 0, 0)
                    loss = -delta.where(delta < 0, 0)
                    avg_gain = float(gain.rolling(14).mean().iloc[-1])
                    avg_loss = float(loss.rolling(14).mean().iloc[-1])
                    rs = avg_gain / avg_loss if avg_loss != 0 else 0
                    rsi = float(100 - (100 / (1 + rs)) if avg_loss != 0 else 100)
                    
                    reasons = []
                    score = 0
                    
                    # A. Macroeconomic Alignment Factors
                    if vix_val > 18.0 and name in ["ITC", "Sun Pharma", "TCS", "Infosys"]:
                        reasons.append(f"Defensive Macro Play (High VIX: {vix_val:.1f})")
                        score += 1.5
                    elif vix_val <= 18.0 and name not in ["ITC", "Sun Pharma"]:
                        reasons.append(f"Risk-On Macro Flow (Low VIX)")
                        score += 0.5
                        
                    # B. Live News Sentiment Factors
                    if sym in positive_news_stocks:
                        reasons.append("Bullish News/Target Upgrade")
                        score += 2.0
                    
                    # C. Technical & Momentum Factors
                    if current_price > sma50:
                        reasons.append("Above 50-DMA")
                        score += 1
                    if sma20 > sma50:
                        reasons.append("Bullish Trend")
                        score += 1.5
                    if 40 <= rsi <= 65:
                        reasons.append(f"Healthy RSI ({rsi:.0f})")
                        score += 1
                    elif rsi < 40:
                        reasons.append(f"Oversold Value (RSI {rsi:.0f})")
                        score += 2
                        
                    # D. Volume & Relative Strength Factors
                    if curr_vol > (avg_vol * 1.5):
                        reasons.append("Heavy Buying Volume")
                        score += 1.5
                        
                    if stock_ret > nifty_ret:
                        reasons.append("Outperforming Nifty")
                        score += 1
                        
                    # Format reasons cleanly (take top 3 heavily weighted reasons for brevity)
                    if not reasons:
                        reasons.append("Consolidation Setup")
                        
                    suggestions.append((score, name, sym, current_price, stock_ret * 100, ", ".join(reasons[:3])))
            except Exception:
                continue
                
        # Sort by highest score containing macro/news/technicals
        suggestions.sort(key=lambda x: x[0], reverse=True)
        
        # Keep top 5
        suggestions = suggestions[:5]
        
    except Exception as e:
        return f"⚠️ Could not complete AI screening: {e}"
        
    md = "### 💎 Top Stocks to Consider Today\n\n"
    md += "Based on a dynamic robust evaluation of **current momentum, relative strength against the Nifty, volume breakouts, and technical trends**, here are the top 5 stocks showing the strongest actionable setups today:\n\n"
    
    if not suggestions:
        md += "> *Screening data unavailable at the moment. Please try again.*"
    else:
        md += "| Stock | Ticker | Current Price | 1-Month Return | Key Driving Factors |\n"
        md += "| :--- | :--- | :--- | :--- | :--- |\n"
        for score, name, sym, price, ret, rationale in suggestions:
            trend_color = "🟢" if ret >= 0 else "🔴"
            md += f"| **{name}** | `{sym}` | ₹{price:,.2f} | {trend_color} {ret:+.1f}% | ⚡ {rationale} |\n"
            
    md += "\n--- \n*Disclaimer: These dynamic recommendations rank short-term volume surges, trend structure, and relative market outperformance. Perform detailed fundamental analysis in the **Stock Analysis** tab before trading.*"
    return md

def get_market_pulse():
    import urllib.request
    import urllib.parse
    import xml.etree.ElementTree as ET
    from contextlib import closing
    
    pulse_md = "### 📈 Market Pulse: Stocks in Focus\n\n"
    pulse_md += "Monitor the following key corporate updates across the Indian Market affecting specific equity instruments regarding **Results, Board Meetings, Dividends (Record Dates), and Acquisitions**:\\n\\n"
    
    topics = [
        ("📅 Upcoming Record Dates / Dividends", "dividend record date stock India when:7d"),
        ("🤝 Mergers & Acquisitions", "acquisition merger stock news India when:7d"),
        ("📊 Earnings Results", "Q3 Q4 quarterly results stock India when:7d"),
        ("🏛️ Board Meetings", "board meeting stock India when:7d")
    ]
    
    for section_title, query_str in topics:
        pulse_md += f"#### {section_title}\n"
        try:
            query = urllib.parse.quote(query_str)
            url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
            
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with closing(urllib.request.urlopen(req, timeout=5)) as response:
                xml_data = response.read()
            
            root = ET.fromstring(xml_data)
            items = root.findall('.//item')
            
            if not items:
                pulse_md += "- *No major updates today.*\n\n"
                continue
                
            for item in items[:4]: # Top 4 for each
                title = item.find('title')
                link = item.find('link')
                
                title_text = title.text if title is not None else "No Title"
                link_text = link.text if link is not None else "#"
                
                if '-' in title_text:
                    title_text = "-".join(title_text.split('-')[:-1]).strip()
                    
                pulse_md += f"- [{title_text}]({link_text})\n"
                
            pulse_md += "\n"
        except Exception:
            pulse_md += "- *Failed to fetch live updates.*\n\n"
            
    return pulse_md

# -------------------------------
# Gradio UI
# -------------------------------
with gr.Blocks(title="🇮🇳 Indian Stock Market AI Analyst", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 📈 Indian Stock Market AI Analyst")
    gr.Markdown("Advanced Technical & Fundamental Analysis with AI Reasoning")
    
    with gr.Tabs():
        # ---------------------------
        # TAB 1: Macro Economy
        # ---------------------------
        with gr.TabItem("🌍 Macro Economy"):
            with gr.Group():
                market_triggers_md = gr.Markdown("⏳ *Loading Key Market Triggers...*")
                
        # ---------------------------
        # TAB 2: Market Pulse
        # ---------------------------
        with gr.TabItem("📊 Market Pulse"):
            with gr.Group():
                market_pulse_md = gr.Markdown("⏳ *Loading Upcoming Stock Events...*")

        # ---------------------------
        # TAB 3: AI Top Picks
        # ---------------------------
        with gr.TabItem("💎 AI Top Picks"):
            with gr.Group():
                top_picks_md = gr.Markdown("⏳ *Running AI Market Screener...*")
                
        # ---------------------------
        # TAB 4: Stock Analysis
        # ---------------------------
        with gr.TabItem("🔎 Stock Analysis"):
            with gr.Row():
                # Left column (inputs)
                with gr.Column(scale=1):
                    # Pre-compute choices for better search (Name | Ticker)
                    SEARCH_CHOICES = [f"{name} | {ticker}" for name, ticker in STOCK_MAPPING.items()]
                    
                    stock_input = gr.Dropdown(
                        choices=SEARCH_CHOICES,
                        label="Search Stock (Name or Symbol)",
                        info="Start typing Company Name OR Ticker to filter...",
                        interactive=True,
                        allow_custom_value=True,
                        
                        value=SEARCH_CHOICES[0]
                    )

                    with gr.Row():
                        period_dropdown = gr.Dropdown(
                            choices=["1mo", "3mo", "6mo", "1y", "2y", "5y"],
                            value="6mo",
                            label="Period"
                        )
                        interval_dropdown = gr.Dropdown(
                            choices=["1d", "1wk", "1mo"],
                            value="1d",
                            label="Interval"
                        )
                    
                    run_button = gr.Button("🚀 Run AI Analysis", variant="primary")

                # Right column (outputs)
                with gr.Column(scale=2):
                    output_chart = gr.Image(label="📈 Technical Chart")
                    output_text = gr.Markdown(label="🤖 AI Analysis Report")
                    output_details = gr.Textbox(label="📊 Technical Signal Details", lines=10)

    run_button.click(
        fn=query_stock,
        inputs=[stock_input, period_dropdown, interval_dropdown],
        outputs=[output_text, output_chart, output_details]
    )

    demo.load(fn=get_market_triggers, inputs=None, outputs=market_triggers_md)
    demo.load(fn=get_market_pulse, inputs=None, outputs=market_pulse_md)
    demo.load(fn=get_potential_stocks, inputs=None, outputs=top_picks_md)

demo.launch()