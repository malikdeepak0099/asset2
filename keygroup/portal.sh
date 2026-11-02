# KEY GROUP owner portal (owner panel + admin panel + listing pages) - install / update on the droplet
set -u
RAW=https://raw.githubusercontent.com/malikdeepak0099/asset2/main/keygroup
SITE=/opt/keygroup/site
DIR=/opt/keygroup-portal
cd /opt/keygroup || { echo "STOP: /opt/keygroup not found"; exit 1; }
# 0) backups: install daily backup + restore scripts, and back up before every update
for f in backup.sh restore.sh restore_test.sh monitor.sh; do curl -fsSL "$RAW/$f?$(date +%s)" -o "/opt/keygroup/$f" && chmod 700 "/opt/keygroup/$f"; done
( crontab -l 2>/dev/null | grep -v 'keygroup/backup.sh' | grep -v 'keygroup/monitor.sh' | grep -v 'keygroup/restore_test.sh'
  echo "30 3 * * * /bin/bash /opt/keygroup/backup.sh >> /var/log/keygroup-backup.log 2>&1"
  echo "*/5 * * * * /bin/bash /opt/keygroup/monitor.sh >> /var/log/keygroup-monitor.log 2>&1"
  echo "0 5 * * 0 /bin/bash /opt/keygroup/restore_test.sh >> /var/log/keygroup-restore-test.log 2>&1" ) | crontab -
[ -d /opt/keygroup-portal/data ] && bash /opt/keygroup/backup.sh
# 1) website pages
curl -fsSL "$RAW/u.sh?$(date +%s)" | bash || { echo "STOP: website update failed"; exit 1; }
curl -fsSL "$RAW/site/manifest.txt?$(date +%s)" -o /tmp/kg-manifest.txt || { echo "STOP: could not download the file list"; exit 1; }
for f in $(cat /tmp/kg-manifest.txt); do
  mkdir -p "$SITE/$(dirname $f)"
  curl -fsSL "$RAW/site/$f?$(date +%s)" -o "$SITE/$f" || { echo "STOP: could not download $f"; exit 1; }
done
chmod -R a+rX "$SITE"
# 2) portal service
mkdir -p "$DIR/data" && cd "$DIR"
for f in app.py chatbot.py kb.py requirements.txt Dockerfile docker-compose.yml; do
  curl -fsSL "$RAW/portal/$f?$(date +%s)" -o "$f" || { echo "STOP: could not download $f"; exit 1; }
