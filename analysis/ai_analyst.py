"""
AI Analysis Engine — Sell-Side Investment Bank Style Reports
Format: Goldman/Morgan Stanley equity research quality
Bilingual: Full English → Full Chinese translation
"""
import json, datetime
from typing import List, Any
from dataclasses import dataclass
from analysis.llm_client import call_llm

TODAY    = datetime.date.today().strftime("%B %d, %Y")
TODAY_CN = datetime.date.today().strftime("%Y年%m月%d日")


@dataclass
class StartupScore:
    name: str; description: str; score: float
    signals: dict; memo: str; category: str


# ══════════════════════════════════════════════════════════════════════════════
# SELL-SIDE STYLE MARKET INTELLIGENCE REPORT
# ══════════════════════════════════════════════════════════════════════════════

SELLSIDE_PROMPT = """You are a senior equity research analyst at a bulge-bracket investment bank (Goldman Sachs, Morgan Stanley, or JPMorgan level). You are writing the daily cross-sector intelligence report distributed to institutional clients.

Your report must match the quality, depth, and format of actual sell-side research. This means:
- Every recommendation must have a price target with methodology
- Every thesis must have 3+ specific, verifiable evidence points
- Every risk must be rated HIGH/MEDIUM/LOW with specific mechanism
- Every sector call must reference comparable company multiples
- Bull/Base/Bear scenario analysis with specific price targets

Market Data:
{context}

---

Write the report in English first, then provide a COMPLETE Chinese translation below (identical structure and depth).

═══════════════════════════════════════════════════════════════════════
FRONTIER TECH RADAR | EQUITY RESEARCH
Cross-Sector Market Intelligence Report | {date}
CONFIDENTIAL — FOR INSTITUTIONAL CLIENTS ONLY
═══════════════════════════════════════════════════════════════════════

## EXECUTIVE SUMMARY

**Market Regime:** [One sentence — what Markov state data tells us about current regime]
**Top Sector Call:** [Sector name] — [BUY/NEUTRAL/UNDERWEIGHT]
**Hidden Gem of the Day:** [Ticker] — [One-line thesis]
**ETF Rotation Signal:** [Best ETF entry today and why]
**Key Risk to Watch:** [Most important macro/micro risk this week]

---

## PART I — QUANTITATIVE MARKET REGIME ANALYSIS

### 1.1 Markov Chain State Distribution
Analyze the Markov state data across all covered sectors:
- What percentage of stocks are in BULL/BEAR/SIDEWAYS states?
- What does aggregate state persistence tell us? (High persistence = trending market)
- Expected 5-day return distribution based on Markov chains
- [Use specific ticker examples with exact probabilities from the data]

### 1.2 Mean Reversion Opportunity Map
- Which sectors have the most negative aggregate Z-scores? (Most oversold)
- Kalman Filter analysis: where is actual price furthest below Kalman fair value?
- Hurst Exponent interpretation: are we in a mean-reverting or trending market?

### 1.3 Factor Performance Attribution
- Which factor is working right now: Value, Growth, Quality, or Momentum?
- [Based on which stocks scored highest vs lowest in each factor]

---

## PART II — SECTOR DEEP DIVES (Top 3 Opportunities)

For each of the 3 most interesting sectors:

### SECTOR: [Name]
**Rating:** [OVERWEIGHT / NEUTRAL / UNDERWEIGHT]
**Thesis in One Line:** [Specific, non-generic]

**Why Now — Catalysts:**
1. [Specific macro or micro catalyst with timeline]
2. [Technical setup: reference Z-score, Markov state, Hurst exponent]
3. [Competitive dynamic or regulatory change]

**Top Pick: [TICKER] — [Company Name]**
- **Rating:** [BUY / HOLD / SELL] | **Price Target:** $[X] | **Upside:** [X]%
- **Methodology:** [Revenue multiple [X]x on FY2026E revenue of $[X]M = $[X] target]
  OR [DCF: [X]% growth, [X]% terminal, [X]% WACC → $[X] intrinsic value]
- **Key Metrics:** Revenue Growth [X]%, Margin [X]%, PE [X]x, GARP=[X], Quant=[X]/100
- **Quant Signal:** Hurst=[X] ([mean-reverting/trending]), Kalman Z=[X] ([below/above fair value]), Markov P(bull)=[X]%
- **Investment Thesis:**
  [3-4 sentences. What is the specific edge? Why does the market misunderstand this stock? What's the non-consensus view?]
- **Scenario Analysis:**
  | Scenario | Price | Upside | Key Assumption |
  |----------|-------|--------|----------------|
  | Bull      | $X    | +X%    | [specific condition] |
  | Base      | $X    | +X%    | [base case] |
  | Bear      | $X    | -X%    | [specific downside trigger] |
- **Catalyst Timeline:**
  - 0-3 months: [specific near-term event]
  - 3-6 months: [medium-term catalyst]
  - 6-12 months: [longer-term thesis confirmation]
- **Risk Matrix:**
  | Risk | Severity | Probability | Mitigation |
  |------|----------|-------------|------------|
  | [Risk 1] | HIGH | [X]% | [how to monitor] |
  | [Risk 2] | MEDIUM | [X]% | [how to monitor] |

**ETF Exposure:** [Which ETF to buy for sector exposure, and why individual stock beats ETF here or vice versa]

---

## PART III — HIDDEN GEMS: ASYMMETRIC OPPORTUNITIES

*These are non-consensus, high-risk/high-reward ideas that institutional consensus has not yet priced in. Position sizing: 1-3% max.*

For each of the top 3 hidden gems in the data:

### [TICKER] — [Company Name]
**Category:** [Quantum/Space/Nuclear/AI/Biotech/etc.]
**Market Cap:** $[X]B | **Price:** $[X] | **Rating:** SPECULATIVE BUY / WATCH / AVOID

**The Non-Consensus View:**
[2-3 sentences: What does the market currently believe about this stock? Why is that belief wrong or incomplete? What specific information asymmetry exists?]

**Evidence Base:**
- Revenue trajectory: [X]% growth, [specific data point]
- Institutional behavior: [short interest %, insider ownership, analyst coverage count]
- Technical positioning: [RSI, Z-score, Kalman Z, Hurst interpretation]
- Key relationships/partnerships: [specific company names, contract values if available]

**Valuation Framework:**
- Current: $[X]B market cap
- Bull case market opportunity: $[X]B TAM
- If captures [X]% share at [X]x revenue multiple → $[X] price target
- Comparable: [comp company at similar stage, what multiple it traded at]

**Catalyst Map (next 12 months):**
1. [Q-date or event]: [specific catalyst — FDA approval, contract award, revenue milestone]
2. [Q-date or event]: [second catalyst]

**Risk/Reward:**
- Upside: [X]% in bull case (12 months)
- Downside: [X]% if thesis fails
- Risk/Reward ratio: [X]:1

**Short Interest Flag:** [If short interest >15%, note it and interpret: contrarian signal or smart money shorting?]

---

## PART IV — ETF STRATEGY & ROTATION

### ETF Rankings (by overall attractiveness today)

For the top 5 ETFs from the data:

| Rank | ETF | Theme | Quant Score | Signal | 1Y Return | Entry Rationale |
|------|-----|-------|-------------|--------|-----------|-----------------|
| 1 | [X] | [X] | [X]/100 | [X] | [X]% | [specific reason] |
[...continue for all ranked ETFs...]

### ETF vs Individual Stock Decision Framework
**Use ETF when:** [3 specific conditions — e.g., high dispersion within sector, uncertain single-stock picking, want sector beta without idiosyncratic risk]
**Use Individual Stock when:** [3 specific conditions — e.g., clear catalyst, specific quant signal, Hurst + Z-score both support entry]

**Best ETF entry today:** [Ticker + specific reasoning using quant data]

---

## PART V — PRIORITY RANKINGS

### ⭐⭐⭐ STRONG BUY — Highest Conviction
[TICKER] | $[X] → $[X] target (+X%) | [One sentence with one specific quant number]

### ⭐⭐ BUY — Build Position
[TICKER] | [One sentence rationale with quant signal]

### 🔬 SPECULATIVE (Hidden Gems)
[TICKER] | Risk/Reward [X]:1 | [One sentence thesis — acknowledge high risk]

### ⏸ WATCH — Not Yet
[TICKER] | [What specific signal/event would trigger entry]

*IMPORTANT DISCLAIMER: For educational and research purposes only. Not investment advice.*

───────────────────────────────────────────────────────────────

# 机构研究报告 | 前沿科技雷达
跨行业市场情报 | {date_cn}
（完整中文版 — 与英文版完全对应）

═══════════════════════════════════════════════════════

## 执行摘要

[完整翻译英文版执行摘要，保留所有 ticker 和数字]

---

## 第一部分 — 量化市场状态分析

### 1.1 马尔可夫链状态分布
[完整翻译，保留所有数字和 ticker]

### 1.2 均值回归机会地图
[完整翻译]

### 1.3 因子绩效归因
[完整翻译]

---

## 第二部分 — 板块深度分析（前3大机会）

[对每个板块完整翻译，包括：
- 评级和投资逻辑
- 目标价方法论（收益乘数/DCF 等）
- 场景分析表格（牛市/基准/熊市）
- 催化剂时间轴
- 风险矩阵]

---

## 第三部分 — 隐藏宝石：不对称机会

[对每只小市值/冷门股完整翻译，包括：
- 市场共识 vs 我们的非共识观点
- 证据基础（空头比例、内部人持仓、机构覆盖）
- 估值框架（TAM、市值/机会对比）
- 催化剂时间轴
- 风险/回报比率]

---

## 第四部分 — ETF 策略与轮动

[完整翻译 ETF 排名表格和个股 vs ETF 决策框架]

---

## 第五部分 — 优先排名

[完整翻译所有评级，保留所有数字]

---

*重要免责声明：本报告仅供教育和研究目的，不构成投资建议。*"""


