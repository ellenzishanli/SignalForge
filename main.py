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
os.environ.setdefault("LESS", "-RS")  # horizontal scroll in all pagers

from whales.whale_display import run_whale_tracker
from scrapers.github_trending import fetch_github_trending
from scrapers.producthunt import fetch_producthunt_top
from scrapers.feeds import fetch_feeds
from scrapers.reddit_ai import fetch_reddit_hot
from scrapers.yc import fetch_yc_latest
from scrapers.macro_news import fetch_macro_headlines
from stocks.sector_scan import scan_all_sectors, scan_etfs, render_sector_table, render_etf_table, build_sector_context_for_ai
from stocks.hidden_gems import scan_hidden_gems, render_hidden_gems_table
from analysis.ai_analyst import summarize_daily_data, analyze_full_market
from analysis.llm_client import get_provider
from analysis.headline_trades import analyze_headline_trades, render_headline_trades_panel
from analysis.emailer import send_daily_report, check_email_config
from config.universe import SECTORS

console = Console(width=280)
TODAY = datetime.now().strftime("%Y-%m-%d")
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

_SCROLL_HINT = "[dim]← → scroll horizontally  |  ↑ ↓ scroll vertically  |  q to exit[/dim]"


def run_headline_trades() -> str:
    """
    Fetch macro headlines, run LLM analysis, display a Rich panel in the pager,
    and return the raw analysis text (for use in email reports).
    """
    console.print("[bold red]🚨 Fetching macro headlines...[/bold red]")
    with console.status("Fetching RSS feeds..."):
        headlines = fetch_macro_headlines()
    console.print(f"  ✓ {len(headlines)} headlines fetched\n")

    console.print("[bold yellow]🧠 Analyzing macro shocks...[/bold yellow]")
    with console.status("LLM identifying macro events and trade ideas..."):
        analysis = analyze_headline_trades(headlines)
    console.print("  ✓ Analysis done — opening in pager...\n")

    panel = render_headline_trades_panel(analysis)
    display = Console(width=280)
    with display.pager(styles=True):
        display.print(Rule("[bold red]🚨 Macro Shock Monitor[/bold red]"))
        display.print()
        display.print(panel)
        display.print()
        display.print(_SCROLL_HINT)

    return analysis


def run_stocks(briefing_mode: bool = False):
    """Core stock analysis — sectors + hidden gems + ETF."""

    # ── Phase 1: Data loading (spinners visible in terminal) ──────────────────
    console.print(Rule(f"[bold green]📈 Market Scan — {TODAY}[/bold green]"))
    console.print(f"[dim]LLM: {get_provider().upper()} | Sectors: {len(SECTORS)} | Mode: {'full' if not briefing_mode else 'stocks-only'}[/dim]\n")

    console.print("[bold]📦 Scanning ETFs...[/bold]")
    etf_stocks = scan_etfs()
    console.print(f"  ✓ {len(etf_stocks)} ETFs loaded\n")

    console.print(f"[bold]🔭 Scanning {len(SECTORS)} market sectors...[/bold]")
    sector_results = scan_all_sectors(top_n=4)
    all_sector_stocks = sector_results.get("_all", [])
    console.print(f"  ✓ {len(all_sector_stocks)} stocks loaded across {len(SECTORS)} sectors\n")

    console.print("[bold]💎 Scanning hidden gems universe...[/bold]")
    gems = scan_hidden_gems()
    console.print(f"  ✓ {len(gems)} gems loaded\n")

    console.print("[bold yellow]🧠 Generating bilingual AI market analysis...[/bold yellow]")
    context = build_sector_context_for_ai(sector_results, etf_stocks, gems)
    with console.status("AI analyzing (English + Chinese)..."):
        analysis = analyze_full_market(context, len(SECTORS), len(gems))
    console.print("  ✓ Analysis done\n")

    console.print("[bold red]🚨 Fetching macro headlines...[/bold red]")
    with console.status("Fetching RSS feeds..."):
        headlines = fetch_macro_headlines()
    console.print(f"  ✓ {len(headlines)} headlines fetched\n")

    console.print("[bold yellow]🧠 Analyzing macro shocks...[/bold yellow]")
    with console.status("LLM identifying macro events and trade ideas..."):
        headline_analysis = analyze_headline_trades(headlines)
    console.print("  ✓ Macro analysis done — opening results in pager...\n")

    # ── Phase 2: Display (in pager — use ← → to scroll wide tables) ──────────
    display = Console(width=280)
    with display.pager(styles=True):
        display.print(Rule(f"[bold green]📈 Market Scan — {TODAY}[/bold green]"))
        display.print()

        display.print(render_etf_table(etf_stocks))
        display.print()

        for sector_name, stocks in sector_results.items():
            if sector_name == "_all" or not stocks:
                continue
            display.print(render_sector_table(sector_name, stocks))
            display.print()

        display.print(render_hidden_gems_table(gems))
        display.print()

        display.print(render_headline_trades_panel(headline_analysis))
        display.print()

        display.print(Panel(
            Markdown(analysis),
            title="[bold yellow]Market Intelligence Report / 市场情报报告[/bold yellow]",
            border_style="yellow", padding=(1, 2),
        ))
        display.print()
        display.print(_SCROLL_HINT)

    return sector_results, etf_stocks, gems, analysis, headline_analysis


