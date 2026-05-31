# SignalForge 🔭

**AI-powered quantitative investment research platform** — daily tech intelligence + multi-factor stock analysis across all market sectors.

Built for investors, finance professionals, and quant enthusiasts who want institutional-quality signals without a Bloomberg terminal.

---

## What It Does

### 📈 Stock Analysis (Quant Engine)
- **5-module scoring system** (each 0–100): Technical · Statistical · ML Trend · Risk · Fundamental
- Covers **100+ stocks across 10 sectors** + **75 ETFs** (Tech, Bonds, Commodities, International, Real Estate, Factor ETFs)
- **Hidden Gems scanner**: 30 under-the-radar small/mid-cap names (quantum computing, space, nuclear, biotech, eVTOL)

### 🧠 Quantitative Methods
| Method | What it does |
|--------|-------------|
| **Markov Chain** | Models market regime (BULL/BEAR/SIDEWAYS) via transition probability matrix |
| **Kalman Filter** | Tracks "true" fair value behind noisy price data (Apollo-era aerospace math applied to stocks) |
| **Hurst Exponent** | Detects mean-reverting (H<0.5) vs trending (H>0.5) behavior via R/S analysis |
| **MACD** | Momentum via EMA crossovers + histogram direction |
| **Stochastic Oscillator** | %K/%D overbought/oversold signal |
| **ADX** | Trend strength (>25 = developing, >40 = strong) |
| **OBV** | On-Balance Volume — detects institutional accumulation/distribution |
| **ATR** | Volatility regime detection (coiling vs expanding) |
| **Fibonacci Retracements** | Key support/resistance levels from 60-day swing |
| **Sharpe / Sortino Ratio** | Risk-adjusted return quality |
| **VaR (99%) + CVaR** | Tail risk measurement |
| **Multi-Factor Model** | Value 25% · Growth 30% · Quality 25% · Momentum 20% |
| **GARP / PEG Ratio** | Growth At Reasonable Price scoring |
| **Linear Regression Trend** | ML slope, R², velocity, acceleration on price |

### 🔭 Daily Tech Briefing
- GitHub Trending · TechCrunch/VentureBeat/arXiv RSS · Reddit AI communities · YC companies
- AI-generated briefing: top startups, research breakthroughs, funding intelligence, non-obvious trends

---

## Quick Start

