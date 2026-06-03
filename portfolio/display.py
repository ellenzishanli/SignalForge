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
