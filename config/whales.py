"""
Whale Registry — Smart Money Tracker
Organized by tab. Each entity has a CIK (for 13F), Form 4, or other data source.
"""

# ── Tab 1: Top US Institutional Investors ─────────────────────────────────────
# ── Value Investors & Activists (core long-term focus) ───────────────────────
INSTITUTIONAL = [
    {"name": "Berkshire Hathaway",    "manager": "Warren Buffett",        "cik": "0001067983", "style": "Value / Long-only",        "known_for": "Apple, OXY, AMEX, BofA. Never shorts. Decade-long holds."},
    {"name": "Baupost Group",         "manager": "Seth Klarman",          "cik": "0001060349", "style": "Deep Value / Distressed",  "known_for": "Margin of Safety author. Patient capital. Often 30-40% cash."},
    {"name": "Pershing Square",       "manager": "Bill Ackman",           "cik": "0002026053", "style": "Value Activist",           "known_for": "Chipotle, Hilton, Universal Music. Concentrated 8-12 names."},
    {"name": "Scion Asset Mgmt",      "manager": "Michael Burry",         "cik": "0001649978", "style": "Contrarian Value",        "known_for": "Predicted 2008 crash. Deep fundamental work. Often early + painful."},
    {"name": "Third Point LLC",       "manager": "Dan Loeb",              "cik": "0001040792", "style": "Value Activist / Tech",    "known_for": "Disney, Sony, Shell activism. Forces strategic change."},
    {"name": "Elliott Management",    "manager": "Paul Singer",           "cik": "0001048268", "style": "Activist / Distressed",   "known_for": "Largest activist HF. Tech companies, Argentina debt."},
    {"name": "Sachem Head Capital",   "manager": "Scott Ferguson",        "cik": "0001582090", "style": "Value Activist",           "known_for": "Ackman protégé. 8-12 concentrated value positions."},
    # ── Global Macro / Growth ─────────────────────────────────────────────────
    {"name": "Duquesne Family Office","manager": "Stanley Druckenmiller",  "cik": "0001536411", "style": "Global Macro / Growth",   "known_for": "30yr no losing year. Reads earnings momentum + macro inflections."},
    {"name": "Viking Global",         "manager": "Andreas Halvorsen",     "cik": "0001103804", "style": "L/S Equity / Tiger Cub",  "known_for": "Tiger Cub lineage. Strong tech + healthcare fundamental picks."},
    {"name": "D1 Capital Partners",   "manager": "Dan Sundheim",          "cik": "0001747057", "style": "Concentrated Growth",     "known_for": "Ex-Viking CIO. Big concentrated bets. AMZN, Datadog, Toast."},
    {"name": "Durable Capital",       "manager": "Henry Ellenbogen",      "cik": "0001798849", "style": "Long-term Growth",        "known_for": "Ex-T.Rowe. Multi-year holds. Early Duolingo, GitLab, HashiCorp."},
    {"name": "Whale Rock Capital",    "manager": "Alex Sacerdote",        "cik": "0001387322", "style": "Tech Fundamental L/S",    "known_for": "Early Shopify, Snowflake, Cloudflare. Deep tech due diligence."},
    # ── Quant / Macro Giants (13F shows long equity book, not full strategy) ──
    {"name": "Bridgewater Associates","manager": "Ray Dalio",             "cik": "0001350694", "style": "Global Macro / All-Weather","known_for": "$150B. Pure Alpha + All Weather. Principles-driven macro."},
    {"name": "Two Sigma Advisers",    "manager": "John Overdeck / David Siegel","cik": "0001478735", "style": "Quant / Systematic", "known_for": "ML + AI driven. 10,000+ positions. 13F = statistical long book."},
    {"name": "Renaissance Technologies","manager": "Peter Brown",         "cik": "0001037389", "style": "Quant / Medallion",       "known_for": "Best track record ever. Medallion +66%/yr. 13F = Instit. Equities only."},
    {"name": "D. E. Shaw & Co.",      "manager": "David Shaw",            "cik": "0001009207", "style": "Quant / Multi-strat",     "known_for": "Systematic + discretionary. Early Amazon investor. $60B AUM."},
    {"name": "Citadel Advisors",      "manager": "Ken Griffin",           "cik": "0001423053", "style": "Multi-strategy / Options","known_for": "Largest HF by revenue. Massive options flow. 27 consecutive winning years."},
    {"name": "Point72 Asset Mgmt",    "manager": "Steve Cohen",           "cik": "0001603466", "style": "Multi-strategy",          "known_for": "Former SAC Capital. Strong equity L/S. 120+ pods globally."},
    # Appaloosa: Tepper converted to family office 2019 — no longer files 13F
    {"name": "Appaloosa/Tepper",      "manager": "David Tepper",          "cik": None,         "style": "Distressed / Macro",      "known_for": "Bought banks in 2009 for 10x. Family office since 2019. Track via media."},
    # Jane Street & investment banks: market makers / prop desks — not value investors
    # Their 13F filings reflect client flow + hedges, not investment conviction
]

