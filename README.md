# 🇮🇳 BharatStock Analyzer

An institutional-grade stock market analytics platform tailored for Indian Equities (NSE/BSE). Powered by **FastAPI**, **Yahoo Finance**, official macroeconomic feeds (RBI, MOSPI, FRED, NSE), and **Next.js 14** with TradingView Lightweight Charts.

---

## 🌟 Key Application Features (4 Core Tabs)

### 1. 🌍 Tab 1: Macro Economy Outlook (Landing Tab)
- **10 Market-Based Indicators**: Nifty 50, Sensex, India VIX, USD/INR, Brent Crude, Gold, US 10Y Yield, DXY, S&P 500, and Nasdaq with 1D/1W/1M/1Y change metrics and interactive 30-day SVG sparklines.
- **Official Macroeconomic Data**: RBI Repo Rate (6.50%), Headline CPI Inflation, Real GDP Growth, IIP, Manufacturing/Services PMI, India 10Y Benchmark G-Sec, Forex Reserves, and 5-day FII/DII Net Flows with explicit primary source tags and timestamps.
- **Algorithmic Macro Regime Classifier**: Automated rule-based classification into **Risk-On**, **Neutral**, or **Risk-Off** driven by VIX levels, Nifty vs. 200 DMA, FII flows, and crude oil trends with complete factor attribution.
- **Nifty Sector Rotation Heatmap**: 10 key Nifty sectoral indices (Bank, IT, Auto, Pharma, FMCG, Metal, Realty, Energy, Infra, PSU Bank) with 1W, 1M, 3M returns and Relative Strength (RS) vs. Nifty 50.
- **AI Narrative Summary**: Crisp institutional takeaways on "What this regime means for equities".

### 2. 📊 Tab 2: Market Pulse (Corporate Actions & Events)
- **Corporate Actions Feed**: Dividends (yield, ex-date, record-date), Stock Splits, Bonus Issues (ratio), Buybacks (offer price vs. CMP), Rights Issues, Board Meetings, and Quarterly Earnings Dates.
- **Dual View Modes**: Interactive Timeline Calendar and Detailed Structured Table.
- **Signal Tagging**: Rule-based 🟢 Positive, 🟡 Neutral, and 🔴 Negative tags with plain English rationales.
- **Results Season Tracker (Q2 FY25)**: Net Revenue, Net Profit (PAT), YoY & QoQ growth %, EBIT margins, and Beat/Miss classifications.
- **Market Activity**: Institutional Bulk/Block deals, Daily FII/DII net flows, Volume spikes (>1.5x 20-DMA), and 52-Week High breakout lists.

### 3. 💎 Tab 3: Top Picks for Short-Term Profit Booking
- **Universe**: Liquid universe across Nifty 500 equities.
- **6 Algorithmic Swing Setups**:
  1. *Volume Breakout*: 20-day high breakout with >1.8x volume expansion and healthy RSI (52-72).
  2. *Pullback to 20/50 EMA*: Trend continuation bounce in primary uptrend.
  3. *RSI Oversold Reversal*: Mean-reversion rebound from oversold levels (<35 to >38).
  4. *MACD Trend Crossover*: Fresh bullish crossover confirmed above 50 EMA.
  5. *Bollinger Squeeze Expansion*: Multi-week volatility contraction breaking out above upper band.
  6. *Support Level Bounce*: Candlestick rejection off major horizontal or Fibonacci support.
- **Trade Plan Structure**: Entry Zone, ATR-based Volatility Stop-Loss, Target 1 ($1.5\times$ Risk, $R:R \ge 1.5$), Target 2 ($3.0\times$ Risk, $R:R \ge 3.0$), Signal Strength Score (0-100), and Staged Profit-Booking Plan (*"Book 50% at T1, trail stop to breakeven, ride remaining 50% to T2"*).
- **Empirical 2-Year Backtest Evidence**: Verified Win Rate (%), Average Return (%), Profit Factor, Max Drawdown (%), and Sample Size ($N$).
- **Watchlist Profit-Booking Alerts**: Live flags for stocks in user watchlist reaching targets or entering overbought RSI (>75).

