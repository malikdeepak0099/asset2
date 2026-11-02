"""KEY GROUP Assistant — one Telegram bot, a private assistant for every agent.

* Agent profile sync: the agent's own MyHome.ge profile is read daily (and on /sync);
  every listing goes into the agent's personal database and into the Master CRM
  ("Agent Listings" tab). New / changed / removed listings are reported to the agent
  and, consolidated for all agents, to the owner (admin) in the same bot.
* Owner listings: agent sends an owner's MyHome.ge / SS.ge link -> data is extracted ->
  agent calls the owner, taps "owner agreed" -> bot prepares the KEY GROUP listing
  (GE/EN/RU texts, fields, photos) ready to post, and saves it to the Master CRM.
"""
import html
import json
import os
import re
import sys
import threading
import time
import traceback
from datetime import datetime, timezone, timedelta

import requests

import drafts
import extract
import profiles
import texts
from store import Store

TOKEN = os.environ["BOT_TOKEN"].strip()
API = f"https://api.telegram.org/bot{TOKEN}/"
ADMIN_ID = os.environ.get("ADMIN_ID", "").strip()
EXTRA_ADMINS = {a.strip() for a in os.environ.get("ADMINS", "").split(",") if a.strip()}
COMPANY_PHONE = os.environ.get("COMPANY_PHONE", "+995 577 114 118").strip()
CRM_URL = os.environ.get("CRM_URL", "").strip()
CRM_SECRET = os.environ.get("CRM_SECRET", "").strip()
PORTAL_URL = os.environ.get("PORTAL_URL", "https://keygroup.ge").strip().rstrip("/")
DATA_DIR = os.environ.get("DATA_DIR", "/data")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
TBILISI = timezone(timedelta(hours=4))
DAILY_SYNC_HOUR = int(os.environ.get("DAILY_SYNC_HOUR", "9"))
AGENT_NAMES = [n.strip() for n in os.environ.get("AGENT_NAMES", "Demetre,Nini,Ana,Dato,Nika,Giorgi,Zura").split(",") if n.strip()]
DB = Store(os.path.join(DATA_DIR, "agents.db"))
SYNC_LOCK = threading.Lock()

TYPE_KA = {"flat": "ბინა", "house": "კერძო სახლი", "land": "მიწა", "commercial": "კომერციული", "hotel": "სასტუმრო"}
DEAL_KA = {"sale": "იყიდება", "rent": "ქირავდება", "": "—"}
B_DEAL = {"sale": "იყიდება", "rent": "ქირავდება", "daily": "დღიური ქირა"}


# ---------------------------------------------------------------- state

def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"agents": {}, "pending": {}, "offset": 0, "profiles": {}}


def save_state():
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(STATE, f, ensure_ascii=False)
    os.replace(tmp, STATE_FILE)


STATE = load_state()
STATE.setdefault("profiles", {})
STATE.setdefault("last_daily", "")
STATE.setdefault("admins", [])


def admins():
    return ({ADMIN_ID} if ADMIN_ID else set()) | EXTRA_ADMINS | set(STATE.get("admins", []))


def is_admin(uid):
    return str(uid) in admins()


def send_admins(text, buttons=None):
    """text may be a function(uid) -> str so every admin gets their own language."""
    for a in admins():
        send(a, text(a) if callable(text) else text, buttons)


def lang_of(uid):
    uid = str(uid)
    return STATE.setdefault("lang", {}).get(uid) or ("en" if is_admin(uid) else "ka")


def tr(uid, ka, en):
    return en if lang_of(uid) == "en" else ka


BOT_USERNAME = ""
for pair in os.environ.get("AGENTS", "").split(","):
    if ":" in pair:
        i, n = pair.split(":", 1)
        STATE["agents"].setdefault(i.strip(), n.strip())


def agent_name(uid):
    uid = str(uid)
    if uid in STATE["agents"]:
        return STATE["agents"][uid]
    if uid in admins():
        return "Deepak"
    return None


# ---------------------------------------------------------------- telegram

def tg(method, **params):
    try:
        r = requests.post(API + method, json=params, timeout=60)
        out = r.json()
        if not out.get("ok"):
            print("TG error", method, out.get("description"))
        return out
    except Exception as e:
        print("TG exception", method, e)
        return {}


