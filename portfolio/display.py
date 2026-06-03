"""
Rich rendering for the defensive portfolio engine.
"""
from rich.table import Table
from rich.panel import Panel
from rich import box

from portfolio.engine import PortfolioResult

_SLEEVE_STYLE = {"alpha": "bold green", "defensive": "cyan", "convexity": "magenta"}
_SLEEVE_LABEL = {"alpha": "ALPHA", "defensive": "DEFENSE", "convexity": "CONVEX"}


def _c(v, good_high=True, hi=0.0, lo=0.0, fmt="{:+.2f}"):
    s = fmt.format(v)
    if v != v:  # NaN
        return "[dim]—[/dim]"
    if good_high:
        color = "green" if v > hi else "red" if v < lo else "white"
    else:
        color = "green" if v < lo else "red" if v > hi else "white"
    return f"[{color}]{s}[/{color}]"


def render_factor_table(result: PortfolioResult) -> Table:
    """Per-name beta-adjusted alpha: beta, Dimson beta, alpha, appraisal, convexity."""
    t = Table(
        title="🔬 Beta-Adjusted Alpha — Factor Model (vs SPY, 5y daily)",
        box=box.ROUNDED, show_lines=False, header_style="bold white on dark_blue",
        min_width=170,
    )
    t.add_column("Ticker", style="bold", width=7, no_wrap=True)
    t.add_column("Name", width=22, no_wrap=True)
    t.add_column("Sleeve", width=8)
    t.add_column("Beta", justify="right", width=7)
    t.add_column("Dimson β", justify="right", width=9)
    t.add_column("Alpha%/yr", justify="right", width=10)
    t.add_column("Appraisal", justify="right", width=10)
    t.add_column("Down β", justify="right", width=8)
    t.add_column("Up β", justify="right", width=7)
    t.add_column("Convexity", justify="right", width=10)
    t.add_column("R²", justify="right", width=6)

    for p in sorted(result.profiles, key=lambda x: x.appraisal_ratio, reverse=True):
        slv_c = _SLEEVE_STYLE.get(p.sleeve, "white")
        t.add_row(
            p.ticker, p.name[:22],
            f"[{slv_c}]{_SLEEVE_LABEL.get(p.sleeve, p.sleeve)}[/{slv_c}]",
            f"{p.beta:.2f}",
            f"{p.beta_lagged:.2f}",
            _c(p.alpha_annual, hi=0, lo=0, fmt="{:+.1f}"),
            _c(p.appraisal_ratio, hi=0.3, lo=0, fmt="{:+.2f}"),
            f"{p.downside_beta:.2f}" if p.downside_beta == p.downside_beta else "—",
            f"{p.upside_beta:.2f}" if p.upside_beta == p.upside_beta else "—",
            _c(p.convexity, hi=0, lo=0, fmt="{:+.2f}"),
            f"{p.r_squared:.2f}",
        )
    return t


def render_portfolio_table(result: PortfolioResult) -> Table:
    """The constructed defensive book — weights by name."""
    pf = result.portfolio
    t = Table(
        title=f"🛡️  Defensive Portfolio — target β {pf.target_beta:.2f}, achieved β {pf.port_beta:.2f}",
        box=box.ROUNDED, show_lines=False, header_style="bold white on dark_green",
        min_width=150,
    )
    t.add_column("Ticker", style="bold", width=7, no_wrap=True)
    t.add_column("Name", width=24, no_wrap=True)
    t.add_column("Sleeve", width=8)
    t.add_column("Weight", justify="right", width=8)
    t.add_column("Beta", justify="right", width=7)
    t.add_column("Alpha%/yr", justify="right", width=10)
    t.add_column("Appraisal", justify="right", width=10)
    t.add_column("Weight bar", width=24)

    for h in result.portfolio.holdings:
        p = h.profile
        slv_c = _SLEEVE_STYLE.get(p.sleeve, "white")
        bar = "█" * max(1, round(h.weight * 80))
        t.add_row(
            p.ticker, p.name[:24],
            f"[{slv_c}]{_SLEEVE_LABEL.get(p.sleeve, p.sleeve)}[/{slv_c}]",
            f"[bold]{h.weight*100:.1f}%[/bold]",
            f"{p.beta_lagged:.2f}",
            _c(p.alpha_annual, hi=0, lo=0, fmt="{:+.1f}"),
            _c(p.appraisal_ratio, hi=0.3, lo=0, fmt="{:+.2f}"),
            f"[{slv_c}]{bar}[/{slv_c}]",
        )
    if pf.cash_weight > 0.005:
        t.add_row("CASH", "Cash / dry powder", "[dim]CASH[/dim]",
                  f"[bold]{pf.cash_weight*100:.1f}%[/bold]", "0.00", "—", "—",
                  "[dim]" + "█" * max(1, round(pf.cash_weight * 80)) + "[/dim]")
    return t


