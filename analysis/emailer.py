"""
Daily Report Emailer — sends the SignalForge daily report via Gmail SMTP.

Required environment variables:
    GMAIL_ADDRESS      — your Gmail address (sender)
    GMAIL_APP_PASSWORD — 16-character Gmail App Password
                         (myaccount.google.com → Security → 2-Step Verification → App passwords)

Usage:
    from analysis.emailer import send_daily_report, check_email_config
    if check_email_config():
        send_daily_report(report_md, headline_trades=trades_text)
"""
import os
import re
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

_TO_ADDRESS = "ellenli0208@gmail.com"
_SMTP_HOST  = "smtp.gmail.com"
_SMTP_PORT  = 465


def check_email_config() -> bool:
    """Return True if both GMAIL_ADDRESS and GMAIL_APP_PASSWORD are set."""
    return bool(os.getenv("GMAIL_ADDRESS")) and bool(os.getenv("GMAIL_APP_PASSWORD"))


# ── Minimal, dependency-free Markdown → HTML for the dark email theme ─────────
def _esc(text: str) -> str:
    """Escape HTML special chars."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline_md(text: str) -> str:
    """Inline markdown: escape, then **bold** and _italic_."""
    text = _esc(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong style='color:#e8f0f8;'>\1</strong>", text)
    text = re.sub(r"(?<![\w*])_(.+?)_(?![\w*])", r"<em style='color:#9fc0d8;'>\1</em>", text)
    return text


def _md_table_html(header: str, rows: list) -> str:
    def cells(row: str):
        return [c.strip() for c in row.strip().strip("|").split("|")]
    th = "".join(
        f"<th style=\"text-align:left;padding:6px 10px;border-bottom:2px solid #2a4a6a;"
        f"color:#7ec8e3;font-size:12px;white-space:nowrap;\">{_inline_md(c)}</th>"
        for c in cells(header)
    )
    body = []
    for r in rows:
        tds = "".join(
            f"<td style=\"padding:5px 10px;border-bottom:1px solid #1a2530;"
            f"color:#cdd9e3;font-size:12px;\">{_inline_md(c)}</td>"
            for c in cells(r)
        )
        body.append(f"<tr>{tds}</tr>")
    return (
        "<table cellspacing=\"0\" cellpadding=\"0\" style=\"width:100%;border-collapse:collapse;"
        "margin:10px 0 18px 0;font-family:'Courier New',Courier,monospace;\">"
        f"<thead><tr>{th}</tr></thead><tbody>{''.join(body)}</tbody></table>"
    )


def _md_to_html(md: str) -> str:
    """Render the subset of Markdown we emit: headings, tables, lists, hr,
    bold/italic, and paragraphs. Self-contained — no external dependency."""
    lines = md.split("\n")
    out, in_list, i = [], False, 0

    def close_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    sep_re = re.compile(r"^\s*\|[\s:|-]+\|?\s*$")
    while i < len(lines):
        line = lines[i].rstrip()

        # Table: a header row followed by a |---|---| separator.
        if line.startswith("|") and i + 1 < len(lines) and sep_re.match(lines[i + 1]):
            close_list()
            header = line
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i])
                i += 1
            out.append(_md_table_html(header, rows))
            continue

        if not line.strip():
            close_list(); i += 1; continue

        if line.startswith("### "):
            close_list()
            out.append(f"<h3 style=\"color:#9fd0e8;font-size:14px;margin:18px 0 8px;"
                       f"font-family:'Courier New',Courier,monospace;\">{_inline_md(line[4:])}</h3>")
        elif line.startswith("## "):
            close_list()
            out.append(f"<h2 style=\"color:#5ba3d9;font-size:16px;margin:24px 0 10px;"
                       f"border-bottom:1px solid #1e4080;padding-bottom:6px;"
                       f"font-family:'Courier New',Courier,monospace;\">{_inline_md(line[3:])}</h2>")
        elif line.startswith("# "):
            close_list()
            out.append(f"<h1 style=\"color:#5ba3d9;font-size:18px;margin:8px 0 14px;"
                       f"font-family:'Courier New',Courier,monospace;\">{_inline_md(line[2:])}</h1>")
        elif line.strip() == "---":
            close_list()
            out.append("<hr style=\"border:none;border-top:1px solid #1a2a3a;margin:18px 0;\">")
        elif line.lstrip().startswith("- "):
            if not in_list:
                out.append("<ul style=\"margin:6px 0 12px;padding-left:20px;color:#cdd9e3;"
                           "font-size:13px;line-height:1.6;\">")
                in_list = True
            out.append(f"<li>{_inline_md(line.lstrip()[2:])}</li>")
        else:
            close_list()
            out.append(f"<p style=\"color:#cdd9e3;font-size:13px;line-height:1.65;margin:6px 0;"
                       f"font-family:'Courier New',Courier,monospace;\">{_inline_md(line)}</p>")
        i += 1

    close_list()
    return "\n".join(out)


def _build_html(report_md: str, headline_trades: str = "") -> str:
    """Build a dark-themed HTML email from the markdown report text."""

    headline_section = ""
    if headline_trades and headline_trades.strip():
        headline_section = f"""
        <div style="
            margin: 24px 0;
            padding: 20px 24px;
            background: #1a0a0a;
            border: 2px solid #cc2222;
            border-radius: 6px;
        ">
            <h2 style="
                margin: 0 0 14px 0;
                font-size: 16px;
                color: #ff4444;
                font-family: 'Courier New', Courier, monospace;
                letter-spacing: 0.05em;
            ">🚨 Macro Shock Monitor</h2>
            <pre style="
                margin: 0;
                white-space: pre-wrap;
                word-break: break-word;
                font-family: 'Courier New', Courier, monospace;
                font-size: 13px;
                line-height: 1.6;
                color: #f5c6c6;
            ">{_esc(headline_trades)}</pre>
        </div>
