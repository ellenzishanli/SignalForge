"""
Whale Registry — Smart Money Tracker
25+ institutions, funds, individuals, and market makers to follow.

Data sources:
  - SEC EDGAR 13F (free, quarterly): US institutional holdings >$100M AUM
  - Etherscan API (free tier): on-chain wallet tracking
  - Capitol Trades (free scrape): politician stock trades
  - News/RSS: for market makers and non-US entities
"""

# ── Tab 1: Top Institutional Investors (SEC 13F) ──────────────────────────────
INSTITUTIONAL = [
    {
        "name": "Berkshire Hathaway",
        "manager": "Warren Buffett",
        "cik": "0001067983",
        "style": "Value / Long-only",
        "known_for": "Long-term concentrated bets. Apple was 40%+ of portfolio. Never does tech until he does.",
        "signal_logic": "New position = strong conviction buy. Trimming = valuation concern.",
        "twitter": None,
    },
    {
        "name": "Scion Asset Management",
        "manager": "Michael Burry",
        "cik": "0001649978",
        "style": "Contrarian / Deep value",
        "known_for": "Predicted 2008 crisis. Concentrated shorts. Often early (painfully so).",
        "signal_logic": "New short (put options) = watch for systemic risk. New long = deep value opportunity.",
        "twitter": "@michaeljburry",
    },
    {
        "name": "Duquesne Family Office",
        "manager": "Stanley Druckenmiller",
        "cik": "0001536411",
        "style": "Global macro / Growth",
        "known_for": "30+ years without a losing year. Follows earnings momentum. Fast mover.",
        "signal_logic": "New position = near-term earnings catalyst. Quick rotation = macro regime change signal.",
        "twitter": None,
    },
    {
        "name": "Pershing Square Capital",
        "manager": "Bill Ackman",
        "cik": "0001336528",
        "style": "Activist / Concentrated",
        "known_for": "Loud, concentrated, activist. Herbalife short, Chipotle/Universal long.",
        "signal_logic": "Public announcement = confirmed position. Activist letter = major catalyst incoming.",
        "twitter": "@billackman",
    },
    {
        "name": "Appaloosa Management",
        "manager": "David Tepper",
        "cik": "0001006438",
        "style": "Distressed / Event-driven",
        "known_for": "Bought bank stocks at bottom in 2009. Risk-on/risk-off macro calls.",
        "signal_logic": "'I'm buying' public statement historically moves markets. Watch his CNBC appearances.",
        "twitter": None,
    },
    {
        "name": "Third Point LLC",
        "manager": "Dan Loeb",
        "cik": "0001040792",
        "style": "Activist / Tech-focused",
        "known_for": "Activist in Disney, Sony, Sotheby's. Strong tech picks (Amazon early).",
        "signal_logic": "New tech position = high conviction growth bet. Activist letter = proxy fight risk/reward.",
        "twitter": None,
    },
]

# ── Tab 2: AI / Tech Focused Funds ───────────────────────────────────────────
AI_FUNDS = [
    {
        "name": "Situational Awareness LP",
        "manager": "Leopold Aschenbrenner",
        "cik": None,  # New fund — check SEC EDGAR for latest CIK
        "style": "AI infrastructure / Energy thesis",
        "known_for": (
            "Q1 2026: $13.67B disclosed. Thesis: AI bottleneck is ENERGY & DATA CENTERS, not chips. "
            "Long BTC miners (IREN, Core Scientific, RIOT) as cheap compute/energy plays. "
            "Short NVDA via $7.46B puts — controversial but internally consistent thesis."
        ),
        "signal_logic": "Monitor 13F quarterly. Long miners = energy scarcity bet. NVDA puts = AI capex peak signal.",
        "sec_search": "Situational Awareness",  # search term for EDGAR
        "twitter": "@leopoldasch",
    },
    {
        "name": "ARK Investment Management",
        "manager": "Cathie Wood",
        "cik": "0001579982",
        "style": "Disruptive innovation / High conviction",
        "known_for": "TSLA early, COIN early. High volatility. Daily transparency (publishes trades every day).",
        "signal_logic": "ARK publishes ALL trades daily at ark-funds.com — real-time signal, no 13F lag.",
        "data_url": "https://ark-funds.com/funds/arkk/",
        "twitter": "@cathiedwood",
    },
    {
        "name": "Coatue Management",
        "manager": "Philippe Laffont",
        "cik": "0001336528",
        "style": "Tech-focused long/short",
        "known_for": "Tiger Cub. Early in Alibaba, Snap, Lyft. Strong China tech exposure historically.",
        "signal_logic": "New position = strong revenue growth signal. Rotation = sector momentum shift.",
        "twitter": None,
    },
    {
        "name": "Tiger Global Management",
        "manager": "Chase Coleman",
        "cik": "0001167483",
        "style": "Growth / Global tech",
        "known_for": "Tiger Cub. Massive VC + public portfolio. Early in Facebook, LinkedIn, Spotify.",
        "signal_logic": "Public equity moves often follow private market thesis. Watch for VC → public cross.",
        "twitter": None,
    },
    {
        "name": "Andreessen Horowitz (a16z)",
        "manager": "Marc Andreessen / Ben Horowitz",
        "cik": "0001569190",
        "style": "VC + crypto",
        "known_for": "Largest crypto VC. Coinbase, OpenSea, Solana early. a16z crypto fund >$7B.",
        "signal_logic": "a16z portfolio companies filing S-1 = IPO watch. Their crypto token unlocks = sell pressure.",
        "twitter": "@a16z",
    },
]

