#!/bin/bash
SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)/monitor.sh"
CRON_JOB="*/5 * * * * $SCRIPT_PATH"
(crontab -l 2>/dev/null | grep -v "monitor.sh"; echo "$CRON_JOB") | crontab -
echo "Cron job installed: $CRON_JOB"