def run_whales_only():
    """Whale tracker only — 6 tabs of smart money intelligence."""
    console.print(Rule(f"[bold yellow]🐋 Smart Money Tracker — {TODAY}[/bold yellow]"))
    run_whale_tracker()


def run_tech_radar():
    """Full run: whales FIRST, then stocks, then tech briefing."""

    # ── 0. Whale Tracker (has its own pager) ──────────────────────────────────
    console.print(Rule(f"[bold yellow]🐋 Part 0: Smart Money / Whale Tracker[/bold yellow]"))
    run_whale_tracker()
    console.print()

    # ── 1. Stocks (has its own pager) ─────────────────────────────────────────
    sector_results, etf_stocks, gems, stock_analysis, _headline_analysis = run_stocks(briefing_mode=False)
    console.print()

    # ── 2. Tech Briefing ──────────────────────────────────────────────────────
    console.print(Rule("[bold cyan]🔭 Tech Radar Briefing[/bold cyan]"))

    console.print("[bold]Fetching tech data sources...[/bold]")
    with console.status("Fetching..."):
        github   = fetch_github_trending()
        products = fetch_producthunt_top()
        feeds    = fetch_feeds()
        reddit   = fetch_reddit_hot()
        yc       = fetch_yc_latest("W25")
    console.print(f"  ✓ GitHub:{len(github)} | Feeds:{len(feeds)} | Reddit:{len(reddit)} | YC:{len(yc)}\n")

    with console.status("Generating tech briefing (bilingual)..."):
        briefing = summarize_daily_data(github, products, feeds, reddit, yc)
    console.print("  ✓ Briefing done — opening in pager...\n")

    display = Console(width=280)
    with display.pager(styles=True):
        display.print(Rule("[bold cyan]🔭 Frontier Tech Radar — Daily Briefing[/bold cyan]"))
        display.print()
        display.print(Panel(
            Markdown(briefing),
            title="[bold cyan]Frontier Tech Radar — Daily Briefing / 每日科技简报[/bold cyan]",
            border_style="cyan", padding=(1, 2),
        ))
        display.print()
        display.print(_SCROLL_HINT)

    # Save combined report
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

    # ── Phase 1: Loading ──────────────────────────────────────────────────────
    console.print(Rule(f"[bold yellow]💎 Hidden Gems Scan — {TODAY}[/bold yellow]"))
    gems = scan_hidden_gems()
    console.print(f"  ✓ {len(gems)} gems loaded\n")

    console.print("[bold]🧠 AI analysis...[/bold]")
    from stocks.sector_scan import build_sector_context_for_ai
    context = build_sector_context_for_ai({}, [], gems)
    with console.status("Analyzing..."):
        analysis = analyze_full_market(context, 0, len(gems))
    console.print("  ✓ Done — opening in pager...\n")

    # ── Phase 2: Display ──────────────────────────────────────────────────────
    display = Console(width=280)
    with display.pager(styles=True):
        display.print(Rule(f"[bold yellow]💎 Hidden Gems — {TODAY}[/bold yellow]"))
        display.print()
        display.print(render_hidden_gems_table(gems))
        display.print()
        display.print(Panel(Markdown(analysis), title="[bold yellow]Hidden Gems Analysis[/bold yellow]",
                            border_style="yellow", padding=(1, 2)))
        display.print()
        display.print(_SCROLL_HINT)