def analyze_full_market(context: str, n_sectors: int = 0, n_gems: int = 0) -> str:
    prompt = SELLSIDE_PROMPT.format(
        context=context, date=TODAY, date_cn=TODAY_CN
    )
    return call_llm(prompt, max_tokens=2500)


def analyze_ai_infrastructure(context: str) -> str:
    """
    Focused take on the AI infrastructure value chain: which names look like the
    'next Micron' — undervalued/fair with high growth and real upside — vs. which
    are already extended. Bilingual (EN + 中文), concise to stay within token caps.
    """
    prompt = f"""You are a buy-side analyst specializing in the AI infrastructure
value chain (compute silicon, foundry, memory, networking/optics, servers &
cooling, neoclouds, and the power layer). Below are the top-ranked opportunities
from a quant screen that rewards FAIR/CHEAP valuation + high growth + analyst
upside, and penalizes already-extended momentum names.

{context}

Today: {TODAY}.

Write a concise briefing in this exact structure:

## 🚀 The "Next Micron" Candidates
3–5 names with the best asymmetric setup (still reasonably valued, strong growth,
real upside). For each: 1 sentence on the thesis + the single biggest risk.

## 🔗 Value-Chain Read
2–3 sentences: which LAYER of the stack looks most mispriced right now and why
(e.g. is the market paying up for silicon while ignoring power/cooling?).

## ⚠️ Crowded / Extended
1–2 names that are great companies but where the easy money may be made.

Keep it tight and decision-useful — no filler. Then provide a full 中文 translation
under a "## 中文分析" heading with the same structure."""
    return call_llm(prompt, max_tokens=2000)


