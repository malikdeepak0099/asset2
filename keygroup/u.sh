# KEY GROUP website update for keygroup.ge (run in the DigitalOcean droplet console)
set -u
SITE=/opt/keygroup/site
RAW=https://raw.githubusercontent.com/malikdeepak0099/asset2/main/keygroup
CRM='https://script.google.com/macros/s/AKfycbxrhM71nw5yFyxWobNt1afBS2uhoq0CGEJguudYHT4ZQuRg809CxWIxEXJZvJDXslSA/exec'
[ -d "$SITE" ] || { echo "STOP: $SITE not found - nothing changed"; exit 1; }
cd "$SITE"
curl -fsSL "$RAW/index.html?$(date +%s)" -o index.new.html || { echo "STOP: could not download the new page - nothing changed"; exit 1; }
grep -q 'KEY GROUP' index.new.html || { echo "STOP: downloaded page looks wrong - nothing changed"; rm -f index.new.html; exit 1; }
[ -f index.html ] && cp index.html "index.backup-$(date +%Y%m%d-%H%M).html"
mv index.new.html index.html
mkdir -p img
for p in hero:8ad93447-40e3-41b8-b1a0-a509490a8ad1 vake:4cae281b-91eb-49e0-bc3e-74d7d24f5597 saburtalo:b40d1576-c15c-4653-a7d7-43d111ee36df oldtbilisi:f5c49673-65f6-4f93-8f97-9ec763ec8387 batumi:67f78f55-d517-4f74-91c9-7a48a3323d37; do
  n=${p%%:*}; id=${p#*:}
  [ -s "img/$n.png" ] || curl -fsSL -o "img/$n.png" "https://www.figma.com/api/mcp/asset/$id.png" || echo "photo missing: $n"
done
cat > /opt/keygroup/update_listings.sh <<EOS
#!/bin/sh
# Pulls active listings (no owner names/phones) from the KEY GROUP Master CRM for keygroup.ge
T=$SITE/listings.json.tmp
curl -fsSL --max-time 120 "$CRM?action=listings" -o "\$T" && grep -q '"ok":true' "\$T" && [ \$(wc -c < "\$T") -gt 500 ] && mv "\$T" $SITE/listings.json || rm -f "\$T"
EOS
chmod +x /opt/keygroup/update_listings.sh
echo '*/30 * * * * root /opt/keygroup/update_listings.sh' > /etc/cron.d/keygroup-listings
chmod 644 /etc/cron.d/keygroup-listings
/opt/keygroup/update_listings.sh
chmod -R a+rX "$SITE"
if [ -s "$SITE/listings.json" ]; then
  echo "listings loaded: $(grep -o '"count":[0-9]*' "$SITE/listings.json")"
else
  echo "listings not loaded yet (site shows the 13 built-in listings; will retry every 30 min)"
fi
echo "DONE - keygroup.ge updated: live CRM listings + website leads"
