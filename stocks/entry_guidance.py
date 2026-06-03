"""
Actionable entry guidance — turn a "what to watch" pick into a "how to act" plan.

The factor model and leaderboards answer *which* names look attractive, but not
*how to buy them today*. This module adds the operational layer:

  1. ETF proxy   — for every single-name pick, the closest theme/sector ETF, so you
                   can take the exposure in a diversified, liquid wrapper instead of
                   a thin micro-cap (addresses single-name blowup + liquidity risk).
  2. Limit price — a disciplined entry limit below the last price, scaled by how
                   *extended* the name is. Near a 52-week high → demand a bigger
                   pullback (don't chase); already pulled back → a smaller discount.
  3. 52w position— how far the name sits below its 52-week high (the Fidelity-style
                   range read) so you can see whether you're buying near the top.

Everything here is heuristic and deterministic — no network calls — so it is fast
and unit-testable. It consumes the price fields the scanners already fetch.
"""
from dataclasses import dataclass
from typing import Optional

# ── Theme / sector ETF map ───────────────────────────────────────────────────
# Keyed by a keyword that appears in an AI-infra layer name, a sector bucket, a
# hidden-gem category, or a yfinance sector string. First match wins, so order
# the more specific keys before the generic ones.
_THEME_ETF = [
    # AI-infra value-chain layers (matched as substrings of the layer label)
    ("compute silicon", ("SMH",  "VanEck Semiconductor ETF")),
    ("foundry",         ("SOXX", "iShares Semiconductor ETF")),
    ("semi equipment",  ("SOXX", "iShares Semiconductor ETF")),
    ("memory",          ("SMH",  "VanEck Semiconductor ETF")),
    ("networking",      ("SMH",  "VanEck Semiconductor ETF")),
    ("optics",          ("SMH",  "VanEck Semiconductor ETF")),
    ("servers",         ("XLK",  "Technology Select Sector SPDR")),
    ("cooling",         ("XLK",  "Technology Select Sector SPDR")),
    ("neocloud",        ("WCLD", "WisdomTree Cloud Computing ETF")),
    ("data center",     ("WCLD", "WisdomTree Cloud Computing ETF")),
    ("power",           ("XLU",  "Utilities Select Sector SPDR")),
    ("energy",          ("XLU",  "Utilities Select Sector SPDR")),
    ("hyperscaler",     ("QQQ",  "Invesco Nasdaq 100 ETF")),

    # Sector buckets / gem categories
    ("semiconductor",   ("SMH",  "VanEck Semiconductor ETF")),
    ("cloud",           ("WCLD", "WisdomTree Cloud Computing ETF")),
    ("software",        ("WCLD", "WisdomTree Cloud Computing ETF")),
    ("clean energy",    ("ICLN", "iShares Global Clean Energy ETF")),
    ("solar",           ("TAN",  "Invesco Solar ETF")),
    ("nuclear",         ("URA",  "Sprott Uranium Miners ETF")),
    ("grid",            ("XLU",  "Utilities Select Sector SPDR")),
    ("defense",         ("ITA",  "iShares U.S. Aerospace & Defense ETF")),
    ("aerospace",       ("ITA",  "iShares U.S. Aerospace & Defense ETF")),
    ("space",           ("ITA",  "iShares U.S. Aerospace & Defense ETF")),
    ("biotech",         ("XBI",  "SPDR S&P Biotech ETF")),
    ("healthcare",      ("XLV",  "Health Care Select Sector SPDR")),
    ("health",          ("XLV",  "Health Care Select Sector SPDR")),
    ("fintech",         ("XLF",  "Financial Select Sector SPDR")),
    ("crypto",          ("XLF",  "Financial Select Sector SPDR")),
    ("robotic",         ("BOTZ", "Global X Robotics & AI ETF")),
    ("autonomous",      ("BOTZ", "Global X Robotics & AI ETF")),
    ("quantum",         ("ARKQ", "ARK Autonomous Tech & Robotics ETF")),
    ("ai",              ("AIQ",  "Global X AI & Technology ETF")),
    ("cyber",           ("XLK",  "Technology Select Sector SPDR")),
    ("data infra",      ("XLK",  "Technology Select Sector SPDR")),

    # yfinance sector strings (broad fallback)
    ("technology",          ("XLK",  "Technology Select Sector SPDR")),
    ("financial",           ("XLF",  "Financial Select Sector SPDR")),
    ("industrials",         ("XLI",  "Industrials Select Sector SPDR")),
    ("consumer cyclical",   ("XLY",  "Consumer Discretionary SPDR")),
    ("consumer defensive",  ("XLP",  "Consumer Staples Select SPDR")),
    ("utilities",           ("XLU",  "Utilities Select Sector SPDR")),
    ("real estate",         ("XLRE", "Real Estate Select Sector SPDR")),
    ("basic materials",     ("XLB",  "Materials Select Sector SPDR")),
    ("communication",       ("XLC",  "Communication Services SPDR")),
]