# ══════════════════════════════════════════════════════════════════════════════
# TECH BRIEFING (sell-side style, bilingual)
# ══════════════════════════════════════════════════════════════════════════════

def summarize_daily_data(
    github_repos: List[Any],
    ph_products: List[Any],
    feed_items: List[Any],
    reddit_posts: List[Any],
    yc_companies: List[Any],
) -> str:
    github_text = "\n".join([
        f"- [{r.language}] {r.name}: {r.description[:120]} | ⭐{r.stars_today} today / {r.total_stars} total"
        for r in github_repos[:20]
    ]) or "No GitHub data."

    feed_text = "\n".join([
        f"[{f.source}] {f.title}\n  → {f.summary[:200]}"
        for f in feed_items[:25]
    ]) or "No feed data."

    reddit_text = "\n".join([
        f"[r/{p.subreddit} | ↑{p.score} | 💬{p.num_comments}] {p.title}"
        for p in reddit_posts[:15]
    ]) or "Reddit not configured."

    yc_text = "\n".join([
        f"- {c.name} ({c.batch}): {c.description[:130]}"
        for c in yc_companies[:15]
    ]) or "No YC data."

    prompt = f"""Senior VC analyst writing daily briefing for investment team. Sharp, non-obvious insights only.

Data:
=== GITHUB TRENDING ===
{github_text}

=== NEWS (TechCrunch, VentureBeat, arXiv) ===
{feed_text}

=== REDDIT AI COMMUNITIES ===
{reddit_text}

=== YC & EARLY-STAGE ===
{yc_text}

Write English first, then complete Chinese translation with identical structure.

# 🔭 Frontier Tech Radar — {TODAY}

## ⚡ Signal of the Day
[One paragraph. The most important development — specific mechanism, specific impact on public markets.]

## 🚀 Startups to Watch (10 picks — more than usual, include both obvious and non-obvious)
For each: **[Name]** — What they do | Why now | Non-obvious edge | Comparable/comp valuation | Risk
Include: YC companies, GitHub trending projects, any stealth-mode or pre-launch mentioned in news.

## 🧠 Research & Model Breakthroughs
[4-6 items. What was released, technical capability unlocked, which company benefits, investable angle.]

## 💰 Funding Intelligence
[ALL funding signals. Round size, valuation if mentioned, lead investor, comparable exit multiples.]

## 📈 Pattern Recognition (Non-Obvious Trends)
[5 trends visible ONLY by connecting dots. Think: what technology, behavior, or market dynamic is forming that mainstream observers haven't named yet?]

## 🎯 Public Market Investment Angle
[3-4 specific stocks/ETFs that benefit from today's signals. Give the exact mechanism and timeline.]

## 🔬 VC/PE Lens — Early-Stage Opportunities
[2-3 emerging themes where you'd want early-stage exposure. What problem space? What would a Series A pitch look like? What's the exit path?]

---

# 🔭 科技雷达 — {TODAY_CN}

## ⚡ 今日最强信号
[完整翻译]

## 🚀 值得关注的初创公司（10个，多于往常）
[每个：名称 | 做什么 | 为什么是现在 | 非共识优势 | 可比公司/估值 | 风险]

## 🧠 研究与模型突破
[完整翻译]

## 💰 融资情报
[完整翻译所有融资信号]

## 📈 模式识别（普通人看不到的趋势）
[完整翻译5个趋势]

## 🎯 公开市场投资角度
[完整翻译]

## 🔬 VC/PE 视角 — 早期投资机会
[完整翻译]"""

    return call_llm(prompt, max_tokens=4000)


