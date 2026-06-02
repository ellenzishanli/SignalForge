"""
Stock Universe — organized by sector.
Beyond AI: covers clean energy, nuclear, defense, biotech, fintech, storage, industrials.
Hidden gems: small/mid-cap, under-analyst-coverage, recent IPOs.
"""

# ── Sector Watchlists ──────────────────────────────────────────────────────────

SECTORS = {

    "AI & Compute Infrastructure": [
        "NVDA", "AMD", "INTC", "AVGO", "MRVL", "ARM", "QCOM",
        "SMCI",  # Super Micro Computer — AI server builder
        "CRUS",  # Cirrus Logic — edge AI chips
        "LSCC",  # Lattice Semiconductor — low-power FPGAs
    ],

    "Cloud & Software Platform": [
        "MSFT", "GOOGL", "AMZN", "META", "ORCL", "CRM", "NOW",
        "SNOW", "DDOG", "MDB", "NET", "PLTR",
        "GTLB",  # GitLab — DevOps platform
        "HUBS",  # HubSpot — CRM AI
        "CFLT",  # Confluent — data streaming
    ],

    "Clean Energy & Solar": [
        "ENPH",  # Enphase Energy — solar microinverters
        "SEDG",  # SolarEdge — solar optimizers
        "FSLR",  # First Solar — utility-scale solar
        "RUN",   # Sunrun — residential solar
        "ARRY",  # Array Technologies — solar tracking
        "CSIQ",  # Canadian Solar
        "NEE",   # NextEra — largest US renewable utility
        "BEP",   # Brookfield Renewable Partners
        "CWEN",  # Clearway Energy
        "PLUG",  # Plug Power — hydrogen fuel cells
    ],

    "Nuclear & Grid Storage": [
        "CEG",   # Constellation Energy — largest US nuclear operator
        "VST",   # Vistra Energy — nuclear + thermal
        "ETR",   # Entergy — nuclear utility
        "NNE",   # Nano Nuclear Energy (small modular reactors)
        "OKLO",  # Oklo — micro nuclear reactors (Sam Altman backed)
        "SMR",   # NuScale Power — small modular reactors
        "NRGV",  # Energy Vault — gravity energy storage
        "STEM",  # Stem Inc — AI-driven grid storage
        "FLUX",  # Flux Power — lithium battery packs
        "FREYR", # FREYR Battery — EV battery manufacturing
    ],

    "Defense & Aerospace": [
        "LMT",   # Lockheed Martin — F-35, missiles
        "RTX",   # Raytheon — defense electronics
        "NOC",   # Northrop Grumman — stealth aircraft
        "GD",    # General Dynamics — navy, IT services
        "LHX",   # L3Harris — tactical comms
        "KTOS",  # Kratos Defense — drones, hypersonics
        "RKLB",  # Rocket Lab — small satellite launch
        "ASTS",  # AST SpaceMobile — space-based broadband
        "LUNR",  # Intuitive Machines — NASA lunar missions
        "SPCE",  # Virgin Galactic — commercial spaceflight
        "JOBY",  # Joby Aviation — eVTOL air taxi
        "ACHR",  # Archer Aviation — eVTOL
    ],

    "Biotech & Healthcare AI": [
        "ISRG",  # Intuitive Surgical — robotic surgery
        "IONS",  # Ionis Pharmaceuticals — RNA drugs
        "RXRX",  # Recursion Pharmaceuticals — AI drug discovery
        "SDGR",  # Schrödinger — AI molecular simulation
        "EXAI",  # Exscientia — AI pharma
        "NVAX",  # Novavax — mRNA vaccines
        "VERV",  # Verve Therapeutics — gene editing heart disease
        "CRSP",  # CRISPR Therapeutics
        "BEAM",  # Beam Therapeutics — base editing
        "PACB",  # Pacific Biosciences — long-read DNA sequencing
    ],

    "Fintech & Crypto Infrastructure": [
        "SQ",    # Block (Square) — payments + Bitcoin
        "AFRM",  # Affirm — BNPL
        "UPST",  # Upstart — AI lending
        "SOFI",  # SoFi Technologies — digital bank
        "HOOD",  # Robinhood — retail investing
        "COIN",  # Coinbase — crypto exchange
        "MSTR",  # MicroStrategy — Bitcoin treasury
        "MARA",  # Marathon Digital — Bitcoin mining
        "RIOT",  # Riot Platforms — Bitcoin mining
        "CLSK",  # CleanSpark — Bitcoin mining + energy
    ],

    "Robotics & Autonomous Systems": [
        "TSLA",  # Tesla — FSD + Optimus robot
        "PATH",  # UiPath — software robotics (RPA)
        "IRBT",  # iRobot — consumer robotics
        "NNDM",  # Nano Dimension — 3D printing + AI manufacturing
        "XPOF",  # Xponential Fitness (adjacent to AI fitness tech)
        "VRNS",  # Varonis — data security AI
        "SOUN",  # SoundHound — voice AI
        "BBAI",  # BigBear.ai — defense analytics
        "GFAI",  # Guardforce AI — security robots
    ],

    "Semiconductor Equipment & Materials": [
        "AMAT",  # Applied Materials — chip manufacturing equipment
        "KLAC",  # KLA Corporation — process control
        "LRCX",  # Lam Research — etch + deposition
        "ASML",  # ASML — EUV lithography monopoly
        "ONTO",  # Onto Innovation — optical metrology
        "ACMR",  # ACM Research — wafer cleaning
        "CAMT",  # Camtek — inspection for advanced packaging
        "COHU",  # Cohu — semiconductor test handlers
        "UCTT",  # Ultra Clean Holdings — chip fab components
    ],

    "Data Infrastructure & Cybersecurity": [
        "PSTG",  # Pure Storage — all-flash storage
        "NTAP",  # NetApp — hybrid cloud storage
        "WDC",   # Western Digital — HDDs + NAND flash
        "STX",   # Seagate — hard drives for AI data centers
        "CRWD",  # CrowdStrike — AI cybersecurity
        "S",     # SentinelOne — AI endpoint security
        "PANW",  # Palo Alto Networks — cybersecurity platform
        "ZS",    # Zscaler — cloud security
        "TENB",  # Tenable — vulnerability management
        "QLYS",  # Qualys — cloud security
    ],
}