def render_risk_parity_table(result: PortfolioResult) -> Table:
    """The Bridgewater Equal-Risk-Contribution book — weights vs each name's vol.

    The story to read: weight runs *inverse* to volatility. Low-vol ballast
    (bonds, gold, defensives) gets scaled UP, high-vol growth gets scaled DOWN,
    until every name contributes the same share of portfolio risk.
    """
    rp = result.rp_portfolio
    t = Table(
        title=f"⚖️  Risk Parity (Equal Risk Contribution) — achieved β {rp.port_beta:.2f}",
        box=box.ROUNDED, show_lines=False, header_style="bold white on dark_magenta",
        min_width=150,
    )
    t.add_column("Ticker", style="bold", width=7, no_wrap=True)
    t.add_column("Name", width=24, no_wrap=True)
    t.add_column("Sleeve", width=8)
    t.add_column("Weight", justify="right", width=8)
    t.add_column("Ann Vol", justify="right", width=8)
    t.add_column("Beta", justify="right", width=7)
    t.add_column("Weight bar", width=24)

    for h in rp.holdings:
        p = h.profile
        slv_c = _SLEEVE_STYLE.get(p.sleeve, "white")
        bar = "█" * max(1, round(h.weight * 80))
        t.add_row(
            p.ticker, p.name[:24],
            f"[{slv_c}]{_SLEEVE_LABEL.get(p.sleeve, p.sleeve)}[/{slv_c}]",
            f"[bold]{h.weight*100:.1f}%[/bold]",
            f"{p.total_vol_annual:.0f}%",
            f"{p.beta_lagged:.2f}",
            f"[{slv_c}]{bar}[/{slv_c}]",
        )
    if rp.cash_weight > 0.005:
        t.add_row("CASH", "Cash / dry powder", "[dim]CASH[/dim]",
                  f"[bold]{rp.cash_weight*100:.1f}%[/bold]", "0%", "0.00",
                  "[dim]" + "█" * max(1, round(rp.cash_weight * 80)) + "[/dim]")
    return t


def render_method_comparison_panel(result: PortfolioResult) -> Panel:
    """Defensive Alpha vs Risk Parity, head to head, on the 5y stress numbers."""
    da, rp = result.stress, result.rp_stress
    dap, rpp = result.portfolio, result.rp_portfolio

    def row(label, da_v, rp_v, fmt="{:.2f}", good_high=True, suffix=""):
        def col(v):
            if v != v:
                return "[dim]—[/dim]"
            return fmt.format(v) + suffix
        # Highlight whichever method is better on this metric.
        a, b = da_v, rp_v
        a_better = (a > b) if good_high else (a < b)
        a_s = f"[bold green]{col(a)}[/bold green]" if a == a and b == b and a_better else col(a)
        b_s = f"[bold green]{col(b)}[/bold green]" if a == a and b == b and not a_better else col(b)
        return f"  {label:<26} {a_s:>22}   {b_s:>22}"

    lines = []
    lines.append(f"  [bold]{'Metric':<26} {'🛡️  Defensive Alpha':>16}   {'⚖️  Risk Parity':>16}[/bold]")
    lines.append("  " + "─" * 64)
    lines.append(row("Annual return", da.port_ann_return, rp.port_ann_return, "{:+.1f}", True, "%"))
    lines.append(row("Annual vol", da.port_ann_vol, rp.port_ann_vol, "{:.1f}", False, "%"))
    lines.append(row("Sharpe ratio", da.port_sharpe, rp.port_sharpe, "{:.2f}", True))
    lines.append(row("Max drawdown", da.port_max_drawdown, rp.port_max_drawdown, "{:+.1f}", True, "%"))
    lines.append(row("Downside capture", da.downside_capture, rp.downside_capture, "{:.2f}", False))
    lines.append(row("Capture ratio", da.capture_ratio, rp.capture_ratio, "{:.2f}", True))
    lines.append(row("Portfolio beta", dap.port_beta, rpp.port_beta, "{:.2f}", False))
    lines.append("")
    lines.append("[dim]Both books are built from the SAME universe. Defensive Alpha sizes by "
                 "beta-adjusted alpha (AQR); Risk Parity sizes purely so every name contributes "
                 "equal risk (Bridgewater All Weather). Green = better on that metric.[/dim]")
    return Panel("\n".join(lines),
                 title="[bold]🆚 Two Methodologies — Defensive Alpha vs Risk Parity (5y)[/bold]",
                 border_style="magenta", padding=(1, 2))


