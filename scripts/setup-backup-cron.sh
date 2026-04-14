#!/bin/bash

SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)/backup-db.sh"
CRON_JOB="0 2 * * * $SCRIPT_PATH"
(crontab -l 2>/dev/null | grep -v "backup-db.sh"; echo "$CRON_JOB") | crontab -
echo "Cron job installed: $CRON_JOB"