"""

    report_section = f"""
        <div style="margin: 24px 0;">
            {_md_to_html(report_md)}
        </div>
"""

    today_str = datetime.now().strftime("%A, %B %d, %Y")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SignalForge Daily Report</title>
</head>
<body style="
    margin: 0;
    padding: 0;
    background-color: #0d0d0d;
    color: #d0d8e0;
    font-family: 'Courier New', Courier, monospace;
">
  <table width="100%" cellpadding="0" cellspacing="0" style="background: #0d0d0d;">
    <tr>
      <td align="center" style="padding: 32px 16px;">
        <table width="860" cellpadding="0" cellspacing="0" style="max-width: 860px; width: 100%;">

          <!-- Header -->
          <tr>
            <td style="
                background: linear-gradient(135deg, #0a1628 0%, #112244 100%);
                border-bottom: 3px solid #1e4080;
                padding: 28px 32px;
                border-radius: 8px 8px 0 0;
            ">
              <div style="
                  font-size: 22px;
                  font-weight: bold;
                  color: #5ba3d9;
                  letter-spacing: 0.04em;
              ">SignalForge 🔭 Daily Intelligence Report</div>
              <div style="
                  margin-top: 6px;
                  font-size: 13px;
                  color: #7a9fc0;
              ">{today_str}</div>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="
                background: #111820;
                padding: 28px 32px;
                border-radius: 0 0 8px 8px;
            ">
              {headline_section}
              {report_section}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding: 20px 0; text-align: center;">
              <div style="
                  font-size: 11px;
                  color: #3a4a5a;
                  letter-spacing: 0.05em;
              ">Generated by SignalForge — automated investment research</div>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    return html


def send_daily_report(report_md: str, headline_trades: str = "") -> None:
    """
    Send the daily SignalForge report as an HTML email via Gmail SMTP (SSL, port 465).

    Args:
        report_md:       The full markdown report text (will be placed in a <pre> block).
        headline_trades: Optional macro shock analysis text to highlight at the top.

    Reads GMAIL_ADDRESS and GMAIL_APP_PASSWORD from environment variables.
    Prints a clear setup message if credentials are missing rather than crashing.
    """
    from_addr = os.getenv("GMAIL_ADDRESS", "").strip()
    app_password = os.getenv("GMAIL_APP_PASSWORD", "").strip()

    if not from_addr or not app_password:
        print(
            "\n[emailer] Email credentials not configured — skipping send.\n"
            "  To enable email reports:\n"
            "    1. Enable 2-Step Verification on your Google account\n"
            "    2. Go to myaccount.google.com → Security → App passwords\n"
            "    3. Generate a 16-char app password\n"
            "    4. Set in .env:\n"
            "         GMAIL_ADDRESS=your_address@gmail.com\n"
            "         GMAIL_APP_PASSWORD=your_16_char_password\n"
        )
        return

    subject = f"SignalForge Daily Report — {datetime.now().strftime('%Y-%m-%d')}"
    html_body = _build_html(report_md, headline_trades)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = from_addr
    msg["To"]      = _TO_ADDRESS

    # Plain-text fallback
    plain_parts = []
    if headline_trades:
        plain_parts.append("=== MACRO SHOCK MONITOR ===\n" + headline_trades + "\n")
    plain_parts.append("=== FULL REPORT ===\n" + report_md)
    msg.attach(MIMEText("\n".join(plain_parts), "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(_SMTP_HOST, _SMTP_PORT, context=context) as server:
            server.login(from_addr, app_password)
            server.sendmail(from_addr, _TO_ADDRESS, msg.as_string())
        print(f"[emailer] Report sent to {_TO_ADDRESS} ✓")
    except smtplib.SMTPAuthenticationError:
        print(
            "[emailer] Authentication failed — check your GMAIL_APP_PASSWORD.\n"
            "  Make sure you're using an App Password, not your regular Gmail password.\n"
            "  See: myaccount.google.com → Security → 2-Step Verification → App passwords"
        )
    except smtplib.SMTPException as exc:
        print(f"[emailer] SMTP error while sending report: {exc}")
    except OSError as exc:
        print(f"[emailer] Network error while sending report: {exc}")
