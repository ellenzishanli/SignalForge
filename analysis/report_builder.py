"""
Markdown report builder for the daily email.

The terminal renders rich Rich tables, but the email is assembled from a plain
markdown file (output/radar_YYYY-MM-DD.md) that historically held only the LLM
*narrative* for each section — so the actual data (leaderboards, ETF/sector/gem
tables, whale holdings) never reached the inbox. These helpers turn the same data
objects the terminal uses into compact markdown tables so the email mirrors the
terminal: every section, with its data, not just the prose.

Each function returns a markdown string (or "" when there's nothing to show).
"""
from typing import Dict, List


# ── small formatting helpers ────────────────────────────────────────────────
def _f(v, fmt="{:.1f}", dash="—"):
    """Format an optional number, falling back to a dash."""
    try:
        if v is None or v != v:      # None or NaN
            return dash
        return fmt.format(v)
    except (TypeError, ValueError):
        return dash


def _pct(v):
    return _f(v, "{:+.1f}%")


def _qscore(stock):
    q = getattr(stock, "quant", None)
    return q.overall_quant_score if q is not None else None


# ── AI Infrastructure Value Chain ───────────────────────────────────────────
def ai_infra_section_md(picks: List, analysis: str = "", top_n: int = 20) -> str:
    """Leaderboard + 'next Micron' candidates + the LLM narrative."""
    if not picks:
        return analysis or ""
    lines: List[str] = []
    lines.append("### 🏆 Opportunity Leaderboard — Best Risk/Reward Setups")
    lines.append("")
    lines.append("| # | Ticker | Name | Layer | Price | 6M | 1Y | PE | RevGr | Quant | Opp | ⭐ |")
    lines.append("|---|--------|------|-------|-------|----|----|----|-------|-------|-----|----|")
    for i, p in enumerate(sorted(picks, key=lambda x: x.opportunity_score, reverse=True)[:top_n], 1):
        s = p.stock
        layer = p.layer.split("—")[0].strip()
        lines.append(
            f"| {i} | {s.ticker} | {s.name[:22]} | {layer[:18]} | "
            f"${_f(s.current_price, '{:,.2f}')} | {_pct(s.return_6m)} | {_pct(s.return_1y)} | "
            f"{_f(s.pe_ratio)} | {_pct(s.revenue_growth)} | {_f(_qscore(s), '{:.0f}')} | "
            f"{p.opportunity_score:.0f} | {'⭐' if p.is_next_micron else ''} |"
        )
    lines.append("")

    winners = [p for p in picks if p.is_next_micron]
    if winners:
        lines.append("### 🚀 \"Next Micron\" Candidates — Asymmetric Setups")
        lines.append("")
        for p in sorted(winners, key=lambda x: x.opportunity_score, reverse=True):
            s = p.stock
            lines.append(f"- **{s.ticker}** ({s.name[:28]}) — {p.label} · {p.rationale}")
        lines.append("")

    if analysis and analysis.strip():
        lines.append(analysis.strip())
    return "\n".join(lines)


# ── Actionable entry guide (ETF proxy + limit price + 52w position) ──────────
def entry_guide_section_md(picks: List, top_n: int = 15) -> str:
    """For the top opportunity picks: where they sit vs the 52-week high, a
    disciplined suggested limit price, and the closest ETF proxy to buy instead
    of the single name."""
    from stocks.entry_guidance import build_entry_guide
    if not picks:
        return ""
    ranked = sorted(picks, key=lambda x: x.opportunity_score, reverse=True)[:top_n]
    rows = []
    for p in ranked:
        s = p.stock
        g = build_entry_guide(
            s.ticker, getattr(s, "current_price", 0),
            getattr(s, "pct_from_52w_high", 0.0), layer=getattr(p, "layer", ""),
            market_cap_b=getattr(s, "market_cap_b", None),
            pe_ratio=getattr(s, "pe_ratio", None),
            return_1m=getattr(s, "return_1m", None), return_6m=getattr(s, "return_6m", None),
        )
        if g is None:
            continue
        pe_str = f"{g.valuation_tag} ({g.pe_ratio:.0f})" if g.pe_ratio else g.valuation_tag
        rows.append(
            f"| {g.ticker} | ${_f(g.current_price, '{:,.2f}')} | {_f(g.pct_from_52w_high, '{:+.1f}%')} | "
            f"${_f(g.limit_price, '{:,.2f}')} (−{g.limit_discount_pct:.1f}%) | "
            f"{pe_str} | {g.trend_tag or '—'} | {g.etf_ticker} | {g.liquidity_tier or '—'} |"
        )
    if not rows:
        return ""
    head = ("### 🎯 Actionable Entry Guide — Limit Price, Valuation & ETF Proxy\n\n"
            "_Disciplined pullback limits (bigger discount near 52-week highs), current "
            "valuation (P/E), a momentum/alpha-decay read, the closest liquid ETF proxy, "
            "and a liquidity flag for thin micro-caps where slippage is real._\n\n"
            "| Ticker | Last | % off 52w High | Suggested Limit | Valuation (PE) | Trend | ETF | Liquidity |\n"
            "|--------|------|----------------|-----------------|----------------|-------|-----|-----------|")
    return head + "\n" + "\n".join(rows) + "\n"


