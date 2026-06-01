"""
Headline Trades — Macro Shock Monitor

Takes financial headlines and uses the LLM to identify macro shocks and
generate actionable long/short trade ideas.

Usage:
    from analysis.headline_trades import analyze_headline_trades, render_headline_trades_panel
    text  = analyze_headline_trades(headlines)
    panel = render_headline_trades_panel(text)
"""
from __future__ import annotations

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Console

from analysis.llm_client import call_llm


_SYSTEM_PROMPT = """\
You are a senior macro trader and portfolio manager at a multi-billion-dollar hedge fund.
Your job is to quickly scan news headlines and identify ONLY the genuinely market-moving
macro events — not noise — and generate specific, actionable trade ideas.
Be direct, concise, and ruthlessly selective. Do not pad the response."""

_USER_PROMPT_TEMPLATE = """\
Here are today's financial headlines:

{headlines_block}

---

Analyze these headlines and do the following:

1. Identify 2-5 GENUINELY MARKET-MOVING macro events only. Skip noise. Focus on:
   - Geopolitical shocks (wars, sanctions, trade policy changes)
   - Central bank surprises (Fed, ECB, BoJ — rate decisions, guidance shifts)
   - Commodity shocks (oil, gas, metals — supply disruptions or demand collapses)
   - Major earnings surprises from bellwether companies
   - Supply chain disruptions (ports, semiconductors, food)
   - Significant regulatory actions (antitrust, crypto, banking)

2. For EACH event, output EXACTLY this format (no markdown headers, just plain text blocks):

EVENT: [Short name of the event]
IMPACT: [1-sentence description of the market impact]
SECTORS AFFECTED: [comma-separated list]
LONG IDEAS: [specific tickers, e.g. XOM, SLB, CVX]
SHORT IDEAS: [specific tickers, e.g. UAL, DAL, AAL]
DIRECTION: [RISK-ON / RISK-OFF / SECTOR-ROTATION / MIXED]
CONFIDENCE: [HIGH / MEDIUM / LOW]
TIME HORIZON: [INTRADAY / 1-5 DAYS / 1-4 WEEKS]
RATIONALE: [2-3 sentences explaining the trade logic]

3. After all events, add a one-line summary:
OVERALL MARKET TONE: [BULLISH / BEARISH / NEUTRAL / VOLATILE]

If there are NO genuinely market-moving events in the headlines, output exactly:
NO MACRO SHOCKS IDENTIFIED — markets likely range-bound today.
"""


def _format_headlines_block(headlines: list[dict]) -> str:
    """Format the list of headline dicts into a compact text block for the prompt."""
    lines = []
    for i, h in enumerate(headlines, 1):
        source = h.get("source", "Unknown")
        title  = h.get("title",   "").strip()
        summary = h.get("summary", "").strip()
        published = h.get("published", "")
        line = f"{i}. [{source}] {title}"
        if published:
            line += f" ({published[:16]})"
        if summary and summary.lower() != title.lower():
            # Truncate summary to keep prompt lean
            line += f"\n   {summary[:200]}"
        lines.append(line)
    return "\n".join(lines)


def analyze_headline_trades(headlines: list[dict]) -> str:
    """
    Run LLM analysis on macro headlines to identify market-moving events
    and generate long/short trade ideas.

    Args:
        headlines: list of dicts from fetch_macro_headlines()

    Returns:
        Raw LLM analysis text (structured plain-text format).
    """
    if not headlines:
        return "NO MACRO SHOCKS IDENTIFIED — no headlines available."

    headlines_block = _format_headlines_block(headlines)
    prompt = _USER_PROMPT_TEMPLATE.format(headlines_block=headlines_block)

    try:
        result = call_llm(prompt, system=_SYSTEM_PROMPT, max_tokens=2000)
        return result.strip()
    except Exception as exc:
        return f"[Error running headline trade analysis: {exc}]"


def render_headline_trades_panel(analysis_text: str) -> Panel:
    """
    Render the LLM analysis text as a Rich Panel for display in the pager.

    Args:
        analysis_text: raw text returned by analyze_headline_trades()

    Returns:
        A Rich Panel ready to print.
    """
    lines = analysis_text.strip().splitlines()

    # Build a Rich Text object with coloured fields
    body = Text()

    field_colors = {
        "EVENT":                "bold bright_yellow",
        "IMPACT":               "white",
        "SECTORS AFFECTED":     "cyan",
        "LONG IDEAS":           "bold green",
        "SHORT IDEAS":          "bold red",
        "DIRECTION":            "bright_magenta",
        "CONFIDENCE":           "bright_white",
        "TIME HORIZON":         "bright_cyan",
        "RATIONALE":            "dim white",
        "OVERALL MARKET TONE":  "bold bright_yellow",
    }

    for line in lines:
        stripped = line.strip()
        matched = False
        for field, style in field_colors.items():
            if stripped.upper().startswith(field + ":"):
                colon_pos = stripped.index(":")
                label = stripped[:colon_pos + 1]
                value = stripped[colon_pos + 1:].strip()
                body.append(label + " ", style="bold dim")
                body.append(value + "\n", style=style)
                matched = True
                break
        if not matched:
            if stripped == "":
                body.append("\n")
            else:
                body.append(stripped + "\n", style="dim white")

    panel = Panel(
        body,
        title="[bold red on black] 🚨 Macro Shock Monitor — Headline Trades [/bold red on black]",
        border_style="bright_red",
        padding=(1, 2),
    )
    return panel