# ══════════════════════════════════════════════════════════════════════════════
# AI INFRASTRUCTURE VALUE CHAIN
# ══════════════════════════════════════════════════════════════════════════════
# The full "picks-and-shovels" stack behind the AI buildout — organized top-of-
# stack (closest to the chip) down to the power layer that feeds it. This is the
# universe to hunt the "next Micron" in: companies still at fair/moderate
# valuations with strong growth and real analyst upside, BEFORE they re-rate.
# Each entry is (ticker, readable name). Ordered by layer.

AI_INFRASTRUCTURE = {
    "🧠 Compute Silicon — GPUs / Accelerators / CPUs": [
        ("NVDA", "Nvidia"),
        ("AMD",  "Advanced Micro Devices"),
        ("AVGO", "Broadcom"),
        ("ARM",  "Arm Holdings"),
        ("MRVL", "Marvell Technology"),
        ("ALAB", "Astera Labs — AI connectivity silicon"),
        ("INTC", "Intel"),
        ("QCOM", "Qualcomm"),
    ],

    "🏭 Foundry & Semi Equipment — the factories": [
        ("TSM",  "Taiwan Semiconductor (TSMC)"),
        ("ASML", "ASML — EUV lithography monopoly"),
        ("AMAT", "Applied Materials"),
        ("LRCX", "Lam Research"),
        ("KLAC", "KLA Corporation"),
    ],

    "💾 Memory & Storage": [
        ("MU",   "Micron Technology — HBM for AI"),
        ("WDC",  "Western Digital"),
        ("STX",  "Seagate Technology"),
        ("SNDK", "SanDisk — NAND flash"),
    ],

    "🔌 Networking & Optics — the nervous system": [
        ("ANET", "Arista Networks"),
        ("CSCO", "Cisco Systems"),
        ("CRDO", "Credo Technology — active copper"),
        ("CIEN", "Ciena — optical transport"),
        ("COHR", "Coherent — optical/laser"),
        ("LITE", "Lumentum — optical transceivers"),
        ("FN",   "Fabrinet — optical manufacturing"),
    ],

    "🖥️ Servers, Cooling & Power Gear — the body": [
        ("SMCI", "Super Micro Computer"),
        ("DELL", "Dell Technologies"),
        ("HPE",  "Hewlett Packard Enterprise"),
        ("VRT",  "Vertiv — thermal & power management"),
        ("ETN",  "Eaton — electrical/power"),
        ("MOD",  "Modine — liquid cooling"),
    ],

    "☁️ Neoclouds & AI Data Centers — the landlords": [
        ("NBIS", "Nebius Group — AI cloud"),
        ("CRWV", "CoreWeave — GPU cloud"),
        ("IREN", "IREN — AI data centers"),
        ("APLD", "Applied Digital — HPC hosting"),
        ("CIFR", "Cipher Mining — HPC pivot"),
        ("CORZ", "Core Scientific — AI/HPC"),
        ("WULF", "TeraWulf — HPC hosting"),
    ],

    "⚡ Power & Energy — the fuel": [
        ("CEG",  "Constellation Energy — largest US nuclear"),
        ("VST",  "Vistra — nuclear + thermal"),
        ("NEE",  "NextEra Energy"),
        ("GEV",  "GE Vernova — grid & turbines"),
        ("TLN",  "Talen Energy — nuclear to data centers"),
        ("EQT",  "EQT Corp — natural gas"),
        ("OKLO", "Oklo — micro reactors"),
        ("SMR",  "NuScale Power — SMRs"),
        ("EOSE", "Eos Energy — grid storage"),
    ],

    "🏛️ Hyperscalers — the buyers (demand side)": [
        ("MSFT", "Microsoft"),
        ("GOOGL","Alphabet"),
        ("AMZN", "Amazon"),
        ("META", "Meta Platforms"),
        ("ORCL", "Oracle"),
    ],
}


