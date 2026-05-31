"""
Whale Tracker Display — Rich tables for all 6 tabs.
Shown at the TOP of the output, before sector scans.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from rich.table import Table
from rich.panel import Panel
from rich.console import Console
from rich.columns import Columns
from rich import box
from rich.text import Text
from typing import List, Dict, Optional
from whales.sec_13f import Filing13F, fetch_13f, fetch_ark_holdings, fetch_capitol_trades
from config.whales import ALL_WHALES, TAB_LABELS, SEC_13F_ENTITIES

console = Console(width=220)


def render_13f_table(filing: Filing13F, top_n: int = 15) -> Table:
    """Show top holdings from a 13F filing."""
    t = Table(
        title=f"📋 {filing.entity_name} | Period: {filing.period} | Filed: {filing.filed_date} | AUM: ${filing.total_value_usd/1e9:.1f}B",
        box=box.ROUNDED, show_lines=True, header_style="bold cyan",
        min_width=100,
    )
    t.add_column("Rank",     justify="right", width=5)
    t.add_column("Company",              width=28, no_wrap=True)
    t.add_column("Ticker",               width=8)
    t.add_column("Value",    justify="right", width=12)
    t.add_column("Shares",   justify="right", width=12)
    t.add_column("Type",     justify="center", width=8)
    t.add_column("Signal",   justify="center", width=10)

    for i, h in enumerate(filing.holdings[:top_n], 1):
        value_str = f"${h.value_usd/1e6:.1f}M" if h.value_usd < 1e9 else f"${h.value_usd/1e9:.2f}B"
        type_str = f"[red]{h.put_call}[/red]" if h.put_call in ("Put", "Call") else "Long"
        signal = "[red]SHORT[/red]" if h.put_call == "Put" else "[green]LONG[/green]"

        t.add_row(
            str(i), h.name[:28], h.ticker or "—",
            value_str,
            f"{h.shares:,}" if h.shares else "—",
            type_str, signal,
        )
    return t


def render_whale_summary_table(tab_name: str, entities: List[Dict]) -> Table:
    """Overview table for a whale tab — who they are and their current thesis."""
    label = TAB_LABELS.get(tab_name, tab_name)
    t = Table(
        title=label,
        box=box.ROUNDED, show_lines=True,
        header_style="bold yellow",
        min_width=200,
    )
    t.add_column("Name",       width=24, no_wrap=True)
    t.add_column("Manager",    width=20, no_wrap=True)
    t.add_column("Style",      width=22, no_wrap=True)
    t.add_column("Current Thesis / Known For",   width=70)
    t.add_column("Signal Logic",                 width=45)
    t.add_column("Data Source", justify="center", width=12)

    for e in entities:
        cik = e.get("cik")
        data_src = "SEC 13F" if cik else ("On-chain" if e.get("wallets") else "News")
        t.add_row(
            e["name"][:24],
            e.get("manager", "—")[:20],
            e.get("style", "—")[:22],
            e.get("known_for", "—")[:70],
            e.get("signal_logic", "—")[:45],
            data_src,
        )
    return t


def render_ark_table(holdings: List[Dict], fund: str) -> Table:
    """ARK daily holdings table."""
    t = Table(
        title=f"🚀 ARK {fund} — Today's Holdings (Published Daily)",
        box=box.ROUNDED, show_lines=True, header_style="bold green",
    )
    t.add_column("Rank",    justify="right", width=5)
    t.add_column("Ticker",              width=8)
    t.add_column("Name",                width=30)
    t.add_column("Shares",  justify="right", width=12)
    t.add_column("Weight",  justify="right", width=8)
    t.add_column("Signal",  justify="center", width=8)

    for i, h in enumerate(holdings[:15], 1):
        weight = h.get("weight_pct", 0)
        signal = "[green]CORE[/green]" if weight > 5 else "[yellow]HOLD[/yellow]"
        t.add_row(
            str(i), h.get("ticker","—"), h.get("name","—")[:30],
            f"{h.get('shares',0):,}", f"{weight:.1f}%", signal,
        )
    return t


def render_capitol_trades_table(trades: List[Dict]) -> Table:
    """Recent politician stock trades."""
    t = Table(
        title="🏛️ Congressional Trades — Recent Disclosures (via Capitol Trades)",
        box=box.ROUNDED, show_lines=True, header_style="bold red",
    )
    t.add_column("Politician",  width=22, no_wrap=True)
    t.add_column("Ticker",      width=8)
    t.add_column("Action",      justify="center", width=10)
    t.add_column("Amount",      justify="right", width=14)
    t.add_column("Filed",       width=12)
    t.add_column("Signal",      justify="center", width=10)

    for trade in trades:
        action = trade.get("action", "")
        action_color = "green" if "Purchase" in action else "red" if "Sale" in action else "white"
        signal = "[green]BUY[/green]" if "Purchase" in action else "[red]SELL[/red]"
        t.add_row(
            trade.get("politician","—")[:22],
            trade.get("ticker","—"),
            f"[{action_color}]{action}[/{action_color}]",
            trade.get("amount","—"),
            trade.get("filed_date","—"),
            signal,
        )
    return t


def render_crypto_whale_table(entities: List[Dict]) -> Table:
    """Crypto whale overview with on-chain context."""
    t = Table(
        title="🐋 Crypto Whales & Market Makers — Wallet + Thesis Tracker",
        box=box.ROUNDED, show_lines=True, header_style="bold magenta",
        min_width=200,
    )
    t.add_column("Entity",          width=24, no_wrap=True)
    t.add_column("Type",            width=16)
    t.add_column("Known For",       width=55)
    t.add_column("Signal Logic",    width=50)
    t.add_column("Twitter",         width=18)
    t.add_column("Controversy",     width=20)

    for e in entities:
        controversy = e.get("controversy", "None")
        c_color = "red" if controversy and controversy != "None" else "dim"
        t.add_row(
            e["name"][:24],
            e.get("type", "—")[:16],
            e.get("known_for", "—")[:55],
            e.get("signal_logic", "—")[:50],
            e.get("twitter", "—") or "—",
            f"[{c_color}]{controversy[:20]}[/{c_color}]",
        )
    return t


def run_whale_tracker() -> str:
    """
    Main entry point — fetch all whale data and render all 6 tabs.
    Returns a text summary for AI analysis.
    """
    console.print("\n[bold yellow]🐋 WHALE TRACKER — Smart Money Intelligence[/bold yellow]\n")

    summary_lines = []

    # ── Tab 1 & 2: Institutional + AI Funds (SEC 13F) ─────────────────────────
    console.print("[bold cyan]Tab 1 & 2: Institutional Holdings (SEC 13F)[/bold cyan]")
    console.print(render_whale_summary_table("institutional", ALL_WHALES["institutional"]))
    console.print()
    console.print(render_whale_summary_table("ai_funds", ALL_WHALES["ai_funds"]))
    console.print()

    # Fetch actual 13F for Berkshire and Scion (highest signal value)
    priority_13f = [
        ("Berkshire Hathaway", "0001067983"),
        ("Scion Asset Management", "0001649978"),
        ("ARK Investment Management", "0001579982"),
    ]

    for name, cik in priority_13f[:2]:  # limit to avoid rate limiting
        console.print(f"  [dim]Fetching 13F: {name}...[/dim]")
        filing = fetch_13f(name, cik)
        if filing and filing.holdings:
            console.print(render_13f_table(filing))
            console.print()
            summary_lines.append(
                f"{name} (Q{filing.period}): Top holdings = "
                + ", ".join([f"{h.ticker or h.name[:15]} ${h.value_usd/1e6:.0f}M"
                             for h in filing.holdings[:5]])
            )

    # ARK daily holdings
    console.print("[dim]Fetching ARK daily holdings...[/dim]")
    ark_holdings = fetch_ark_holdings("ARKK")
    if ark_holdings:
        console.print(render_ark_table(ark_holdings, "ARKK"))
        console.print()

    # ── Tab 3: Asia Whales ────────────────────────────────────────────────────
    console.print("[bold cyan]Tab 3: Asia Whales[/bold cyan]")
    console.print(render_whale_summary_table("asia_whales", ALL_WHALES["asia_whales"]))
    console.print()

    # ── Tab 4: Crypto Whales ──────────────────────────────────────────────────
    console.print("[bold cyan]Tab 4: Crypto Whales[/bold cyan]")
    console.print(render_crypto_whale_table(ALL_WHALES["crypto_whales"]))
    console.print()

    # ── Tab 5: Market Makers ──────────────────────────────────────────────────
    console.print("[bold cyan]Tab 5: Market Makers[/bold cyan]")
    console.print(render_crypto_whale_table(ALL_WHALES["market_makers"]))
    console.print()

    # ── Tab 6: Political Money ────────────────────────────────────────────────
    console.print("[bold cyan]Tab 6: Political Money[/bold cyan]")
    console.print(render_whale_summary_table("political_money", ALL_WHALES["political_money"]))

    console.print("\n[dim]Fetching recent Congressional trades...[/dim]")
    capitol = fetch_capitol_trades(limit=15)
    if capitol:
        console.print(render_capitol_trades_table(capitol))
        summary_lines.append(
            "Recent Congressional trades: "
            + ", ".join([f"{t['politician']} {t['action']} {t['ticker']}" for t in capitol[:5]])
        )

    console.print()
    return "\n".join(summary_lines)
