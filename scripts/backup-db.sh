#!/bin/bash

BACKUP_DIR="/var/backups/aura"
LOGFILE="/var/log/aura-monitor.log"
CONTAINER_NAME="aura-postgres"
BACKUP_FILE="aura_backup_$(date '+%Y-%m-%d_%H-%M').dump"
BACKUP_PATH="$BACKUP_DIR/$BACKUP_FILE"

log_message() {
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $1" >> "$LOGFILE"
}

mkdir -p "$BACKUP_DIR" || {
    log_message "Backup FAILED - could not create $BACKUP_DIR"
    exit 1
}

if docker exec "$CONTAINER_NAME" sh -c 'pg_dump -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-postgres}" -Fc' > "$BACKUP_PATH"; then
    ls -1t "$BACKUP_DIR"/aura_backup_*.dump 2>/dev/null | tail -n +8 | xargs -r rm -f
    log_message "Backup OK - $BACKUP_PATH"
else
    rm -f "$BACKUP_PATH"
    log_message "Backup FAILED - pg_dump in $CONTAINER_NAME"
    exit 1
fi