# ══════════════════════════════════════════════════════════════════════════════
# FULL ETF UNIVERSE — all sectors, not just tech
# ══════════════════════════════════════════════════════════════════════════════

AI_ETFS = [
    # ── AI / Tech Theme ──────────────────────────────────────────────────────
    ("BOTZ", "Global X Robotics & AI ETF"),
    ("AIQ",  "Global X AI & Technology ETF"),
    ("ROBO", "ROBO Global Robotics ETF"),
    ("ARKQ", "ARK Autonomous Tech & Robotics"),
    ("CHAT", "Roundhill Generative AI ETF"),
    ("IRBO", "iShares Robotics & AI ETF"),
    ("WCLD", "WisdomTree Cloud Computing ETF"),
    ("CLOU", "Global X Cloud Computing ETF"),
    ("DRIV", "Global X Autonomous & EV ETF"),

    # ── Semiconductors ───────────────────────────────────────────────────────
    ("SOXX", "iShares Semiconductor ETF"),
    ("SMH",  "VanEck Semiconductor ETF"),
    ("PSI",  "Invesco Dynamic Semiconductors"),

    # ── Broad Market & Factor ETFs ────────────────────────────────────────────
    ("QQQ",  "Invesco Nasdaq 100 — Tech-heavy large cap"),
    ("SPY",  "SPDR S&P 500 — Broad market benchmark"),
    ("IWM",  "iShares Russell 2000 — Small cap"),
    ("VUG",  "Vanguard Growth ETF — Growth factor"),
    ("VTV",  "Vanguard Value ETF — Value factor"),
    ("MTUM", "iShares Momentum Factor ETF — Momentum"),
    ("QUAL", "iShares Quality Factor ETF — Quality"),
    ("USMV", "iShares Min Volatility ETF — Low vol"),

    # ── S&P 500 Sector ETFs (SPDR) ────────────────────────────────────────────
    ("XLK",  "SPDR Technology Select Sector"),
    ("XLF",  "SPDR Financial Select Sector"),
    ("XLE",  "SPDR Energy Select Sector"),
    ("XLV",  "SPDR Health Care Select Sector"),
    ("XLI",  "SPDR Industrials Select Sector"),
    ("XLB",  "SPDR Materials Select Sector"),
    ("XLRE", "SPDR Real Estate Select Sector"),
    ("XLU",  "SPDR Utilities Select Sector"),
    ("XLP",  "SPDR Consumer Staples Select Sector"),
    ("XLY",  "SPDR Consumer Discretionary Sector"),
    ("XLC",  "SPDR Communication Services Sector"),

    # ── Clean Energy & Resources ──────────────────────────────────────────────
    ("ICLN", "iShares Global Clean Energy ETF"),
    ("TAN",  "Invesco Solar ETF"),
    ("ACES", "ALPS Clean Energy ETF"),
    ("LIT",  "Global X Lithium & Battery Tech ETF"),
    ("COPX", "Global X Copper Miners ETF"),
    ("URA",  "Sprott Uranium Miners ETF"),

    # ── Defense & Aerospace ──────────────────────────────────────────────────
    ("ITA",  "iShares U.S. Aerospace & Defense ETF"),
    ("PPA",  "Invesco Aerospace & Defense ETF"),
    ("XAR",  "SPDR S&P Aerospace & Defense ETF"),

    # ── Biotech & Healthcare ──────────────────────────────────────────────────
    ("ARKG", "ARK Genomic Revolution ETF"),
    ("XBI",  "SPDR S&P Biotech ETF — Equal weight biotech"),
    ("IBB",  "iShares Nasdaq Biotechnology ETF"),
    ("LABD", "Direxion Daily S&P Biotech Bear 3x — short hedge"),

    # ── Bonds ─────────────────────────────────────────────────────────────────
    ("TLT",  "iShares 20+ Year Treasury Bond — Long duration"),
    ("IEF",  "iShares 7-10 Year Treasury Bond — Medium duration"),
    ("SHY",  "iShares 1-3 Year Treasury Bond — Short duration"),
    ("HYG",  "iShares iBoxx High Yield Corporate Bond"),
    ("LQD",  "iShares Investment Grade Corporate Bond"),
    ("AGG",  "iShares Core US Aggregate Bond Market"),
    ("TIP",  "iShares TIPS Bond — Inflation protected"),

    # ── Commodities ───────────────────────────────────────────────────────────
    ("GLD",  "SPDR Gold Shares — Gold"),
    ("SLV",  "iShares Silver Trust — Silver"),
    ("USO",  "United States Oil Fund — Crude oil"),
    ("PDBC", "Invesco Optimum Yield Diversified Commodity"),
    ("DBA",  "Invesco DB Agriculture Fund"),
    ("WEAT", "Teucrium Wheat Fund"),

    # ── International ─────────────────────────────────────────────────────────
    ("EEM",  "iShares MSCI Emerging Markets ETF"),
    ("EFA",  "iShares MSCI EAFE — Developed markets ex-US"),
    ("FXI",  "iShares China Large-Cap ETF"),
    ("EWJ",  "iShares MSCI Japan ETF"),
    ("INDA", "iShares MSCI India ETF"),
    ("VGK",  "Vanguard FTSE Europe ETF"),
    ("EWZ",  "iShares MSCI Brazil ETF"),

    # ── Real Estate ───────────────────────────────────────────────────────────
    ("VNQ",  "Vanguard Real Estate ETF — US REITs"),
    ("REM",  "iShares Mortgage Real Estate ETF"),
    ("REET", "iShares Global REIT ETF"),

    # ── Dividend & Income ─────────────────────────────────────────────────────
    ("SCHD", "Schwab US Dividend Equity ETF — High quality dividend"),
    ("VYM",  "Vanguard High Dividend Yield ETF"),
    ("DVY",  "iShares Select Dividend ETF"),

    # ── Volatility & Alternative ──────────────────────────────────────────────
    ("VXX",  "iPath Series B S&P 500 VIX — Volatility"),
    ("SQQQ", "ProShares UltraPro Short QQQ — 3x inverse Nasdaq"),
    ("TQQQ", "ProShares UltraPro QQQ — 3x leveraged Nasdaq"),
    ("GDX",  "VanEck Gold Miners ETF"),
]