### 4. 🔎 Tab 4: Stock Deep-Dive & Valuation Suite
- **Universal NSE Search**: Instant autocomplete across 500+ Indian stocks.
- **5 Specialized Sub-tabs**:
  - **Overview**: Live quote, 52-week slider, upcoming actions, and **Combined Verdict Card** (Fundamental + Technical + Macro).
  - **Fundamental & Intrinsic Value**:
    * **Interactive 2-Stage DCF Simulator**: Live UI sliders for Stage 1 Growth %, Stage 2 Growth %, Terminal Rate %, Discount Rate / WACC %, and Margin of Safety % with instant recalculation.
    * **Graham Number & Revised Graham Formula**: $\sqrt{22.5 \times EPS \times BVPS}$ and $V = \frac{EPS \times (8.5 + 2g) \times 4.4}{Y}$.
    * **Banking/NBFC Valuation**: Auto-detects financial institutions and switches to **Justified P/B - ROE Model**.
    * **Blended Intrinsic Value & Margin of Safety**: Undervalued (>25%), Fairly Valued, Overvalued.
    * **Company Valuation Multiples**: Enterprise Value (EV), EBITDA, EV/EBITDA, EV/Sales, Operating Cash Flow, CapEx, Free Cash Flow to Firm (FCFF), Free Cash Flow to Equity (FCFE), FCF Yield %, and Price to FCF.
    * **0-100 Quality Scorecard & 0-9 Piotroski F-Score**: ROE, ROCE, Debt/Equity, Interest Coverage, CAGR, Margins, and FCF consistency.
  - **Technical Analysis**:
    * **TradingView Lightweight Candlestick Chart** with timeframe selector (1mo, 3mo, 6mo, 1y, 2y) and volume overlay.
    * Indicators: SMA/EMA 20/50/100/200, RSI, MACD, Bollinger Bands, ATR, Stochastic, OBV, VWAP.
    * Automated Support/Resistance detection and Fibonacci Retracement levels.
    * Overall Technical Rating (Strong Buy / Buy / Neutral / Sell / Strong Sell).
  - **Financial Statements**: Annual balance sheet and audited cash flows in ₹ Crores.
  - **Sector Peer Comparison**: Real-time peer benchmarking table.

---

## 🛠️ Architecture & Tech Stack

- **Backend**: Python 3.11+, FastAPI, `yfinance`, `pandas`, `numpy`, `pandas-ta`, `SQLAlchemy`, `SQLite`, `APScheduler`, `pytest`.
- **Frontend**: Next.js 14, TypeScript, Tailwind CSS, TradingView Lightweight Charts, Recharts, Lucide Icons.
- **Data Guarantee**: Numbers are **never** fabricated. If an external API is unavailable, the verified fallback cache is served with explicit timestamp and source attribution.

---

## 🚀 Quick Start Guide

