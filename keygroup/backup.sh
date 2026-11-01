#!/bin/bash
# KEY GROUP daily backup: owner portal (database + photos), Telegram bot data and settings.
# Keeps the newest 14 archives in /opt/backups. Restore: bash /opt/keygroup/restore.sh
set -u
OUT=/opt/backups
mkdir -p "$OUT"
STAMP=$(date +%Y%m%d-%H%M)
TMP=$(mktemp -d)
# consistent copy of the live SQLite database (taken inside the running container)
if docker ps --format '{{.Names}}' | grep -qx kg-portal; then
  docker exec kg-portal python -c "
import sqlite3
src = sqlite3.connect('/data/portal.db'); dst = sqlite3.connect('/data/portal-backup.db')
src.backup(dst); dst.close(); src.close()
print('db ok')" >/dev/null 2>&1 || echo "warning: database snapshot failed"
fi
tar -czf "$TMP/kg-$STAMP.tgz" \
  --exclude='opt/keygroup-portal/data/portal.db' --exclude='opt/keygroup-portal/data/portal.db-*' \
  -C / opt/keygroup-portal/data opt/keygroup-portal/.env \
  $( [ -d /opt/keygroup-listing/data ] && echo opt/keygroup-listing/data ) \
  $( [ -f /opt/keygroup-listing/.env ] && echo opt/keygroup-listing/.env ) \
  $( [ -f /opt/keygroup/Caddyfile ] && echo opt/keygroup/Caddyfile ) 2>/dev/null
mv "$TMP/kg-$STAMP.tgz" "$OUT/" && rm -rf "$TMP"
chmod 600 "$OUT"/kg-*.tgz
ls -1t "$OUT"/kg-*.tgz | tail -n +15 | xargs -r rm -f
SIZE=$(du -h "$OUT/kg-$STAMP.tgz" | cut -f1)
echo "backup saved: $OUT/kg-$STAMP.tgz ($SIZE) — $(ls -1 "$OUT"/kg-*.tgz | wc -l) backups kept"