# ── Hidden Gems — under-the-radar, small/mid cap, recent IPOs ─────────────────
# Under $15B market cap, less analyst coverage, high growth potential
# Great for "experimental" portfolio — higher risk, asymmetric upside

HIDDEN_GEMS = [
    # Quantum Computing
    "IONQ",  # IonQ — pure-play trapped-ion quantum computing
    "RGTI",  # Rigetti Computing — superconducting quantum chips
    "QUBT",  # Quantum Computing Inc — quantum optimization SaaS
    "ARQQ",  # Arqit Quantum — quantum encryption (satellite-based)

    # Space & Satellites
    "ASTS",  # AST SpaceMobile — building space-based cell network
    "RKLB",  # Rocket Lab — small sat launch, cheaper than SpaceX
    "LUNR",  # Intuitive Machines — NASA lunar payloads
    "RDW",   # Redwire Space — space manufacturing

    # Nuclear & Energy Storage (speculative)
    "OKLO",  # Oklo — micro reactors, backed by Sam Altman
    "NNE",   # Nano Nuclear Energy — ultra-small modular reactors
    "SMR",   # NuScale — SMR pioneer, only NRC-approved design
    "NRGV",  # Energy Vault — gravity storage towers

    # AI Infra (smaller players)
    "SMCI",  # Super Micro Computer — AI server rack systems
    "SOUN",  # SoundHound — voice AI, <$3B market cap
    "BBAI",  # BigBear.ai — defense AI analytics
    "GFAI",  # Guardforce AI — security robot company

    # Biotech AI
    "RXRX",  # Recursion Pharma — AI drug discovery, partnered with NVIDIA
    "SDGR",  # Schrödinger — physics-based molecular simulation AI
    "BEAM",  # Beam Therapeutics — base editing gene therapy
    "PACB",  # PacBio — long-read sequencing, AI genomics

    # Fintech / Crypto
    "UPST",  # Upstart — AI credit underwriting
    "AFRM",  # Affirm — AI-driven BNPL
    "HOOD",  # Robinhood — retail brokerage, expanding crypto

    # Robotics / Autonomy
    "JOBY",  # Joby Aviation — eVTOL air taxi, Toyota-backed
    "ACHR",  # Archer Aviation — eVTOL
    "KTOS",  # Kratos — autonomous drones, hypersonics
    "GENI",  # Genius Sports — AI sports data

    # Deep Tech / Misc
    "DOCS",  # Doximity — AI tools for physicians
    "TMDX",  # TransMedics — AI organ transplant logistics
    "EXAI",  # Exscientia — AI-first pharma
]

# Legacy config compatibility
AI_BASKET_STOCKS = SECTORS["AI & Compute Infrastructure"] + SECTORS["Cloud & Software Platform"]
DASHBOARD_CORE = ["NVDA", "AMD", "MSFT", "GOOGL", "AMZN", "META",
                   "PLTR", "NET", "SNOW", "AVGO", "ARM", "INTC"]

STOCK_SCREEN = {
    "min_consecutive_down_days": 2,
    "min_single_day_drop_pct":  -3.0,
    "min_growth_1m_pct":         3.0,
    "min_growth_6m_pct":         5.0,
    "min_growth_1y_pct":         8.0,
}

SIGNAL_WEIGHTS = {
    "github_growth":   0.25,
    "vc_backing":      0.25,
    "developer_buzz":  0.20,
    "hiring_growth":   0.15,
    "revenue_signal":  0.10,
    "twitter_discuss": 0.05,
}
