"""
AI Infrastructure Value Chain — opportunity scanner.

Goal: find the "next Micron" — companies across the AI infrastructure stack
(compute silicon → foundry → memory → networking → servers → neoclouds → power)
that are still at fair/moderate valuations but have strong growth and real
analyst upside, BEFORE the market re-rates them.

This deliberately favors the *asymmetric setup* over the already-extended winner:
a name up +300% on a 60x forward P/E scores LOWER than one growing 40% with a
fair multiple and 30% analyst upside. We want potential energy, not spent fuel.
"""
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from rich.table import Table
from rich.console import Console
from rich import box

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.universe import AI_INFRASTRUCTURE
from stocks.sector_scan import SectorStock, fetch_sector_stock
from stocks.parallel import parallel_fetch

console = Console(width=280)


@dataclass
class AIInfraPick:
    stock: SectorStock
    layer: str
    opportunity_score: float          # 0-100, higher = better risk/reward setup
    label: str                        # 🚀 EMERGING WINNER, 💎 UNDERVALUED, etc.
    is_next_micron: bool              # asymmetric: cheap-ish + high growth + upside
    rationale: str                    # short why-it-scored line


# ── Opportunity scoring ────────────────────────────────────────────────────────

def _value_component(s: SectorStock) -> float:
    """0–30. Cheaper = higher. Uses GARP rating + forward P/E sanity check."""
    garp = s.quant.fundamental.garp_rating if s.quant else "N/A"
    base = {"CHEAP": 30, "FAIR": 22, "N/A": 14, "EXPENSIVE": 9, "VERY_EXPENSIVE": 3}.get(garp, 14)
    # Forward P/E adjustment — reward reasonable multiples, penalize nosebleed ones.
    fpe = s.forward_pe
    if fpe is not None and fpe > 0:
        if fpe <= 20:   base += 4
        elif fpe <= 35: base += 1
        elif fpe >= 70: base -= 5
        elif fpe >= 50: base -= 2
    return max(0.0, min(30.0, base))


def _upside_component(s: SectorStock) -> float:
    """0–25. Analyst mean-target upside. >40% maxes out."""
    up = s.upside_to_target
    if up is None:
        return 8.0  # unknown → neutral-ish, don't punish hard
    if up <= 0:
        return max(0.0, 5 + up * 0.1)  # mild penalty for downside targets
    return min(25.0, up * 0.6)


def _growth_component(s: SectorStock) -> float:
    """0–25. Revenue + earnings growth. The 'potential' in potential energy."""
    rg = s.revenue_growth if s.revenue_growth is not None else 0.0
    eg = s.earnings_growth if s.earnings_growth is not None else 0.0
    # Revenue growth weighted more (cleaner signal than volatile EPS growth).
    score = min(18.0, max(0.0, rg) * 0.45) + min(7.0, max(0.0, eg) * 0.10)
    return min(25.0, score)


def _quant_component(s: SectorStock) -> float:
    """0–20. Existing 5-factor quant score as confirmation of the technical setup."""
    if not s.quant:
        return 8.0
    return min(20.0, s.quant.overall_quant_score * 0.20)


def _is_overextended(s: SectorStock) -> bool:
    """Already-spent fuel: huge run AND a rich multiple AND overbought."""
    big_run = (s.return_6m or 0) > 80
    rich = (s.quant.fundamental.garp_rating in ("EXPENSIVE", "VERY_EXPENSIVE")) if s.quant else False
    overbought = (s.quant.technical.stochastic.k_pct > 80) if s.quant else False
    return big_run and (rich or overbought)


