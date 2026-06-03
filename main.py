#!/usr/bin/env python3
"""
SignalForge
Modes:
  full     — AI infra + whales + stocks (all sectors + gems + ETF) + tech briefing
  aii      — AI Infrastructure value-chain scan (hunt the 'next Micron')
  portfolio— Defensive Alpha: beta-adjusted alpha + downside-protected construction
  stocks   — sector scan + hidden gems + ETF (no tech news)
  briefing — tech news only (no stocks)
  gems     — hidden gems only (fastest)
  whales   — smart money tracker only (7 tabs)
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
from stocks.ai_infrastructure import (
    scan_ai_infrastructure, render_opportunity_leaderboard,
    render_layer_table, build_ai_infra_context,
)
from portfolio.engine import run_portfolio_engine
from portfolio.display import (
    render_factor_table, render_portfolio_table,
    render_stress_panel, render_education_panel, build_portfolio_context,
    render_risk_parity_table, render_method_comparison_panel,
)
from analysis.ai_analyst import summarize_daily_data, analyze_full_market, analyze_ai_infrastructure, analyze_portfolio
from analysis.llm_client import get_provider
from analysis.headline_trades import analyze_headline_trades, render_headline_trades_panel
from analysis.emailer import send_daily_report, check_email_config
from analysis.report_builder import (
    ai_infra_section_md, whales_section_md, etf_section_md,
    sectors_section_md, gems_section_md,
)
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


def run_portfolio(target_beta: float = 0.60):
    """
    Defensive portfolio engine — beta-adjusted alpha + AQR-style construction.
    Builds a portfolio designed to keep most of the upside while losing far less
    when the market falls. Returns nothing (renders to pager).
    """
    console.print(Rule(f"[bold green]🛡️  Defensive Alpha — Portfolio Construction — {TODAY}[/bold green]"))
    console.print("[dim]Beta-adjusted alpha (appraisal ratio) + convexity sleeve → win when the market is down[/dim]\n")

    console.print("[bold]📊 Fetching 5y price histories + SPY benchmark...[/bold]")
    with console.status("Fetching universe...") as status:
        def _progress(done, tot):
            status.update(f"Fetching price histories... {done}/{tot}")
        result = run_portfolio_engine(target_beta=target_beta, progress=_progress)
    console.print(f"  ✓ {len(result.profiles)} names modeled vs SPY\n")

    pf, s = result.portfolio, result.stress
    console.print(f"  ✓ Portfolio beta {pf.port_beta:.2f} | downside capture {s.downside_capture:.2f} | "
                  f"wins {s.win_rate_down_months:.0f}% of down months\n")

    console.print("[bold yellow]🧠 Generating plain-English portfolio commentary (EN + 中文)...[/bold yellow]")
    with console.status("AI explaining the strategy..."):
        commentary = analyze_portfolio(build_portfolio_context(result))
    console.print("  ✓ Commentary done — opening in pager...\n")

    display = Console(width=280)
    with display.pager(styles=True):
        display.print(Rule(f"[bold green]🛡️  Defensive Alpha — {TODAY}[/bold green]"))
        display.print()
        display.print(render_education_panel())
        display.print()
        display.print(render_factor_table(result))
        display.print()
        display.print(render_portfolio_table(result))
        display.print()
        display.print(render_stress_panel(result))
        display.print()
        if result.rp_portfolio is not None:
            display.print(render_risk_parity_table(result))
            display.print()
            display.print(render_method_comparison_panel(result))
            display.print()
        display.print(Panel(
            Markdown(commentary),
            title="[bold green]Portfolio Strategist Commentary / 投资组合策略解读[/bold green]",
            border_style="green", padding=(1, 2),
        ))
        display.print()
        display.print(_SCROLL_HINT)

    # Build a markdown section for the email/report.
    report_md = _portfolio_report_md(result, commentary)
    return result, report_md


def _portfolio_report_md(result, commentary: str) -> str:
    """Plain-markdown rendering of the portfolio for the email report."""
    pf, s = result.portfolio, result.stress
    lines = []
    lines.append("### 🛡️ Defensive Portfolio — Holdings")
    lines.append("")
    lines.append("| Ticker | Name | Sleeve | Weight | Beta | Alpha%/yr | Appraisal |")
    lines.append("|--------|------|--------|--------|------|-----------|-----------|")
    for h in result.portfolio.holdings:
        p = h.profile
        lines.append(f"| {p.ticker} | {p.name} | {p.sleeve} | {h.weight*100:.1f}% | "
                     f"{p.beta_lagged:.2f} | {p.alpha_annual:+.1f} | {p.appraisal_ratio:+.2f} |")
    if pf.cash_weight > 0.005:
        lines.append(f"| CASH | Cash | cash | {pf.cash_weight*100:.1f}% | 0.00 | — | — |")
    lines.append("")
    lines.append(f"**Portfolio beta {pf.port_beta:.2f}** (target {pf.target_beta:.2f}) · "
                 f"alpha {pf.port_alpha_annual:+.1f}%/yr · appraisal {pf.port_appraisal:.2f}")
    lines.append("")
    lines.append("### 🛡️ Stress Test — Win When the Market Is Down")
    lines.append("")
    lines.append(f"- **Downside capture:** {s.downside_capture:.2f}  ·  **Upside capture:** {s.upside_capture:.2f}  ·  **Capture ratio:** {s.capture_ratio:.2f}")
    lines.append(f"- **Win rate in down months:** {s.win_rate_down_months:.0f}%")
    lines.append(f"- **Max drawdown:** portfolio {s.port_max_drawdown:.1f}% vs SPY {s.spy_max_drawdown:.1f}%")
    lines.append(f"- **Annual return:** portfolio {s.port_ann_return:.1f}% vs SPY {s.spy_ann_return:.1f}%  ·  **Sharpe:** {s.port_sharpe:.2f} vs {s.spy_sharpe:.2f}")
    for label, d in s.stress_windows.items():
        lines.append(f"- **{label}:** portfolio {d['port']:+.1f}% vs SPY {d['spy']:+.1f}%")
    lines.append("")

    # ── Risk Parity comparison (Bridgewater All Weather) ──────────────────────
    if result.rp_portfolio is not None and result.rp_stress is not None:
        rp, rs = result.rp_portfolio, result.rp_stress
        lines.append("### ⚖️ Risk Parity vs Defensive Alpha — Same Universe, Two Methods")
        lines.append("")
        lines.append("| Metric | 🛡️ Defensive Alpha | ⚖️ Risk Parity |")
        lines.append("|--------|--------------------|----------------|")
        lines.append(f"| Annual return | {s.port_ann_return:+.1f}% | {rs.port_ann_return:+.1f}% |")
        lines.append(f"| Annual vol | {s.port_ann_vol:.1f}% | {rs.port_ann_vol:.1f}% |")
        lines.append(f"| Sharpe | {s.port_sharpe:.2f} | {rs.port_sharpe:.2f} |")
        lines.append(f"| Max drawdown | {s.port_max_drawdown:.1f}% | {rs.port_max_drawdown:.1f}% |")
        lines.append(f"| Downside capture | {s.downside_capture:.2f} | {rs.downside_capture:.2f} |")
        lines.append(f"| Portfolio beta | {pf.port_beta:.2f} | {rp.port_beta:.2f} |")
        lines.append("")

    lines.append(commentary)
    return "\n".join(lines)


def run_ai_infra():
    """
    AI Infrastructure value-chain scan — hunt the 'next Micron'.
    Scores every name across the stack on valuation + growth + analyst upside,
    surfacing fairly-valued high-potential setups over already-extended winners.
    Returns (analysis_text, picks) for reuse in the full report / email.
    """
    console.print(Rule(f"[bold green]🛰️  AI Infrastructure Value Chain — {TODAY}[/bold green]"))
    console.print("[dim]Hunting the next Micron: fair value + high growth + real upside, across the whole AI stack[/dim]\n")

    console.print("[bold]🛰️  Scanning AI infrastructure value chain...[/bold]")
    picks = scan_ai_infrastructure()
    console.print(f"  ✓ {len(picks)} names scored across {len(set(p.layer for p in picks))} layers\n")

    n_winners = sum(1 for p in picks if p.is_next_micron)
    console.print(f"  ⭐ {n_winners} 'next Micron' asymmetric setups flagged\n")

    console.print("[bold yellow]🧠 Generating AI infrastructure briefing (EN + 中文)...[/bold yellow]")
    with console.status("AI analyzing the value chain..."):
        analysis = analyze_ai_infrastructure(build_ai_infra_context(picks))
    console.print("  ✓ Analysis done — opening in pager...\n")

    display = Console(width=280)
    with display.pager(styles=True):
        display.print(Rule(f"[bold green]🛰️  AI Infrastructure Value Chain — {TODAY}[/bold green]"))
        display.print()
        display.print(render_opportunity_leaderboard(picks, top_n=20))
        display.print()
        display.print(Rule("[dim]Value-chain breakdown by layer[/dim]"))
        display.print()

        # Per-layer tables, preserving the value-chain order from the universe.
        from config.universe import AI_INFRASTRUCTURE
        for layer in AI_INFRASTRUCTURE:
            layer_picks = [p for p in picks if p.layer == layer]
            if layer_picks:
                display.print(render_layer_table(layer, layer_picks))
                display.print()

        display.print(Panel(
            Markdown(analysis),
            title="[bold green]AI Infrastructure Intelligence / AI 基础设施情报[/bold green]",
            border_style="green", padding=(1, 2),
        ))
        display.print()
        display.print(_SCROLL_HINT)

    return analysis, picks


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
    """Whale tracker only — 7 tabs of smart money intelligence."""
    console.print(Rule(f"[bold yellow]🐋 Smart Money Tracker — {TODAY}[/bold yellow]"))
    run_whale_tracker()


def run_tech_radar():
    """Full run: AI infra FIRST, then whales, stocks, then tech briefing."""

    # ── 0. AI Infrastructure Value Chain (the headline section) ───────────────
    console.print(Rule(f"[bold green]🛰️  Part 0: AI Infrastructure Value Chain[/bold green]"))
    ai_infra_analysis, ai_picks = run_ai_infra()
    console.print()

    # ── 1. Defensive Alpha — Portfolio Construction ───────────────────────────
    console.print(Rule(f"[bold green]🛡️  Part 1: Defensive Alpha — Portfolio Construction[/bold green]"))
    _portfolio_result, portfolio_report_md = run_portfolio()
    console.print()

    # ── 2. Whale Tracker (has its own pager) ──────────────────────────────────
    console.print(Rule(f"[bold yellow]🐋 Part 2: Smart Money / Whale Tracker[/bold yellow]"))
    _whale_summary, whale_trades = run_whale_tracker()
    console.print()

    # ── 3. Stocks (has its own pager) ─────────────────────────────────────────
    sector_results, etf_stocks, gems, stock_analysis, headline_analysis = run_stocks(briefing_mode=False)
    console.print()

    # ── 4. Tech Briefing ──────────────────────────────────────────────────────
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

    # Save combined report — mirror every terminal section (data tables + the
    # LLM narrative) so the daily email is complete, not just the prose.
    output_file = OUTPUT_DIR / f"radar_{TODAY}.md"

    def _section(f, title, *blocks):
        """Write a '## title' section only if it has real content."""
        body = "\n\n".join(b.strip() for b in blocks if b and b.strip())
        if body:
            f.write(f"## {title}\n\n{body}\n\n---\n\n")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"# Frontier Tech Radar — {TODAY}\n\n")
        _section(f, "🛰️ AI Infrastructure Value Chain",
                 ai_infra_section_md(ai_picks, ai_infra_analysis))
        _section(f, "🛡️ Defensive Alpha — Portfolio Construction",
                 portfolio_report_md)
        _section(f, "🐋 Smart Money — Whale & Insider Tracker",
                 whales_section_md(whale_trades))
        _section(f, "📦 ETF Rankings",
                 etf_section_md(etf_stocks))
        _section(f, "🔭 Sector Leaders",
                 sectors_section_md(sector_results))
        _section(f, "💎 Hidden Gems",
                 gems_section_md(gems))
        _section(f, "📊 Market Intelligence Report",
                 stock_analysis)
        _section(f, "🔭 Tech Briefing",
                 briefing)
    console.print(f"\n[bold green]✅ Report saved: {output_file}[/bold green]")
    return headline_analysis


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
    # headline analysis already runs inside run_stocks() → run_tech_radar()
    headline_trades_text = run_tech_radar()

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
    parser.add_argument("--mode", choices=["full", "aii", "portfolio", "stocks", "briefing", "gems", "whales", "backtest", "email"], default="full")
    parser.add_argument("--target-beta", type=float, default=0.60, help="Target portfolio beta for --mode portfolio (default 0.60)")
    args = parser.parse_args()

    provider = get_provider()
    if provider == "groq" and not os.getenv("GROQ_API_KEY"):
        console.print("[red]Error: Set GROQ_API_KEY in .env[/red]"); sys.exit(1)

    if args.mode == "full":         run_tech_radar()
    elif args.mode == "aii":        run_ai_infra()
    elif args.mode == "portfolio":  run_portfolio(target_beta=args.target_beta)
    elif args.mode == "stocks":     run_stocks()
    elif args.mode == "briefing":   run_briefing_only()
    elif args.mode == "gems":       run_gems_only()
    elif args.mode == "whales":     run_whales_only()
    elif args.mode == "backtest":   run_backtest_mode()
    elif args.mode == "email":      run_email_mode()