def run_briefing_only():
    """Tech briefing only."""

    # ── Phase 1: Loading ──────────────────────────────────────────────────────
    console.print(Rule(f"[bold cyan]🔭 Tech Briefing — {TODAY}[/bold cyan]"))
    with console.status("Fetching data sources..."):
        github   = fetch_github_trending()
        products = fetch_producthunt_top()
        feeds    = fetch_feeds()
        reddit   = fetch_reddit_hot()
        yc       = fetch_yc_latest("W25")
    console.print(f"  ✓ GitHub:{len(github)} | Feeds:{len(feeds)} | Reddit:{len(reddit)} | YC:{len(yc)}\n")

    with console.status("Generating bilingual briefing..."):
        briefing = summarize_daily_data(github, products, feeds, reddit, yc)
    console.print("  ✓ Done — opening in pager...\n")

    # ── Phase 2: Display ──────────────────────────────────────────────────────
    display = Console(width=280)
    with display.pager(styles=True):
        display.print(Rule(f"[bold cyan]🔭 Tech Briefing — {TODAY}[/bold cyan]"))
        display.print()
        display.print(Panel(Markdown(briefing), title="[bold cyan]Daily Tech Briefing / 每日科技简报[/bold cyan]",
                            border_style="cyan", padding=(1, 2)))
        display.print()
        display.print(_SCROLL_HINT)


def run_email_mode():
    """
    Full run (whales + stocks + briefing) then email the saved report.

    Workflow:
      1. run_tech_radar()  — generates output/radar_YYYY-MM-DD.md
      2. run_headline_trades()  — fetches and analyses macro headlines
      3. Read the saved report file
      4. Send HTML email with headline trades + full report
    """
    console.print(Rule(f"[bold blue]📧 Email Report Mode — {TODAY}[/bold blue]"))

    # Full pipeline — saves report to output/radar_{TODAY}.md
    run_tech_radar()

    # Standalone headline trades (run_tech_radar already ran stocks which
    # fetches headlines internally, but we want a fresh standalone panel here
    # for the email; use the already-computed analysis if possible)
    console.print()
    console.print(Rule("[bold red]🚨 Running Standalone Headline Trades for Email[/bold red]"))
    headline_trades_text = run_headline_trades()

    # Read the saved report
    output_file = OUTPUT_DIR / f"radar_{TODAY}.md"
    report_md = ""
    if output_file.exists():
        report_md = output_file.read_text(encoding="utf-8")
        console.print(f"\n[dim]Report file: {output_file}[/dim]")
    else:
        console.print(f"[yellow]Warning: report file not found at {output_file}[/yellow]")
        report_md = "(Report file not found — check run_tech_radar output)"

    # Send email
    console.print()
    console.print("[bold blue]📧 Sending email report...[/bold blue]")
    if not check_email_config():
        console.print(
            "[yellow]Email not configured. Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env "
            "to enable automatic email delivery.[/yellow]"
        )
    send_daily_report(report_md, headline_trades=headline_trades_text)
    console.print("[bold green]✅ Email mode complete.[/bold green]")


def run_backtest_mode():
    """Walk-forward backtest + factor weight optimization."""
    from stocks.backtest import run_backtest_and_display
    run_backtest_and_display(console)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Frontier Tech Radar")
    parser.add_argument("--mode", choices=["full", "stocks", "briefing", "gems", "whales", "backtest", "email"], default="full")
    args = parser.parse_args()

    provider = get_provider()
    if provider == "groq" and not os.getenv("GROQ_API_KEY"):
        console.print("[red]Error: Set GROQ_API_KEY in .env[/red]"); sys.exit(1)

    if args.mode == "full":         run_tech_radar()
    elif args.mode == "stocks":     run_stocks()
    elif args.mode == "briefing":   run_briefing_only()
    elif args.mode == "gems":       run_gems_only()
    elif args.mode == "whales":     run_whales_only()
    elif args.mode == "backtest":   run_backtest_mode()
    elif args.mode == "email":      run_email_mode()