def score_pick(s: SectorStock, layer: str) -> AIInfraPick:
    v  = _value_component(s)
    up = _upside_component(s)
    gr = _growth_component(s)
    q  = _quant_component(s)
    # Demote already-extended names so the leaderboard surfaces fresh setups first —
    # the fundamentals may be great, but the easy money is likely already made.
    extended_penalty = 12.0 if _is_overextended(s) else 0.0
    opp = round(max(0.0, v + up + gr + q - extended_penalty), 1)

    garp = s.quant.fundamental.garp_rating if s.quant else "N/A"
    rg   = s.revenue_growth or 0.0
    upv  = s.upside_to_target or 0.0
    r6   = s.return_6m or 0.0

    # "Next Micron" = high growth + still-reasonable valuation + real upside,
    # and NOT already blown off the top.
    is_next_micron = (
        rg >= 25 and
        garp in ("CHEAP", "FAIR", "N/A") and
        upv > 10 and
        not _is_overextended(s)
    )

    # Label by profile
    if _is_overextended(s):
        label = "⚠️ EXTENDED"
    elif is_next_micron and opp >= 65:
        label = "🚀 EMERGING WINNER"
    elif garp in ("CHEAP", "FAIR") and upv >= 15:
        label = "💎 UNDERVALUED"
    elif upv >= 30:
        label = "🔥 HIGH UPSIDE"
    elif (s.quant and s.quant.overall_quant_score >= 60 and r6 > 30):
        label = "⚡ MOMENTUM"
    else:
        label = "➡️ NEUTRAL"

    bits = []
    if garp in ("CHEAP", "FAIR"): bits.append(f"valuation {garp}")
    if rg >= 20:  bits.append(f"rev +{rg:.0f}%")
    if upv > 10:  bits.append(f"{upv:.0f}% analyst upside")
    if s.quant:   bits.append(f"quant {s.quant.overall_quant_score:.0f}")
    rationale = ", ".join(bits) if bits else "limited edge"

    return AIInfraPick(stock=s, layer=layer, opportunity_score=opp,
                       label=label, is_next_micron=is_next_micron, rationale=rationale)


# ── Scan ────────────────────────────────────────────────────────────────────────

def scan_ai_infrastructure(universe: Dict[str, List[Tuple[str, str]]] = None) -> List[AIInfraPick]:
    """Fetch the whole AI infra value chain concurrently and score every name."""
    if universe is None:
        universe = AI_INFRASTRUCTURE

    name_by_ticker = {t: n for layer in universe.values() for t, n in layer}
    jobs = [(t, layer) for layer, names in universe.items() for t, _ in names]

    with console.status(f"  Scanning AI infrastructure value chain ({len(jobs)} stocks)...") as status:
        def _progress(done, tot):
            status.update(f"  AI infra value chain... {done}/{tot} loaded")
        stocks = parallel_fetch(
            jobs,
            lambda job: fetch_sector_stock(job[0], job[1]),
            progress=_progress,
        )

    picks = []
    for s in stocks:
        s.name = name_by_ticker.get(s.ticker, s.name)  # readable name
        picks.append(score_pick(s, s.sector_label))
    picks.sort(key=lambda p: p.opportunity_score, reverse=True)
    return picks


# ── Rendering ───────────────────────────────────────────────────────────────────

_LABEL_STYLE = {
    "🚀 EMERGING WINNER": "bold green",
    "💎 UNDERVALUED":     "green",
    "🔥 HIGH UPSIDE":     "cyan",
    "⚡ MOMENTUM":        "yellow",
    "➡️ NEUTRAL":         "white",
    "⚠️ EXTENDED":        "red",
}


def _fmt_pct(v, plus=True):
    if v is None:
        return "—"
    c = "green" if v >= 0 else "red"
    sign = "+" if (plus and v >= 0) else ""
    return f"[{c}]{sign}{v:.1f}%[/{c}]"


