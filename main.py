#!/usr/bin/env python3
"""
SignalForge
Modes:
  full     — whales + stocks (all sectors + gems + ETF) + tech briefing
  stocks   — sector scan + hidden gems + ETF (no tech news)
  briefing — tech news only (no stocks)
  gems     — hidden gems only (fastest)
  whales   — smart money tracker only (6 tabs)
"""
import os, sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.rule import Rule

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from whales.whale_display import run_whale_tracker
from scrapers.github_trending import fetch_github_trending
from scrapers.producthunt import fetch_producthunt_top
from scrapers.feeds import fetch_feeds
from scrapers.reddit_ai import fetch_reddit_hot
from scrapers.yc import fetch_yc_latest
from stocks.sector_scan import scan_all_sectors, scan_etfs, render_sector_table, render_etf_table, build_sector_context_for_ai
from stocks.hidden_gems import scan_hidden_gems, render_hidden_gems_table
from analysis.ai_analyst import summarize_daily_data, analyze_full_market
from analysis.llm_client import get_provider
from config.universe import SECTORS

console = Console(width=220)
TODAY = datetime.now().strftime("%Y-%m-%d")
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def run_stocks(briefing_mode: bool = False):
    """Core stock analysis — sectors + hidden gems + ETF."""
    console.print(Rule(f"[bold green]📈 Market Scan — {TODAY}[/bold green]"))
    console.print(f"[dim]LLM: {get_provider().upper()} | Sectors: {len(SECTORS)} | Mode: {'full' if not briefing_mode else 'stocks-only'}[/dim]\n")

    # ── ETF scan (always first) ────────────────────────────────────────────────
    console.print("[bold]📦 Scanning ETFs...[/bold]")
    etf_stocks = scan_etfs()
    console.print(f"  ✓ {len(etf_stocks)} ETFs loaded\n")
    console.print(render_etf_table(etf_stocks))
    console.print()

    # ── Sector scan ────────────────────────────────────────────────────────────
    console.print(f"[bold]🔭 Scanning {len(SECTORS)} market sectors...[/bold]")
    sector_results = scan_all_sectors(top_n=4)
    all_sector_stocks = sector_results.get("_all", [])
    console.print(f"  ✓ {len(all_sector_stocks)} stocks loaded across {len(SECTORS)} sectors\n")

    for sector_name, stocks in sector_results.items():
        if sector_name == "_all" or not stocks:
            continue
        console.print(render_sector_table(sector_name, stocks))
        console.print()

    # ── Hidden Gems ────────────────────────────────────────────────────────────
    console.print("[bold]💎 Scanning hidden gems universe...[/bold]")
    gems = scan_hidden_gems()
    console.print(f"  ✓ {len(gems)} gems loaded\n")
    console.print(render_hidden_gems_table(gems))
    console.print()

    # ── AI Analysis ────────────────────────────────────────────────────────────
    console.print("[bold yellow]🧠 Generating bilingual AI market analysis...[/bold yellow]")
    context = build_sector_context_for_ai(sector_results, etf_stocks, gems)
    with console.status("AI analyzing (English + Chinese)..."):
        analysis = analyze_full_market(context, len(SECTORS), len(gems))

    console.print(Panel(
        Markdown(analysis),
        title="[bold yellow]Market Intelligence Report / 市场情报报告[/bold yellow]",
        border_style="yellow", padding=(1, 2),
    ))

    return sector_results, etf_stocks, gems, analysis


def run_whales_only():
    """Whale tracker only — 6 tabs of smart money intelligence."""
    console.print(Rule(f"[bold yellow]🐋 Smart Money Tracker — {TODAY}[/bold yellow]"))
    run_whale_tracker()


def run_tech_radar():
    """Full run: whales FIRST, then stocks, then tech briefing."""
    # ── 0. Whale Tracker (shown first) ────────────────────────────────────────
    console.print(Rule(f"[bold yellow]🐋 Part 0: Smart Money / Whale Tracker[/bold yellow]"))
    run_whale_tracker()
    console.print()

    sector_results, etf_stocks, gems, stock_analysis = run_stocks(briefing_mode=False)

    console.print()
    console.print(Rule("[bold cyan]🔭 Tech Radar Briefing[/bold cyan]"))

    with console.status("Fetching tech data sources..."):
        github   = fetch_github_trending()
        products = fetch_producthunt_top()
        feeds    = fetch_feeds()
        reddit   = fetch_reddit_hot()
        yc       = fetch_yc_latest("W25")

    console.print(f"[dim]GitHub:{len(github)} | Feeds:{len(feeds)} | Reddit:{len(reddit)} | YC:{len(yc)}[/dim]\n")

    with console.status("Generating tech briefing (bilingual)..."):
        briefing = summarize_daily_data(github, products, feeds, reddit, yc)

    console.print(Panel(
        Markdown(briefing),
        title="[bold cyan]Frontier Tech Radar — Daily Briefing / 每日科技简报[/bold cyan]",
        border_style="cyan", padding=(1, 2),
    ))

    # Save
    output_file = OUTPUT_DIR / f"radar_{TODAY}.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"# Frontier Tech Radar — {TODAY}\n\n")
        f.write("## Market Intelligence Report\n\n")
        f.write(stock_analysis + "\n\n---\n\n")
        f.write("## Tech Briefing\n\n")
        f.write(briefing + "\n")
    console.print(f"\n[bold green]✅ Report saved: {output_file}[/bold green]")


def run_gems_only():
    """Quick scan: hidden gems only."""
    console.print(Rule(f"[bold yellow]💎 Hidden Gems Scan — {TODAY}[/bold yellow]"))
    gems = scan_hidden_gems()
    console.print(f"[dim]{len(gems)} gems loaded[/dim]\n")
    console.print(render_hidden_gems_table(gems))

    console.print("\n[bold]🧠 AI analysis...[/bold]")
    from stocks.sector_scan import build_sector_context_for_ai
    context = build_sector_context_for_ai({}, [], gems)
    with console.status("Analyzing..."):
        analysis = analyze_full_market(context, 0, len(gems))
    console.print(Panel(Markdown(analysis), title="Hidden Gems Analysis", border_style="yellow", padding=(1,2)))


def run_briefing_only():
    """Tech briefing only."""
    console.print(Rule(f"[bold cyan]🔭 Tech Briefing — {TODAY}[/bold cyan]"))
    with console.status("Fetching..."):
        github = fetch_github_trending()
        products = fetch_producthunt_top()
        feeds  = fetch_feeds()
        reddit = fetch_reddit_hot()
        yc     = fetch_yc_latest("W25")
    with console.status("Generating bilingual briefing..."):
        briefing = summarize_daily_data(github, products, feeds, reddit, yc)
    console.print(Panel(Markdown(briefing), title="Daily Tech Briefing", border_style="cyan", padding=(1,2)))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Frontier Tech Radar")
    parser.add_argument("--mode", choices=["full", "stocks", "briefing", "gems", "whales"], default="full")
    args = parser.parse_args()

    provider = get_provider()
    if provider == "groq" and not os.getenv("GROQ_API_KEY"):
        console.print("[red]Error: Set GROQ_API_KEY in .env[/red]"); sys.exit(1)

    if args.mode == "full":       run_tech_radar()
    elif args.mode == "stocks":   run_stocks()
    elif args.mode == "briefing": run_briefing_only()
    elif args.mode == "gems":     run_gems_only()
    elif args.mode == "whales":   run_whales_only()
