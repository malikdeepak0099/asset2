#!/usr/bin/env python3
"""KEY GROUP weekly landing-page report (runs on the droplet, read-only on the portal database).

For each visit session in the period: the first page viewed is the landing page and the
external referrer is the source (google.* = Google search). Counts what those sessions did:
WhatsApp clicks, call clicks, enquiry forms and viewing requests. No names or phone numbers
are read. Writes /opt/keygroup/seo/reports/<YYYY-MM-DD>.json and prints a table.
Usage: python3 kg_report.py [days]   (default 7)
"""
import collections, json, os, sqlite3, sys, time

DB = os.environ.get("KG_DB", "/opt/keygroup-portal/data/portal.db")
OUT = os.environ.get("KG_REPORTS", "/opt/keygroup/seo/reports")
ACTIONS = ("whatsapp_click", "call_click", "lead_submitted", "viewing_requested")


def source(ref):
    r = (ref or "").lower()
    if not r:
        return "direct/unknown"
    if "google." in r:
        return "google"
    for k in ("bing.", "yandex.", "duckduckgo.", "yahoo."):
        if k in r:
            return "other search"
    for k in ("facebook.", "instagram.", "tiktok.", "t.co", "youtube.", "l.wl.co", "whatsapp"):
        if k in r:
            return "social"
    return "referral:" + r[:40]


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    since = time.time() - days * 86400
    con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    rows = con.execute("SELECT name, sid, page, props, ts FROM events WHERE ts>=? AND name IN (%s) ORDER BY ts"
                       % ",".join("?" * (len(ACTIONS) + 1)), (since, "page_view") + ACTIONS).fetchall()
    land = {}
    stats = collections.defaultdict(lambda: collections.Counter())
    for name, sid, page, props, ts in rows:
        try:
            p = json.loads(props or "{}")
        except Exception:
            p = {}
        if name == "page_view" and sid not in land:
            land[sid] = (page.split("?")[0] or "/", source(p.get("ref")))
            stats[land[sid]]["sessions"] += 1
        elif name in ACTIONS and sid in land:
            stats[land[sid]][name] += 1
    out = [{"landing": k[0], "source": k[1], **v} for k, v in stats.items()]
    out.sort(key=lambda r: (r["source"] != "google", -r.get("sessions", 0)))
    os.makedirs(OUT, exist_ok=True)
    f = os.path.join(OUT, time.strftime("%Y-%m-%d") + ".json")
    json.dump({"days": days, "generated": time.strftime("%F %T"), "rows": out}, open(f, "w"), ensure_ascii=False, indent=1)
    print("%-48s %-14s %8s %6s %6s %6s %6s" % ("landing page", "source", "sessions", "wa", "call", "form", "view"))
    for r in out[:60]:
        print("%-48s %-14s %8d %6d %6d %6d %6d" % (r["landing"][:48], r["source"][:14], r.get("sessions", 0), r.get("whatsapp_click", 0),
                                                   r.get("call_click", 0), r.get("lead_submitted", 0), r.get("viewing_requested", 0)))
    print("saved", f)


if __name__ == "__main__":
    main()