# ══════════════════════════════════════════════════════════════════════════════
# STARTUP SCORING
# ══════════════════════════════════════════════════════════════════════════════

def score_startup(name: str, description: str, signals: dict) -> StartupScore:
    signals_text = "\n".join([f"- {k}: {v}" for k, v in signals.items()])
    prompt = f"""VC analyst at top firm. Score startup rigorously. Most are 4-6/10.

Startup: {name}
Description: {description}
Signals: {signals_text}

JSON only:
{{"score":<0-10>,"category":"<AI Tool|AI Infra|Foundation Model|AI App|Dev Tool|Other>",
"score_rationale":"<2 specific sentences>","bull_case":"<2 sentences>","bear_case":"<1-2 sentences>",
"comparable":"<company+valuation at similar stage>","moat":"<specific advantage or none>",
"verdict":"<Watch|Invest|Pass>","time_horizon":"<6M|1Y|2Y+>"}}"""
    raw = call_llm(prompt, max_tokens=600)
    try:
        data = json.loads(raw[raw.find("{"):raw.rfind("}")+1])
        memo = (f"**{data.get('verdict')} | {data.get('time_horizon')}**\n"
                f"Bull: {data.get('bull_case')}\nBear: {data.get('bear_case')}\n"
                f"Moat: {data.get('moat')}\nComp: {data.get('comparable')}")
        return StartupScore(name=name, description=description,
                            score=float(data.get("score",5.0)), signals=signals,
                            memo=memo, category=data.get("category","Other"))
    except Exception:
        return StartupScore(name=name, description=description,
                            score=5.0, signals=signals, memo=raw[:500], category="Unknown")