# ── Tab 2: AI / Tech Focused Funds ────────────────────────────────────────────
AI_FUNDS = [
    # Situational Awareness: correct CIK is 0002045724, files 13F — latest 2026-05-18
    {"name": "Situational Awareness LP","manager": "Leopold Aschenbrenner","cik": "0002045724", "style": "AI Infrastructure",       "known_for": "Ex-OpenAI. $13.67B AUM. AI compute = energy bottleneck thesis. BTC miners, NVDA puts."},
    {"name": "ARK Investment Mgmt",    "manager": "Cathie Wood",           "cik": "0001579982", "style": "Disruptive Innovation",   "known_for": "TSLA early, COIN early. Publishes ALL trades DAILY."},
    {"name": "Coatue Management",      "manager": "Philippe Laffont",      "cik": "0001336528", "style": "Tech L/S / Tiger Cub",   "known_for": "Alibaba early, Snap, Lyft. Strong China tech."},
    {"name": "Tiger Global",           "manager": "Chase Coleman",         "cik": "0001167483", "style": "Growth / Global Tech",   "known_for": "Facebook, LinkedIn, Spotify early. VC + public."},
    {"name": "a16z (Andreessen)",      "manager": "Marc Andreessen",       "cik": "0001569190", "style": "VC / Crypto",            "known_for": "Coinbase, OpenSea, Solana. $7B+ crypto fund."},
    {"name": "Founders Fund",          "manager": "Peter Thiel",           "cik": None,         "style": "VC / Contrarian",        "known_for": "SpaceX, Palantir, Anduril. Anti-consensus."},
    {"name": "Sequoia Capital",        "manager": "Roelof Botha",          "cik": "0001783398", "style": "VC / Global",            "known_for": "Apple, Google, OpenAI, Stripe early."},
    {"name": "Dragoneer Investment",   "manager": "Marc Stad",             "cik": "0001413754", "style": "Growth / SaaS",          "known_for": "Snowflake, Nubank, Roblox early backer."},
]

# ── Tab 3: Asia Whales ────────────────────────────────────────────────────────
ASIA_WHALES = [
    # Hillhouse stopped US 13F filings in 2021 (went private / reduced US exposure)
    {"name": "Hillhouse Capital",      "manager": "Zhang Lei (张磊)",      "cik": "0001762304", "style": "Long-term / China+Global", "known_for": "JD.com, Meituan, CATL early. Yale endowment style. Last 13F: Q1 2021."},
    {"name": "SoftBank Vision Fund",   "manager": "Masayoshi Son",         "cik": "0001640251", "style": "Tech Moonshots",          "known_for": "Arm, Alibaba. Now: $100B+ OpenAI ecosystem bets."},
    {"name": "GIC Singapore",          "manager": "GIC Private Ltd",       "cik": "0001641614", "style": "Sovereign Wealth",        "known_for": "$770B+ AUM. Patient capital. Infrastructure focus."},
    {"name": "Temasek Holdings",       "manager": "Singapore Govt",        "cik": None,         "style": "Sovereign Wealth",        "known_for": "$300B AUM. Grab, GoTo, ByteDance, Alibaba exposure."},
    {"name": "CIC (China Inv Corp)",   "manager": "Peng Chun",             "cik": None,         "style": "Sovereign Wealth",        "known_for": "$1.3T AUM. China's sovereign fund. US property + PE."},
    {"name": "Alibaba / DAMO",         "manager": "Jack Ma / AI Team",     "cik": None,         "style": "Strategic / AI",          "known_for": "Investing in AI startups globally. Ant Group."},
    {"name": "DST Global",             "manager": "Yuri Milner",           "cik": "0001548144", "style": "Growth / Global Tech",   "known_for": "Facebook $200M (10x). Twitter, Airbnb, Spotify early."},
    {"name": "Keystone Capital (HK)",  "manager": "Various HK Family Ofc", "cik": None,         "style": "Family Office",           "known_for": "Tracks HK ultra-HNW. Bellwether for Asia flow."},
]