### Option 1: Running with Docker Compose (Recommended)
```bash
# 1. Clone repository
git clone https://github.com/your-username/bharatstock-analyzer.git
cd bharatstock-analyzer

# 2. Start full-stack application
docker-compose up --build
```
- Frontend UI (local): `http://localhost:3000`
- Live site: [pawanstockrecommendations.com](https://pawanstockrecommendations.com)
- FastAPI OpenAPI Docs: `http://localhost:8000/docs`

---

### Option 2: Running Locally

#### 1. Backend Setup (FastAPI)
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

pip install -r requirements.txt

# Run FastAPI backend server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Frontend Setup (Next.js)
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` in your browser.

---

## 🧪 Running Unit Tests
```bash
cd backend
pytest tests -v
```

---

## ⚖️ Legal & SEBI Disclaimer
BharatStock Analyzer is an analytical and educational research software tool. It is **not** an investment advisory service or a SEBI-registered recommendation. Market data from Yahoo Finance and free public APIs may be delayed or approximate. Short-term swing setups involve capital risk. Always conduct your own research or consult a registered financial advisor before investing.
---

## 🧮 Research Methodology (v2)

### Valuation: one primary method per company
| Company type | Primary method | Why |
|---|---|---|
| Banks, NBFCs, insurers | **FCFE** (sustainable growth = ROE × retention, Ke-discounted) | Debt is raw material for lenders, so cash flow to equity is the right measure. P/B-ROE is shown as a cross-check. |
| Non-financials with positive normalised FCFF | **FCFF 2-stage DCF** (WACC-discounted, value-driver terminal value `NOPAT × (1 − g/RONIC)`) | Capital-structure-neutral cash flow. RONIC is capped at 25% and never below WACC. |
| Non-financials with negative FCFF, positive EBITDA | **EV/EBITDA** (live same-sector peer median; sector fallback flagged as an assumption) | An intrinsic DCF is unreliable when FCFF is negative. |
| Anything else | **Not applicable** | No number is fabricated. The reason is shown. |

All inputs come from the annual income statement, balance sheet and cash-flow statement (INR). Missing inputs are listed in `data_gaps` and lower the confidence rating.

**Key assumptions** (all visible in each response under `inputs`):
- Risk-free rate 6.80% (India 10Y G-Sec, `INDIA_10Y_GSEC_DEFAULT`), equity risk premium 6.50%.
- Beta: Yahoo raw beta, Blume-adjusted (0.67 × raw + 0.33), bounded to 0.8–2.0.
- Cost of debt = interest expense / total debt, bounded to Rf to Rf + 5pp. Tax = effective rate, bounded 15–35%.
- Terminal growth 4.5%. Stage-1 growth = revenue CAGR (clamped −5% to 15%), fading linearly to terminal growth over years 6–10.
- Piotroski F-score is computed from statements (9 checks, scored only on checks that could be computed).

### Triangulation (Buy / Hold / Sell)
Composite = 45% fundamental (valuation margin of safety + quality) + 35% technical (existing 0–100 engine) + 20% macro (regime plus stock-specific sentiment). Actions: ≥70 Strong Buy, ≥60 Buy, ≥45 Hold, ≥35 Reduce, otherwise Sell. The response also reports whether the fundamental and technical evidence agree.

### Page 1: Macro sentiment for a stock
`GET /api/macro/stock-sentiment/{symbol}` maps current indicators (crude, USD/INR, India VIX, Nifty, US 10Y, Nasdaq) to the stock's sector using the rules in `backend/app/config/stock_macro_rules.json`. Each factor is shown with its indicator value.

### Page 2: Daily Two Picks
- Screens the Nifty 500 universe (`DAILY_UNIVERSE_SIZE`, default 120) every weekday at 16:30 IST, and on demand via `POST /api/daily-picks/refresh`.
- Hard exclusions: no usable price history, no applicable valuation, or illiquid (under ₹10 Cr average daily turnover).
- Soft gates: margin of safety ≥15%, quality ≥55, above 200-DMA, technical ≥55, composite ≥60, risk:reward ≥1.5, macro not negative, data confidence not Low. Unmet gates lower the **conviction** label and are listed. The two picks are always the best available, from different sectors.

### Known limits
- Official macro series (RBI repo, CPI, GDP, PMI, G-Sec) are static fallbacks from `macro_fallback.json` and are dated 2024. They are not refreshed automatically.
- The sector EV/EBITDA fallback table (`sector_ev_ebitda.json`) contains analyst assumptions, not market data. It is flagged wherever it is used.
- Yahoo statements for some Indian issuers are restated or distorted by mergers. HDFC Bank's trailing ROE, for example, reflects the post-merger equity base. Review `inputs` before relying on any single output.
- Analytical output for education only. Not SEBI-registered investment advice.
