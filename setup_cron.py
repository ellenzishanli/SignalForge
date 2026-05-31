#!/usr/bin/env python3
"""
Set up daily cron job for Frontier Tech Radar.
Runs Mon-Fri at 7:30 AM.
"""
import subprocess
import os

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = subprocess.run(["which", "python3"], capture_output=True, text=True).stdout.strip()
LOG_DIR = os.path.join(PROJECT_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

CRON_LINE = (
    f"30 7 * * 1-5 cd {PROJECT_DIR} && "
    f"{PYTHON} {PROJECT_DIR}/main.py --mode full "
    f">> {LOG_DIR}/cron.log 2>&1"
)

result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
existing = result.stdout if result.returncode == 0 else ""

if CRON_LINE in existing:
    print("✅ Cron job already installed.")
else:
    new_crontab = existing.rstrip() + "\n" + CRON_LINE + "\n"
    proc = subprocess.run(["crontab", "-"], input=new_crontab, text=True)
    if proc.returncode == 0:
        print(f"✅ Cron job installed: runs Mon-Fri at 7:30 AM")
        print(f"   Logs: {LOG_DIR}/cron.log")
    else:
        print("❌ Failed to install cron job.")
        print(f"Manual setup — add this to crontab -e:\n{CRON_LINE}")
