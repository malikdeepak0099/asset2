#!/bin/bash
# KEY GROUP restore: lists backups, asks which one, puts the owner portal data back and restarts it.
set -u
OUT=/opt/backups
mapfile -t FILES < <(ls -1t "$OUT"/kg-*.tgz 2>/dev/null)
[ ${#FILES[@]} -gt 0 ] || { echo "No backups found in $OUT"; exit 1; }
echo "Backups (newest first):"
for i in "${!FILES[@]}"; do echo "  $((i+1))) $(basename "${FILES[$i]}")"; done
printf 'Number to restore (Enter = cancel): ' > /dev/tty; read -r N < /dev/tty
[ -n "$N" ] && [ "$N" -ge 1 ] 2>/dev/null && [ "$N" -le ${#FILES[@]} ] || { echo "Cancelled"; exit 0; }
F="${FILES[$((N-1))]}"
# safety copy of the current state first
bash /opt/keygroup/backup.sh >/dev/null 2>&1
TMP=$(mktemp -d)
tar -xzf "$F" -C "$TMP" || { echo "STOP: archive unreadable"; exit 1; }
cd /opt/keygroup-portal && docker compose stop >/dev/null 2>&1
rsync -a --delete "$TMP/opt/keygroup-portal/data/" /opt/keygroup-portal/data/ 2>/dev/null || cp -a "$TMP/opt/keygroup-portal/data/." /opt/keygroup-portal/data/
[ -f /opt/keygroup-portal/data/portal-backup.db ] && cp /opt/keygroup-portal/data/portal-backup.db /opt/keygroup-portal/data/portal.db
rm -f /opt/keygroup-portal/data/portal.db-wal /opt/keygroup-portal/data/portal.db-shm
docker compose up -d >/dev/null 2>&1
rm -rf "$TMP"
sleep 4
docker compose ps | grep -q Up && echo "DONE - restored $(basename "$F")" || echo "PROBLEM - portal did not start, check: docker compose logs"