def render_stress_panel(result: PortfolioResult) -> Panel:
    """The payoff: how the book behaves when the market falls."""
    s = result.stress
    pf = result.portfolio

    def pct(v, good_high=True):
        if v != v:
            return "[dim]—[/dim]"
        c = ("green" if v >= 0 else "red") if good_high else ("green" if v < 0 else "red")
        return f"[{c}]{v:+.1f}%[/{c}]"

    dc = s.downside_capture
    dc_str = f"[green]{dc:.2f}[/green]" if dc == dc and dc < 0.8 else (f"[yellow]{dc:.2f}[/yellow]" if dc == dc else "—")

    lines = []
    lines.append("[bold]Convexity — the whole point: keep upside, cut downside[/bold]")
    lines.append(f"  Downside capture : {dc_str}   [dim](portfolio's share of SPY's DOWN days — lower is better)[/dim]")
    lines.append(f"  Upside capture   : [cyan]{s.upside_capture:.2f}[/cyan]   [dim](share of SPY's UP days — higher is better)[/dim]")
    lines.append(f"  Capture ratio    : [bold]{s.capture_ratio:.2f}[/bold]   [dim](> 1.0 = favorable asymmetry / convexity)[/dim]")
    lines.append(f"  Win rate, down months : [bold green]{s.win_rate_down_months:.0f}%[/bold green]   [dim](how often you beat SPY when SPY is red)[/dim]")
    lines.append("")
    lines.append("[bold]Drawdown & risk-adjusted return (5y)[/bold]")
    lines.append(f"  Max drawdown     : portfolio {pct(s.port_max_drawdown)}  vs  SPY {pct(s.spy_max_drawdown)}")
    lines.append(f"  Annual return    : portfolio {pct(s.port_ann_return)}  vs  SPY {pct(s.spy_ann_return)}")
    lines.append(f"  Annual vol       : portfolio [white]{s.port_ann_vol:.1f}%[/white]  vs  SPY [white]{s.spy_ann_vol:.1f}%[/white]")
    lines.append(f"  Sharpe ratio     : portfolio [bold green]{s.port_sharpe:.2f}[/bold green]  vs  SPY [white]{s.spy_sharpe:.2f}[/white]")

    if s.stress_windows:
        lines.append("")
        lines.append("[bold]Historical stress windows[/bold]")
        for label, d in s.stress_windows.items():
            edge = d["spy"] - d["port"]
            lines.append(
                f"  {label:<22}: portfolio {pct(d['port'])}  vs  SPY {pct(d['spy'])}   "
                f"[dim](saved {edge:+.1f} pts)[/dim]"
            )

    lines.append("")
    lines.append(
        f"[dim]Book: β {pf.port_beta:.2f} (down β {pf.port_downside_beta:.2f} / up β {pf.port_upside_beta:.2f}), "
        f"alpha {pf.port_alpha_annual:+.1f}%/yr, appraisal {pf.port_appraisal:.2f}. "
        f"Sleeves — {', '.join(f'{k} {v*100:.0f}%' for k,v in pf.sleeve_weights.items())}.[/dim]"
    )

    return Panel("\n".join(lines), title="[bold green]🛡️  Defensive Stress Test — Win When the Market Is Down[/bold green]",
                 border_style="green", padding=(1, 2))