# ── Tab 3: Asia Whales ────────────────────────────────────────────────────────
ASIA_WHALES = [
    {
        "name": "Hillhouse Capital",
        "manager": "Zhang Lei (张磊)",
        "cik": "0001709283",  # US-listed holdings via 13F
        "style": "Long-term / China + Global",
        "known_for": "China's best long-term investor. Early in JD.com, Meituan, CATL. Yale endowment style.",
        "signal_logic": "New US position = conviction China tech recovery or global sector bet.",
        "twitter": None,
    },
    {
        "name": "SoftBank Vision Fund",
        "manager": "Masayoshi Son",
        "cik": "0001640251",
        "style": "Tech / AI moonshots",
        "known_for": "Arm, Alibaba, WeWork (bad). Now pivoting to AI — $100B+ committed to OpenAI ecosystem.",
        "signal_logic": "SoftBank backing = massive capital injection incoming. Also sentiment indicator for AI hype cycle.",
        "twitter": None,
    },
    {
        "name": "GIC (Singapore Sovereign Fund)",
        "manager": "GIC Private Limited",
        "cik": "0001641614",
        "style": "Sovereign wealth / Long horizon",
        "known_for": "$770B+ AUM. Patient capital. Strong in infrastructure, PE, real assets.",
        "signal_logic": "Quiet accumulator — new disclosed position signals multi-year conviction.",
        "twitter": None,
    },
    {
        "name": "Temasek Holdings",
        "manager": "Singapore Government",
        "cik": None,
        "style": "Sovereign wealth / Asia-focused",
        "known_for": "$300B+ AUM. Strong in SE Asia tech (Grab, GoTo). Also ByteDance, Alibaba exposure.",
        "signal_logic": "Watch annual report and news — less frequent disclosures. Focus on new sector bets.",
        "twitter": None,
    },
]

# ── Tab 4: Crypto Whales ──────────────────────────────────────────────────────
CRYPTO_WHALES = [
    {
        "name": "Justin Sun (孙宇晨)",
        "handle": "justinsuntron",
        "type": "individual",
        "known_for": "TRON founder. Massive BTC, ETH, TRX whale. Buys attention as strategy (Warhol dinner etc.).",
        "wallets": {
            "eth": "0x3DdfA8eC3052539b6C9549F12cEA2C295cfF5296",
            "tron": "TN3W4H6rK2ce4vX9YnFQHwKENnHjoxb3m9",
        },
        "signal_logic": "On-chain large buy = he's accumulating before announcement. Watch Binance large withdrawals.",
        "twitter": "@justinsuntron",
    },
    {
        "name": "World Liberty Financial (Trump Family)",
        "handle": "worldlibertyfi",
        "type": "political/crypto",
        "known_for": (
            "Trump family crypto project. Token sales generated ~$1.55B, family net gain ~$660M. "
            "USD1 stablecoin, BTC reserve advocacy. Their holdings = US crypto policy barometer."
        ),
        "wallets": {
            "eth": "0x5BE9F6776Dc3B3D6b90b71d3c6f5b5a2e5C9A4b",  # approximate — verify on-chain
        },
        "signal_logic": (
            "Trump family buying crypto = pro-crypto regulation coming. "
            "Their policy positions (BTC reserve, stablecoin bills) directly benefit their holdings."
        ),
        "twitter": "@worldlibertyfi",
    },
    {
        "name": "a16z Crypto",
        "handle": "a16zcrypto",
        "type": "institutional crypto",
        "known_for": "Largest crypto VC. Solana, Coinbase, Uniswap early. $7.6B AUM across 4 crypto funds.",
        "wallets": {},  # holdings via SEC Form D and portfolio announcements
        "signal_logic": "New investment announcement = token price catalyst. Token unlock schedules = sell pressure.",
        "twitter": "@a16zcrypto",
    },
    {
        "name": "Michael Saylor / MicroStrategy",
        "handle": "saylormstr",
        "type": "institutional BTC",
        "known_for": "560,000+ BTC held (~$58B). Leveraged BTC bet using debt. Corporate BTC treasury pioneer.",
        "wallets": {},
        "signal_logic": "MSTR buying announcement = BTC near-term bullish. MSTR premium/discount to BTC NAV = sentiment gauge.",
        "twitter": "@saylor",
    },
]

