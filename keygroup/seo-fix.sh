# KEY GROUP keygroup.ge SEO fix (run in the DigitalOcean droplet console as root):
#   curl -fsSL https://raw.githubusercontent.com/malikdeepak0099/asset2/seo-fix/keygroup/seo-fix.sh | bash
#   - www.keygroup.ge -> https://keygroup.ge 301
#   - unknown URLs return a real 404 (agent profiles become real files)
#   - clean sitemap.xml (no /tbilisi/ /batumi/ /ka/ /ru/), all real landing pages added
#   - every listing gets its own title / description / social preview in the first HTML
#   - current listings as direct links on the hub, buyer guides, Tbilisi/Batumi and district pages
#   - landing-page attribution for WhatsApp/enquiries + weekly report (Mondays, /opt/keygroup/seo/reports)
# Backs up the Caddyfile, checks the site afterwards and restores the backup if a core check fails.
# Does NOT replace the portal app, the website pages or any data.
set -u
RAW=https://raw.githubusercontent.com/malikdeepak0099/asset2/seo-fix/keygroup
SITE=/opt/keygroup/site
cd /opt/keygroup || { echo "STOP: /opt/keygroup not found - nothing changed"; exit 1; }
CF=$(ls Caddyfile caddy/Caddyfile 2>/dev/null | head -n1)
[ -n "$CF" ] || { echo "STOP: Caddyfile not found - nothing changed"; exit 1; }
mkdir -p /opt/keygroup/seo
curl -fsSL "$RAW/seo/kg_seo.py?$(date +%s)" -o /opt/keygroup/seo/kg_seo.py.new || { echo "STOP: download failed - nothing changed"; exit 1; }
python3 -m py_compile /opt/keygroup/seo/kg_seo.py.new || { echo "STOP: generator broken - nothing changed"; exit 1; }
mv /opt/keygroup/seo/kg_seo.py.new /opt/keygroup/seo/kg_seo.py
curl -fsSL "$RAW/seo/kg_report.py?$(date +%s)" -o /opt/keygroup/seo/kg_report.py || echo "report script not downloaded"

# 1) new pages (buyer guides / hub) listed in seo/pages.txt
if curl -fsSL "$RAW/seo/pages.txt?$(date +%s)" -o /tmp/kg-seo-pages.txt; then
  for f in $(cat /tmp/kg-seo-pages.txt); do
    mkdir -p "$SITE/$(dirname "$f")"
    curl -fsSL "$RAW/site/$f?$(date +%s)" -o "$SITE/$f.new" && mv "$SITE/$f.new" "$SITE/$f" || echo "page not downloaded: $f"
  done
fi

# 2) generate agent pages, listing pages, sitemap.xml, 404.html
echo "Generating pages (first run can take a few minutes)..."
python3 /opt/keygroup/seo/kg_seo.py || { echo "STOP: generator failed - Caddy not changed"; exit 1; }
chmod -R a+rX "$SITE"

# 3) Caddy rules
BK="$CF.bak-seo-$(date +%s)"; cp "$CF" "$BK"
echo "--- site headers before:"; grep -nE '^[^#[:space:]][^{]*\{' "$CF"
python3 - "$CF" <<'PY'
import re, sys
p = sys.argv[1]; s = open(p).read(); orig = s
# find the main keygroup.ge block header (exact address, not staging/invest)
hm = None
for m in re.finditer(r'^([^\n#{]+)\{[ \t]*$', s, re.M):
    addrs = [a.strip() for a in re.split(r'[,\s]+', m.group(1)) if a.strip()]
    if any(a in ('keygroup.ge', 'https://keygroup.ge', 'keygroup.ge:443') for a in addrs):
        hm = m; break
if not hm: sys.exit("keygroup.ge block not found")
addrs = [a.strip() for a in re.split(r'[,\s]+', hm.group(1)) if a.strip()]
www = [a for a in addrs if 'www.keygroup.ge' in a]
if www:
    keep = [a for a in addrs if a not in www]
    s = s[:hm.start()] + ", ".join(keep) + " {" + s[hm.end():]
other_www = [m for m in re.finditer(r'^([^\n#{]+)\{[ \t]*$', s, re.M) if 'www.keygroup.ge' in m.group(1)]
if other_www and 'kg-www-redirect' not in s:
    print("NOTE: a separate www.keygroup.ge block already exists - left unchanged:", other_www[0].group(1).strip())