def build_portfolio_context(result: PortfolioResult) -> str:
    """Compact text summary of the portfolio + stress results for the LLM (low-token)."""
    pf, s = result.portfolio, result.stress
    lines = ["=== CONSTRUCTED DEFENSIVE PORTFOLIO ==="]
    lines.append(
        f"Whole-portfolio: Dimson beta {pf.port_beta} (target {pf.target_beta}), "
        f"downside beta {pf.port_downside_beta}, upside beta {pf.port_upside_beta}, "
        f"alpha {pf.port_alpha_annual:+.1f}%/yr, appraisal {pf.port_appraisal}."
    )
    lines.append("Sleeve weights: " + ", ".join(f"{k} {v*100:.0f}%" for k, v in pf.sleeve_weights.items()))
    lines.append("\nHoldings (weight | sleeve | beta | alpha%/yr | appraisal):")
    for h in result.portfolio.holdings:
        p = h.profile
        lines.append(f"  {p.ticker} {p.name}: {h.weight*100:.1f}% | {p.sleeve} | "
                     f"beta {p.beta_lagged} | alpha {p.alpha_annual:+.1f}% | appraisal {p.appraisal_ratio}")
    lines.append("\n=== STRESS TEST (5y) ===")
    lines.append(f"Downside capture {s.downside_capture} (share of SPY DOWN days — lower better), "
                 f"upside capture {s.upside_capture}, capture ratio {s.capture_ratio}.")
    lines.append(f"Win rate in down months: {s.win_rate_down_months}%.")
    lines.append(f"Max drawdown: portfolio {s.port_max_drawdown}% vs SPY {s.spy_max_drawdown}%.")
    lines.append(f"Annual return: portfolio {s.port_ann_return}% vs SPY {s.spy_ann_return}%. "
                 f"Sharpe: {s.port_sharpe} vs {s.spy_sharpe}.")
    for label, d in s.stress_windows.items():
        lines.append(f"{label}: portfolio {d['port']:+.1f}% vs SPY {d['spy']:+.1f}%.")
    return "\n".join(lines)


def render_education_panel() -> Panel:
    """A short primer so the terminal teaches the concepts as it runs."""
    txt = """[bold]How to read this — beta-adjusted alpha & convexity[/bold]

[bold cyan]Beta[/bold cyan] = how much a stock moves when the market moves. Beta 2.0 → it falls ~2% when SPY
falls 1%. Beta is the part of your return you can buy for free from an index fund.

[bold cyan]Dimson β[/bold cyan] = "true" beta, including a 1-day lag. Catches names whose price digests
market moves slowly (Asness's point: plain beta understates real market risk).

[bold cyan]Alpha[/bold cyan] = the return LEFT OVER after stripping out beta. This is the genuine, unique
edge — the only part that improves a diversified portfolio.

[bold cyan]Appraisal ratio[/bold cyan] = alpha ÷ idiosyncratic-vol. Your [bold]beta-adjusted alpha score[/bold]: how
much unique return you earn per unit of unique risk. AQR's rule: weight holdings
in proportion to this. Higher = better.

[bold cyan]Convexity[/bold cyan] = up-beta minus down-beta. Positive means a name participates on the way
up but resists on the way down — the asymmetry every defensive investor wants.

[bold]The construction:[/bold] weight by appraisal ratio, tilt toward low beta (betting-against-
beta), then add the [magenta]convexity sleeve[/magenta] — trend-following (DBMF/KMLM), anti-beta
(BTAL), gold, long bonds — to pull whole-portfolio beta down to target. AQR's
research names trend-following the single best crisis diversifier that still earns
a positive long-run return (unlike put options, which bleed ~3%/yr)."""
    return Panel(txt, title="[bold]📘 Primer: Beta-Adjusted Alpha & Defensive Construction[/bold]",
                 border_style="blue", padding=(1, 2))
