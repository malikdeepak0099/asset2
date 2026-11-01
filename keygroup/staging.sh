# KEY GROUP staging: puts the newest version on https://staging.keygroup.ge with an EMPTY test database
# (no customer data) so changes can be checked before they go live with portal.sh.
set -u
RAW=https://raw.githubusercontent.com/malikdeepak0099/asset2/main/keygroup
STG=/opt/keygroup/site/_staging
DIR=/opt/keygroup-portal-staging
PROD=/opt/keygroup-portal
[ -f "$PROD/.env" ] || { echo "STOP: install the live portal first (portal.sh)"; exit 1; }
mkdir -p "$STG" "$DIR/data"
# 1) website files
curl -fsSL "$RAW/index.html?$(date +%s)" -o "$STG/index.html" || { echo "STOP: download failed"; exit 1; }
printf 'User-agent: *\nDisallow: /\n' > "$STG/robots.txt"
[ -d /opt/keygroup/site/img ] && cp -r /opt/keygroup/site/img "$STG/"
[ -f /opt/keygroup/site/listings.json ] && cp /opt/keygroup/site/listings.json "$STG/"
curl -fsSL "$RAW/site/manifest.txt?$(date +%s)" -o /tmp/kg-stg-manifest.txt || { echo "STOP: file list"; exit 1; }
for f in $(cat /tmp/kg-stg-manifest.txt); do
  mkdir -p "$STG/$(dirname "$f")"
  curl -fsSL "$RAW/site/$f?$(date +%s)" -o "$STG/$f" || { echo "STOP: could not download $f"; exit 1; }
done
chmod -R a+rX "$STG"
# 2) staging portal (own container + own empty database)
cd "$DIR"
for f in app.py chatbot.py kb.py requirements.txt Dockerfile; do
  curl -fsSL "$RAW/portal/$f?$(date +%s)" -o "$f" || { echo "STOP: could not download $f"; exit 1; }
done
NET=$(grep '^CADDY_NETWORK=' "$PROD/.env" | cut -d= -f2-)
cat > docker-compose.yml <<YML
services:
  portal:
    build: .
    container_name: kg-portal-staging
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./data:/data
      - $STG:/site:ro
    networks:
      - web
networks:
  web:
    external: true
    name: $NET
YML
if [ ! -s .env ]; then
  SPW=$(python3 -c 'import secrets; print(secrets.token_urlsafe(9))')
  printf 'DATA_DIR=/data\nSITE_URL=https://staging.keygroup.ge\nSITE_DIR=/site\nADMIN_PHONE=+995577114118\nADMIN_PASSWORD=%s\nBOT_TOKEN=\nALERT_CHATS=\nCRM_URL=\n' "$SPW" > .env
  chmod 600 .env
  FIRST=1
else
  FIRST=0
fi
docker compose up -d --build --force-recreate 2>&1 | tail -1
sleep 6
docker compose ps | grep -q Up || { echo "PROBLEM - staging portal did not start:"; docker compose logs --tail 20; exit 1; }
# 3) Caddy: staging.keygroup.ge site + hide /_staging on the live domain
cd /opt/keygroup
CF=$(ls Caddyfile caddy/Caddyfile 2>/dev/null | head -n1)
if ! grep -q 'staging.keygroup.ge' "$CF"; then
  BK="$CF.bak-$(date +%s)"; cp "$CF" "$BK"
  python3 - "$CF" <<'PY'
import sys, re
p = sys.argv[1]; s = open(p).read()
m = re.search(r'^[^\n#]*keygroup\.ge[^\n]*\{[ \t]*\n', s, re.M)
if m and "_staging" not in s[m.end():m.end() + 400]:
    s = s[:m.end()] + "\trespond /_staging/* 404\n" + s[m.end():]
s += """

staging.keygroup.ge {
\theader X-Robots-Tag "noindex, nofollow"
\treverse_proxy /api/* kg-portal-staging:8000
\treverse_proxy /uploads/* kg-portal-staging:8000
\troot * /srv/site/_staging
\ttry_files {path} {path}.html
\tfile_server
}
"""
open(p, "w").write(s)
PY
  docker compose restart caddy >/dev/null 2>&1; sleep 6
  if ! docker compose ps caddy | grep -q Up; then echo "PROBLEM - restoring Caddy"; cp "$BK" "$CF"; docker compose restart caddy; exit 1; fi
fi
echo "DONE - staging updated: https://staging.keygroup.ge  (admin: https://staging.keygroup.ge/admin/)"
if [ "$FIRST" = "1" ]; then
  echo "========== STAGING ADMIN LOGIN (test only) =========="
  echo "Phone:    577 114 118"
  echo "Password: $SPW"
  echo "====================================================="
fi
echo "If the page does not open: add DNS record  A  staging  ->  167.71.54.48  in DigitalOcean (Networking > Domains)."
