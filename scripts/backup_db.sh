#!/bin/bash
set -euo pipefail

BACKUP_DIR="$HOME/Documents/hitl-translation/db-backups"
DB_NAME="translation_db"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql"
KEEP_DAYS=14

mkdir -p "$BACKUP_DIR"
pg_dump "$DB_NAME" > "$BACKUP_FILE"
gzip "$BACKUP_FILE"
echo "Backup written: ${BACKUP_FILE}.gz"

# Remove backups older than KEEP_DAYS
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +$KEEP_DAYS -delete
echo "Cleanup done. Current backups:"
ls -lht "$BACKUP_DIR"
