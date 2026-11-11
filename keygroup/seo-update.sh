# KEY GROUP keygroup.ge SEO content update (files only — never touches Caddy). Run in the droplet console as root:
#   curl -fsSL https://raw.githubusercontent.com/malikdeepak0099/asset2/seo-fix/keygroup/seo-update.sh | bash
# Updates: generator (homepage = Georgia service area, invest-page INR/AED guide block, inventory blocks),
# buyer pages, kg-attrib.js (market GE/IN/AE), weekly report. Backs up the pages first and restores them
# if a content check fails.
set -u
RAW=https://raw.githubusercontent.com/malikdeepak0099/asset2/seo-fix/keygroup
SITE=/opt/keygroup/site
SEO=/opt/keygroup/seo
cd /opt/keygroup || { echo "STOP: /opt/keygroup not found"; exit 1; }
mkdir -p $SEO
for f in seo/kg_seo.py seo/kg_report.py seo/pages.txt; do
  curl -fsSL "$RAW/$f?$(date +%s)" -o "$SEO/$(basename $f).new" || { echo "STOP: download $f failed - nothing changed"; exit 1; }
done
python3 -m py_compile $SEO/kg_seo.py.new && python3 -m py_compile $SEO/kg_report.py.new || { echo "STOP: scripts broken - nothing changed"; exit 1; }
# backup of every page this update can change
BK=$SEO/site-bak-$(date +%s).tgz
( cd $SITE && tar czf $BK index.html invest-in-georgia ka/invest-in-georgia ru/invest-in-georgia assets/kg-attrib.js \
    georgia ka/georgia buy-property-in-georgia-from-india buy-property-in-georgia-from-uae 2>/dev/null )
echo "backup: $BK"
title() { curl -s --max-time 20 "https://keygroup.ge$1" | grep -o '<title>[^<]*' | head -n1; }
SAME="/search/ /tbilisi/apartments-for-sale/ /privacy/ /nika/ /project/"
BEFORE=$(for p in $SAME; do echo "$p $(title $p)"; done)
mv $SEO/kg_seo.py.new $SEO/kg_seo.py; mv $SEO/kg_report.py.new $SEO/kg_report.py; mv $SEO/pages.txt.new $SEO/pages.txt
for f in $(cat $SEO/pages.txt); do
  mkdir -p "$SITE/$(dirname "$f")"
  curl -fsSL "$RAW/site/$f?$(date +%s)" -o "$SITE/$f.new" && mv "$SITE/$f.new" "$SITE/$f" || echo "not downloaded: $f"
done
python3 $SEO/kg_seo.py || echo "generator reported a problem"
chmod -R a+rX $SITE
AFTER=$(for p in $SAME; do echo "$p $(title $p)"; done)
FAIL=0
[ "$BEFORE" = "$AFTER" ] || { echo "PROBLEM: unrelated pages changed"; diff <(echo "$BEFORE") <(echo "$AFTER"); FAIL=1; }
H=$(title /); case "$H" in *"Property in Georgia"*) ;; *) echo "PROBLEM: homepage title: $H"; FAIL=1;; esac
curl -s https://keygroup.ge/ | grep -q '"@type":"Country","name":"Georgia"' || { echo "PROBLEM: schema not updated"; FAIL=1; }
curl -s https://keygroup.ge/invest-in-georgia/ | grep -q 'kg-guides' || { echo "PROBLEM: invest page block missing"; FAIL=1; }
curl -s https://keygroup.ge/assets/portal.css | grep -q '{' || { echo "PROBLEM: css"; FAIL=1; }
if [ $FAIL = 1 ]; then echo "RESTORING pages from $BK"; ( cd $SITE && tar xzf $BK ); exit 1; fi
echo "homepage: $H"
echo "invest: $(curl -s https://keygroup.ge/invest-in-georgia/ | grep -o 'Budget examples at today[^<]*' | head -n1)"
echo "DONE - content update live"