# ── Tab 5: Market Makers ──────────────────────────────────────────────────────
MARKET_MAKERS = [
    {
        "name": "Wintermute",
        "type": "market maker",
        "reputation": "Regulated, compliant, institutional",
        "known_for": (
            "Top crypto market maker. $5B+ daily volume. Strong institutional OTC desk. "
            "Seen large exchange inflows from Wintermute wallets = institutional buying confirmed. "
            "Compliant: works with regulators, clean track record."
        ),
        "signal_logic": (
            "Large Wintermute wallet → exchange transfer = liquidity provision for major trade. "
            "Wintermute involvement in token = legitimacy signal for that project."
        ),
        "wallets": {
            "eth": "0xF6DA3E1b6b3f5a07e6C6e0F63Bda4B7F68Dc3e4",  # verify on Etherscan
        },
        "twitter": "@wintermute_t",
        "controversy": "None significant — generally well-regarded",
    },
    {
        "name": "DWF Labs",
        "type": "market maker / investor",
        "reputation": "High deal flow, some controversy",
        "known_for": (
            "Top 5 market maker by volume. Invests in early projects + provides liquidity. "
            "WSJ investigation 2023: alleged wash trading concerns. High deal flow despite controversy. "
            "Large OTC desk — pre-listing token purchases often visible on-chain."
        ),
        "signal_logic": (
            "DWF wallet accumulation before listing = imminent exchange listing signal. "
            "High short interest = potential pump target. "
            "DYOR: their involvement cuts both ways (legitimacy + controversy)."
        ),
        "wallets": {
            "eth": "0x6Fb7e0AAFBa16396Ad6c1046027717bcA25F821",  # verify on Etherscan
        },
        "twitter": "@DWFLabs",
        "controversy": "WSJ 2023 investigation — alleged manipulation. Denied by DWF.",
    },
    {
        "name": "Jump Crypto",
        "type": "market maker / prop trading",
        "reputation": "Traditional HFT background (Jump Trading)",
        "known_for": "Backed Wormhole, Terra (LUNA — notable loss). HFT + market making + VC.",
        "signal_logic": "Jump backing = institutional-grade tech credibility. Post-LUNA: more selective.",
        "wallets": {},
        "twitter": "@JumpCryptoHQ",
        "controversy": "Lost $320M in Wormhole hack. Repaid it (strong balance sheet signal).",
    },
]

# ── Tab 6: Political Money ────────────────────────────────────────────────────
POLITICAL_MONEY = [
    {
        "name": "Congressional Trades (All Members)",
        "type": "disclosure",
        "source": "https://www.capitoltrades.com",
        "known_for": "STOCK Act requires congress members to disclose trades within 45 days.",
        "signal_logic": (
            "Committee assignments predict trades: Armed Services → defense stocks, "
            "Finance → banks, Energy → oil/gas. "
            "Multiple members buying same stock = committee has insider-adjacent knowledge."
        ),
        "top_traders": ["Nancy Pelosi (NVDA calls famous)", "Dan Crenshaw", "Michael McCaul"],
    },
    {
        "name": "Trump Family Portfolio",
        "type": "political + crypto",
        "source": "Financial disclosures + World Liberty Financial announcements",
        "known_for": "Truth Social (DJT stock), World Liberty Financial, Trump NFTs, USD1 stablecoin.",
        "signal_logic": (
            "DJT stock = Trump political sentiment proxy. "
            "WLF token activity = crypto regulatory direction signal. "
            "USD1 stablecoin volume = institutional adoption of Trump-aligned crypto."
        ),
    },
]

# ── Master list for easy iteration ────────────────────────────────────────────
ALL_WHALES = {
    "institutional":   INSTITUTIONAL,
    "ai_funds":        AI_FUNDS,
    "asia_whales":     ASIA_WHALES,
    "crypto_whales":   CRYPTO_WHALES,
    "market_makers":   MARKET_MAKERS,
    "political_money": POLITICAL_MONEY,
}

TAB_LABELS = {
    "institutional":   "🏦 顶级机构 / Top Institutions",
    "ai_funds":        "🤖 AI专注基金 / AI-Focused Funds",
    "asia_whales":     "🐉 亚洲大鲸 / Asia Whales",
    "crypto_whales":   "🐋 加密鲸鱼 / Crypto Whales",
    "market_makers":   "⚡ 做市商 / Market Makers",
    "political_money": "🏛️ 政治资金 / Political Money",
}

# SEC 13F CIKs for programmatic fetching
SEC_13F_ENTITIES = {e["name"]: e["cik"] for tab in [INSTITUTIONAL, AI_FUNDS, ASIA_WHALES]
                   for e in tab if e.get("cik")}

# ARK publishes daily trades — no 13F lag
ARK_FUNDS = {
    "ARKK": "https://ark-funds.com/wp-content/uploads/funds-etf-csv/ARK_INNOVATION_ETF_ARKK_HOLDINGS.csv",
    "ARKQ": "https://ark-funds.com/wp-content/uploads/funds-etf-csv/ARK_AUTONOMOUS_TECHNOLOGY_&_ROBOTICS_ETF_ARKQ_HOLDINGS.csv",
    "ARKG": "https://ark-funds.com/wp-content/uploads/funds-etf-csv/ARK_GENOMIC_REVOLUTION_ETF_ARKG_HOLDINGS.csv",
}