elif 'kg-www-redirect' not in s:
    s = s.rstrip("\n") + "\n\n# kg-www-redirect\nwww.keygroup.ge {\n\tredir https://keygroup.ge{uri} permanent\n}\n"
# agent profiles are real files now: drop the catch-all rewrite that caused soft 404s
s = re.sub(r'[ \t]*@kgagentprofile \{.*?\n[ \t]*\}\n[ \t]*rewrite @kgagentprofile /agent/index\.html\n', '', s, flags=re.S)
# listings: serve the pre-rendered page first, the normal page as fallback
s = s.replace('rewrite @kgagentlisting /p/index.html', 'try_files @kgagentlisting /_ssr{path}.html /p/index.html')
# sitemap.xml is now a static file built hourly
s = re.sub(r'[ \t]*reverse_proxy /sitemap\.xml kg-portal:8000\n', '', s)
# branded 404 page
blk = re.search(r'^([^\n#{]+)\{[ \t]*$', s[hm.start():], re.M)
start = hm.start() + blk.end() + 1
if 'kg-404' not in s:
    s = s[:start] + "\t# kg-404\n\thandle_errors {\n\t\t@kg404 expression {err.status_code} == 404\n\t\trewrite @kg404 /404.html\n\t\tfile_server\n\t}\n" + s[start:]
if s != orig: open(p, 'w').write(s)
print("Caddyfile updated" if s != orig else "Caddyfile already up to date")
PY
[ $? -eq 0 ] || { echo "STOP: could not update Caddyfile - restored"; cp "$BK" "$CF"; exit 1; }
CADDY_C=$(docker compose ps -q caddy)
if ! docker exec "$CADDY_C" caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null 2>&1; then
  echo "Caddy rules not valid - restored the previous config:"; docker exec "$CADDY_C" caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile 2>&1 | tail -3
  cp "$BK" "$CF"; exit 1
fi
docker compose restart caddy >/dev/null 2>&1; sleep 8

# 4) checks (core failures restore the backup)
code() { curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$1"; }
L=$(grep -o '<loc>https://keygroup.ge/[a-z0-9-]*/[a-z0-9-]*-[0-9]*</loc>' $SITE/sitemap.xml | head -n1 | sed 's/<[^>]*>//g')
A=$(grep -o '<loc>https://keygroup.ge/[a-z][a-z0-9-]*/</loc>' $SITE/sitemap.xml | sed 's/<[^>]*>//g' | while read u; do [ -f "$SITE/$(echo $u | cut -d/ -f4)/.kg-agent" ] && echo $u && break; done)
FAIL=0
for u in https://keygroup.ge/ https://keygroup.ge/search/ https://keygroup.ge/tbilisi/apartments-for-sale/ https://keygroup.ge/api/sitemap.xml "$L" "$A" https://keygroup.ge/sitemap.xml; do
  c=$(code "$u"); echo "$c  $u"; [ "$c" = 200 ] || FAIL=1
done
curl -s --max-time 20 "$L" | grep -q '<title>Property — KEY GROUP' && { echo "listing title not pre-rendered"; FAIL=1; }
if [ $FAIL = 1 ]; then echo "PROBLEM - restoring the previous Caddy config"; cp "$BK" "$CF"; docker compose restart caddy >/dev/null 2>&1; exit 1; fi
echo "$(code https://keygroup.ge/nonexistent-kg-test/)  /nonexistent-kg-test/ (want 404)"
echo "$(code https://keygroup.ge/tbilisi/)  /tbilisi/ (want 404)"
echo "$(curl -s -o /dev/null -w '%{http_code} -> %{redirect_url}' https://www.keygroup.ge/search/)  www (want 301 -> https://keygroup.ge/search/)"
echo "listing title: $(curl -s "$L" | grep -o '<title>[^<]*' | head -n1)"

# 5) refresh hourly
echo '17 * * * * root /usr/bin/python3 /opt/keygroup/seo/kg_seo.py >> /var/log/kg-seo.log 2>&1' > /etc/cron.d/keygroup-seo
echo '20 6 * * 1 root /usr/bin/python3 /opt/keygroup/seo/kg_report.py 7 >> /var/log/kg-report.log 2>&1' >> /etc/cron.d/keygroup-seo
chmod 644 /etc/cron.d/keygroup-seo
echo "DONE - SEO fix is live. Backup of the old Caddyfile: $BK"
