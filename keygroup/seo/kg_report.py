#!/usr/bin/env python3
"""KEY GROUP weekly landing-page report (runs on the droplet, read-only on the portal database).

Per visit session in the period: the first page viewed is the landing page, the external
referrer is the source (google.* = Google search), and the market (GE / IN / AE / other) comes
from kg-attrib.js (browser time zone). Counts what those sessions did: WhatsApp clicks, call
clicks, enquiry forms and viewing requests. No names or phone numbers are read.
Writes /opt/keygroup/seo/reports/<YYYY-MM-DD>.json and prints a table.
Usage: python3 kg_report.py [days]   (default 7)
"""
import collections, json, os, sqlite3, sys, time

DB = os.environ.get("KG_DB", "/opt/keygroup-portal/data/portal.db")
OUT = os.environ.get("KG_REPORTS", "/opt/keygroup/seo/reports")
ACTIONS = ("whatsapp_click", "call_click", "lead_submitted", "viewing_requested")
DEDUP = ("whatsapp_click", "call_click")  # sent by chat.js and by kg-attrib.js: count one of them


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
    sess = {}
    for name, sid, page, props, ts in rows:
        try:
            p = json.loads(props or "{}")
        except Exception:
            p = {}
        s = sess.get(sid)
        if s is None:
            if name != "page_view":
                continue
            s = sess[sid] = {"land": (page or "/").split("?")[0], "src": source(p.get("ref")), "mkt": "",
                             "plain": collections.Counter(), "attrib": collections.Counter()}
            continue
        if name == "page_view":
            continue
        if p.get("mkt") and not s["mkt"]:
            s["mkt"] = str(p["mkt"])
        s["attrib" if p.get("via") == "attrib" else "plain"][name] += 1
    stats = collections.defaultdict(collections.Counter)
    for s in sess.values():
        mkt = s["mkt"] or "unknown"
        mkt = mkt if mkt in ("GE", "IN", "AE") else ("other" if mkt.startswith("other") else "unknown")
        k = (s["land"], s["src"], mkt)
        stats[k]["sessions"] += 1
        for a in ACTIONS:
            if a in DEDUP:
                n = s["attrib"][a] or s["plain"][a]
            else:
                n = s["attrib"][a] + s["plain"][a]
            stats[k][a] += n
        if any(s["attrib"][a] or s["plain"][a] for a in ACTIONS):
            stats[k]["sessions_with_enquiry"] += 1
    out = [{"landing": k[0], "source": k[1], "market": k[2], **v} for k, v in stats.items()]
    out.sort(key=lambda r: (r["source"] != "google", -r.get("sessions_with_enquiry", 0), -r.get("sessions", 0)))
    os.makedirs(OUT, exist_ok=True)
    f = os.path.join(OUT, time.strftime("%Y-%m-%d") + ".json")
    json.dump({"days": days, "generated": time.strftime("%F %T"), "rows": out}, open(f, "w"), ensure_ascii=False, indent=1)
    print("%-44s %-10s %-7s %8s %7s %5s %5s %5s %5s" % ("landing page", "source", "market", "sessions", "enquiry", "wa", "call", "form", "view"))
    for r in out[:80]:
        print("%-44s %-10s %-7s %8d %7d %5d %5d %5d %5d" % (r["landing"][:44], r["source"][:10], r["market"], r.get("sessions", 0),
                                                         r.get("sessions_with_enquiry", 0), r.get("whatsapp_click", 0), r.get("call_click", 0),
                                                         r.get("lead_submitted", 0), r.get("viewing_requested", 0)))
    print("saved", f)


if __name__ == "__main__":
    main()
