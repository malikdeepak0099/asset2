# KEY GROUP keygroup.ge SEO fix, part 2 (Caddy rules only). Run in the droplet console as root:
#   curl -fsSL https://raw.githubusercontent.com/malikdeepak0099/asset2/seo-fix/keygroup/seo-fix2.sh | bash
# - www.keygroup.ge -> https://keygroup.ge 301
# - unknown URLs return a real 404 page (agent profiles are real files made by kg_seo.py)
# - listings: pre-rendered page (/_ssr/...) when it exists, the normal page otherwise
# - sitemap.xml served from the static file made hourly by kg_seo.py
# Safety: compares page titles before/after and restores the backup if any page changed unexpectedly.
set -u
cd /opt/keygroup || { echo "STOP: /opt/keygroup not found"; exit 1; }
CF=Caddyfile
[ -f "$CF" ] || { echo "STOP: Caddyfile not found"; exit 1; }
PAGES="/ /search/ /tbilisi/apartments-for-sale/ /ka/tbilisi/apartments-for-sale/ /invest-in-georgia/ /privacy/ /nika/ /project/ /partners/ /assets/portal.css /assets/portal.js /robots.txt"
snap() {
  for p in $PAGES; do
    b=$(curl -s --max-time 20 "https://keygroup.ge$p")
    t=$(printf '%s' "$b" | grep -o '<title>[^<]*' | head -n1)
    [ -n "$t" ] || t="len=$(printf '%s' "$b" | head -c 400 | md5sum | cut -c1-8)"
    echo "$p $t"
  done
}
BEFORE=$(snap)
BK="$CF.bak-seo2-$(date +%s)"; cp "$CF" "$BK"
python3 - "$CF" <<'PY'
import re, sys
p = sys.argv[1]; s = open(p).read(); orig = s
hm = None
for m in re.finditer(r'^([^\n#{]+)\{[ \t]*$', s, re.M):
    addrs = [a.strip() for a in re.split(r'[,\s]+', m.group(1)) if a.strip()]
    if any(a in ('keygroup.ge', 'https://keygroup.ge') for a in addrs):
        hm = m; break
if not hm: sys.exit("keygroup.ge block not found")
addrs = [a.strip() for a in re.split(r'[,\s]+', hm.group(1)) if a.strip()]
if any('www.keygroup.ge' in a for a in addrs):
    s = s[:hm.start()] + ", ".join(a for a in addrs if 'www.keygroup.ge' not in a) + " {" + s[hm.end():]
if 'kg-www-redirect' not in s and not re.search(r'^\s*www\.keygroup\.ge\s*\{', s, re.M):
    s = s.rstrip("\n") + "\n\n# kg-www-redirect\nwww.keygroup.ge {\n\tredir https://keygroup.ge{uri} permanent\n}\n"
# agent profiles are real files now: drop the catch-all profile rewrite (cause of soft 404s)
s = re.sub(r'[ \t]*@kgagentprofile \{.*?\n[ \t]*\}\n[ \t]*rewrite @kgagentprofile /agent/index\.html\n', '', s, flags=re.S)
# listings: pre-rendered file first (two disjoint matchers, no try_files with matchers)
if 'kgssr' not in s:
    s = s.replace('\t\tnot file\n\t}\n\trewrite @kgagentlisting /p/index.html',
                  '\t\tnot file\n\t\tnot file /_ssr{path}.html\n\t}\n\trewrite @kgagentlisting /p/index.html\n'
                  '\t@kgssr {\n\t\tpath_regexp ^/[a-z0-9-]+/[a-z0-9-]*-[0-9]+$\n\t\tfile /_ssr{path}.html\n\t}\n\trewrite @kgssr /_ssr{path}.html', 1)
s = re.sub(r'[ \t]*reverse_proxy /sitemap\.xml kg-portal:8000\n', '', s)
if 'kg-404' not in s:
    blk = re.search(r'^([^\n#{]+)\{[ \t]*$', s[hm.start():], re.M)
    at = hm.start() + blk.end() + 1
    s = s[:at] + "\t# kg-404\n\thandle_errors {\n\t\t@kg404 expression {err.status_code} == 404\n\t\trewrite @kg404 /404.html\n\t\tfile_server {\n\t\t\tstatus 404\n\t\t}\n\t}\n" + s[at:]
if s != orig: open(p, 'w').write(s)
print("Caddyfile updated" if s != orig else "Caddyfile already up to date")
PY
[ $? -eq 0 ] || { cp "$BK" "$CF"; echo "STOP: patch failed - restored"; exit 1; }
CADDY_C=$(docker compose ps -q caddy)
if ! docker exec "$CADDY_C" caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/tmp/kg-validate.log 2>&1; then
  cp "$BK" "$CF"; echo "Caddy rules not valid - restored:"; tail -3 /tmp/kg-validate.log; exit 1
fi
docker compose restart caddy >/dev/null 2>&1; sleep 8
AFTER=$(snap)
if [ "$BEFORE" != "$AFTER" ]; then
  echo "PROBLEM - pages changed, restoring:"; diff <(echo "$BEFORE") <(echo "$AFTER")
  cp "$BK" "$CF"; docker compose restart caddy >/dev/null 2>&1; sleep 6; exit 1
fi
L=$(grep -o '<loc>https://keygroup.ge/[a-z0-9-]*/[a-z0-9-]*-[0-9]*</loc>' /opt/keygroup/site/sitemap.xml | head -n1 | sed 's/<[^>]*>//g')
LT=$(curl -s "$L" | grep -o '<title>[^<]*' | head -n1)
case "$LT" in
  *"Property — KEY GROUP"*|"") echo "PROBLEM - listing not pre-rendered ($LT), restoring"; cp "$BK" "$CF"; docker compose restart caddy >/dev/null 2>&1; exit 1;;
esac
echo "pages unchanged: OK"
echo "listing: $L -> $LT"
echo "$(curl -s -o /dev/null -w '%{http_code}' https://keygroup.ge/p/?id=1360)  /p/?id=1360 (want 200)"
echo "$(curl -s -o /dev/null -w '%{http_code}' https://keygroup.ge/nonexistent-kg-test/)  /nonexistent-kg-test/ (want 404)"
echo "$(curl -s -o /dev/null -w '%{http_code}' https://keygroup.ge/tbilisi/)  /tbilisi/ (want 404)"
echo "$(curl -s -o /dev/null -w '%{http_code} -> %{redirect_url}' https://www.keygroup.ge/search/)  www (want 301)"
curl -s https://keygroup.ge/sitemap.xml | grep -c '<loc>' | sed 's/^/sitemap urls: /'
curl -s https://keygroup.ge/sitemap.xml | grep -cE '<loc>https://keygroup.ge/(tbilisi|batumi|ka|ru)/</loc>' | sed 's/^/invalid urls in sitemap (want 0): /'
echo "DONE. Backup: $BK"
