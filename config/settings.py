# Redirect to universe.py — settings.py kept for backward compat
from config.universe import (
    AI_BASKET_STOCKS, AI_ETFS, DASHBOARD_CORE,
    STOCK_SCREEN, SIGNAL_WEIGHTS, SECTORS, HIDDEN_GEMS
)
AI_ETFS = [t for t, _ in AI_ETFS]  # strip names for legacy callers

# ============================================================
# 系统配置 / System Configuration
# ============================================================

# AI 篮子股票 + ETF 完整列表 / Full AI basket: stocks + ETFs
AI_BASKET_STOCKS = [
    # ── AI 芯片 / AI Chips ──────────────────────────────────
    "NVDA",   # NVIDIA — GPU 霸主 / GPU leader
    "AMD",    # AMD — 挑战 NVIDIA 的芯片 / NVIDIA challenger
    "INTC",   # Intel — 转型中的芯片巨头 / Transforming chip giant
    "AVGO",   # Broadcom — AI 网络芯片 / AI networking chips
    "MRVL",   # Marvell — 定制 AI 芯片 / Custom AI silicon
    "ARM",    # ARM Holdings — AI 芯片架构 / AI chip architecture
    "QCOM",   # Qualcomm — 端侧 AI / On-device AI
    # ── 云平台 / Cloud & AI Platforms ───────────────────────
    "MSFT",   # Microsoft — Azure + Copilot
    "GOOGL",  # Alphabet — Gemini + TPU + Search AI
    "AMZN",   # Amazon — AWS Bedrock + Trainium
    "META",   # Meta — Llama + AI infra
    "ORCL",   # Oracle — OCI AI cloud, rapid growth
    "IBM",    # IBM — 企业 AI / Enterprise AI (watsonx)
    # ── 数据 / MLOps / Data & MLOps ─────────────────────────
    "SNOW",   # Snowflake — AI data cloud
    "DDOG",   # Datadog — AI observability
    "MDB",    # MongoDB — AI-native database
    "NET",    # Cloudflare — AI inference at edge
    "PLTR",   # Palantir — AI for enterprise & government
    "S",      # SentinelOne — AI cybersecurity
    "CRWD",   # CrowdStrike — AI-powered security
    # ── AI 应用层 / AI Application Layer ────────────────────
    "CRM",    # Salesforce — Einstein AI + Agentforce
    "NOW",    # ServiceNow — AI workflow automation
    "ADBE",   # Adobe — Firefly generative AI
    "AAPL",   # Apple — on-device AI / Apple Intelligence
    "TSLA",   # Tesla — FSD + Dojo supercomputer
    # ── AI 纯玩家 / AI Pure-plays ────────────────────────────
    "SOUN",   # SoundHound — voice AI
    "AI",     # C3.ai — enterprise AI software
    "PATH",   # UiPath — AI-powered RPA
    "BBAI",   # BigBear.ai — defense AI
]

# AI 主题 ETF / AI-themed ETFs
AI_ETFS = [
    "BOTZ",   # Global X Robotics & AI ETF
    "AIQ",    # Global X AI & Technology ETF
    "ROBO",   # ROBO Global Robotics & Automation
    "ARKQ",   # ARK Autonomous Tech & Robotics ETF
    "IRBO",   # iShares Robotics and AI Multisector ETF
    "CHAT",   # Roundhill Generative AI & Technology ETF
    "WEBL",   # Direxion Daily Dow Jones Internet Bull 3X (高风险/high risk)
    "QQQ",    # Invesco QQQ — Nasdaq 100 proxy
    "SOXX",   # iShares Semiconductor ETF
    "SMH",    # VanEck Semiconductor ETF
]

# 股票折扣筛选阈值 / Stock discount screener thresholds
# 放宽标准以找到更多机会 / Relaxed to surface more opportunities
STOCK_SCREEN = {
    "min_consecutive_down_days": 2,     # 连续下跌天数 / Consecutive red days (lowered from 3)
    "min_single_day_drop_pct":  -3.0,   # 单日跌幅 / Single-day drop % (lowered from -4%)
    "min_growth_1m_pct":         3.0,   # 过去1月涨幅 / 1M return threshold (lowered)
    "min_growth_6m_pct":         5.0,   # 过去6月涨幅 / 6M return threshold (lowered)
    "min_growth_1y_pct":         8.0,   # 过去1年涨幅 / 1Y return threshold (lowered)
}

# Dashboard 展示：不管有没有触发信号，都展示这些核心股票
# Always show these in the dashboard regardless of signal triggers
DASHBOARD_CORE = [
    "NVDA", "AMD", "MSFT", "GOOGL", "AMZN", "META",
    "PLTR", "NET", "SNOW", "AVGO", "ARM", "INTC",
]

# 信号权重 / Signal scoring weights (for startup scoring)
SIGNAL_WEIGHTS = {
    "github_growth":   0.25,
    "vc_backing":      0.25,
    "developer_buzz":  0.20,
    "hiring_growth":   0.15,
    "revenue_signal":  0.10,
    "twitter_discuss": 0.05,
}