### 1. Get a free LLM API key
Sign up at [console.groq.com](https://console.groq.com) — free tier, fast, uses Llama 3.3 70B.

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure
```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### 4. Run
```bash
# Full run: sector scan + hidden gems + ETF + tech briefing
python3 main.py --mode full

# Stock analysis only (all sectors + ETF + hidden gems)
python3 main.py --mode stocks

# Hidden gems only (fastest)
python3 main.py --mode gems

# Tech briefing only
python3 main.py --mode briefing
```

---

## Output Example

### Hidden Gems Table
```
💎 Hidden Gems & Experimental Picks
┌──────┬────────────────┬─────────────────────┬──────────┬──────────┬────────┬────────┬─────────┬─────────┬─────────┐
│Ticker│Category        │Name                 │Price     │Mkt Cap   │1M Ret  │1Y Ret  │Tech/100 │Stat/100 │Signal   │
├──────┼────────────────┼─────────────────────┼──────────┼──────────┼────────┼────────┼─────────┼─────────┼─────────┤
│ RKLB │ Space          │ Rocket Lab Corp     │ $143.48  │ $83.1B   │ +86.3% │+396.0% │      53 │      59 │ BUY     │
│ ASTS │ Space          │ AST SpaceMobile     │ $113.41  │ $44.0B   │ +62.4% │+357.0% │      53 │      57 │ BUY     │
│ IONQ │ Quantum        │ IonQ Inc            │  $72.07  │  $25.4B  │ +35.0% │+576.0% │      47 │      30 │ HOLD    │
└──────┴────────────────┴─────────────────────┴──────────┴──────────┴────────┴────────┴─────────┴─────────┴─────────┘
```

### Bilingual AI Analysis
Every report generates a complete English analysis followed by a full Chinese translation — same structure, same depth.

---

## Project Structure

```
signalforge/
├── main.py                     # Entry point (4 modes)
├── config/
│   ├── universe.py             # Stock universe: 10 sectors, 75 ETFs, 30 hidden gems
│   └── settings.py             # Screener thresholds, signal weights
├── stocks/
│   ├── quant.py                # Master quant engine (5 sub-scores)
│   ├── technical.py            # MACD, Stochastic, ATR, OBV, Fibonacci, ADX
│   ├── risk_metrics.py         # Sharpe, Sortino, VaR, CVaR, Beta, ML trend
│   ├── sector_scan.py          # Sector-by-sector scanner + ETF table
│   ├── hidden_gems.py          # Small/mid-cap experimental picks
│   ├── screener.py             # Discount buy signals + GARP value picks
│   └── data_enrichment.py      # Finviz scraper (short interest, analyst ratings)
├── scrapers/
│   ├── github_trending.py      # GitHub Trending
│   ├── feeds.py                # TechCrunch, VentureBeat, arXiv RSS
│   ├── reddit_ai.py            # Reddit AI communities
│   └── yc.py                   # YC company directory
├── analysis/
│   ├── ai_analyst.py           # Sell-side style bilingual AI reports
│   └── llm_client.py           # Multi-provider LLM client
└── output/                     # Daily reports saved as Markdown
```

---

## LLM Providers

Supports multiple providers — switch via `.env`:

| Provider | Cost | Model | Setup |
|----------|------|-------|-------|
| **Groq** (default) | Free | Llama 3.3 70B | [console.groq.com](https://console.groq.com) |
| Anthropic | Paid | Claude Opus/Sonnet | [console.anthropic.com](https://console.anthropic.com) |
| Google Gemini | Free tier | Gemini 1.5 Flash | [aistudio.google.com](https://aistudio.google.com) |
| Ollama | Local/free | Any local model | [ollama.com](https://ollama.com) |

```env
# .env
LLM_PROVIDER=groq
GROQ_API_KEY=your_key_here
```

---

## Sector Coverage

| Sector | Example Tickers |
|--------|----------------|
| AI & Compute Infrastructure | NVDA, AMD, ARM, AVGO, MRVL |
| Cloud & Software Platform | MSFT, GOOGL, SNOW, NET, PLTR |
| Clean Energy & Solar | ENPH, FSLR, NEE, PLUG |
| Nuclear & Grid Storage | CEG, OKLO, SMR, NNE |
| Defense & Aerospace | LMT, RTX, KTOS, RKLB, ASTS |
| Biotech & Healthcare AI | RXRX, SDGR, CRSP, BEAM |
| Fintech & Crypto | COIN, UPST, AFRM, HOOD |
| Robotics & Autonomous | TSLA, PATH, JOBY, ACHR |
| Semiconductor Equipment | AMAT, ASML, KLAC, LRCX |
| Data Infrastructure | PSTG, CRWD, PANW, ZS |

Plus **75 ETFs** across: Tech themes · S&P 500 sectors · Bonds (TLT/HYG/AGG) · Commodities (GLD/USO) · International (EEM/FXI/INDA) · Real Estate (VNQ) · Factor (MTUM/QUAL/USMV) · Dividend (SCHD/VYM)

---

## For VC/PE/Finance Careers

This project demonstrates:
- **Quantitative methods**: Markov chains, Kalman filtering, Hurst exponent, multi-factor models
- **Financial analysis**: GARP valuation, sell-side research format, scenario analysis
- **Data engineering**: multi-source scraping (Yahoo Finance, Finviz, SEC EDGAR, RSS feeds)
- **AI integration**: LLM-powered analysis with multi-provider support
- **Systems design**: modular architecture, CLI tooling, automated reporting

---

## Disclaimer

This tool is for **educational and research purposes only**. It does not constitute investment advice. All quantitative models have inherent limitations. Always do your own due diligence before making investment decisions.

---

## License

MIT License — free to use, modify, and distribute.
