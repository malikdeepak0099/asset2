#!/usr/bin/env python3
"""KEY GROUP keygroup.ge SEO generator (runs hourly on the droplet).

Builds, without touching the portal code:
  site/sitemap.xml        portal sitemap minus invalid URLs, plus every real static page
  site/_ssr/<agent>/<slug>.html   listing page with its own title/description/OG/JSON-LD in the first HTML
  site/<agent>/index.html  agent profile page with its own title (marker file .kg-agent)
  site/404.html            branded not-found page
Only reads public endpoints of https://keygroup.ge. Never deletes anything it did not create.
"""
import html, json, os, re, sys, time, urllib.request

SITE_URL = "https://keygroup.ge"
SITE = os.environ.get("KG_SITE", "/opt/keygroup/site")
SSR = os.path.join(SITE, "_ssr")
MAX_AGE = 24 * 3600
BACKUP = os.environ.get("KG_BACKUP", "/opt/keygroup/seo/orig")
SKIP_DIRS = {"admin", "account", "publish", "compare", "upload", "agent", "p", "_ssr", "_staging",
             "assets", "img", "media", "uploads", "privacy"}


def get(path, timeout=30):
    req = urllib.request.Request(SITE_URL + path, headers={"User-Agent": "kg-seo/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")


def esc(s):
    return html.escape(str(s or ""), quote=True)


def clean(text, n=158):
    t = re.sub(r"[^\w\s.,:;$€₾/()%²+\-–—'’№#@&·]", " ", str(text or ""), flags=re.U)
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= n else t[: n - 1].rsplit(" ", 1)[0] + "…"


def write_if_changed(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        if open(path, encoding="utf-8").read() == data:
            return False
    except FileNotFoundError:
        pass
    tmp = path + ".tmp"
    open(tmp, "w", encoding="utf-8").write(data)
    os.replace(tmp, path)
    os.chmod(path, 0o644)
    return True


def set_head(page, title, desc, canonical, image=None, ld=None, og_type="website"):
    page = re.sub(r"<title>.*?</title>", "<title>" + esc(title) + "</title>", page, count=1, flags=re.S)
    page = re.sub(r'<meta name="description"[^>]*>', '<meta name="description" content="' + esc(desc) + '">', page, count=1)
    extra = ['<link rel="canonical" href="' + esc(canonical) + '">',
             '<meta property="og:type" content="' + og_type + '">',
             '<meta property="og:site_name" content="KEY GROUP Real Estate">',
             '<meta property="og:title" content="' + esc(title) + '">',
             '<meta property="og:description" content="' + esc(desc) + '">',
             '<meta property="og:url" content="' + esc(canonical) + '">',
             '<meta name="twitter:card" content="summary_large_image">',
             '<meta name="twitter:title" content="' + esc(title) + '">',
             '<meta name="twitter:description" content="' + esc(desc) + '">']
    if image:
        extra += ['<meta property="og:image" content="' + esc(image) + '">',
                  '<meta name="twitter:image" content="' + esc(image) + '">']
    if ld:
        extra.append('<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/") + "</script>")
    page = page.replace("</head>", "\n".join(extra) + "\n</head>", 1)
    return add_attrib(page)


ATTRIB = '<script src="/assets/kg-attrib.js?v=1" defer></script>'


def add_attrib(page):
    return page if "kg-attrib.js" in page else page.replace("</body>", ATTRIB + "\n</body>", 1)


def listing_page(tpl, l, path):
    deal = {"rent": "For rent", "sale": "For sale"}.get(l.get("deal"), "Property")
    title = (l.get("title") or deal + " in " + (l.get("district") or l.get("city") or "Georgia")).strip()
    cur = {"USD": "$", "EUR": "€", "GEL": "₾"}.get(l.get("currency"), (l.get("currency") or "") + " ")
    price = ""
    if l.get("price"):
        price = cur + "{:,.0f}".format(float(l["price"])) + (" / month" if l.get("deal") == "rent" else "")
    bits = [b for b in [price, (str(int(l["area"])) + " m²") if l.get("area") else "",
                        (str(l["rooms"]) + " rooms") if l.get("rooms") else "",
                        ", ".join(x for x in [l.get("district"), l.get("city")] if x)] if b]
    first = (l.get("description") or "").split("\n\n")[0].strip().rstrip(".")
    desc = clean(" · ".join(bits) + ". " + (first + ". " if first else "") + "KEY GROUP Real Estate, WhatsApp +995 577 114 118.")
    url = SITE_URL + path
    photos = l.get("photos") or []
    image = SITE_URL + "/uploads/" + photos[0] if photos else SITE_URL + "/img/hero.png"
    ld = {"@context": "https://schema.org", "@type": "RealEstateListing", "name": title, "url": url,
          "description": desc, "image": [SITE_URL + "/uploads/" + p for p in photos[:6]] or [image],
          "datePosted": time.strftime("%Y-%m-%d", time.gmtime(l.get("created") or time.time()))}
    if l.get("price"):
        ld["offers"] = {"@type": "Offer", "price": float(l["price"]), "priceCurrency": l.get("currency") or "USD",
                        "businessFunction": "http://purl.org/goodrelations/v1#" + ("LeaseOut" if l.get("deal") == "rent" else "Sell")}
    return set_head(tpl, title + " — KEY GROUP", desc, url, image, ld, "article")


# pages that get a server-rendered "current listings" block with direct links (crawlable)
INVENTORY = [
    # file, filter, language, show INR/AED
    ("georgia/property-for-sale/index.html", {"deal": "sale"}, "en", False),
    ("ka/georgia/property-for-sale/index.html", {"deal": "sale"}, "ka", False),
    ("buy-property-in-georgia-from-india/index.html", {"deal": "sale", "type": "flat", "city": "Tbilisi"}, "en", True),
    ("buy-property-in-georgia-from-uae/index.html", {"deal": "sale", "type": "flat"}, "en", True),
    ("tbilisi/apartments-for-sale/index.html", {"deal": "sale", "type": "flat", "city": "Tbilisi"}, "en", False),
    ("ka/tbilisi/apartments-for-sale/index.html", {"deal": "sale", "type": "flat", "city": "Tbilisi"}, "ka", False),
    ("tbilisi/apartments-for-rent/index.html", {"deal": "rent", "type": "flat", "city": "Tbilisi"}, "en", False),
    ("ka/tbilisi/apartments-for-rent/index.html", {"deal": "rent", "type": "flat", "city": "Tbilisi"}, "ka", False),
    ("batumi/apartments-for-sale/index.html", {"deal": "sale", "city": "Batumi"}, "en", False),
    ("ka/batumi/apartments-for-sale/index.html", {"deal": "sale", "city": "Batumi"}, "ka", False),
    ("tbilisi/saburtalo/index.html", {"deal": "sale", "district": "Saburtalo"}, "en", False),
    ("ka/tbilisi/saburtalo/index.html", {"deal": "sale", "district": "Saburtalo"}, "ka", False),
    ("tbilisi/vake/index.html", {"deal": "sale", "district": "Vake"}, "en", False),
    ("ka/tbilisi/vake/index.html", {"deal": "sale", "district": "Vake"}, "ka", False),
]


def inventory_block(items, lang, fx, rates):
    h = {"en": "Available now (%d)", "ka": "ახლა ხელმისაწვდომია (%d)"}[lang] % len(items)
    if not items:
        msg = {"en": "No listings here right now. Message us on WhatsApp +995 577 114 118 and an agent will send current options.",
               "ka": "ამჟამად განცხადება არ არის. მოგვწერეთ WhatsApp-ზე +995 577 114 118 და აგენტი გამოგიგზავნით ვარიანტებს."}[lang]
        return '<section class="kgl"><p>' + esc(msg) + "</p></section>"
    li = []
    for l in items[:24]:
        cur = {"USD": "$", "EUR": "€", "GEL": "₾"}.get(l.get("currency"), "")
        price = (cur + "{:,.0f}".format(float(l["price"]))) if l.get("price") else ""
        if l.get("deal") == "rent" and price:
            price += " / month"
        if fx and price and l.get("currency") == "USD" and rates:
            inr = float(l["price"]) * rates["INR"]
            inr_s = ("₹%.2f crore" % (inr / 1e7)) if inr >= 1e7 else ("₹%.1f lakh" % (inr / 1e5))
            price += " (≈ %s · AED %s)" % (inr_s, "{:,.0f}".format(float(l["price"]) * rates["AED"]))
        li.append('<li><a href="%s">%s</a>%s</li>' % (esc(l.get("path") or "/p/?id=%s" % l["id"]), esc(l.get("title") or "Listing %s" % l["id"]),
                                                     (" — " + esc(price)) if price else ""))
    return '<section class="kgl"><h2>' + esc(h) + "</h2><ul>" + "".join(li) + "</ul></section>"


def inject_inventory(rates):
    try:
        allx = json.loads(get("/api/listings?limit=200", 60)).get("listings") or []
    except Exception as ex:
        print("inventory not updated:", ex); return
    done = 0
    for rel, f, lang, fx in INVENTORY:
        path = os.path.join(SITE, rel)
        if not os.path.exists(path):
            continue
        items = [l for l in allx if l.get("status") == "active"
                 and all(str(l.get(k) or "").lower() == str(v).lower() for k, v in f.items())]
        items.sort(key=lambda l: -(l.get("created") or 0))
        block = "<!--kg-listings-->" + inventory_block(items, lang, fx, rates) + "<!--/kg-listings-->"
        page = open(path, encoding="utf-8").read()
        bk = os.path.join(BACKUP, rel)
        if not os.path.exists(bk):  # one-time backup of the original page (kept outside the web root)
            os.makedirs(os.path.dirname(bk), exist_ok=True)
            open(bk, "w", encoding="utf-8").write(page)
        if "<!--kg-listings-->" in page:
            page = re.sub(r"<!--kg-listings-->.*?<!--/kg-listings-->", lambda m: block, page, flags=re.S)
        elif '<div class="faqh"' in page:
            page = page.replace('<div class="faqh"', block + '\n  <div class="faqh"', 1)
        else:
            page = page.replace("</main>", block + "\n</main>", 1)
        if ".kgl{" not in page:
            page = page.replace("</style>", ".kgl{margin:26px 0;max-width:900px}.kgl ul{columns:2 320px;padding-left:18px}.kgl li{margin:5px 0;break-inside:avoid}\n</style>", 1)
        write_if_changed(path, add_attrib(page))
        done += 1
    print("inventory blocks:", done)


def main():
    t0 = time.time()
    portal_sm = get("/api/sitemap.xml", 60)
    if "<urlset" not in portal_sm:
        sys.exit("STOP: portal sitemap not available")
    locs = re.findall(r"<url><loc>([^<]+)</loc>(.*?)</url>", portal_sm, flags=re.S)
    listings = [(u, rest) for u, rest in locs if re.search(r"^https://keygroup\.ge/[a-z0-9-]+/[a-z0-9-]*-\d+$", u)]
    singles = {u[len(SITE_URL):].strip("/") for u, _ in locs if re.fullmatch(r"/[a-z][a-z0-9-]{1,30}/?", u[len(SITE_URL):])}
    agents = sorted({u.split("/")[3] for u, _ in listings} | singles)

    # 1) agent profile pages as real files (so unknown /anything/ can return 404)
    atpl = open(os.path.join(SITE, "agent", "index.html"), encoding="utf-8").read()
    good_agents = []
    for slug in agents:
        d = os.path.join(SITE, slug)
        if os.path.isdir(d) and not os.path.exists(os.path.join(d, ".kg-agent")):
            continue  # real site folder (tbilisi, ka, search ...), never overwrite
        try:
            a = json.loads(get("/api/agents?slug=" + slug)).get("agent") or {}
        except Exception:
            a = {}
        if a.get("slug") != slug:
            continue  # not a real agent profile (e.g. /tbilisi/, /ka/)
        name = re.sub(r"\s*·.*$", "", a.get("name") or slug.capitalize())
        title = name + " — KEY GROUP Real Estate agent in Tbilisi"
        desc = "Properties for sale and rent listed by " + name + ", KEY GROUP Real Estate agent in Tbilisi and Batumi. Message on WhatsApp for viewings."
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, ".kg-agent"), "w").close()
        write_if_changed(os.path.join(d, "index.html"), set_head(atpl, title, desc, SITE_URL + "/" + slug + "/"))
        good_agents.append(slug)

    # 2) pre-rendered listing pages
    ptpl = open(os.path.join(SITE, "p", "index.html"), encoding="utf-8").read()
    keep, made, fails = set(), 0, 0
    for u, _ in listings:
        path = u[len(SITE_URL):]
        f = os.path.join(SSR, path.lstrip("/") + ".html")
        keep.add(os.path.abspath(f))
        if os.path.exists(f) and time.time() - os.path.getmtime(f) < MAX_AGE:
            continue
        try:
            l = json.loads(get("/api/listings/" + path.rsplit("-", 1)[1])).get("listing")
            if not l or l.get("status") != "active":
                continue
            write_if_changed(f, listing_page(ptpl, l, path))
            os.utime(f)
            made += 1
        except Exception as e:
            fails += 1
            if fails <= 5:
                print("listing failed", path, e)
    removed = 0
    for root, _, files in os.walk(SSR):
        for n in files:
            p = os.path.abspath(os.path.join(root, n))
            if p not in keep:
                os.remove(p); removed += 1

    # 3) sitemap: valid portal URLs + every real static page
    static = []
    for root, dirs, files in os.walk(SITE):
        rel = os.path.relpath(root, SITE)
        if rel == ".":
            continue
        top = rel.split(os.sep)[0]
        if top in SKIP_DIRS or top.startswith(("_", ".")) or top in good_agents:
            dirs[:] = []
            continue
        if "index.html" in files and rel != ".":
            static.append("/" + rel.replace(os.sep, "/") + "/")
    for p in ("/project/", "/search/", "/partners/"):
        if os.path.exists(os.path.join(SITE, p.strip("/"), "index.html")) and p not in static:
            static.append(p)
    out, seen = [], set()

    def add(loc, rest=""):
        if loc in seen:
            return
        seen.add(loc)
        out.append("<url><loc>" + loc + "</loc>" + rest + "</url>")

    add(SITE_URL + "/", "<changefreq>daily</changefreq>")
    for p in sorted(static):
        add(SITE_URL + p, "<changefreq>weekly</changefreq>")
    for slug in good_agents:
        add(SITE_URL + "/" + slug + "/", "<changefreq>daily</changefreq>")
    for u, rest in locs:
        path = u[len(SITE_URL):]
        if u in seen:
            continue
        if re.fullmatch(r"/[^/]+/?", path) and path.strip("/") not in good_agents and \
                not os.path.exists(os.path.join(SITE, path.strip("/"), "index.html")):
            continue  # invalid: /tbilisi/, /batumi/, /ka/, /ru/ ...
        if re.fullmatch(r"/[a-z0-9-]+/[a-z0-9-]*-\d+", path) and not os.path.exists(os.path.join(SSR, path.lstrip("/") + ".html")):
            continue  # inactive or failed listing
        add(u, rest)
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(out) + "\n</urlset>\n"
    if len(out) < 50:
        sys.exit("STOP: sitemap too small (%d) - not replaced" % len(out))
    write_if_changed(os.path.join(SITE, "sitemap.xml"), sm)

    # 4) indicative exchange rates for the INR/AED guide pages (keeps the last good file on failure)
    rates = {"INR": 95.0, "AED": 3.6725}
    try:
        rates = json.loads(open(os.path.join(SITE, "assets", "kg-fx.json")).read())
    except Exception:
        pass
    try:
        req = urllib.request.Request("https://open.er-api.com/v6/latest/USD", headers={"User-Agent": "kg-seo/1.0"})
        r = json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
        inr, aed = float(r["rates"]["INR"]), float(r["rates"]["AED"])
        if 60 < inr < 200 and 3.5 < aed < 3.8:
            rates = {"INR": round(inr, 2), "AED": round(aed, 4), "date": time.strftime("%d %b %Y")}
            write_if_changed(os.path.join(SITE, "assets", "kg-fx.json"), json.dumps(rates))
    except Exception as ex:
        print("fx not updated:", ex)
    inject_inventory(rates)

    # 5) branded 404 page (only if none exists)
    nf = os.path.join(SITE, "404.html")
    if not os.path.exists(nf):
        write_if_changed(nf, """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Page not found — KEY GROUP Real Estate</title><meta name="robots" content="noindex">
<style>body{font-family:system-ui,sans-serif;background:#0f1b33;color:#fff;display:grid;place-items:center;min-height:100vh;margin:0;text-align:center}a{color:#e8c36a}</style></head>
<body><main><h1>404 — გვერდი ვერ მოიძებნა / Page not found</h1>
<p><a href="/">KEY GROUP — მთავარი / Home</a> · <a href="/search/">Search properties</a> · <a href="https://wa.me/995577114118">WhatsApp +995 577 114 118</a></p></main></body></html>
""")
    print(time.strftime("%F %T"), "OK sitemap=%d urls, agents=%d, listings rendered=%d, removed=%d, failed=%d, %.0fs"
          % (len(out), len(good_agents), made, removed, fails, time.time() - t0))


if __name__ == "__main__":
    main()
