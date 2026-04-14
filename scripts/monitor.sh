#!/bin/bash
LOGFILE="/var/log/aura-monitor.log"
HEALTH=$(curl -s http://localhost:8080/health 2>/dev/null)
STATUS=$(echo "$HEALTH" | grep -o '"status":"[^"]*"' | head -1 | cut -d'"' -f4)
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
if [ "$STATUS" = "healthy" ]; then
    echo "[$TIMESTAMP] OK - AURA backend healthy" >> "$LOGFILE"
else
    echo "[$TIMESTAMP] ALERT - AURA backend status: $STATUS" >> "$LOGFILE"
    echo "[$TIMESTAMP] ALERT - AURA backend status: $STATUS" >&2
fi
