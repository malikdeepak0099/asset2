# KEY GROUP Assistant (agents' personal AI assistant bot) - install / update on the DigitalOcean droplet
set -u
DIR=/opt/keygroup-listing
RAW=https://raw.githubusercontent.com/malikdeepak0099/asset2/main/keygroup/bot
CRM='https://script.google.com/macros/s/AKfycbxrhM71nw5yFyxWobNt1afBS2uhoq0CGEJguudYHT4ZQuRg809CxWIxEXJZvJDXslSA/exec'
command -v docker >/dev/null || { echo "STOP: docker not found"; exit 1; }
mkdir -p "$DIR/data" && cd "$DIR"
for f in bot.py extract.py profiles.py store.py texts.py requirements.txt Dockerfile docker-compose.yml; do
  curl -fsSL "$RAW/$f?$(date +%s)" -o "$f.new" || { echo "STOP: could not download $f - nothing changed"; rm -f ./*.new; exit 1; }
done
for f in *.new; do mv "$f" "${f%.new}"; done
if [ ! -s .env ]; then
  printf "Type the 6-digit setup code and press Enter: "
  read -r CODE < /dev/tty
  RESP=$(curl -fsSL --max-time 60 "$CRM?action=pair&code=$CODE") || { echo "STOP: could not reach the CRM"; exit 1; }
  echo "$RESP" | python3 -c '
import json, sys
d = json.load(sys.stdin)
if not d.get("ok") or not d.get("botToken"):
    print("STOP: setup code not accepted (" + str(d.get("error") or "no bot token in CRM settings") + ")"); sys.exit(1)
crm = sys.argv[1]
with open(".env", "w") as f:
    f.write("BOT_TOKEN=%s\nCRM_SECRET=%s\nADMIN_ID=%s\nCRM_URL=%s\nDATA_DIR=/data\nCOMPANY_PHONE=+995 577 114 118\nDAILY_SYNC_HOUR=9\n" % (d["botToken"], d["botSecret"], d["adminId"], crm))
print("setup code accepted")
' "$CRM" || exit 1
  chmod 600 .env
fi
docker compose up -d --build 2>&1 | tail -3
sleep 8
if docker compose ps | grep -q "Up"; then
  echo "DONE - KEY GROUP Assistant is running."
  BOTNAME=$(curl -fsS "https://api.telegram.org/bot$(grep '^BOT_TOKEN=' .env | cut -d= -f2-)/getMe" | python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["username"])' 2>/dev/null)
  [ -n "$BOTNAME" ] && echo "BOT NAME: @$BOTNAME   LINK: https://t.me/$BOTNAME"
else
  echo "PROBLEM - bot did not start. Last log lines:"; docker compose logs --tail 20
fi
