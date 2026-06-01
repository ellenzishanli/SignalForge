#!/bin/bash
# Daily runner - add to crontab: 0 8 * * 1-5 /path/to/run_daily.sh
cd "$(dirname "$0")"
source .env 2>/dev/null || true
python3 main.py --mode email 2>&1 | tee -a logs/radar_$(date +%Y-%m-%d).log
