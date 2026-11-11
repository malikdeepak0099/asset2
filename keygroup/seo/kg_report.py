#!/usr/bin/env python3
"""KEY GROUP weekly landing-page report (runs on the droplet, read-only on the portal database).

Per visit session in the period: the first page viewed is the landing page, the external
referrer is the source (google.* = Google search), and the market (GE / IN / AE / other) comes
from kg-attrib.js (browser time zone). Counts what those sessions did: WhatsApp clicks, call
clicks, enquiry forms and viewing requests. No names or phone numbers are read.
Writes /opt/keygroup/seo/reports/<YYYY-MM-DD>.json and prints a table.
Usage: python3 kg_report.py [days] [--telegram]   (default 7 days)
--telegram sends a short English summary to the KEY GROUP admin Telegram (bot token from the portal .env).
"""
import collections, json, os, sqlite3, sys, time, urllib.parse, urllib.request

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


ENV = os.environ.get("KG_PORTAL_ENV", "/opt/keygroup-portal/.env")
REPORT_CHATS = os.environ.get("KG_REPORT_CHATS", "8462114396")  # Deepak's Telegram ID


def telegram(text):
    token = ""
    try:
        for line in open(ENV):
            if line.startswith("BOT_TOKEN="):
                token = line.split("=", 1)[1].strip()
    except Exception as e:
        print("telegram: no env", e); return
    if not token:
        print("telegram: no BOT_TOKEN"); return
    for chat in [c for c in REPORT_CHATS.split(",") if c.strip()]:
        try:
            data = urllib.parse.urlencode({"chat_id": chat.strip(), "text": text, "disable_web_page_preview": "true"}).encode()
            urllib.request.urlopen("https://api.telegram.org/bot%s/sendMessage" % token, data, timeout=20).read()
            print("telegram: sent to", chat)
        except Exception as e:
            print("telegram: failed for", chat, e)


def summary(out, days):
    g = [r for r in out if r["source"] == "google"]
    by_m = collections.Counter()
    enq_m = collections.Counter()
    for r in g:
        by_m[r["market"]] += r.get("sessions", 0)
        enq_m[r["market"]] += r.get("sessions_with_enquiry", 0)
    lines = ["KEY GROUP - Google organic report, last %d days" % days, "",
             "Google visits / visits with enquiry (WhatsApp, call, form, viewing):"]
    for m in ("GE", "IN", "AE", "other", "unknown"):
        if by_m[m]:
            lines.append("  %s: %d / %d" % (m, by_m[m], enq_m[m]))
    if not g:
        lines.append("  no Google visits recorded yet")
    top = sorted(g, key=lambda r: (-r.get("sessions_with_enquiry", 0), -r.get("sessions", 0)))[:8]
    if top:
        lines += ["", "Top landing pages from Google:"]
        for r in top:
            lines.append("  %s [%s] visits %d, enquiries %d (wa %d, call %d, form %d)" % (
                r["landing"][:60], r["market"], r.get("sessions", 0), r.get("sessions_with_enquiry", 0),
                r.get("whatsapp_click", 0), r.get("call_click", 0), r.get("lead_submitted", 0)))
    allv = sum(r.get("sessions", 0) for r in out)
    alle = sum(r.get("sessions_with_enquiry", 0) for r in out)
    lines += ["", "All sources: %d visits, %d with an enquiry." % (allv, alle),
              "Mark qualified leads in the CRM using the [ref ...] tag in WhatsApp messages."]
    return "\n".join(lines)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    days = int(args[0]) if args else 7
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
    if "--telegram" in sys.argv:
        telegram(summary(out, days))


if __name__ == "__main__":
    main()
