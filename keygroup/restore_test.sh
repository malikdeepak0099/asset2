#!/bin/bash
# KEY GROUP restore test: opens the newest backup in a temporary folder, checks the database is healthy and
# compares it with the live data. The live site is not touched. Result goes to the console and Telegram.
set -u
F=$(ls -1t /opt/backups/kg-*.tgz 2>/dev/null | head -1)
[ -n "$F" ] || { echo "STOP: no backups yet — run: bash /opt/keygroup/backup.sh"; exit 1; }
TMP=$(mktemp -d /opt/keygroup-portal/data/restoretest.XXXX)
tar -xzf "$F" -C "$TMP" || { echo "PROBLEM: backup archive cannot be opened"; rm -rf "$TMP"; exit 1; }
SUB=$(basename "$TMP")
RES=$(docker exec kg-portal python -c "
import sqlite3, os
b = '/data/$SUB/opt/keygroup-portal/data/portal-backup.db'
if not os.path.exists(b): print('FAIL database missing in backup'); raise SystemExit
c = sqlite3.connect(b); live = sqlite3.connect('/data/portal.db')
chk = c.execute('PRAGMA integrity_check').fetchone()[0]
parts = []
for t in ('users', 'listings', 'leads', 'orders', 'chats'):
    try:
        parts.append('%s %d/%d' % (t, c.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0], live.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0]))
    except Exception:
        parts.append(t + ' n/a')
ph_b = len(os.listdir('/data/$SUB/opt/keygroup-portal/data/uploads')) if os.path.isdir('/data/$SUB/opt/keygroup-portal/data/uploads') else 0
ph_l = len(os.listdir('/data/uploads')) if os.path.isdir('/data/uploads') else 0
print(('OK' if chk == 'ok' else 'FAIL integrity ' + chk) + ' | backup/live: ' + ', '.join(parts) + ', photo files %d/%d' % (ph_b, ph_l))
" 2>&1)
rm -rf "$TMP"
MSG="🧪 Restore test $(basename "$F"): $RES"
echo "$MSG"
ENV=/opt/keygroup-portal/.env
TOKEN=$(grep '^BOT_TOKEN=' "$ENV" | cut -d= -f2-)
for c in $(grep '^ALERT_CHATS=' "$ENV" | cut -d= -f2- | tr ',' ' '); do curl -fsS -m 20 -o /dev/null "https://api.telegram.org/bot${TOKEN}/sendMessage" --data-urlencode chat_id="$c" --data-urlencode text="$MSG" || true; done
case "$RES" in OK*) echo "RESTORE TEST PASSED";; *) echo "RESTORE TEST FAILED";; esac