# ── Tab 4: Crypto Whales ──────────────────────────────────────────────────────
CRYPTO_WHALES = [
    {"name": "Justin Sun (孙宇晨)",    "manager": "self",   "type": "individual",        "wallets_eth": "0x3DdfA8eC3052539b6C9549F12cEA2C295cfF5296", "known_for": "TRON founder. Massive BTC/ETH. Buys attention intentionally.", "twitter": "@justinsuntron"},
    {"name": "World Liberty Financial","manager": "Trump",  "type": "political/crypto",  "wallets_eth": "", "known_for": "Trump family. $1.55B token sales. USD1 stablecoin. Policy barometer.", "twitter": "@worldlibertyfi"},
    {"name": "Michael Saylor/MSTR",    "manager": "Saylor", "type": "institutional BTC", "wallets_eth": "", "known_for": "560k+ BTC held. Leveraged via debt. Corporate BTC treasury pioneer.", "twitter": "@saylor"},
    {"name": "a16z Crypto",            "manager": "a16z",   "type": "institutional",     "wallets_eth": "", "known_for": "Solana, Coinbase, Uniswap. $7.6B across 4 crypto funds.", "twitter": "@a16zcrypto"},
    {"name": "Paradigm",               "manager": "Matt Huang","type": "crypto VC",      "wallets_eth": "", "known_for": "Coinbase, FTX (bad), Uniswap, Optimism. Most technical crypto VC.", "twitter": "@paradigm"},
    {"name": "Binance/CZ",             "manager": "CZ",     "type": "exchange/whale",    "wallets_eth": "", "known_for": "Largest crypto exchange. BNB, BUSD. Post-SEC settlement rebuilding.", "twitter": "@cz_binance"},
    {"name": "Pantera Capital",        "manager": "Dan Morehead","type": "crypto fund",  "wallets_eth": "", "known_for": "First dedicated US Bitcoin fund (2013). 66,000% return on BTC.", "twitter": "@panteracapital"},
    {"name": "Galaxy Digital",         "manager": "Mike Novogratz","type": "institutional","wallets_eth":"", "known_for": "Listed crypto merchant bank. BTC bull. Luna call haunts him.", "twitter": "@novogratz"},
]

# ── Tab 5: Market Makers ──────────────────────────────────────────────────────
MARKET_MAKERS = [
    {"name": "Wintermute",       "type": "crypto MM",    "reputation": "Compliant",    "known_for": "$5B+ daily volume. Institutional OTC. Wallet → exchange = big trade signal.", "twitter": "@wintermute_t",  "controversy": "None"},
    {"name": "DWF Labs",         "type": "crypto MM/VC", "reputation": "Controversial","known_for": "Top 5 by volume. Pre-listing accumulation visible on-chain.", "twitter": "@DWFLabs",       "controversy": "WSJ 2023 wash trading allegation"},
    {"name": "Jump Crypto",      "type": "HFT/MM",       "reputation": "Traditional",  "known_for": "Wormhole, Terra. HFT background. Repaid $320M Wormhole hack.", "twitter": "@JumpCryptoHQ",  "controversy": "Terra/LUNA exposure"},
    {"name": "Virtu Financial",  "type": "HFT/MM (equities)","reputation": "Public",   "known_for": "Public HFT firm (VIRT). Profits from volatility. Penny wide bid-ask.", "twitter": "@VirtuFinancial","controversy": "None"},
    {"name": "Jane Street",      "type": "Options MM",   "reputation": "Elite quant",  "known_for": "ETF arbitrage kings. Biggest options market maker. Hires top quants.", "twitter": None,             "controversy": "None (private)"},
    {"name": "Susquehanna (SIG)","type": "Options MM",   "reputation": "Top tier",     "known_for": "Early TikTok investor via ByteDance. Giant options book.", "twitter": None,             "controversy": "TikTok investment scrutiny"},
    {"name": "Alameda (defunct)","type": "FTX affiliate","reputation": "Collapsed",    "known_for": "Context only: how market maker collapse spreads contagion.", "twitter": None,             "controversy": "Fraud — FTX collapse 2022"},
]

