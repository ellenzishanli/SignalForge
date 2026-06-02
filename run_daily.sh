#!/bin/bash
# Daily runner — cron fires this at 7:00 AM every day (America/Los_Angeles)
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p logs
source .env 2>/dev/null || true
echo "=== SignalForge run started $(date) ===" >> logs/cron.log
/usr/bin/python3 main.py --mode email 2>&1 | tee -a "logs/radar_$(date +%Y-%m-%d).log"
echo "=== run finished $(date) ===" >> logs/cron.log