done
CADDY_ID=$(cd /opt/keygroup && docker compose ps -q caddy)
[ -n "$CADDY_ID" ] || { echo "STOP: caddy is not running"; exit 1; }
NET=$(docker inspect "$CADDY_ID" -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' | awk '{print $1}')
FIRST_RUN=0
if [ ! -s .env ]; then
  FIRST_RUN=1
  PW=$(python3 -c 'import secrets; print(secrets.token_urlsafe(9))')
  BOT=$(grep '^BOT_TOKEN=' /opt/keygroup-listing/.env 2>/dev/null | cut -d= -f2-)
  CHATS=$( (grep -E '^(ADMIN_ID|ADMINS)=' /opt/keygroup-listing/.env 2>/dev/null | cut -d= -f2- | tr '\n' ',') | sed 's/,,*/,/g;s/^,//;s/,$//')
  printf 'DATA_DIR=/data\nSITE_URL=https://keygroup.ge\nADMIN_PHONE=+995577114118\nADMIN_PASSWORD=%s\nBOT_TOKEN=%s\nALERT_CHATS=%s\nCADDY_NETWORK=%s\n' "$PW" "$BOT" "$CHATS" "$NET" > .env
  chmod 600 .env
else
  sed -i "s/^CADDY_NETWORK=.*/CADDY_NETWORK=$NET/" .env
fi
grep -q '^CRM_URL=' .env || { CRMU=$(grep '^CRM_URL=' /opt/keygroup-listing/.env 2>/dev/null | cut -d= -f2-); echo "CRM_URL=$CRMU" >> .env; }
grep -q '^SITE_DIR=' .env || echo "SITE_DIR=/site" >> .env
grep -q '^CRM_SECRET=' .env || { CS=$(grep '^CRM_SECRET=' /opt/keygroup-listing/.env 2>/dev/null | cut -d= -f2-); echo "CRM_SECRET=$CS" >> .env; }
grep -q '^CRM_URL=.\+' .env || { CRMU=$(grep '^CRM_URL=' /opt/keygroup-listing/.env 2>/dev/null | cut -d= -f2-); sed -i '/^CRM_URL=/d' .env; echo "CRM_URL=$CRMU" >> .env; }
docker compose up -d --build --force-recreate 2>&1 | tail -2
sleep 6
docker compose ps | grep -q Up || { echo "PROBLEM - portal did not start:"; docker compose logs --tail 20; exit 1; }
# 3) Caddy routes /api and /uploads to the portal
cd /opt/keygroup
CF=$(ls Caddyfile caddy/Caddyfile 2>/dev/null | head -n1)
if ! grep -q 'kg-portal' "$CF"; then
  BK="$CF.bak-$(date +%s)"; cp "$CF" "$BK"
  python3 - "$CF" <<'PY'
import sys, re
p = sys.argv[1]; s = open(p).read()
m = re.search(r'^[^\n#]*keygroup\.ge[^\n]*\{[ \t]*\n', s, re.M)
if not m: sys.exit("keygroup.ge block not found")
s = s[:m.end()] + "\treverse_proxy /api/* kg-portal:8000\n\treverse_proxy /uploads/* kg-portal:8000\n\trequest_body {\n\t\tmax_size 200MB\n\t}\n" + s[m.end():]
open(p, "w").write(s)
PY
  docker compose restart caddy >/dev/null 2>&1; sleep 6
  if ! docker compose ps caddy | grep -q Up; then echo "PROBLEM - restoring Caddy"; cp "$BK" "$CF"; docker compose restart caddy; exit 1; fi
fi
# 3b) pretty agent URLs: keygroup.ge/nika/ (profile) and keygroup.ge/nika/rent-3-room-apartment-vake-123 (listing)
if ! grep -q 'kg-agent-urls' "$CF"; then
  BK2="$CF.bak-$(date +%s)"; cp "$CF" "$BK2"
  python3 - "$CF" <<'PY'
import sys, re
p = sys.argv[1]; s = open(p).read()
m = re.search(r'^[^\n#]*keygroup\.ge[^\n]*\{[ \t]*\n', s, re.M)
if not m: sys.exit("keygroup.ge block not found")
rules = ("\t# kg-agent-urls\n"
         "\t@kgagentlisting {\n\t\tpath_regexp ^/[a-z0-9-]+/[a-z0-9-]*-[0-9]+/?$\n\t\tnot file\n\t}\n"
         "\trewrite @kgagentlisting /p/index.html\n"
         "\t@kgagentprofile {\n\t\tpath_regexp ^/[a-z][a-z0-9-]{1,30}/?$\n\t\tnot file {path} {path}/index.html {path}.html\n\t}\n"
         "\trewrite @kgagentprofile /agent/index.html\n")
s = s[:m.end()] + rules + s[m.end():]
open(p, "w").write(s)
PY
  CADDY_C=$(docker compose ps -q caddy)
  if docker exec "$CADDY_C" caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null 2>&1 || ! docker exec "$CADDY_C" test -f /etc/caddy/Caddyfile; then
    docker compose restart caddy >/dev/null 2>&1; sleep 6
    if ! docker compose ps caddy | grep -q Up; then echo "PROBLEM - restoring Caddy"; cp "$BK2" "$CF"; docker compose restart caddy; fi
  else
    echo "Caddy rules not valid - restored the previous config"; cp "$BK2" "$CF"
  fi
fi
sleep 2
if curl -fsS https://keygroup.ge/api/health >/dev/null 2>&1 || curl -fsS -H 'Host: keygroup.ge' http://127.0.0.1/api/health >/dev/null 2>&1; then echo "portal reachable: OK"; fi
bash /opt/keygroup/restore_test.sh 2>/dev/null | tail -2
echo "DONE - owner portal is live: https://keygroup.ge/account/  admin: https://keygroup.ge/admin/"
if [ "$FIRST_RUN" = "1" ]; then
  echo "================ ADMIN LOGIN (write it down) ================"
  echo "Phone:    577 114 118"
  echo "Password: $PW"
  echo "Change it in Admin -> Plans & settings after the first login."
  echo "=============================================================="
fi