def send(chat, text, buttons=None):
    p = {"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if buttons:
        p["reply_markup"] = {"inline_keyboard": buttons}
    return tg("sendMessage", **p)


def e(s):
    return html.escape(str(s or ""))


def send_kb(chat, text, reply_markup):
    return tg("sendMessage", chat_id=chat, text=text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=reply_markup)


_RESETS = {}


def too_many_resets(uid, limit=5, window=3600):
    now = time.time()
    hits = [t for t in _RESETS.get(str(uid), []) if now - t < window]
    hits.append(now)
    _RESETS[str(uid)] = hits
    return len(hits) > limit


def outbox_loop():
    """Deliver messages the website queued (e.g. a password reset done by the admin) — every 30 seconds."""
    while True:
        try:
            if CRM_SECRET:
                r = requests.post(PORTAL_URL + "/api/bot/outbox", headers={"X-Bot-Secret": CRM_SECRET}, timeout=30).json()
                for m in r.get("messages") or []:
                    btn = [[{"text": m.get("button_text") or "Open", "url": m["button_url"]}]] if m.get("button_url") else None
                    send(m["tg_id"], m["text"], btn)
        except Exception as ex:
            print("outbox", ex)
        time.sleep(30)


# ---------------------------------------------------------------- views

HELP_EN = (
    "👋 <b>KEY GROUP Assistant</b> — your personal assistant\n\n"
    "<b>Your profile</b>\n"
    "• /profile — send your MyHome.ge profile link (or any of your own listings). Every day I read all your listings, "
    "save them to the CRM and tell you what changed.\n"
    "• /sync — update now · /my — my database\n\n"
    "<b>Owner listing</b>\n"
    "1️⃣ Send me an owner's listing <b>link</b> (myhome.ge or ss.ge).\n"
    "2️⃣ I extract all the details and the owner's phone.\n"
    "3️⃣ Call the owner. If they agree, tap <b>“✅ Owner agreed”</b>.\n"
    "4️⃣ Ask the owner for the <b>original photos</b> and forward them to me (as files = full quality). I never remove logos or edit photos.\n"
    "5️⃣ Tap <b>“👁 Preview”</b>: you see exactly what will be published (title, texts, price, specs, photos, your contact, MyHome and SS format). Fix anything with ✏️.\n"
    "6️⃣ Tap <b>“✅ Approve and publish”</b> once: keygroup.ge + CRM + a ready MyHome / SS package. Nothing is published without your approval.\n\n"
    "/new — new listing without a link · /draft — my open draft · /phone — my contact number (shown instead of the owner's)\n"
    "/login — open my keygroup.ge account (all my listings, leads, editing)\n"
    "/myid — your Telegram ID · /lang — ქართული / English"
)

HELP = (
    "👋 <b>KEY GROUP Assistant</b> — შენი პირადი ასისტენტი\n\n"
    "<b>შენი პროფილი</b>\n"
    "• /profile — გამომიგზავნე შენი MyHome.ge პროფილის ბმული (ან შენი ნებისმიერი განცხადება). "
    "ყოველდღე ავიღებ შენს ყველა განცხადებას, ჩავწერ CRM-ში და გეტყვი რა შეიცვალა.\n"
    "• /sync — ახლავე განახლება · /my — ჩემი ბაზა\n\n"
    "<b>მესაკუთრის განცხადება</b>\n"
    "1️⃣ გამომიგზავნე მესაკუთრის განცხადების <b>ბმული</b> (myhome.ge ან ss.ge).\n"
    "2️⃣ ამოვიღებ ყველა ინფორმაციას და მესაკუთრის ნომერს.\n"
    "3️⃣ დაურეკე მესაკუთრეს. თუ თანახმაა, დააჭირე <b>„✅ მესაკუთრე თანახმაა“</b>.\n"
    "4️⃣ სთხოვე მესაკუთრეს <b>ორიგინალი ფოტოები</b> და გადმომიგზავნე (ფაილად = სრული ხარისხი). ლოგოებს არ ვშლი და ფოტოებს არ ვცვლი.\n"
    "5️⃣ დააჭირე <b>„👁 გადახედვა“</b>: ნახავ ზუსტად რა გამოქვეყნდება (სათაური, ტექსტი, ფასი, მონაცემები, ფოტოები, შენი კონტაქტი, MyHome და SS ფორმატი). ✏️ ღილაკებით შეასწორე.\n"
    "6️⃣ დააჭირე <b>„✅ დამტკიცება და გამოქვეყნება“</b> ერთხელ: keygroup.ge + CRM + მზა პაკეტი MyHome / SS-ისთვის. შენი თანხმობის გარეშე არაფერი ქვეყნდება.\n\n"
    "/new — ახალი განცხადება ბმულის გარეშე · /draft — ჩემი დრაფტი · /phone — ჩემი ნომერი (ჩანს მესაკუთრის ნაცვლად)\n"
    "/login — შესვლა ჩემს keygroup.ge ანგარიშზე (ჩემი ყველა განცხადება, მოთხოვნები, რედაქტირება)\n"
    "/myid — შენი Telegram ID · /lang — ქართული / English"
)

ADMIN_HELP_EN = (
    "\n\n👑 <b>Admin</b>\n/invite — link to send to agents · /team — company report (24 h)\n"
    "/syncall — update all agents now · /agents — agents and their profiles\n/website — agents' MyHome listings on keygroup.ge (on / off / now)\n"
    "/addadmin &lt;ID&gt; — add another admin · /setprofile &lt;TelegramID&gt; &lt;link&gt; — set an agent's profile"
)

ADMIN_HELP = (
    "\n\n👑 <b>ადმინი</b>\n/invite — აგენტების ბმული · /team — კომპანიის ანგარიში · /syncall — ყველა აგენტის განახლება\n/website — აგენტების MyHome განცხადებები keygroup.ge-ზე\n"
    "/agents — აგენტები · /addadmin &lt;ID&gt; — მეორე ადმინი · /setprofile &lt;TelegramID&gt; &lt;ბმული&gt; — აგენტის პროფილი"
)


def help_for(uid):
    if lang_of(uid) == "en":
        return HELP_EN + (ADMIN_HELP_EN if is_admin(uid) else "")
    return HELP + (ADMIN_HELP if is_admin(uid) else "")


def invite_text(uid):
    link = f"https://t.me/{BOT_USERNAME}" if BOT_USERNAME else "(bot link)"
    return tr(uid,
              f"🔗 აგენტების ბმული: {link}\n\nგადაუგზავნე ეს შეტყობინება აგენტებს 👇",
              f"🔗 Link for agents: {link}\n\nForward the next message to your agents 👇"), (
        "👋 KEY GROUP-ის პირადი AI ასისტენტი:\n"
        f"{link}\n\n"
        "1. გახსენი ბმული და დააჭირე Start\n"
        "2. ადმინისტრატორი დაგიდასტურებს\n"
        "3. გამოუგზავნე შენი MyHome.ge პროფილის ბმული — ასისტენტი ყოველდღე ჩაწერს შენს განცხადებებს CRM-ში")


def summary(d):
    price = d.get("price_usd") and f"{d['price_usd']} $" or (d.get("price") and f"{d['price']} {d.get('currency') or ''}") or "—"
    floor = d.get("floor") and (d["floor"] + ("/" + d["total_floors"] if d.get("total_floors") else "")) or "—"
    lines = [
        f"🏠 <b>{e(d.get('title') or 'განცხადება')}</b>",
        f"🔗 {e(d['source'].upper())} · ID {e(d.get('id'))}",
        "",
        f"გარიგება: <b>{DEAL_KA.get(d.get('deal', ''), '—')}</b> · ტიპი: <b>{TYPE_KA.get(d.get('type'), '—')}</b>",
        f"📍 {e(', '.join(x for x in (d.get('city'), d.get('district'), d.get('address')) if x) or '—')}",
        f"📐 {e(d.get('area') or '—')} მ² · 🚪 {e(d.get('rooms') or '—')} ოთახი · 🛏 {e(d.get('bedrooms') or '—')} · 🏢 {e(floor)}",
        f"💰 <b>{e(price)}</b>",
        f"📷 ფოტო: {len(d.get('images') or [])}",
        "",
        f"👤 მესაკუთრე: {e(d.get('owner') or '—')}",
        f"📞 <b>{e(d.get('phone') or '—')}</b>"
        + (" — სრული ნომერი: გახსენი განცხადება MyHome-ზე (შესული ანგარიშით)" if d.get("phone_masked") or not d.get("phone") else ""),
    ]
    if d.get("posted_by_agency"):
        lines.append("")
        lines.append("⚠️ ეს განცხადება სააგენტოს/ბროკერის დადებულია, არა მესაკუთრის.")
    miss = extract.missing_fields(d)
    if miss:
        lines.append("")
        lines.append("⚠️ ვერ ვიპოვე: " + ", ".join(miss) + ". შეავსე საიტზე დადებისას.")
    lines.append("")
    lines.append("📲 დაურეკე მესაკუთრეს და მიიღე თანხმობა.")
    return "\n".join(lines)


def fields_block(d):
    rows = [
        ("გარიგება", DEAL_KA.get(d.get("deal", ""), "")),
        ("ტიპი", TYPE_KA.get(d.get("type"), "")),
        ("ქალაქი", d.get("city")),
        ("უბანი", d.get("district")),
        ("მისამართი", d.get("address")),
        ("ოთახები", d.get("rooms")),
        ("საძინებელი", d.get("bedrooms")),
        ("სართული", d.get("floor")),
        ("სართულიანობა", d.get("total_floors")),
        ("ფართი მ²", d.get("area")),
        ("ფასი $", d.get("price_usd")),
        ("ფასი", d.get("price") if not d.get("price_usd") else ""),
    ]
    out = ["📋 <b>ველები საიტზე დასადებად</b> (დააჭირე და დაკოპირდება):", ""]
    for k, v in rows:
        if v:
            out.append(f"{k}: <code>{e(v)}</code>")
    return "\n".join(out)


def send_photos(chat, urls):
    """Send photos as an album: first by URL, then by downloading and uploading them."""
    if len(urls) == 1:
        if tg("sendPhoto", chat_id=chat, photo=urls[0]).get("ok"):
            return True
    elif tg("sendMediaGroup", chat_id=chat, media=[{"type": "photo", "media": u} for u in urls]).get("ok"):
        return True
    files, media = {}, []
    for n, u in enumerate(urls):
        try:
            r = requests.get(u, timeout=30, headers={"User-Agent": extract.UA})
            r.raise_for_status()
            ext = "webp" if u.lower().split("?")[0].endswith(".webp") else "jpg"
            files[f"p{n}"] = (f"photo{n}.{ext}", r.content)
            media.append({"type": "photo", "media": f"attach://p{n}"})
        except Exception as ex:
            print("photo download failed", u, ex)
    if not media:
        return False
    try:
        if len(media) == 1:
            r = requests.post(API + "sendPhoto", data={"chat_id": chat}, files={"photo": list(files.values())[0]}, timeout=120)
        else:
            r = requests.post(API + "sendMediaGroup", data={"chat_id": chat, "media": json.dumps(media)}, files=files, timeout=120)
        return r.json().get("ok", False)
    except Exception as ex:
        print("photo upload failed", ex)
        return False


# ---------------------------------------------------------------- CRM

def save_to_crm(d, agent, uid, consent_at, ai_used):
    if not CRM_URL:
        return False, "CRM_URL not set"
    payload = {
        "secret": CRM_SECRET, "action": "addBotListing",
        "agent": agent, "telegramId": str(uid), "consentAt": consent_at,
        "source": d.get("source"), "sourceId": d.get("id"), "url": d.get("url"),
        "deal": d.get("deal"), "type": d.get("type"), "city": d.get("city"), "district": d.get("district"),
        "address": d.get("address"), "rooms": d.get("rooms"), "bedrooms": d.get("bedrooms"),
        "floor": d.get("floor"), "totalFloors": d.get("total_floors"), "area": d.get("area"),
        "priceUsd": d.get("price_usd"), "price": d.get("price"), "currency": d.get("currency"),
        "ownerName": d.get("owner"), "ownerPhone": d.get("phone"),
        "titleKa": d.get("texts", {}).get("title_ka"), "photos": len(d.get("images") or []),
        "aiText": "yes" if ai_used else "no",
    }
    try:
        r = requests.post(CRM_URL, json=payload, timeout=60)
        ok = r.status_code == 200 and '"ok":true' in r.text.replace(" ", "")
        return ok, r.text[:200]
    except Exception as ex:
        return False, str(ex)


def crm_post(payload, timeout=90):
    if not CRM_URL:
        return False, "CRM_URL not set"
    payload = dict(payload, secret=CRM_SECRET)
    try:
        r = requests.post(CRM_URL, json=payload, timeout=timeout)
        return (r.status_code == 200 and '"ok":true' in r.text.replace(" ", "")), r.text[:200]
    except Exception as ex:
        return False, str(ex)


def crm_rows(recs, status):
    rows = []
    for r in recs:
        rows.append({k: r.get(k, "") for k in ("source", "id", "url", "title", "deal", "type", "city", "district", "address",
                                               "rooms", "bedrooms", "floor", "total_floors", "area", "price_usd", "price_gel",
                                               "description", "photos", "updated_on_site")}
                    | {"photo_links": " ".join((r.get("images") or [])[:5]), "status": status,
                       "changes": ", ".join(r.get("_changes") or [])})
    return rows


def push_to_crm(uid, name, new, updated, removed, same):
    """Send new/changed/removed listings (and a heartbeat for unchanged ones) to the Master CRM."""
    rows = crm_rows(new, "Active") + crm_rows(updated, "Active") + crm_rows(removed, "Removed")
    seen_only = [{"source": r["source"], "id": r["id"]} for r in same]
    ok_all = True
    for i in range(0, max(len(rows), 1), 80):
        ok, info = crm_post({"action": "agentSync", "agent": name, "telegramId": str(uid),
                             "rows": rows[i:i + 80], "seen": seen_only if i == 0 else []})
        ok_all = ok_all and ok
        if not ok:
            print("CRM agentSync failed:", info)
    crm_post({"action": "agentActivity", "agent": name, "telegramId": str(uid),
              "new": len(new), "updated": len(updated), "removed": len(removed), "total": len(new) + len(updated) + len(same)})
    return ok_all


# ---------------------------------------------------------------- profile sync

def profile_of(uid):
    return STATE["profiles"].setdefault(str(uid), {})


def set_profile_from_text(uid, text):
    """Returns a message for the agent."""
    found = profiles.parse_profile_input(text)
    if not found:
        return None
    kind, val = found
    prof = profile_of(uid)
    if kind == "myhome-listing":
        val = profiles.myhome_user_from_listing(val)
        kind = "myhome"
        if not val:
            return "❌ ამ განცხადებიდან პროფილი ვერ ვიპოვე. გამომიგზავნე პროფილის ბმული (myhome.ge/…?users=…)."
    if kind == "ss-listing":
        val = profiles.ss_user_from_listing(val)
        kind = "ss"
        if not val:
            return "❌ SS.ge პროფილი ვერ ვიპოვე ამ ბმულიდან."
    prof[kind] = val
    save_state()
    if kind == "myhome":
        return f"✅ MyHome.ge პროფილი შენახულია (ID {e(val)}). ახლავე ვიწყებ შენი განცხადებების ჩაწერას…"
    return ("✅ SS.ge პროფილი შენახულია. SS.ge-ზე შენს განცხადებებს ჩავწერ, როცა ბმულს გამომიგზავნი "
            "(SS.ge სრული პროფილის ავტომატური წაკითხვა ჩაირთვება API წვდომის შემდეგ).")


def sync_agent(uid, notify=True):
    """Read the agent's MyHome.ge profile, update their database and the CRM. Returns stats dict."""
    uid = str(uid)
    name = agent_name(uid) or uid
    prof = profile_of(uid)
    stats = {"name": name, "new": [], "updated": [], "removed": [], "total": 0, "error": ""}
    if not prof.get("myhome"):
        stats["error"] = "no profile"
        return stats
    try:
        recs = profiles.myhome_profile(prof["myhome"])
    except Exception as ex:
        traceback.print_exc()
        stats["error"] = f"{type(ex).__name__}: {ex}"[:200]
        if notify:
            send(uid, tr(uid, "⚠️ MyHome.ge პროფილის წაკითხვა ვერ მოხერხდა. მოგვიანებით ვცდი ხელახლა.",
                         "⚠️ Could not read your MyHome.ge profile. I will try again later."))
        return stats
    if not recs and DB.counts(uid).get(uid, {}).get("myhome", {}).get("Active", 0) > 3:
        stats["error"] = "profile returned 0 listings (skipped, possible site problem)"
        return stats
    new, upd, rem, same = DB.apply_snapshot(uid, "myhome", recs, full=getattr(recs, "complete", True))
    stats.update(new=new, updated=upd, removed=rem, total=len(recs))
    queue_site(uid, name, recs, rem)
    push_to_crm(uid, name, new, upd, rem, same)
    if notify:
        send(uid, agent_report(stats, uid))
    return stats


# ---------------------------------------------------------------- agents' own MyHome listings -> keygroup.ge
# Every daily sync queues the agent's own MyHome listings; a background thread sends them to the website one by one
# (under the agent's own profile and phone, with the listing's photos). Unchanged listings are skipped; listings the
# agent removed from MyHome are paused on the website.

SITE_LOCK = threading.Lock()


def site_import_on():
    return STATE.get("site_import", True)


def queue_site(uid, name, recs, removed=()):
    if not site_import_on() or not CRM_SECRET:
        return 0
    uid = str(uid)
    synced = STATE.setdefault("site_synced", {}).setdefault(uid, {})
    with SITE_LOCK:
        q = STATE.setdefault("site_queue", [])
        queued = {(it["uid"], it["rec"]["id"]) for it in q if it.get("rec")}
        n = 0
        for r in recs:
            if r.get("status_on_site") != "active" or synced.get(r["id"]) == r.get("hash") or (uid, r["id"]) in queued:
                continue
            q.append({"uid": uid, "name": name, "rec": r, "tries": 0})
            n += 1
        for r in removed or []:
            if r.get("id") in synced:
                q.append({"uid": uid, "name": name, "gone": r.get("url") or f"https://www.myhome.ge/pr/{r['id']}/", "id": r["id"], "tries": 0})
        save_state()
    return n


def agent_phone_of(uid, name):
    return STATE.get("phones", {}).get(str(uid)) or STATE.get("phones_by_name", {}).get(drafts.name_key(name)) or ""


def site_record_payload(uid, name, r):
    return {"url": r["url"], "deal": r.get("deal"), "type": r.get("type"), "city": r.get("city"), "district": r.get("district"),
            "address": r.get("address"), "rooms": r.get("rooms"), "bedrooms": r.get("bedrooms"), "area": r.get("area"),
            "floor": r.get("floor"), "total_floors": r.get("total_floors"),
            "price_usd": r.get("price_usd") or None, "price": r.get("price_gel") or None, "currency": "USD" if r.get("price_usd") else "GEL",
            "title": r.get("title"), "description": r.get("description"), "agent": name, "contact_phone": agent_phone_of(uid, name),
            "with_photos": True, "photos": (r.get("images") or [])[:12], "profiles": drafts.profile_links(uid),
            "own": True, "quiet": True, "tg": str(uid)}


def site_push_loop():
    """Send queued listings to keygroup.ge — one every few seconds so neither site is overloaded."""
    while True:
        try:
            busy = site_push_once()
        except Exception:
            traceback.print_exc()
            busy = False
        time.sleep(4 if busy else 20)


def site_push_once():
    item = None
    with SITE_LOCK:
        q = STATE.get("site_queue") or []
        if q:
            item = q[0]
    if not item:
        return False
    if True:
        ok_ = False
        try:
            hdr = {"X-Bot-Secret": CRM_SECRET}
            if item.get("gone"):
                ok_ = requests.post(PORTAL_URL + "/api/bot/source-gone", json={"url": item["gone"]}, headers=hdr, timeout=60).json().get("ok")
                if ok_:
                    STATE.setdefault("site_synced", {}).setdefault(item["uid"], {}).pop(item["id"], None)
            elif not agent_phone_of(item["uid"], item["name"]):
                ok_ = True     # no phone for this agent yet: skip (it would land on the company account); retried on the next sync
                STATE.setdefault("site_missing_phone", {})[item["uid"]] = item["name"]
            else:
                j = requests.post(PORTAL_URL + "/api/bot/listing", json=site_record_payload(item["uid"], item["name"], item["rec"]),
                                  headers=hdr, timeout=300).json()
                ok_ = bool(j.get("ok"))
                if ok_:
                    STATE.setdefault("site_synced", {}).setdefault(item["uid"], {})[item["rec"]["id"]] = item["rec"].get("hash")
                else:
                    print("site push", item["rec"]["id"], j.get("error"))
        except Exception as ex:
            print("site push", ex)
        with SITE_LOCK:
            q = STATE.get("site_queue") or []
            if q and q[0] is item:
                q.pop(0)
                if not ok_ and item["tries"] < 2:
                    item["tries"] += 1
                    q.append(item)
            save_state()
        return True


def site_status_text(uid=None):
    en = uid is None or lang_of(uid) == "en"
    q = STATE.get("site_queue") or []
    synced = STATE.get("site_synced", {})
    lines = ["<b>keygroup.ge ⇠ MyHome</b>" + ("" if site_import_on() else (" — OFF" if en else " — გამორთულია"))]
    for auid, name in sorted(STATE.get("agents", {}).items(), key=lambda x: x[1]):
        waiting = sum(1 for it in q if it.get("uid") == auid)
        miss = auid in STATE.get("site_missing_phone", {}) and not agent_phone_of(auid, name)
        lines.append(f"• {e(name)}: {len(synced.get(auid, {}))} " + ("on the website" if en else "საიტზე") +
                     (f" · ⏳ {waiting}" if waiting else "") + (" · ⚠️ " + ("no phone — send /contacts" if en else "ნომერი არ არის — /contacts") if miss else ""))
    return "\n".join(lines)


def fmt_price(r):
    if r.get("price_usd"):
        return f"${int(float(r['price_usd'])):,}"
    if r.get("price_gel"):
        return f"₾{int(float(r['price_gel'])):,}"
    return "—"


def agent_report(st, uid=None):
    en = uid is not None and lang_of(uid) == "en"
    if st.get("error") and st["error"] != "no profile":
        return "⚠️ " + f"<b>{e(st.get('name') or '')}</b>: " + ("could not read the MyHome profile — " if en else "MyHome პროფილის წაკითხვა ვერ მოხერხდა — ") + e(st["error"])
    who = "" if not en or str(uid) not in admins() else f" — {st['name']}"
    if en:
        lines = [f"📊 <b>Listings{e(who)} — {datetime.now(TBILISI):%d.%m %H:%M}</b>",
                 f"On MyHome.ge now: <b>{st['total']}</b>",
                 f"🆕 New: {len(st['new'])} · ✏️ Changed: {len(st['updated'])} · 🗑 Removed: {len(st['removed'])}"]
    else:
        lines = [f"📊 <b>შენი განცხადებები — {datetime.now(TBILISI):%d.%m %H:%M}</b>",
                 f"MyHome.ge-ზე ახლა: <b>{st['total']}</b>",
                 f"🆕 ახალი: {len(st['new'])} · ✏️ შეცვლილი: {len(st['updated'])} · 🗑 მოხსნილი: {len(st['removed'])}"]
    for title, items, icon in (("new", st["new"], "🆕"), ("changed", st["updated"], "✏️"), ("removed", st["removed"], "🗑")):
        for r in items[:5]:
            extra = (" — " + ", ".join(r.get("_changes", []))) if r.get("_changes") else ""
            lines.append(f"{icon} <a href=\"{e(r.get('url'))}\">{e(r.get('title') or r.get('id'))}</a> · {fmt_price(r)}{e(extra)}")
        if len(items) > 5:
            lines.append(f"   … and {len(items) - 5} more" if en else f"   … და კიდევ {len(items) - 5}")
    lines.append("💾 Everything is saved in the Master CRM." if en else "💾 ყველაფერი ჩაწერილია Master CRM-ში.")
    return "\n".join(lines)


def company_report(results, uid=None):
    en = uid is None or lang_of(uid) == "en"
    title = "🏢 KEY GROUP — agents report" if en else "🏢 KEY GROUP — აგენტების ანგარიში"
    lines = [f"<b>{title}</b>\n{datetime.now(TBILISI):%d.%m.%Y %H:%M}", ""]
    tot = {"n": 0, "u": 0, "r": 0, "t": 0}
    for st in sorted(results, key=lambda s: s["name"]):
        if st.get("error") == "no profile":
            lines.append(f"• {e(st['name'])}: ⚠️ " + ("no MyHome.ge profile yet" if en else "პროფილი არ არის მითითებული"))
            continue
        if st.get("error"):
            lines.append(f"• {e(st['name'])}: ⚠️ {e(st['error'])}")
            continue
        lines.append(f"• <b>{e(st['name'])}</b>: {st['total']} " + ("listings" if en else "განცხ.") + f" · 🆕 {len(st['new'])} · ✏️ {len(st['updated'])} · 🗑 {len(st['removed'])}")
        tot["n"] += len(st["new"]); tot["u"] += len(st["updated"]); tot["r"] += len(st["removed"]); tot["t"] += st["total"]
    lines += ["", ("Total" if en else "სულ") + f": <b>{tot['t']}</b> · 🆕 {tot['n']} · ✏️ {tot['u']} · 🗑 {tot['r']}",
              ("Details" if en else "დეტალები") + ": Master CRM → Agent Listings / Agent Activity"]
    return "\n".join(lines)


def sync_all(report_to_admin=True, notify_agents=True):
    with SYNC_LOCK:
        results = []
        for uid in list(STATE["agents"].keys()):
            results.append(sync_agent(uid, notify=notify_agents))
            time.sleep(2)
        if report_to_admin:
            send_admins(lambda a: company_report(results, a))
        return results


def scheduler():
    while True:
        try:
            now = datetime.now(TBILISI)
            today = now.strftime("%Y-%m-%d")
            if now.hour >= DAILY_SYNC_HOUR and STATE.get("last_daily") != today:
                STATE["last_daily"] = today
                save_state()
                sync_all()
        except Exception:
            traceback.print_exc()
        time.sleep(300)


def ask_admin_to_register(user):
    uid = str(user["id"])
    who = " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x) or "?"
    if user.get("username"):
        who += f" (@{user['username']})"
    rows, row = [], []
    for n in AGENT_NAMES:
        row.append({"text": n, "callback_data": f"reg|{uid}|{n}"[:64]})
        if len(row) == 3:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([{"text": "❌ არა", "callback_data": f"rej|{uid}|-"}])
    rows[-1:-1] = [[{"text": "👑 Admin / ადმინი", "callback_data": f"adm|{uid}|-"}]]
    send_admins(lambda a: tr(a, f"🙋 ახალი მომხმარებელი ითხოვს წვდომას: <b>{e(who)}</b> · ID <code>{uid}</code>\nრომელი აგენტია?",
                             f"🙋 New user asks for access: <b>{e(who)}</b> · ID <code>{uid}</code>\nWhich agent is this?"), rows)


# ---------------------------------------------------------------- handlers

PRIVATE_LINK_KA = ("⚠️ ეს შენი <b>პირადი კაბინეტის</b> ბმულია (ჩემი განცხადებები) — მას სხვა ვერ ხედავს და მისგან ვერაფერს ვკითხულობ.\n\n"
                   "👉 გახსენი <b>კონკრეტული განცხადება</b> MyHome.ge-ზე ან SS.ge-ზე და გამომიგზავნე მისი ბმული, მაგ.:\n"
                   "<code>https://www.myhome.ge/pr/23456789/</code>")
PRIVATE_PROFILE_KA = ("⚠️ ეს შენი <b>პირადი კაბინეტის</b> ბმულია — მისგან პროფილს ვერ ვიგებ.\n\n"
                      "👉 გახსენი <b>შენი ნებისმიერი განცხადება</b> MyHome.ge-ზე და გამომიგზავნე:\n<code>/profile https://www.myhome.ge/pr/23456789/</code>\n"
                      "ან საჯარო პროფილის ბმული: <code>/profile https://www.myhome.ge/udzravi-qoneba/?users=1234567</code>")


def on_message(msg):
    chat = msg["chat"]["id"]
    uid = msg["from"]["id"]
    text = (msg.get("text") or msg.get("caption") or "").strip()

    if text.startswith("/myid"):
        send(chat, tr(uid, f"შენი Telegram ID: <code>{uid}</code>\nგაუგზავნე ადმინისტრატორს.",
                      f"Your Telegram ID: <code>{uid}</code>"))
        return
    if text.startswith("/lang"):
        cur = lang_of(uid)
        STATE.setdefault("lang", {})[str(uid)] = "ka" if cur == "en" else "en"
        save_state()
        send(chat, tr(uid, "✅ ენა: ქართული. English-ისთვის: /lang", "✅ Language: English. ქართულისთვის: /lang"))
        return
    # ---- self-service password reset (anyone with a keygroup.ge account; phone verified by Telegram)
    if text.startswith("/reset") or text.startswith("/start reset") or text.startswith("/password"):
        send_kb(chat, "🔑 <b>keygroup.ge — პაროლის აღდგენა</b>\n\nდააჭირე ქვემოთ ღილაკს <b>„📱 ნომრის გაზიარება“</b>. თუ ამ ნომრით ანგარიში გაქვს, "
                      "მაშინვე გამოგიგზავნი შესვლის ბმულს და დააყენებ ახალ პაროლს.\n\n<i>Password reset: tap “Share my number” below.</i>",
                {"keyboard": [[{"text": "📱 ნომრის გაზიარება · Share my number", "request_contact": True}]], "resize_keyboard": True, "one_time_keyboard": True})
        return
    if msg.get("contact"):
        c = msg["contact"]
        if str(c.get("user_id") or "") != str(uid):
            send_kb(chat, "⚠️ გამოიყენე ღილაკი „📱 ნომრის გაზიარება“ — საკუთარი ნომრისთვის.", {"remove_keyboard": True})
            return
        if too_many_resets(uid):
            send_kb(chat, "⏳ ძალიან ბევრი მცდელობა — სცადე ერთ საათში.", {"remove_keyboard": True})
            return
        try:
            r = requests.post(PORTAL_URL + "/api/bot/reset-link", json={"phone": c.get("phone_number"), "tg": str(uid)},
                              headers={"X-Bot-Secret": CRM_SECRET}, timeout=60).json()
        except Exception as ex:
            r = {"ok": False, "error": str(ex)[:100]}
        if not r.get("ok"):
            send_kb(chat, f"⚠️ {e(r.get('error') or 'შეცდომა')}", {"remove_keyboard": True})
        elif not r.get("found"):
            send_kb(chat, "ამ ნომრით keygroup.ge-ზე ანგარიში ვერ ვიპოვე. დარეგისტრირდი: https://keygroup.ge/account/", {"remove_keyboard": True})
        elif r.get("admin") or r.get("blocked"):
            send_kb(chat, "ამ ანგარიშის პაროლი აქედან ვერ აღდგება. მოგვწერე: +995 577 114 118", {"remove_keyboard": True})
        else:
            send_kb(chat, "✅", {"remove_keyboard": True})
            send(chat, f"🔐 <b>{e(r.get('name'))}</b>, დააჭირე ღილაკს — შეხვალ შენს ანგარიშზე და დააყენებ ახალ პაროლს.\n"
                       "ბმული მუშაობს 30 წუთი, ერთხელ. არავის გაუზიარო.", [[{"text": "🔐 ახალი პაროლის დაყენება", "url": r["url"]}]])
        return
    if text.startswith("/invite") and is_admin(uid):
        a, b = invite_text(uid)
        send(chat, a)
        send(chat, b)
        return
    if text.startswith("/addagent") and is_admin(uid):
        parts = text.split(maxsplit=2)
        if len(parts) == 3:
            STATE["agents"][parts[1]] = parts[2]
            save_state()
            send(chat, tr(uid, f"✅ აგენტი დამატებულია: {e(parts[2])} ({e(parts[1])})", f"✅ Agent added: {e(parts[2])} ({e(parts[1])})"))
        else:
            send(chat, tr(uid, "ფორმატი: <code>/addagent 123456789 ნინი</code>", "Format: <code>/addagent 123456789 Nini</code>"))
        return
    if text.startswith("/addadmin") and is_admin(uid):
        parts = text.split()
        if len(parts) == 2 and parts[1].isdigit():
            if parts[1] not in STATE["admins"]:
                STATE["admins"].append(parts[1]); save_state()
            send(chat, tr(uid, f"👑 ადმინი დამატებულია: <code>{e(parts[1])}</code>", f"👑 Admin added: <code>{e(parts[1])}</code>"))
            send(parts[1], "👑 You are now an admin of KEY GROUP Assistant.\n\n" + help_for(parts[1]))
        else:
            send(chat, tr(uid, "ფორმატი: <code>/addadmin 123456789</code>", "Format: <code>/addadmin 123456789</code>"))
        return
    if text.startswith("/agents") and is_admin(uid):
        cnt = DB.counts()
        lst = []
        for i, n in STATE["agents"].items():
            p = STATE["profiles"].get(i, {})
            act = cnt.get(i, {}).get("myhome", {}).get("Active", 0)
            lst.append(f"• {e(n)} — <code>{e(i)}</code> · MyHome: {'✅ ' + str(act) if p.get('myhome') else '❌'} · SS.ge: {'✅' if p.get('ss') else '❌'}")
        send(chat, tr(uid, "აგენტები:\n", "Agents:\n") + ("\n".join(lst) or tr(uid, "ჯერ არავინ — გაგზავნე /invite", "No agents yet — send /invite")))
        return
    if text.startswith("/setprofile") and is_admin(uid) and len([l for l in text.splitlines() if l.strip().startswith("/setprofile")]) > 1:
        # several agents in one message: one "/setprofile <TelegramID> <link>" per line
        done, todo = [], []
        for line in text.splitlines():
            parts = line.strip().split(maxsplit=2)
            if len(parts) != 3 or parts[0] != "/setprofile":
                continue
            if parts[1] not in STATE["agents"]:
                done.append(f"❌ {e(parts[1])}: " + tr(uid, "ასეთი აგენტი არ არის", "no such agent"))
                continue
            try:
                msg_ = set_profile_from_text(parts[1], parts[2])
            except Exception as ex:
                msg_ = f"❌ {e(type(ex).__name__)}"
            done.append(f"<b>{e(agent_name(parts[1]) or parts[1])}</b>: " + (msg_ or tr(uid, "ბმული ვერ ვიცანი", "link not recognised")).split("\n")[0])
            if msg_ and msg_.startswith("✅ MyHome"):
                todo.append(parts[1])
        send(chat, "\n".join(done) or tr(uid, "ვერაფერი ვიცანი.", "Nothing recognised."))

        def _run(ids=todo):
            for a in ids:
                send(chat, agent_report(sync_agent(a, notify=False), uid))
                time.sleep(2)
            send(chat, site_status_text(uid))
        if todo:
            threading.Thread(target=_run, daemon=True).start()
        return
    if text.startswith("/setprofile") and is_admin(uid):
        parts = text.split(maxsplit=2)
        if len(parts) == 3 and parts[1] in STATE["agents"]:
            msg_ = set_profile_from_text(parts[1], parts[2])
            send(chat, msg_ or tr(uid, "ბმული ვერ ვიცანი.", "I could not recognise that link."))
            if msg_ and msg_.startswith("✅ MyHome"):
                threading.Thread(target=lambda: send(chat, agent_report(sync_agent(parts[1], notify=False), uid)), daemon=True).start()
        else:
            send(chat, tr(uid, "ფორმატი", "Format") + ": <code>/setprofile 123456789 https://www.myhome.ge/udzravi-qoneba/?users=9925395</code>")
        return
    if text.startswith("/website") and is_admin(uid):
        arg = (text.split() + [""])[1].lower()
        if arg in ("on", "off"):
            STATE["site_import"] = arg == "on"; save_state()
        if arg == "now":
            STATE["site_synced"] = {}; save_state()     # send everything again (existing listings are updated; photos fetched where missing)
            send(chat, tr(uid, "⏳ ყველა აგენტის განცხადებები იგზავნება keygroup.ge-ზე…", "⏳ Sending every agent's MyHome listings to keygroup.ge…"))
            threading.Thread(target=sync_all, kwargs={"notify_agents": False}, daemon=True).start()
        send(chat, site_status_text(uid) + "\n\n<code>/website on</code> · <code>/website off</code> · <code>/website now</code>")
        return
    if text.startswith("/syncall") and is_admin(uid):
        send(chat, tr(uid, "⏳ ყველა აგენტის განახლება დაიწყო…", "⏳ Updating all agents… the report will follow."))
        threading.Thread(target=sync_all, kwargs={"notify_agents": False}, daemon=True).start()
        return
    if text.startswith("/team") and is_admin(uid):
        since = time.time() - 86400
        act = DB.activity_since(since)
        cnt = DB.counts()
        lines = [tr(uid, "🏢 <b>KEY GROUP — ბოლო 24 საათი</b>", "🏢 <b>KEY GROUP — last 24 hours</b>"), ""]
        for i, n in sorted(STATE["agents"].items(), key=lambda x: x[1]):
            a = act.get(i, {})
            c = cnt.get(i, {}).get("myhome", {}).get("Active", 0)
            lines.append(f"• <b>{e(n)}</b>: {c} " + tr(uid, "აქტიური", "active") + f" · 🆕 {a.get('new', 0)} · ✏️ {a.get('updated', 0)} · 🗑 {a.get('removed', 0)}")
        if len(lines) == 2:
            lines.append(tr(uid, "ჯერ აგენტები არ არიან — გაგზავნე /invite", "No agents yet — send /invite"))
        send(chat, "\n".join(lines))
        return

    if is_admin(uid) and not text.startswith("/"):
        rep = drafts.import_contacts(text)
        if rep and len(drafts.CONTACT_LINE.findall(text)) >= 1 and "myhome.ge" not in text and "ss.ge" not in text:
            send(chat, rep)
            return
    if text.startswith("/contacts") and is_admin(uid):
        pbn, em = STATE.get("phones_by_name", {}), STATE.get("emails", {})
        rows = [f"• {e(i)} ({e(n)}): {e(STATE['phones'].get(i) or pbn.get(drafts.name_key(n)) or '—')} · {e(em.get(drafts.name_key(n)) or '—')}" for i, n in STATE["agents"].items()]
        send(chat, "📇 <b>Agent contacts</b>\n" + ("\n".join(rows) or "—") + "\n\nTo update: paste lines like <code>577 15 11 41 ნინი n.x@gmail.com</code>")
        return
    name = agent_name(uid)
    if not name:
        if admins() and not is_admin(uid):
            ask_admin_to_register(msg["from"])
        send(chat, "👋 ეს KEY GROUP-ის აგენტების ასისტენტია. მოთხოვნა გაეგზავნა ადმინისტრატორს — დადასტურების შემდეგ მოგწერ.")
        return
    if msg.get("photo") or (msg.get("document") and str(msg["document"].get("mime_type", "")).startswith("image/")):
        drafts.add_photo(msg, uid)
        return
    if (not text.startswith("/") or text.startswith("/cancel")) and drafts.apply_edit(chat, uid, text):
        return
    if text.startswith("/phone"):
        ph = re.sub(r"[^\d+]", "", text[len("/phone"):])
        if len(re.sub(r"\D", "", ph)) >= 9:
            if not ph.startswith("+"):
                ph = "+995" + ph[-9:]
            STATE["phones"][str(uid)] = ph
            save_state()
            send(chat, f"✅ შენი საკონტაქტო ნომერი: <b>{e(ph)}</b> — ეს გამოჩნდება შენს განცხადებებში.")
        else:
            send(chat, f"შენი ნომერი: <b>{e(STATE['phones'].get(str(uid)) or '—')}</b>\nშესაცვლელად: <code>/phone 599123456</code>")
        return
    if text.startswith("/login") or text.startswith("/account"):
        ph = STATE["phones"].get(str(uid)) or STATE.get("phones_by_name", {}).get(drafts.name_key(name))
        if not ph:
            send(chat, "ჯერ დაამატე შენი ნომერი: <code>/phone 5XXXXXXXX</code> — შემდეგ ისევ /login")
            return
        try:
            r = requests.post(PORTAL_URL + "/api/bot/agent-access", json={"agent": name, "phone": ph, "profiles": drafts.profile_links(uid), "tg": str(uid)},
                              headers={"X-Bot-Secret": CRM_SECRET}, timeout=60).json()
        except Exception as ex:
            r = {"ok": False, "error": str(ex)[:120]}
        if not r.get("ok"):
            send(chat, f"⚠️ ანგარიში ვერ მოვამზადე: {e(r.get('error'))}")
            return
        send(chat, "🔐 <b>შენი keygroup.ge ანგარიში</b>\n\n"
                   f"📱 ნომერი: <b>{e(r.get('phone'))}</b>\n🏠 განცხადებები: <b>{r.get('listings', 0)}</b>\n"
                   + (f"👤 საჯარო პროფილი: {e(r.get('profile'))}\n" if r.get("profile") else "")
                   + "\nდააჭირე ღილაკს — შეხვალ პირდაპირ (ბმული მუშაობს 15 წუთი, ერთხელ). "
                   + ("პირველ შესვლაზე დააყენე პაროლი — შემდეგ შეხვალ ნომრით და პაროლით keygroup.ge/account-ზე." if not r.get("pw_set")
                      else "პაროლი უკვე გაქვს — შეგიძლია შეხვიდე ნომრით და პაროლით keygroup.ge/account-ზეც.")
                   + "\n\n⚠️ ეს ბმული არავის გაუზიარო.",
             [[{"text": "🔐 შესვლა keygroup.ge-ზე", "url": r["url"]}]])
        return
    if text.startswith("/new"):
        dr = drafts.new_draft(uid, name)
        send(chat, f"🆕 ახალი განცხადება #{e(dr['id'])}\n\n1️⃣ გამომიგზავნე ორიგინალი ფოტოები (უმჯობესია „ფაილად“ — სრული ხარისხი).\n"
                   "2️⃣ დააჭირე „👁 გადახედვა“ და შეავსე ველები ✏️ ღილაკებით.\n3️⃣ დაამტკიცე — გამოქვეყნდება.",
             [[{"text": "👁 გადახედვა", "callback_data": "pv|" + dr["id"]}]])
        return
    if text.startswith("/draft"):
        dr = drafts.current(uid)
        if dr:
            drafts.preview(chat, dr)
        else:
            send(chat, "აქტიური დრაფტი არ გაქვს. გამომიგზავნე ბმული ან /new")
        return
    if text.startswith("/cancel"):
        send(chat, "OK.")
        return
    if text.startswith("/start") or text.startswith("/help"):
        send(chat, help_for(uid))
        if is_admin(uid) and str(uid) not in STATE["agents"]:
            return
        if not profile_of(uid).get("myhome"):
            send(chat, "👉 დავიწყოთ: გამომიგზავნე შენი <b>MyHome.ge პროფილის ბმული</b> ან შენი ნებისმიერი განცხადების ბმული ბრძანებით:\n<code>/profile ბმული</code>")
        return
    if text.startswith("/profile"):
        arg = text[len("/profile"):].strip()
        if not arg:
            p = profile_of(uid)
            send(chat, f"MyHome.ge: {'ID ' + e(p['myhome']) if p.get('myhome') else '❌'}\nSS.ge: {'✅' if p.get('ss') else '❌'}\n\n"
                       "შესაცვლელად: <code>/profile ბმული</code> (პროფილის ან შენი განცხადების ბმული)")
            return
        if arg in ("ბმული", "link") or extract.is_private_link(arg):
            send(chat, PRIVATE_PROFILE_KA)
            return
        send(chat, "⏳ ვამოწმებ…")
        try:
            msg_ = set_profile_from_text(uid, arg)
        except Exception as ex:
            msg_ = f"❌ ვერ გავხსენი ბმული ({e(type(ex).__name__)})."
        send(chat, msg_ or "ბმული ვერ ვიცანი. გამომიგზავნე myhome.ge პროფილის ან განცხადების ბმული.")
        if msg_ and msg_.startswith("✅ MyHome"):
            threading.Thread(target=sync_agent, args=(uid,), daemon=True).start()
        return
    if text.startswith("/sync"):
        if not profile_of(uid).get("myhome"):
            send(chat, "ჯერ მიუთითე პროფილი: <code>/profile ბმული</code>")
            return
        send(chat, "⏳ ვკითხულობ შენს MyHome.ge პროფილს…")
        threading.Thread(target=sync_agent, args=(uid,), daemon=True).start()
        return
    if text.startswith("/my"):
        cnt = DB.counts(str(uid)).get(str(uid), {})
        act = DB.activity_since(time.time() - 7 * 86400, str(uid)).get(str(uid), {})
        lines = [f"📁 <b>შენი ბაზა</b>",
                 f"MyHome.ge: {cnt.get('myhome', {}).get('Active', 0)} აქტიური · SS.ge: {cnt.get('ss', {}).get('Active', 0)}",
                 f"ბოლო 7 დღე: 🆕 {act.get('new', 0)} · ✏️ {act.get('updated', 0)} · 🗑 {act.get('removed', 0)}", ""]
        for r in DB.active(str(uid), 5):
            lines.append(f"• <a href=\"{e(r.get('url'))}\">{e(r.get('title') or r.get('id'))}</a> · {fmt_price(r)}")
        send(chat, "\n".join(lines))
        return
    # a profile link sent without the /profile command
    if re.search(r"[?&]users=\d+|userlist\?userId=", text):
        msg_ = set_profile_from_text(uid, text)
        if msg_:
            send(chat, msg_)
            if msg_.startswith("✅ MyHome"):
                threading.Thread(target=sync_agent, args=(uid,), daemon=True).start()
            return

    url = extract.find_url(text)
    if not url:
        send(chat, "გამომიგზავნე myhome.ge ან ss.ge განცხადების ბმული. /help")
        return

    if extract.is_private_link(url) or not extract.listing_id(url):
        send(chat, PRIVATE_LINK_KA)
        return
    send(chat, "⏳ ვამუშავებ განცხადებას…")
    try:
        d = extract.extract(url)
    except Exception as ex:
        traceback.print_exc()
        code = getattr(ex, "status", "") or type(ex).__name__
        d = extract.from_slug(url)
        site = "SS.ge" if d["source"] == "ss" else "MyHome.ge"
        send(chat, f"⚠️ {site}-მა სერვერს გვერდი არ მისცა ({e(code)}) — სრულ ინფორმაციას ვერ ვკითხულობ.\n"
                   f"ბმულიდან ამოვიღე: {e(B_DEAL.get(d['deal'], '—'))} · {e(d['rooms'] or '—')} ოთახი · {e(TYPE_KA.get(d['type'], '—'))} · {e(d['district'] or '—')}.\n\n"
                   "შეგიძლია მაინც გააგრძელო: დაურეკე მესაკუთრეს, დააჭირე „✅ თანახმაა“, მერე ფასი, ფართი და მისამართი შეავსე ✏️ ღილაკებით.")
        if not d["id"]:
            return
        key = f"{chat}-{int(time.time())}"
        STATE["pending"][key] = {"data": d, "uid": uid, "agent": name, "created": time.time()}
        save_state()
        send(chat, f"🔗 {e(url)}", [[{"text": "✅ მესაკუთრე თანახმაა", "callback_data": "ok|" + key}],
                                    [{"text": "❌ გაუქმება", "callback_data": "no|" + key}]])
        return
    prof = profile_of(uid)
    own = False
    if d.get("source") == "myhome" and prof.get("myhome"):
        own = str(d.get("user_id") or "") == str(prof["myhome"])
    if d.get("source") == "ss" and prof.get("ss"):
        own = str(d.get("user_uuid") or "").lower() == prof["ss"]
    if own:
        rec = profiles.from_single_listing(d)
        new, upd, rem, same = DB.apply_snapshot(str(uid), d["source"], [rec], full=False)
        push_to_crm(uid, name, new, upd, rem, same)
        state_txt = "🆕 დაემატა" if new else ("✏️ განახლდა" if upd else "✔️ უკვე ბაზაშია, ცვლილება არ არის")
        send(chat, f"📌 ეს <b>შენი</b> განცხადებაა ({d['source']}). {state_txt} შენს ბაზაში და CRM-ში.")
        return
    if not (d.get("price") or d.get("price_usd")) and not d.get("area"):
        send(chat, "❌ ამ ბმულზე განცხადების მონაცემები ვერ ვიპოვე (ფასი, ფართი). შეამოწმე, რომ ეს <b>კონკრეტული განცხადების</b> ბმულია და ის ჯერ აქტიურია.\n" + e(url))
        return
    if d.get("refuses_agencies"):
        send(chat, f"🚫 <b>{e(d.get('title') or 'განცხადება')}</b>\n\nმესაკუთრე განცხადებაში წერს, რომ <b>სააგენტოებთან არ თანამშრომლობს</b>. "
                   "ამიტომ ამ განცხადებას არ ვამუშავებ — გთხოვ, არ დაურეკო. აირჩიე სხვა განცხადება.")
        return
    key = f"{chat}-{int(time.time())}"
    STATE["pending"][key] = {"data": d, "uid": uid, "agent": name, "created": time.time()}
    # keep only the 200 newest pending items
    if len(STATE["pending"]) > 200:
        for k in sorted(STATE["pending"], key=lambda k: STATE["pending"][k]["created"])[:-200]:
            STATE["pending"].pop(k, None)
    save_state()
    send(chat, summary(d), [[{"text": "✅ მესაკუთრე თანახმაა", "callback_data": "ok|" + key}],
                           [{"text": "❌ გაუქმება", "callback_data": "no|" + key}]])


def on_callback(cb):
    tg("answerCallbackQuery", callback_query_id=cb["id"])
    action, _, key = (cb.get("data") or "").partition("|")
    chat = cb["message"]["chat"]["id"]
    if action in ("reg", "rej", "adm"):
        if not is_admin(cb["from"]["id"]):
            return
        new_uid, _, agent = key.partition("|")
        tg("editMessageReplyMarkup", chat_id=chat, message_id=cb["message"]["message_id"], reply_markup={"inline_keyboard": []})
        if action == "rej":
            send(chat, tr(chat, f"უარყოფილია: <code>{e(new_uid)}</code>", f"Declined: <code>{e(new_uid)}</code>"))
            return
        if action == "adm":
            if new_uid not in STATE["admins"]:
                STATE["admins"].append(new_uid)
                save_state()
            send(chat, tr(chat, f"👑 ადმინი დამატებულია: <code>{e(new_uid)}</code>", f"👑 Admin added: <code>{e(new_uid)}</code>"))
            send(new_uid, "👑 You are now an admin of KEY GROUP Assistant. Reports will come here too.\n\n" + help_for(new_uid))
            return
        STATE["agents"][new_uid] = agent
        save_state()
        send(chat, tr(chat, f"✅ {e(agent)} დამატებულია (ID <code>{e(new_uid)}</code>).", f"✅ {e(agent)} added (ID <code>{e(new_uid)}</code>). They will get their own private assistant."))
        send(new_uid, f"✅ გამარჯობა {e(agent)}! შენი პირადი ასისტენტი მზადაა.\n\n" + help_for(new_uid))
        send(new_uid, "👉 გამომიგზავნე შენი <b>MyHome.ge პროფილის ბმული</b> ან შენი ნებისმიერი განცხადების ბმული:\n<code>/profile ბმული</code>")
        return
    if action in ("pv", "ed", "uo", "ap", "dc"):
        uid = cb["from"]["id"]
        did, _, field = key.partition("|")
        dr = STATE.get("drafts", {}).get(did)
        if not dr or (str(uid) != dr["uid"] and not is_admin(uid)):
            send(chat, "ეს დრაფტი ვერ ვიპოვე.")
            return
        if action == "pv":
            drafts.preview(chat, dr)
        elif action == "ed":
            drafts.ask_edit(chat, uid, did, field)
        elif action == "uo":
            dr["desc_ka"] = dr.get("source_desc") or dr["desc_ka"]
            if "desc_ka" not in dr["edited"]:
                dr["edited"].append("desc_ka")
            save_state()
            drafts.preview(chat, dr, with_photos=False)
        elif action == "ap":
            tg("editMessageReplyMarkup", chat_id=chat, message_id=cb["message"]["message_id"], reply_markup={"inline_keyboard": []})
            drafts.publish(chat, uid, did)
        elif action == "dc":
            tg("editMessageReplyMarkup", chat_id=chat, message_id=cb["message"]["message_id"], reply_markup={"inline_keyboard": []})
            drafts.discard(chat, uid, did)
        return
    item = STATE["pending"].get(key)
    if not item:
        send(chat, "ეს განცხადება ვადაგასულია. გამომიგზავნე ბმული თავიდან.")
        return
    if str(cb["from"]["id"]) != str(item["uid"]) and not is_admin(cb["from"]["id"]):
        return
    tg("editMessageReplyMarkup", chat_id=chat, message_id=cb["message"]["message_id"], reply_markup={"inline_keyboard": []})
    if action not in ("ok", "no"):
        return
    if action == "no":
        STATE["pending"].pop(key, None)
        save_state()
        send(chat, "გაუქმებულია.")
        return

    d = item["data"]
    consent_at = datetime.now(TBILISI).strftime("%Y-%m-%d %H:%M")
    STATE["pending"].pop(key, None)
    dr = drafts.new_draft(item["uid"], item["agent"], d, consent_at)
    send(chat, f"✅ თანხმობა ჩაწერილია: {consent_at}. ვაქვეყნებ keygroup.ge-ზე…")
    j, agency = drafts.quick_publish(chat, dr, d)
    ok_crm, info = save_to_crm(d, item["agent"], item["uid"], consent_at, False)
    txt, link = drafts.owner_photo_request(d)
    if j.get("ok"):
        msg = (f"🌐 <b>გამოქვეყნდა keygroup.ge-ზე</b> ({j.get('photos', 0)} ფოტო):\n{e(j.get('url'))}\n"
               + (f"👤 შენი პროფილი: {e(j.get('profile'))}\n" if j.get("profile") else
                  "⚠️ შენი ნომერი არ მაქვს — განცხადება KEY GROUP-ის ნომრითაა. დაამატე: <code>/phone 5XXXXXXXX</code>\n")
               + ("⚠️ ეს განცხადება სააგენტოსია — მისი ფოტოები არ გამოვიყენე.\n" if agency else "")
               + ("💾 ჩაწერილია Master CRM-ში.\n" if ok_crm else "⚠️ CRM-ში ჩაწერა ვერ მოხერხდა.\n")
               + "\n✏️ შეცვლა ან მესაკუთრის ორიგინალი ფოტოების დამატება: გადმომიგზავნე ფოტოები და დააჭირე „👁 გადახედვა“ → „✅ დამტკიცება“ — "
               "იგივე განცხადება განახლდება.\n\n"
               f"WhatsApp ტექსტი მესაკუთრისთვის (ორიგინალი ფოტოები):\n<code>{e(txt)}</code>")
    else:
        msg = (f"⚠️ საიტზე გამოქვეყნება ვერ მოხერხდა ({e(j.get('error'))}). შეავსე ✏️ ღილაკებით (ფასი, უბანი) და დააჭირე „✅ დამტკიცება“.\n"
               f"შეიქმნა დრაფტი #{e(dr['id'])}.")
        send_admins(f"⚠️ Website publish error for {e(item['agent'])}: {e(j.get('error'))}")
    send(chat, msg, ([[{"text": "💬 WhatsApp მესაკუთრეს", "url": link}]] if link else []) + [[{"text": "👁 გადახედვა / შეცვლა", "callback_data": "pv|" + dr["id"]}]])
    if j.get("ok"):
        send_admins(lambda a: tr(a, f"🌐 {e(item['agent'])}-მა დაამატა განცხადება keygroup.ge-ზე:\n{e(j.get('url'))}", f"🌐 {e(item['agent'])} listed on keygroup.ge:\n{e(j.get('url'))}"))


# ---------------------------------------------------------------- main loop

def main():
    print("KEY GROUP Assistant started")
    global BOT_USERNAME
    tg("deleteWebhook")
    BOT_USERNAME = (tg("getMe").get("result") or {}).get("username", "")
    tg("setMyCommands", commands=[{"command": "start", "description": "როგორ მუშაობს"},
                                  {"command": "profile", "description": "ჩემი MyHome.ge / SS.ge პროფილი"},
                                  {"command": "sync", "description": "ჩემი განცხადებების განახლება"},
                                  {"command": "my", "description": "ჩემი ბაზა"},
                                  {"command": "new", "description": "ახალი განცხადება ფოტოებით"},
                                  {"command": "draft", "description": "ჩემი დრაფტის გადახედვა"},
                                  {"command": "phone", "description": "ჩემი საკონტაქტო ნომერი"},
                                  {"command": "login", "description": "შესვლა ჩემს keygroup.ge ანგარიშზე"},
                                  {"command": "reset", "description": "პაროლის აღდგენა (keygroup.ge)"},
                                  {"command": "myid", "description": "ჩემი Telegram ID"}])
    for adm in admins():
        tg("setMyCommands", scope={"type": "chat", "chat_id": int(adm)}, commands=[
            {"command": "start", "description": "Help"},
            {"command": "invite", "description": "Link to send to agents"},
            {"command": "team", "description": "Company report (24 h)"},
            {"command": "agents", "description": "Agents and their profiles"},
            {"command": "syncall", "description": "Update all agents now"},
            {"command": "addadmin", "description": "Add another admin"},
            {"command": "contacts", "description": "Agents' phones and emails"},
            {"command": "lang", "description": "English / ქართული"}])
    threading.Thread(target=scheduler, daemon=True).start()
    threading.Thread(target=outbox_loop, daemon=True).start()
    threading.Thread(target=site_push_loop, daemon=True).start()
    while True:
        try:
            r = requests.get(API + "getUpdates", params={"offset": STATE.get("offset", 0), "timeout": 50}, timeout=70)
            for upd in r.json().get("result", []):
                STATE["offset"] = upd["update_id"] + 1
                try:
                    if "message" in upd:
                        on_message(upd["message"])
                    elif "callback_query" in upd:
                        on_callback(upd["callback_query"])
                except Exception:
                    traceback.print_exc()
                save_state()
        except Exception:
            traceback.print_exc()
            time.sleep(5)


drafts.init(sys.modules[__name__])

if __name__ == "__main__":
    main()
