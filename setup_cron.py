#!/usr/bin/env python3
"""
Install (or update) the SignalForge daily cron job.

Schedule: every day at 7:00 AM America/Los_Angeles (PDT/PST automatic).
Action:   run_daily.sh → main.py --mode email
            = AI infra scan + whale tracker + full sector scan + tech briefing
              → saves report to output/ → emails HTML report to configured address

Run this script once to install. Re-run at any time to update or verify.
Idempotent — clears stale SignalForge entries before writing the new one.
"""
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
RUNNER      = PROJECT_DIR / "run_daily.sh"
LOG_DIR     = PROJECT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 7:00 AM every day. cron uses the system timezone — this machine is already
# set to America/Los_Angeles, so no TZ prefix needed.
CRON_LINE = (
    f"0 7 * * * "
    f"cd {PROJECT_DIR} && bash {RUNNER} "
    f">> {LOG_DIR}/cron.log 2>&1"
)

# ── Read existing crontab ──────────────────────────────────────────────────────
result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
existing = result.stdout if result.returncode == 0 else ""

# Remove any previous SignalForge / Frontier Tech Radar lines so we don't
# accumulate stale entries on repeated runs.
filtered = "\n".join(
    line for line in existing.splitlines()
    if "signalforge" not in line.lower()
    and "frontier" not in line.lower()
    and str(RUNNER) not in line
    and "main.py" not in line
)

new_crontab = filtered.rstrip() + "\n" + CRON_LINE + "\n"

proc = subprocess.run(["crontab", "-"], input=new_crontab, text=True, capture_output=True)
if proc.returncode != 0:
    print(f"❌ Failed to install cron job: {proc.stderr.strip()}")
    print(f"\nManual setup — run:  crontab -e  and add:\n  {CRON_LINE}")
    sys.exit(1)

# ── Verify ─────────────────────────────────────────────────────────────────────
verify = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
if str(RUNNER) in verify.stdout:
    print("✅ SignalForge daily email scheduled.")
    print(f"   Time  : 7:00 AM every day  (America/Los_Angeles — PDT/PST auto)")
    print(f"   What  : AI infra + whales + sectors + tech briefing → email")
    print(f"   Email : ellenli0208@gmail.com")
    print(f"   Logs  : {LOG_DIR}/cron.log")
    print(f"\n   Cron line:\n     {CRON_LINE}")
else:
    print("⚠️  Installed but not found in verification — run: crontab -l")
