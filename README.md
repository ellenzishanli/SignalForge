# SignalForge 🔭

> **Smart money tracker + quant research terminal.**
> Follows 20+ top hedge funds via SEC filings. 5-factor quant engine (Kalman filter, Markov chains, Hurst exponent) scoring 150+ stocks across the full AI infrastructure value chain. Congressional & insider trade monitoring. Real-time macro shock alerts. Delivered to your inbox every morning at 7 AM.

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![LLM: Groq](https://img.shields.io/badge/LLM-Groq%20%7C%20Claude%20%7C%20Gemini-purple)](https://console.groq.com)
[![Data: SEC EDGAR](https://img.shields.io/badge/Data-SEC%20EDGAR%20%7C%20Finviz%20%7C%20Yahoo-orange)](https://www.sec.gov/edgar)

Built for investors who want to think like the world's best allocators: **buy great businesses at fair prices and hold**. Not a trading tool. No day-trading noise. Buffett/Klarman-style fundamental analysis enriched with quant scoring and AI.

> *"The stock market is a device for transferring money from the impatient to the patient."* — Warren Buffett

---

## What It Does

### 🛰️ AI Infrastructure Value Chain — Hunt the "Next Micron" (`--mode aii`)

The full **picks-and-shovels stack** behind the AI buildout — ~50 names mapped across every layer, from the chip to the power grid. This is where the next 10x ideas live *before* the market finds them.

| Layer | What it is | Tickers |
|-------|-----------|---------|
| 🧠 **Compute Silicon** | GPUs, accelerators, CPUs | NVDA, AMD, AVGO, ARM, MRVL, ALAB |
| 🏭 **Foundry & Equipment** | The factories making the chips | TSM, ASML, AMAT, LRCX, KLAC |
| 💾 **Memory & Storage** | HBM, NAND, flash | MU, WDC, STX, SNDK |
| 🔌 **Networking & Optics** | Moving data at AI speed | ANET, CSCO, CRDO, CIEN, COHR, FN |
| 🖥️ **Servers & Cooling** | The physical body of AI | SMCI, DELL, HPE, VRT, ETN, MOD |
| ☁️ **Neoclouds & Data Centers** | GPU cloud landlords | NBIS, CRWV, IREN, APLD, CORZ |
| ⚡ **Power & Energy** | The fuel (most underpriced layer) | CEG, VST, NEE, GEV, TLN, EQT |
| 🏛️ **Hyperscalers** | The buyers driving all demand | MSFT, GOOGL, AMZN, META, ORCL |

**Opportunity Score (0–100)** — built to find asymmetric setups *before* re-rating:

```
Opportunity = Valuation (0–30)   ← GARP + forward P/E
            + Upside    (0–25)   ← analyst consensus target
            + Growth    (0–25)   ← revenue + earnings growth
            + Quant     (0–20)   ← 5-factor quant confirmation
            − Extended  penalty  ← demotes names up >80% on rich multiples
```

Labels: **🚀 EMERGING WINNER · 💎 UNDERVALUED · 🔥 HIGH UPSIDE · ⚡ MOMENTUM · ⚠️ EXTENDED**
Asymmetric "next Micron" setups are flagged ⭐ — high growth, fair value, real upside, not overextended.

```bash
python3 main.py --mode aii
```

---

### 🐋 Whale Tracker — Smart Money Intelligence (`--mode whales`)

Track what the world's best investors are actually buying — parsed live from SEC filings, congressional disclosures, and social signals. 23 funds, 7 tabs.

| Tab | Source | What you get |
|-----|--------|-------------|
| **1–2: Institutional + AI Funds** | SEC 13F (live EDGAR parse) | Holdings, QoQ changes, new positions — Berkshire, Bridgewater, Renaissance, Tiger Global, Coatue, D1, Whale Rock, Situational Awareness |
| **3: Quant Giants** | SEC 13F | Citadel (15,000+ positions), Two Sigma, D.E. Shaw, Point72, WorldQuant |
| **4: Crypto Whales** | Public disclosures | Saylor/MSTR, a16z, World Liberty Financial, Pantera, Galaxy Digital |
| **5: Insider Buying** | Finviz scraper | C-suite & director purchases — the strongest buy signal that exists |
| **6: Congressional Trades** | Capitol Trades / QuiverQuant | Real-time STOCK Act disclosures — what politicians are actually buying |
| **7: Social Intelligence** | StockTwits + Finviz News + SEC RSS | Trending tickers, sentiment on whale holdings, 13F filing alerts |

**Funds tracked — 23 managers across 4 categories:**

| Category | Managers |
|----------|---------|
| 🏆 Value / Activist | Berkshire · Baupost · Pershing Square · Scion · Third Point · Elliott · Sachem Head |
| 📈 Growth / Macro | Duquesne · Viking Global · D1 Capital · Durable Capital · Whale Rock · Dragoneer |
| 🤖 AI / Tech | Situational Awareness (Leopold Aschenbrenner) · Coatue · Tiger Global · ARK |
| ⚙️ Quant Giants | Bridgewater · Renaissance · Citadel · Point72 · D.E. Shaw · Two Sigma · WorldQuant Millennium |

Every holding enriched with:
- **5-factor quant score** → follow signal: `⭐⭐⭐ STRONG FOLLOW` to `❌ AVOID`
- **QoQ change detection**: NEW BUY / INCREASED / DECREASED / CLOSED
- **Novelty scoring**: non-consensus picks from Scion/Situational Awareness boosted; mega-cap consensus down-ranked

```bash
python3 main.py --mode whales
```

---

### 📈 Sector Scan + Hidden Gems (`--mode stocks`)

- **5-module quant scoring** (each 0–100): Technical · Statistical · ML Trend · Risk · Fundamental
- **100+ stocks** across 10 sectors · **75 ETFs** (Tech, Bonds, Commodities, International, Factor, Dividend)
- **30 Hidden Gems**: quantum computing, space tech, nuclear, biotech, eVTOL — small/mid-cap, under analyst coverage

### 🧠 Quantitative Engine

| Method | What it does |
|--------|-------------|
| **Kalman Filter** | Tracks "true" fair value behind noisy price data |
| **Markov Chain** | Models market regime (BULL/BEAR/SIDEWAYS) via transition probability matrix |
| **Hurst Exponent** | Detects mean-reverting (H<0.5) vs trending (H>0.5) via R/S analysis |
| **MACD / Stochastic / ADX** | Momentum + trend strength signals |
| **OBV** | On-Balance Volume — detects institutional accumulation |
| **ATR + Fibonacci** | Volatility regime + key support/resistance levels |
| **Sharpe / Sortino / VaR** | Risk-adjusted return + tail risk |
| **Multi-Factor Model** | Value 25% · Growth 30% · Quality 25% · Momentum 20% |
| **GARP / PEG Ratio** | Growth At Reasonable Price scoring |
| **Linear Regression ML** | Price slope, R², velocity, acceleration |

### 🚨 Macro Shock Monitor

LLM scans live RSS from Reuters, FT, WSJ, Bloomberg — identifies macro shock events (rate decisions, earnings, geopolitics) and surfaces the immediate trade setup for each.

### 🔭 Daily Tech Briefing (`--mode briefing`)

GitHub Trending · TechCrunch · VentureBeat · arXiv · Reddit AI communities · YC companies → AI-generated bilingual briefing: top startups, research breakthroughs, funding intelligence, non-obvious trends.

### 📧 Daily Email Report (`--mode email`)

Runs the full pipeline and delivers a dark-themed HTML report to your inbox every morning at 7 AM. Includes all sections: AI infra leaderboard, whale tracker summary, market intelligence, macro alerts, and tech briefing — in English and Chinese.

---

## Quick Start

### 1. Get a free LLM API key
Sign up at [console.groq.com](https://console.groq.com) — free tier, very fast, uses Llama 3.3 70B.

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure
```bash
cp .env.example .env
# Required: GROQ_API_KEY
# Optional: GMAIL_ADDRESS + GMAIL_APP_PASSWORD for daily email
```

### 4. Run
```bash
# AI Infrastructure value chain — hunt the "next Micron"
python3 main.py --mode aii

# Smart money tracker — 23 hedge funds, 7 tabs
python3 main.py --mode whales

# Full run: AI infra → whales → sectors → tech briefing
python3 main.py --mode full

# Email mode: full run + deliver to inbox
python3 main.py --mode email

# Just stocks (sectors + ETFs + hidden gems)
python3 main.py --mode stocks

# Hidden gems only (~1 min, fastest)
python3 main.py --mode gems

# Tech briefing only
python3 main.py --mode briefing
```

### 5. Schedule daily 7 AM email
```bash
python3 setup_cron.py
# Installs a cron job: every day at 7:00 AM (America/Los_Angeles)
# Sends the full report to the Gmail address in your .env
```

### 6. Navigate the output

Every mode uses a built-in scrollable pager (`less`).

| Key | Action |
|-----|--------|
| `← →` | Scroll horizontally through wide tables |
| `↑ ↓` or `j` / `k` | Scroll vertically |
| `G` | Jump to bottom |
| `g` | Jump to top |
| `/` then text | Search |
| `q` | Exit pager |

---

## Performance

All data fetches run on a **concurrent thread pool** — stocks, ETFs, and whale holdings are fetched in parallel, not sequentially. SEC EDGAR requests go through a global rate limiter (8 req/s, under EDGAR's 10 req/s fair-access ceiling).

| Task | Before | After |
|------|--------|-------|
| 100+ sector stocks | ~3 min | **~25s** |
| 75 ETFs | ~90s | **~8s** |
| 23 hedge fund 13F filings | ~45s | **~12s** |
| 30 hidden gems | ~60s | **~7s** |

---

## Project Structure

```
signalforge/
├── main.py                     # Entry point — 7 modes
├── config/
│   ├── universe.py             # AI infra value chain + 10 sectors + 75 ETFs + 30 hidden gems
│   ├── whales.py               # 23-fund registry with CIKs, styles, known-for
│   └── settings.py             # Screener thresholds, signal weights
├── stocks/
│   ├── ai_infrastructure.py    # AI infra value-chain scanner + Opportunity Score engine
│   ├── parallel.py             # Thread-pool helper — concurrent ticker fetches
│   ├── quant.py                # Master quant engine (5 sub-scores, 0–100)
│   ├── technical.py            # MACD, Stochastic, ATR, OBV, Fibonacci, ADX
│   ├── risk_metrics.py         # Sharpe, Sortino, VaR, CVaR, Beta, ML trend
│   ├── sector_scan.py          # Sector scanner + ETF table
│   ├── hidden_gems.py          # Small/mid-cap experimental picks
│   ├── screener.py             # Discount buy signals + GARP value picks
│   ├── backtest.py             # Walk-forward backtester + OLS weight optimization
│   └── data_enrichment.py      # Finviz scraper — short interest, analyst ratings
├── whales/
│   ├── whale_display.py        # Whale tracker — 7 tabs, quant enrichment, novelty ranking
│   ├── sec_13f.py              # SEC EDGAR 13F parser — rate-limited, parallel, no re-downloads
│   └── social_signals.py       # Congressional trades, insider buying, StockTwits, news
├── scrapers/
│   ├── github_trending.py      # GitHub Trending
│   ├── feeds.py                # TechCrunch, VentureBeat, arXiv RSS
│   ├── reddit_ai.py            # Reddit AI communities
│   ├── yc.py                   # YC company directory
│   └── macro_news.py           # Reuters, FT, WSJ macro headlines
├── analysis/
│   ├── ai_analyst.py           # Sell-side style bilingual AI reports (EN + 中文)
│   ├── llm_client.py           # Multi-provider LLM client — Groq, Claude, Gemini, Ollama
│   ├── headline_trades.py      # Macro shock → trade idea LLM analysis
│   └── emailer.py              # Dark-themed HTML email via Gmail SMTP
├── run_daily.sh                # Cron entry point
├── setup_cron.py               # One-command cron installer (7 AM daily)
└── output/                     # Daily reports saved as Markdown
```

---

## LLM Providers

| Provider | Cost | Model | Setup |
|----------|------|-------|-------|
| **Groq** (default) | Free | Llama 3.3 70B | [console.groq.com](https://console.groq.com) |
| Anthropic | Paid | Claude Opus/Sonnet | [console.anthropic.com](https://console.anthropic.com) |
| Google Gemini | Free tier | Gemini 1.5 Flash | [aistudio.google.com](https://aistudio.google.com) |
| Ollama | Local/free | Any local model | [ollama.com](https://ollama.com) |

```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_key_here

# Optional — for daily email delivery
GMAIL_ADDRESS=you@gmail.com
GMAIL_APP_PASSWORD=your_16_char_app_password
```

---

## For VC / PE / Finance / Quant Careers

This project demonstrates end-to-end financial engineering skills:

| Skill | Implementation |
|-------|---------------|
| **Quantitative finance** | Kalman filter, Markov chains, Hurst exponent, Sharpe/Sortino/VaR, multi-factor models, GARP/PEG |
| **Data engineering** | Multi-source scraping: SEC EDGAR, Finviz, Yahoo Finance, StockTwits, Reddit, GitHub, RSS |
| **Systems design** | Concurrent architecture, global rate limiting, modular CLI, automated scheduling |
| **AI/LLM integration** | Multi-provider LLM client, bilingual sell-side research, macro event analysis |
| **Financial analysis** | 13F parsing, QoQ change detection, congressional trade monitoring, insider signal tracking |
| **Investment research** | Value-chain mapping, opportunity scoring, novelty ranking, sector rotation framework |

---

## Disclaimer

For **educational and research purposes only**. Not investment advice. All models have inherent limitations. Do your own due diligence.

---

## License

MIT License — free to use, modify, and distribute.