def render_opportunity_leaderboard(picks: List[AIInfraPick], top_n: int = 20) -> Table:
    """The headline table: best risk/reward setups across the whole value chain."""
    t = Table(
        title="🎯 AI Infrastructure — Opportunity Leaderboard (best risk/reward first)",
        box=box.ROUNDED, show_lines=True,
        header_style="bold white on dark_green", min_width=200,
    )
    t.add_column("#",         justify="right", width=3)
    t.add_column("Ticker",    style="bold",    width=7, no_wrap=True)
    t.add_column("Name",      width=22, no_wrap=True)
    t.add_column("Layer",     width=20, no_wrap=True)
    t.add_column("Price",     justify="right", width=10)
    t.add_column("6M",        justify="right", width=8)
    t.add_column("1Y",        justify="right", width=8)
    t.add_column("Fwd PE",    justify="right", width=8)
    t.add_column("Rev Gr",    justify="right", width=8)
    t.add_column("Analyst↑",  justify="right", width=9)
    t.add_column("GARP",      justify="center", width=9)
    t.add_column("Quant",     justify="right", width=6)
    t.add_column("Opp",       justify="right", width=6)
    t.add_column("Signal",    width=19)

    gc = {"CHEAP":"bold green","FAIR":"green","EXPENSIVE":"yellow","VERY_EXPENSIVE":"red","N/A":"dim"}

    for i, p in enumerate(picks[:top_n], 1):
        s = p.stock
        garp = s.quant.fundamental.garp_rating if s.quant else "N/A"
        qs   = s.quant.overall_quant_score if s.quant else 0
        layer_short = p.layer.split("—")[0].strip()[:20]
        opp_c = "bold green" if p.opportunity_score >= 65 else "green" if p.opportunity_score >= 50 else "yellow" if p.opportunity_score >= 38 else "red"
        lbl_c = _LABEL_STYLE.get(p.label, "white")
        star = "⭐" if p.is_next_micron else "  "

        t.add_row(
            str(i), s.ticker, f"{star}{s.name[:20]}", layer_short,
            f"${s.current_price:,.2f}",
            _fmt_pct(s.return_6m), _fmt_pct(s.return_1y),
            f"{s.forward_pe:.0f}x" if s.forward_pe else "—",
            _fmt_pct(s.revenue_growth),
            _fmt_pct(s.upside_to_target),
            f"[{gc.get(garp,'white')}]{garp}[/{gc.get(garp,'white')}]",
            f"{qs:.0f}",
            f"[{opp_c}]{p.opportunity_score:.0f}[/{opp_c}]",
            f"[{lbl_c}]{p.label}[/{lbl_c}]",
        )
    return t


def render_layer_table(layer: str, picks: List[AIInfraPick]) -> Table:
    """Compact per-layer view so the value-chain structure stays visible."""
    t = Table(title=layer, box=box.SIMPLE_HEAD, header_style="bold cyan", min_width=160)
    t.add_column("Ticker", style="bold", width=7, no_wrap=True)
    t.add_column("Name",   width=24, no_wrap=True)
    t.add_column("Price",  justify="right", width=10)
    t.add_column("6M",     justify="right", width=8)
    t.add_column("Rev Gr", justify="right", width=8)
    t.add_column("Analyst↑", justify="right", width=9)
    t.add_column("GARP",   justify="center", width=9)
    t.add_column("Opp",    justify="right", width=6)
    t.add_column("Signal", width=19)

    gc = {"CHEAP":"bold green","FAIR":"green","EXPENSIVE":"yellow","VERY_EXPENSIVE":"red","N/A":"dim"}
    for p in sorted(picks, key=lambda x: x.opportunity_score, reverse=True):
        s = p.stock
        garp = s.quant.fundamental.garp_rating if s.quant else "N/A"
        lbl_c = _LABEL_STYLE.get(p.label, "white")
        star = "⭐" if p.is_next_micron else ""
        t.add_row(
            s.ticker, f"{star}{s.name[:23]}", f"${s.current_price:,.2f}",
            _fmt_pct(s.return_6m), _fmt_pct(s.revenue_growth), _fmt_pct(s.upside_to_target),
            f"[{gc.get(garp,'white')}]{garp}[/{gc.get(garp,'white')}]",
            f"{p.opportunity_score:.0f}",
            f"[{lbl_c}]{p.label}[/{lbl_c}]",
        )
    return t


def build_ai_infra_context(picks: List[AIInfraPick], top_n: int = 12) -> str:
    """Concise context for the LLM — only the top opportunities, to keep tokens low."""
    lines = ["=== AI INFRASTRUCTURE — TOP OPPORTUNITIES (ranked by risk/reward) ==="]
    for p in picks[:top_n]:
        s = p.stock
        lines.append(
            f"{s.ticker} ({s.name}) [{p.layer.split('—')[0].strip()}] {p.label}"
            f"{' ⭐NEXT-MICRON-SETUP' if p.is_next_micron else ''}: "
            f"price ${s.current_price} | analyst_target ${s.analyst_target if s.analyst_target else 'NONE'} "
            f"({s.upside_to_target if s.upside_to_target is not None else 'N/A'}% upside) | "
            f"6M {s.return_6m:+.0f}% | 1Y {s.return_1y:+.0f}% | "
            f"FwdPE {s.forward_pe or 'N/A'} | RevGr {s.revenue_growth or 'N/A'}% | "
            f"GARP {s.quant.fundamental.garp_rating if s.quant else 'N/A'} | "
            f"Quant {s.quant.overall_quant_score:.0f}/100 | Opp {p.opportunity_score:.0f}/100"
        )
    return "\n".join(lines)