# ── Tab 6: Political Money ────────────────────────────────────────────────────
POLITICAL_MONEY = [
    {"name": "Nancy Pelosi",         "party": "D", "committee": "Armed Services (past)", "known_for": "NVDA calls before AI boom. MSFT, GOOG, AAPL. Highest profile trader.", "source": "Capitol Trades"},
    {"name": "Dan Crenshaw",         "party": "R", "committee": "Homeland Security",    "known_for": "Defense + energy trades. Cybersecurity committee access.", "source": "Capitol Trades"},
    {"name": "Michael McCaul",       "party": "R", "committee": "Foreign Affairs",      "known_for": "Defense stocks correlated with committee votes.", "source": "Capitol Trades"},
    {"name": "Tommy Tuberville",     "party": "R", "committee": "Armed Services",       "known_for": "Frequent defense contractor trades. Holding $1M-$50M in stock.", "source": "Capitol Trades"},
    {"name": "Trump Family/WLF",     "party": "R", "committee": "Executive Branch",     "known_for": "DJT stock + World Liberty Financial + USD1. Policy=portfolio.", "source": "Disclosures"},
    {"name": "Senate Finance Mbrs",  "party": "Both","committee": "Finance",            "known_for": "Watch for financial stock trades before rate decisions.", "source": "Senate STOCK Act"},
    {"name": "House Energy Mbrs",    "party": "Both","committee": "Energy & Commerce",  "known_for": "Oil/gas + utilities trades before energy legislation.", "source": "House STOCK Act"},
]

# ── Additional Sources (Tab 7+ / supplementary) ───────────────────────────────
ADDITIONAL_SOURCES = {
    "Form 4 (Insider Trades)": {
        "url": "https://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=14&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=&xp=1&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=100&page=1",
        "description": "SEC Form 4 insider buying — when CEOs buy their own stock it's a strong signal",
    },
    "Dataroma Superinvestors": {
        "url": "https://www.dataroma.com/m/home.php",
        "description": "Aggregates 13F data for 70+ superinvestors in one place",
    },
    "Unusual Whales (Options Flow)": {
        "url": "https://unusualwhales.com",
        "description": "Unusual options activity often precedes big moves — smart money via options",
    },
    "WhaleWisdom": {
        "url": "https://whalewisdom.com",
        "description": "13F aggregator — tracks quarter-over-quarter changes easily",
    },
}

# Master registry
ALL_WHALES = {
    "institutional":   INSTITUTIONAL,
    "ai_funds":        AI_FUNDS,
    "asia_whales":     ASIA_WHALES,
    "crypto_whales":   CRYPTO_WHALES,
    "market_makers":   MARKET_MAKERS,
    "political_money": POLITICAL_MONEY,
}

TAB_LABELS = {
    "institutional":   "🏦 Top US Institutions (13F)",
    "ai_funds":        "🤖 AI/Tech Focused Funds",
    "asia_whales":     "🐉 Asia Whales",
    "crypto_whales":   "🐋 Crypto Whales",
    "market_makers":   "⚡ Market Makers",
    "political_money": "🏛️ Political Money",
}

ARK_FUNDS = {
    "ARKK": "https://ark-funds.com/wp-content/uploads/funds-etf-csv/ARK_INNOVATION_ETF_ARKK_HOLDINGS.csv",
    "ARKQ": "https://ark-funds.com/wp-content/uploads/funds-etf-csv/ARK_AUTONOMOUS_TECHNOLOGY_&_ROBOTICS_ETF_ARKQ_HOLDINGS.csv",
}

SEC_13F_ENTITIES = {
    e["name"]: e["cik"]
    for tab in [INSTITUTIONAL, AI_FUNDS, ASIA_WHALES]
    for e in tab if e.get("cik")
}