# ── Whale / Smart Money ─────────────────────────────────────────────────────
def whales_section_md(trades: List, top_n: int = 25) -> str:
    """Consolidated whale holdings + the strongest new/increased buy signals."""
    if not trades:
        return ""
    # De-duplicate by ticker, keeping the highest-quant-score signal per name.
    best: Dict[str, object] = {}
    for t in trades:
        cur = best.get(t.ticker)
        if cur is None or t.quant_score > cur.quant_score:
            best[t.ticker] = t
    deduped = sorted(best.values(), key=lambda x: x.quant_score, reverse=True)

    lines: List[str] = []
    lines.append(f"_{len(trades)} raw signals across {len(best)} unique tickers._")
    lines.append("")
    lines.append("### 🏦 Top Whale Holdings — by Quant Confirmation")
    lines.append("")
    lines.append("| Ticker | Company | Whale | Action | Quant | Signal | Follow |")
    lines.append("|--------|---------|-------|--------|-------|--------|--------|")
    for t in deduped[:top_n]:
        lines.append(
            f"| {t.ticker} | {t.company[:20]} | {t.whale[:22]} | {t.action} | "
            f"{_f(t.quant_score, '{:.0f}')} | {t.quant_signal} | {t.follow} |"
        )
    lines.append("")

    new_buys = [t for t in trades if t.action in ("NEW BUY", "INCREASED")]
    if new_buys:
        new_best = sorted(
            {t.ticker: t for t in sorted(new_buys, key=lambda x: x.quant_score)}.values(),
            key=lambda x: x.quant_score, reverse=True,
        )
        lines.append("### 🆕 New & Increased Positions — Strongest Buy Signal")
        lines.append("")
        lines.append("| Ticker | Company | Whale | Quant | Follow |")
        lines.append("|--------|---------|-------|-------|--------|")
        for t in new_best[:15]:
            lines.append(
                f"| {t.ticker} | {t.company[:20]} | {t.whale[:22]} | "
                f"{_f(t.quant_score, '{:.0f}')} | {t.follow} |"
            )
        lines.append("")
    return "\n".join(lines)


# ── ETFs ────────────────────────────────────────────────────────────────────
def etf_section_md(etf_stocks: List, top_n: int = 20) -> str:
    if not etf_stocks:
        return ""
    ranked = sorted(etf_stocks, key=lambda s: (_qscore(s) or 0), reverse=True)[:top_n]
    lines = ["### 📦 ETF Rankings — by Quant Score", "",
             "| Ticker | Name | Price | 1M | 6M | 1Y | Quant |",
             "|--------|------|-------|----|----|----|-------|"]
    for s in ranked:
        lines.append(
            f"| {s.ticker} | {s.name[:30]} | ${_f(s.current_price, '{:,.2f}')} | "
            f"{_pct(s.return_1m)} | {_pct(s.return_6m)} | {_pct(s.return_1y)} | "
            f"{_f(_qscore(s), '{:.0f}')} |"
        )
    lines.append("")
    return "\n".join(lines)


# ── Sectors ─────────────────────────────────────────────────────────────────
def sectors_section_md(sector_results: Dict, per_sector: int = 4) -> str:
    sectors = {k: v for k, v in sector_results.items() if k != "_all" and v}
    if not sectors:
        return ""
    lines = ["### 🔭 Sector Leaders — Top Names per Sector", ""]
    for sector_name, stocks in sectors.items():
        top = sorted(stocks, key=lambda s: (_qscore(s) or 0), reverse=True)[:per_sector]
        if not top:
            continue
        lines.append(f"**{sector_name}**")
        lines.append("")
        lines.append("| Ticker | Name | Price | 6M | 1Y | PE | RevGr | Quant |")
        lines.append("|--------|------|-------|----|----|----|-------|-------|")
        for s in top:
            lines.append(
                f"| {s.ticker} | {s.name[:22]} | ${_f(s.current_price, '{:,.2f}')} | "
                f"{_pct(s.return_6m)} | {_pct(s.return_1y)} | {_f(s.pe_ratio)} | "
                f"{_pct(s.revenue_growth)} | {_f(_qscore(s), '{:.0f}')} |"
            )
        lines.append("")
    return "\n".join(lines)


# ── Hidden Gems ─────────────────────────────────────────────────────────────
def gems_section_md(gems: List, top_n: int = 20) -> str:
    if not gems:
        return ""
    ranked = sorted(gems, key=lambda s: (_qscore(s) or 0), reverse=True)[:top_n]
    lines = ["### 💎 Hidden Gems — Asymmetric Small/Mid-Cap Setups", "",
             "| Ticker | Name | Category | Price | 6M | 1Y | Quant | Thesis |",
             "|--------|------|----------|-------|----|----|-------|--------|"]
    for g in ranked:
        lines.append(
            f"| {g.ticker} | {g.name[:20]} | {getattr(g, 'gem_category', '')[:14]} | "
            f"${_f(g.current_price, '{:,.2f}')} | {_pct(g.return_6m)} | {_pct(g.return_1y)} | "
            f"{_f(_qscore(g), '{:.0f}')} | {getattr(g, 'gem_thesis', '')[:60]} |"
        )
    lines.append("")
    return "\n".join(lines)
