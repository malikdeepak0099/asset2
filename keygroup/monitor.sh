#!/bin/bash
# KEY GROUP health monitor — runs every 5 minutes from cron. Sends a Telegram alert when something breaks
# and another one when it is fixed (no repeated spam while a problem continues).
set -u
ENV=/opt/keygroup-portal/.env
TOKEN=$(grep '^BOT_TOKEN=' "$ENV" 2>/dev/null | cut -d= -f2-)
CHATS=$(grep '^ALERT_CHATS=' "$ENV" 2>/dev/null | cut -d= -f2- | tr ',' ' ')
STATE=/var/lib/kg-monitor.state
P=()
curl -fsS -m 20 -o /dev/null https://keygroup.ge/ || P+=("Website keygroup.ge is not answering")
curl -fsS -m 20 https://keygroup.ge/api/health 2>/dev/null | grep -q '"ok":true' || P+=("Owner portal / API is down")
docker ps --format '{{.Names}}' | grep -qx kg-portal || P+=("Portal container kg-portal is not running")
[ -n "$(cd /opt/keygroup && docker compose ps -q caddy 2>/dev/null)" ] || P+=("Web server (Caddy) is not running")
if [ -d /opt/keygroup-listing ]; then
  [ -n "$(cd /opt/keygroup-listing && docker compose ps -q 2>/dev/null)" ] || P+=("Telegram listing bot is not running")
fi
DISK=$(df -P / | awk 'NR==2{gsub("%","",$5); print $5}')
[ "${DISK:-0}" -ge 85 ] && P+=("Disk is ${DISK}% full")
MEM=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
[ "${MEM:-999}" -lt 150 ] && P+=("Low memory: ${MEM} MB free")
LAST=$(ls -1t /opt/backups/kg-*.tgz 2>/dev/null | head -1)
if [ -z "$LAST" ] || [ $(( $(date +%s) - $(stat -c %Y "$LAST") )) -gt 108000 ]; then P+=("No backup in the last 30 hours"); fi
NOW=$(printf '%s\n' "${P[@]:-}" | sed '/^$/d' | sort)
OLD=$(cat "$STATE" 2>/dev/null || true)
if [ "$NOW" != "$OLD" ]; then
  if [ -n "$NOW" ]; then MSG="🚨 KEY GROUP server alert%0A$(printf '%s\n' "$NOW" | sed 's/^/• /' | sed ':a;N;$!ba;s/\n/%0A/g')";
  else MSG="✅ KEY GROUP server: all checks OK again"; fi
  for c in $CHATS; do curl -fsS -m 20 -o /dev/null "https://api.telegram.org/bot${TOKEN}/sendMessage" -d chat_id="$c" -d text="$MSG" || true; done
  printf '%s' "$NOW" > "$STATE"
fi
[ -n "$NOW" ] && { echo "$(date '+%F %T') PROBLEMS:"; echo "$NOW"; } || echo "$(date '+%F %T') all OK"