_DEFAULT_ETF = ("QQQ", "Invesco Nasdaq 100 ETF")

# A few high-conviction single-name overrides where the best proxy is unambiguous.
_TICKER_ETF = {
    "NVDA": ("SMH", "VanEck Semiconductor ETF"),
    "AMD":  ("SMH", "VanEck Semiconductor ETF"),
    "TSM":  ("SMH", "VanEck Semiconductor ETF"),
    "ASML": ("SOXX", "iShares Semiconductor ETF"),
    "MU":   ("SMH", "VanEck Semiconductor ETF"),
    "PLTR": ("WCLD", "WisdomTree Cloud Computing ETF"),
    "COIN": ("XLF", "Financial Select Sector SPDR"),
    "MSTR": ("XLF", "Financial Select Sector SPDR"),
}


@dataclass
class EntryGuide:
    ticker: str
    current_price: float
    pct_from_52w_high: float      # negative = below the high
    limit_price: float            # suggested entry limit
    limit_discount_pct: float     # how far below current the limit sits, %
    etf_ticker: str
    etf_name: str
    note: str                     # short human-readable rationale


def recommend_etf(ticker: str, layer: str = "", sector: str = "",
                  gem_category: str = "") -> tuple:
    """Return (etf_ticker, etf_name) — the closest liquid proxy for a name."""
    if ticker and ticker.upper() in _TICKER_ETF:
        return _TICKER_ETF[ticker.upper()]
    haystack = " ".join(x for x in (layer, sector, gem_category) if x).lower()
    for key, etf in _THEME_ETF:
        if key in haystack:
            return etf
    return _DEFAULT_ETF


def suggest_limit_price(current_price: float, pct_from_52w_high: float) -> tuple:
    """
    Suggest a disciplined entry limit below the last price. The closer a name is
    to its 52-week high, the bigger the pullback we insist on (don't chase);
    names already well off the high need only a small discount.

    Returns (limit_price, discount_pct, note).
    """
    ext = pct_from_52w_high if pct_from_52w_high is not None else 0.0
    if ext >= -2:           # within 2% of the high — extended
        disc, note = 5.0, "near 52w high — wait for a ~5% pullback, don't chase"
    elif ext >= -7:
        disc, note = 3.5, "close to highs — set a ~3.5% pullback limit"
    elif ext >= -15:
        disc, note = 2.0, "modestly off highs — ~2% limit"
    elif ext >= -30:
        disc, note = 1.0, "pulled back — small ~1% limit, accumulate"
    else:                   # deep drawdown
        disc, note = 0.5, "deep off highs — near-market limit, don't lowball quality"
    limit = round(current_price * (1 - disc / 100.0), 2)
    return limit, disc, note


def render_entry_guide_table(picks, top_n: int = 15):
    """Rich table of entry guidance for the top opportunity picks (terminal view)."""
    from rich.table import Table
    from rich import box
    t = Table(
        title="🎯 Actionable Entry Guide — Limit Price & ETF Proxy",
        box=box.ROUNDED, header_style="bold white on dark_green", min_width=150,
    )
    t.add_column("Ticker", style="bold", width=7)
    t.add_column("Last", justify="right", width=10)
    t.add_column("% off 52w High", justify="right", width=15)
    t.add_column("Suggested Limit", justify="right", width=18)
    t.add_column("ETF Proxy", width=10)
    t.add_column("Note", width=46)
    ranked = sorted(picks, key=lambda x: x.opportunity_score, reverse=True)[:top_n]
    for p in ranked:
        s = p.stock
        g = build_entry_guide(s.ticker, getattr(s, "current_price", 0),
                              getattr(s, "pct_from_52w_high", 0.0), layer=getattr(p, "layer", ""))
        if g is None:
            continue
        ext = g.pct_from_52w_high
        ext_c = "red" if ext >= -3 else "yellow" if ext >= -12 else "green"
        t.add_row(
            g.ticker, f"${g.current_price:,.2f}",
            f"[{ext_c}]{ext:+.1f}%[/{ext_c}]",
            f"${g.limit_price:,.2f} [dim](−{g.limit_discount_pct:.1f}%)[/dim]",
            f"[cyan]{g.etf_ticker}[/cyan]", f"[dim]{g.note}[/dim]",
        )
    return t


def build_entry_guide(ticker: str, current_price: float, pct_from_52w_high: float,
                      layer: str = "", sector: str = "", gem_category: str = "") -> Optional[EntryGuide]:
    """Assemble the full entry plan for one name. Returns None if price missing."""
    if not current_price or current_price <= 0:
        return None
    limit, disc, note = suggest_limit_price(current_price, pct_from_52w_high)
    etf_t, etf_n = recommend_etf(ticker, layer, sector, gem_category)
    return EntryGuide(
        ticker=ticker, current_price=round(float(current_price), 2),
        pct_from_52w_high=round(float(pct_from_52w_high or 0.0), 1),
        limit_price=limit, limit_discount_pct=disc,
        etf_ticker=etf_t, etf_name=etf_n, note=note,
    )
