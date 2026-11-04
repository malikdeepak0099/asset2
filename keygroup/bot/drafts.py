"""Listing drafts: agent sends a link (or /new) + original photos -> bot prepares the listing ->
agent previews and edits -> one approval publishes it (keygroup.ge + CRM + MyHome/SS posting kit).

Photos are kept exactly as the agent sent them: no logo / watermark removal, no edits.
Nothing is published without the agent's explicit "Approve and publish" tap.
"""
import html
import json
import os
import re
import shutil
import time
import uuid

import requests

B = None   # the bot module, set by init()

FIELDS = {   # field -> (Georgian label, kind)
    "title": ("სათაური", "text"), "desc_ka": ("აღწერა (ქართ.)", "text"), "desc_en": ("აღწერა (ინგ.)", "text"),
    "price": ("ფასი (მაგ. 150000 USD)", "price"), "deal": ("გარიგება (იყიდება / ქირავდება / დღიური)", "deal"),
    "type": ("ტიპი (ბინა / სახლი / კომერციული / მიწა / სასტუმრო)", "ptype"),
    "city": ("ქალაქი", "text"), "district": ("უბანი", "text"), "address": ("მისამართი", "text"),
    "area": ("ფართი მ²", "num"), "rooms": ("ოთახები", "num"), "bedrooms": ("საძინებელი", "num"),
    "floor": ("სართული (მაგ. 5/12)", "floor"), "features": ("მახასიათებლები (მძიმით)", "list"),
}
DEAL_IN = {"sale": "sale", "იყიდება": "sale", "ყიდვა": "sale", "rent": "rent", "ქირავდება": "rent", "ქირა": "rent",
           "daily": "daily", "დღიური": "daily"}
TYPE_IN = {"flat": "flat", "ბინა": "flat", "house": "house", "სახლი": "house", "კერძო სახლი": "house", "commercial": "commercial",
           "კომერციული": "commercial", "land": "land", "მიწა": "land", "hotel": "hotel", "სასტუმრო": "hotel"}
PHONE_RE = re.compile(r"(\+?995[\s\-]?)?(\(?5\d{2}\)?[\s\-]?\d{2}[\s\-]?\d{2}[\s\-]?\d{2}|\b\d{3}[\s\-]?\d{2}[\s\-]?\d{2}[\s\-]?\d{2}\b)")
MAX_PHOTOS = 25
LAST_GROUP = {}


def init(bot_module):
    global B
    B = bot_module
    B.STATE.setdefault("drafts", {})
    B.STATE.setdefault("draft_of", {})
    B.STATE.setdefault("await", {})
    B.STATE.setdefault("phones", {})


def e(s):
    return html.escape(str(s or ""))


def ddir(did):
    return os.path.join(B.DATA_DIR, "drafts", did)


def strip_phones(text):
    return PHONE_RE.sub("", str(text or "")).strip()


# ---------------------------------------------------------------- create / open

def new_draft(uid, agent, d=None, consent_at=""):
    d = d or {}
    did = uuid.uuid4().hex[:10]
    price, cur = (d.get("price_usd"), "USD") if d.get("price_usd") else (d.get("price"), "GEL" if d.get("price") else "USD")
    dr = {
        "id": did, "uid": str(uid), "agent": agent, "created": time.time(), "status": "draft", "consent_at": consent_at,
        "source": {k: d.get(k) for k in ("source", "url", "id", "owner", "phone", "posted_at")} if d else {},
        "source_desc": strip_phones(d.get("description"))[:4000],
        "deal": d.get("deal") or "sale", "type": d.get("type") or "flat", "city": d.get("city") or "", "district": d.get("district") or "",
        "address": d.get("address") or "", "area": d.get("area") or "", "rooms": d.get("rooms") or "", "bedrooms": d.get("bedrooms") or "",
        "floor": d.get("floor") or "", "total_floors": d.get("total_floors") or "", "price": price or "", "currency": cur,
        "features": d.get("features") or [], "details": d.get("details") or [], "lat": d.get("lat") or 0, "lon": d.get("lon") or 0,
        "video_url": d.get("video_url") or "", "title": "", "desc_ka": "", "desc_en": "", "desc_ru": "", "edited": [], "photos": [],
    }
    B.STATE["drafts"][did] = dr
    B.STATE["draft_of"][str(uid)] = did
    prune()
    B.save_state()
    return dr


def current(uid):
    did = B.STATE["draft_of"].get(str(uid))
    dr = B.STATE["drafts"].get(did or "")
    return dr if dr and dr["status"] == "draft" else None


def prune():
    """Keep drafts for 30 days (photos on disk included)."""
    cut = time.time() - 30 * 86400
    for did, dr in list(B.STATE["drafts"].items()):
        if dr.get("created", 0) < cut:
            shutil.rmtree(ddir(did), ignore_errors=True)
            B.STATE["drafts"].pop(did, None)


NAME_ALIAS = {"dato": "davit", "daviti": "davit", "demetre": "deme", "demeti": "deme", "demetri": "deme", "giorgi": "giorgi",
              "gio": "giorgi", "nini": "nini", "nika": "nika", "ana": "ana", "anna": "ana"}


def name_key(name):
    """'დავითი' / 'Dato' / 'Davit' -> 'davit' so the admin's list matches the agents' Telegram names."""
    n = B.texts.translit(str(name or "").strip().split(" ")[0], "en").lower()
    n = re.sub(r"[^a-z]", "", n)
    return NAME_ALIAS.get(n, n)


def agent_phone(dr):
    """The agent's own number if we know it (never the company number for the agent profile)."""
    return B.STATE["phones"].get(dr["uid"]) or B.STATE.setdefault("phones_by_name", {}).get(name_key(dr["agent"])) or ""


def profile_links(uid):
    p = B.STATE.get("profiles", {}).get(str(uid), {})
    out = {}
    if p.get("myhome"):
        out["myhome"] = f"https://www.myhome.ge/udzravi-qoneba/?users={p['myhome']}"
    if p.get("ss"):
        out["ss"] = f"https://home.ss.ge/ka/udzravi-qoneba/userlist?userId={p['ss']}"
    return out


def site_payload(dr):
    name, phone = contact(dr)
    return {"url": (dr["source"] or {}).get("url") or f"draft:{dr['id']}", "deal": dr["deal"], "type": dr["type"], "city": dr["city"],
            "district": dr["district"], "address": dr["address"], "rooms": dr["rooms"], "bedrooms": dr["bedrooms"], "area": dr["area"],
            "floor": dr["floor"], "total_floors": dr["total_floors"], "price": dr["price"], "currency": dr["currency"],
            "title": dr.get("title_en") or dr["title"],
            "description": "\n\n".join(x for x in (dr["desc_en"], dr["desc_ka"]) if x)
                           + ("\n\n" + "\n".join(f"• {k}: {v}" for k, v in dr.get("details") or []) if dr.get("details") else ""),
            "agent": name, "contact_phone": agent_phone(dr), "video_url": dr.get("video_url"), "lat": dr.get("lat"), "lon": dr.get("lon"),
            "profiles": profile_links(dr["uid"]), "tg": dr["uid"],
            # the property owner — private on keygroup.ge: only this agent and the office see it (the agent's CRM search)
            "owner_name": (dr["source"] or {}).get("owner") or "", "owner_phone": (dr["source"] or {}).get("phone") or ""}


def is_own_listing(uid, d):
    """True when the link is the agent's own listing (same MyHome user id / SS user as the agent's saved profile)."""
    p = B.STATE.get("profiles", {}).get(str(uid), {})
    if d.get("user_id") and p.get("myhome") and str(d["user_id"]) == str(p["myhome"]):
        return True
    return bool(d.get("user_uuid") and p.get("ss") and str(d["user_uuid"]).lower() == str(p["ss"]).lower())


def quick_publish(chat, dr, d):
    """Owner agreed -> the listing goes live on keygroup.ge at once with the listing's own photos (as they are, nothing removed)
    and the agent's contact. The draft stays open: edits or original photos later update the same listing."""
    compose(dr)
    payload = site_payload(dr)
    own = is_own_listing(dr["uid"], d)
    agency = bool(d.get("posted_by_agency")) and not own     # the agent's own listing: its photos are theirs to use
    payload.update(with_photos=not agency, photos=(d.get("images") or [])[:15], own=own)
    if own:   # the agent's own ad: the "owner" shown there is the agent
        payload.update(owner_name="", owner_phone="")
    try:
        r = requests.post(B.PORTAL_URL + "/api/bot/listing", json=payload, headers={"X-Bot-Secret": B.CRM_SECRET}, timeout=240)
        j = r.json()
    except Exception as ex:
        j = {"ok": False, "error": str(ex)[:120]}
    if j.get("ok"):
        dr["site_url"] = j.get("url")
        B.save_state()
    return j, agency


def contact(dr):
    phone = B.STATE["phones"].get(dr["uid"]) or B.STATE.setdefault("phones_by_name", {}).get(name_key(dr["agent"])) or B.COMPANY_PHONE
    return dr["agent"], phone


CONTACT_LINE = re.compile(r"((?:\+?995[\s-]?)?5\d{2}(?:[\s-]?\d){6})\s+([^\s\d@]+)(?:\s+([\w.+-]+@[\w-]+\.[\w.]+))?")


def import_contacts(text):
    """Admin pastes lines like '577 15 11 41 ნინი n.x@gmail.com'. Returns a report, or None if the text is not such a list."""
    rows = CONTACT_LINE.findall(text or "")
    if not rows:
        return None
    by_key = {}
    for tid, nm in B.STATE["agents"].items():
        by_key.setdefault(name_key(nm), []).append(tid)
    pbn, emails = B.STATE.setdefault("phones_by_name", {}), B.STATE.setdefault("emails", {})
    out = []
    for ph, nm, mail in rows:
        digits = re.sub(r"\D", "", ph)[-9:]
        phone, key = "+995" + digits, name_key(nm)
        pbn[key] = phone
        if mail:
            emails[key] = mail
        ids = by_key.get(key, [])
        for tid in ids:
            B.STATE["phones"][tid] = phone
        out.append(f"{'✅' if ids else '🕓'} {e(nm)} — {e(phone)}" + (f" · {e(mail)}" if mail else "")
                   + ("" if ids else " (Telegram-ში ჯერ არ არის — დაემატება, როცა შემოვა)"))
    B.save_state()
    return "📇 <b>აგენტების კონტაქტები შენახულია</b>\n" + "\n".join(out) + "\n\nეს ნომრები გამოჩნდება მათ განცხადებებში მესაკუთრის ნომრის ნაცვლად."


def compose(dr):
    """(Re)write the texts unless the agent edited them. Contact = the agent's phone, never the owner's."""
    name, phone = contact(dr)
    d = {"deal": dr["deal"], "type": dr["type"], "city": dr["city"], "district": dr["district"], "address": dr["address"],
         "area": dr["area"], "rooms": dr["rooms"], "bedrooms": dr["bedrooms"], "floor": dr["floor"], "total_floors": dr["total_floors"],
         "price_usd": dr["price"] if dr["currency"] == "USD" else "", "price": dr["price"], "currency": dr["currency"]}
    try:
        tx, _ = B.texts.build(d, phone, name)
    except Exception:
        tx = {}
    feats = (", ".join(dr["features"][:20]))
    if "title" not in dr["edited"]:
        dr["title"] = tx.get("title_ka") or dr["title"]
    if "desc_ka" not in dr["edited"]:
        dr["desc_ka"] = (tx.get("ka") or "") + (f"\n\n✔️ {feats}" if feats else "")
    if "desc_en" not in dr["edited"]:
        dr["desc_en"] = tx.get("en") or ""
    dr["desc_ru"] = tx.get("ru") or dr.get("desc_ru", "")
    dr["title_en"] = tx.get("title_en") or ""


# ---------------------------------------------------------------- photos

def add_photo(msg, uid):
    """Store the photo exactly as received (largest size; a 'file' keeps the full original quality)."""
    dr = current(uid)
    if not dr:
        B.send(msg["chat"]["id"], "📷 ჯერ გამომიგზავნე განცხადების ბმული ან დაიწყე ახალი: /new — შემდეგ ფოტოები.")
        return
    if len(dr["photos"]) >= MAX_PHOTOS:
        B.send(msg["chat"]["id"], f"⚠️ მაქსიმუმ {MAX_PHOTOS} ფოტო.")
        return
    fid, ext = None, "jpg"
    if msg.get("photo"):
        fid = msg["photo"][-1]["file_id"]
    elif msg.get("document") and str(msg["document"].get("mime_type", "")).startswith("image/"):
        fid = msg["document"]["file_id"]
        ext = (msg["document"].get("file_name") or "x.jpg").rsplit(".", 1)[-1].lower()[:5] or "jpg"
    if not fid:
        return
    info = B.tg("getFile", file_id=fid).get("result") or {}
    if not info.get("file_path"):
        B.send(msg["chat"]["id"], "⚠️ ფოტო ვერ ჩამოვტვირთე (Telegram-ის ლიმიტი 20 MB). სცადე თავიდან.")
        return
    raw = requests.get(f"https://api.telegram.org/file/bot{B.TOKEN}/{info['file_path']}", timeout=120).content
    os.makedirs(ddir(dr["id"]), exist_ok=True)
    name = f"{int(time.time() * 1000)}.{ext if ext in ('jpg', 'jpeg', 'png', 'webp', 'heic') else 'jpg'}"
    with open(os.path.join(ddir(dr["id"]), name), "wb") as f:
        f.write(raw)
    dr["photos"].append(name)
    B.save_state()
    grp = msg.get("media_group_id")
    if grp and LAST_GROUP.get(str(uid)) == grp:
        return
    LAST_GROUP[str(uid)] = grp
    B.send(msg["chat"]["id"], f"📷 ფოტოები ემატება… (ახლა {len(dr['photos'])})\nროცა დაასრულებ — დააჭირე „👁 გადახედვა“.",
           [[{"text": "👁 გადახედვა", "callback_data": "pv|" + dr["id"]}]])


def photo_paths(dr):
    return [os.path.join(ddir(dr["id"]), p) for p in dr["photos"] if os.path.exists(os.path.join(ddir(dr["id"]), p))]


def send_album(chat, paths, numbered=True, as_files=False):
    for i in range(0, len(paths), 10):
        chunk = paths[i:i + 10]
        files, media = {}, []
        for n, p in enumerate(chunk):
            key = f"p{n}"
            files[key] = (os.path.basename(p), open(p, "rb").read())
            item = {"type": "document" if as_files else "photo", "media": f"attach://{key}"}
            if numbered:
                item["caption"] = str(i + n + 1)
            media.append(item)
        try:
            if len(media) == 1:
                kind = "document" if as_files else "photo"
                requests.post(B.API + ("sendDocument" if as_files else "sendPhoto"), data={"chat_id": chat, "caption": media[0].get("caption", "")},
                              files={kind: list(files.values())[0]}, timeout=180)
            else:
                requests.post(B.API + "sendMediaGroup", data={"chat_id": chat, "media": json.dumps(media)}, files=files, timeout=180)
        except Exception as ex:
            print("album failed", ex)


# ---------------------------------------------------------------- preview

def money(dr):
    try:
        p = f"{int(float(dr['price'])):,}"
    except (TypeError, ValueError):
        p = str(dr["price"] or "—")
    sym = {"USD": "$", "GEL": "₾", "EUR": "€"}.get(dr["currency"], dr["currency"])
    return f"{p} {sym}" + (" / თვე" if dr["deal"] == "rent" else " / დღე" if dr["deal"] == "daily" else "")


def floor_txt(dr):
    return f"{dr['floor']}/{dr['total_floors']}" if dr.get("total_floors") else str(dr.get("floor") or "—")


def preview_text(dr):
    name, phone = contact(dr)
    deal = {"sale": "იყიდება", "rent": "ქირავდება", "daily": "დღიური ქირა"}.get(dr["deal"], dr["deal"])
    lines = [f"👁 <b>გადახედვა — განცხადება #{e(dr['id'])}</b>", "",
             f"<b>{e(dr['title'])}</b>", f"💰 <b>{e(money(dr))}</b> · {e(deal)} · {e(B.TYPE_KA.get(dr['type'], dr['type']))}",
             f"📍 {e(', '.join(x for x in (dr['city'], dr['district'], dr['address']) if x) or '—')}",
             f"📐 {e(dr['area'] or '—')} მ² · 🚪 {e(dr['rooms'] or '—')} ოთახი · 🛏 {e(dr['bedrooms'] or '—')} · 🏢 {e(floor_txt(dr))}"]
    for k, v in dr.get("details") or []:
        lines.append(f"• {e(k)}: {e(v)}")
    if dr["features"]:
        lines.append("✔️ " + e(", ".join(dr["features"][:25])))
    lines += ["", f"📷 ფოტო: <b>{len(dr['photos'])}</b> (ორიგინალი, ცვლილების გარეშე)",
              f"👤 კონტაქტი საიტებზე: <b>{e(name)} · {e(phone)}</b> (მესაკუთრის ნომერი არსად ჩანს)",
              "", "🇬🇪 <b>აღწერა:</b>", e(dr["desc_ka"][:1500]), "", "🇬🇧 <b>Description:</b>", e(dr["desc_en"][:900])]
    if not B.STATE["phones"].get(dr["uid"]):
        lines += ["", "⚠️ შენი ნომერი არ მაქვს — ახლა კომპანიის ნომერია. დაამატე: <code>/phone 599123456</code>"]
    return "\n".join(lines)[:4000]


def platform_text(dr, platform):
    """What will go to MyHome.ge / SS.ge — the same fields, in each site's form order."""
    name, phone = contact(dr)
    deal = {"sale": "იყიდება", "rent": "ქირავდება", "daily": "ქირავდება დღიურად"}.get(dr["deal"], "")
    rows = [("გარიგების ტიპი", deal), ("ქონების ტიპი", B.TYPE_KA.get(dr["type"], "")), ("ქალაქი", dr["city"]), ("უბანი", dr["district"]),
            ("მისამართი", dr["address"]), ("ფართი მ²", dr["area"]), ("ოთახები", dr["rooms"]), ("საძინებელი", dr["bedrooms"]),
            ("სართული", dr["floor"]), ("სართულიანობა", dr["total_floors"]), ("ფასი", dr["price"]), ("ვალუტა", dr["currency"])]
    if platform == "ss":
        rows.insert(0, ("სათაური", dr["title"]))
    head = {"myhome": "🟠 <b>MyHome.ge</b>", "ss": "🔵 <b>SS.ge</b>"}[platform]
    out = [head + " — ასე აიტვირთება (დააჭირე ველს და დაკოპირდება):", ""]
    out += [f"{k}: <code>{e(v)}</code>" for k, v in rows if v not in ("", None, 0)]
    if dr["features"]:
        out.append("მახასიათებლები: " + e(", ".join(dr["features"][:25])))
    out += [f"საკონტაქტო: <code>{e(name)}</code> · <code>{e(phone)}</code>", "", "აღწერა:", f"<code>{e(dr['desc_ka'][:3000])}</code>"]
    return "\n".join(out)[:4000]


def keyboard(dr):
    i = dr["id"]
    b = lambda t, d: {"text": t, "callback_data": d}
    return [[b("✏️ სათაური", f"ed|{i}|title"), b("✏️ ფასი", f"ed|{i}|price"), b("✏️ გარიგება", f"ed|{i}|deal")],
            [b("✏️ აღწერა ქართ.", f"ed|{i}|desc_ka"), b("✏️ Description EN", f"ed|{i}|desc_en")],
            [b("✏️ უბანი", f"ed|{i}|district"), b("✏️ მისამართი", f"ed|{i}|address"), b("✏️ ქალაქი", f"ed|{i}|city")],
            [b("✏️ ფართი", f"ed|{i}|area"), b("✏️ ოთახები", f"ed|{i}|rooms"), b("✏️ სართული", f"ed|{i}|floor")],
            [b("✏️ ტიპი", f"ed|{i}|type"), b("✏️ მახასიათებლები", f"ed|{i}|features")]
            + ([b("📝 ორიგ. აღწერა", f"uo|{i}")] if dr.get("source_desc") else []),
            [b("🗑 ფოტოს წაშლა", f"ed|{i}|photo_del"), b("⭐ მთავარი ფოტო", f"ed|{i}|photo_main")],
            [b("✅ დამტკიცება და გამოქვეყნება", f"ap|{i}")],
            [b("❌ გაუქმება", f"dc|{i}")]]


def preview(chat, dr, with_photos=True):
    compose(dr)
    B.save_state()
    if with_photos and dr["photos"]:
        send_album(chat, photo_paths(dr))
    if dr.get("site_id"):
        B.offer_auto_publish(chat, dr["site_id"])
    B.send(chat, platform_text(dr, "myhome"))
    B.send(chat, platform_text(dr, "ss"))
    B.send(chat, preview_text(dr), keyboard(dr))


# ---------------------------------------------------------------- edits

def ask_edit(chat, uid, did, field):
    dr = B.STATE["drafts"].get(did)
    if not dr or dr["status"] != "draft":
        B.send(chat, "ეს დრაფტი აღარ არის აქტიური.")
        return
    B.STATE["await"][str(uid)] = {"draft": did, "field": field}
    label = {"photo_del": "წასაშლელი ფოტოების ნომრები (მაგ. 2 5)", "photo_main": "რომელი ფოტო იყოს მთავარი? (ნომერი)"}.get(field) or FIELDS[field][0]
    cur = "" if field.startswith("photo") else dr.get(field)
    if field == "price":
        cur = f"{dr['price']} {dr['currency']}"
    if field == "features":
        cur = ", ".join(dr["features"])
    if field == "floor":
        cur = floor_txt(dr)
    B.send(chat, f"✏️ <b>{e(label)}</b>\nახლანდელი: <code>{e(str(cur)[:1500])}</code>\n\nგამომიგზავნე ახალი მნიშვნელობა (ან /cancel).")


def apply_edit(chat, uid, text):
    """Returns True when the message was an answer to an edit question."""
    w = B.STATE["await"].pop(str(uid), None)
    if not w:
        return False
    dr = B.STATE["drafts"].get(w["draft"])
    if not dr or text.startswith("/cancel"):
        B.send(chat, "გაუქმებულია.")
        return True
    f, v, err = w["field"], text.strip(), ""
    if f == "price":
        m = re.search(r"([\d\s.,]+)\s*(usd|\$|gel|₾|lari|ლარი|eur|€)?", v, re.I)
        num = re.sub(r"[^\d.]", "", (m.group(1) if m else "").replace(",", ""))
        if num:
            dr["price"] = float(num) if "." in num else int(num)
            c = (m.group(2) or "").lower()
            dr["currency"] = "GEL" if c in ("gel", "₾", "lari", "ლარი") else "EUR" if c in ("eur", "€") else "USD" if c in ("usd", "$") else dr["currency"]
        else:
            err = "ფასი ვერ გავიგე. მაგ.: 150000 USD"
    elif f == "deal":
        dr["deal"] = DEAL_IN.get(v.lower(), "") or (err := "დაწერე: იყიდება / ქირავდება / დღიური") and dr["deal"]
    elif f == "type":
        dr["type"] = TYPE_IN.get(v.lower(), "") or (err := "დაწერე: ბინა / სახლი / კომერციული / მიწა / სასტუმრო") and dr["type"]
    elif f in ("area", "rooms", "bedrooms"):
        n = re.sub(r"[^\d.]", "", v.replace(",", "."))
        if n:
            dr[f] = float(n) if "." in n else int(n)
        else:
            err = "დაწერე რიცხვი."
    elif f == "floor":
        a, _, b = v.partition("/")
        dr["floor"], dr["total_floors"] = a.strip(), b.strip() or dr["total_floors"]
    elif f == "features":
        dr["features"] = [x.strip() for x in re.split(r"[,\n;]", v) if x.strip()][:40]
    elif f == "photo_del":
        nums = sorted({int(x) for x in re.findall(r"\d+", v)}, reverse=True)
        for n in nums:
            if 1 <= n <= len(dr["photos"]):
                name = dr["photos"].pop(n - 1)
                try:
                    os.remove(os.path.join(ddir(dr["id"]), name))
                except OSError:
                    pass
    elif f == "photo_main":
        n = int((re.findall(r"\d+", v) or ["0"])[0])
        if 1 <= n <= len(dr["photos"]):
            dr["photos"].insert(0, dr["photos"].pop(n - 1))
    else:
        dr[f] = v[:5000]
        if f in ("title", "desc_ka", "desc_en") and f not in dr["edited"]:
            dr["edited"].append(f)
    B.save_state()
    if err:
        B.send(chat, "⚠️ " + err)
        B.STATE["await"][str(uid)] = w
        return True
    B.send(chat, "✅ შეიცვალა.")
    preview(chat, dr, with_photos=f.startswith("photo"))
    return True


# ---------------------------------------------------------------- publish

def publish(chat, uid, did):
    dr = B.STATE["drafts"].get(did)
    if not dr or dr["status"] != "draft":
        B.send(chat, "ეს დრაფტი უკვე გამოქვეყნებულია ან გაუქმებულია.")
        return
    if str(uid) != dr["uid"] and not B.is_admin(uid):
        return
    compose(dr)
    if not dr["price"] or not (dr["district"] or dr["address"]):
        B.send(chat, "⚠️ გამოქვეყნებამდე შეავსე ფასი და უბანი/მისამართი.", keyboard(dr))
        return
    dr["status"] = "publishing"
    B.save_state()
    B.send(chat, "⏳ ვაქვეყნებ…")
    name, phone = contact(dr)
    results = []
    # 1) keygroup.ge (photos as sent; the website makes its own web-size copies, the originals stay untouched)
    site_ok, site_url = False, ""
    try:
        payload = site_payload(dr)
        files = [("photos", (os.path.basename(p), open(p, "rb").read())) for p in photo_paths(dr)[:15]]
        r = requests.post(B.PORTAL_URL + "/api/bot/listing", data={"data": json.dumps(payload)}, files=files or None,
                          headers={"X-Bot-Secret": B.CRM_SECRET}, timeout=240)
        j = r.json()
        site_ok, site_url = bool(j.get("ok")), j.get("url") or j.get("error") or str(r.status_code)
        if site_ok and j.get("id"):
            dr["site_id"] = j["id"]
    except Exception as ex:
        site_url = str(ex)[:120]
    results.append(("🌐 keygroup.ge", site_ok, site_url))
    # 2) Master CRM
    crm_d = {"source": (dr["source"] or {}).get("source") or "bot", "id": (dr["source"] or {}).get("id") or dr["id"],
             "url": (dr["source"] or {}).get("url") or site_url, "deal": dr["deal"], "type": dr["type"], "city": dr["city"],
             "district": dr["district"], "address": dr["address"], "rooms": dr["rooms"], "bedrooms": dr["bedrooms"], "floor": dr["floor"],
             "total_floors": dr["total_floors"], "area": dr["area"], "price_usd": dr["price"] if dr["currency"] == "USD" else "",
             "price": dr["price"], "currency": dr["currency"], "owner": (dr["source"] or {}).get("owner"), "phone": "",
             "texts": {"title_ka": dr["title"]}, "images": dr["photos"]}
    crm_ok, crm_info = B.save_to_crm(crm_d, dr["agent"], dr["uid"], dr["consent_at"] or "draft", False)
    results.append(("💾 Master CRM", crm_ok, "" if crm_ok else crm_info))
    # 3) MyHome.ge / SS.ge: official partner access is needed for automatic posting; until then a ready posting kit.
    for plat, label in (("myhome", "🟠 MyHome.ge"), ("ss", "🔵 SS.ge")):
        results.append((label, None, "მზა პაკეტი ქვემოთ — ავტომატური ატვირთვა ჩაირთვება, როცა საიტი პარტნიორულ წვდომას მოგვცემს"))
    dr["status"] = "published"
    dr["published_at"] = time.time()
    dr["site_url"] = site_url if site_ok else ""
    B.STATE["draft_of"].pop(str(uid), None)
    B.save_state()
    lines = ["✅ <b>გამოქვეყნდა</b> — #" + e(dr["id"]), ""]
    for label, okk, info in results:
        icon = "✅" if okk else ("📋" if okk is None else "⚠️")
        lines.append(f"{icon} {label}" + (f": {e(info)}" if info else ""))
    B.send(chat, "\n".join(lines))
    B.send(chat, platform_text(dr, "myhome"))
    B.send(chat, platform_text(dr, "ss"))
    if dr["photos"]:
        B.send(chat, "📎 ორიგინალი ფოტოები ფაილებად (MyHome / SS-ზე ასატვირთად):")
        send_album(chat, photo_paths(dr), numbered=False, as_files=True)
    B.send_admins(lambda a: B.tr(a, f"📤 {e(dr['agent'])}-მა გამოაქვეყნა განცხადება #{e(dr['id'])}\n{e(money(dr))} · {e(dr['district'] or dr['address'])}\n{e(site_url if site_ok else 'საიტზე ვერ აიტვირთა: ' + site_url)}",
                                 f"📤 {e(dr['agent'])} published listing #{e(dr['id'])}\n{e(money(dr))} · {e(dr['district'] or dr['address'])}\n{e(site_url if site_ok else 'website upload failed: ' + site_url)}"))


def discard(chat, uid, did):
    dr = B.STATE["drafts"].get(did)
    if dr and (str(uid) == dr["uid"] or B.is_admin(uid)) and dr["status"] == "draft":
        dr["status"] = "cancelled"
        B.STATE["draft_of"].pop(str(uid), None)
        shutil.rmtree(ddir(did), ignore_errors=True)
        B.save_state()
    B.send(chat, "❌ დრაფტი გაუქმდა.")


def owner_photo_request(d, text=None):
    """Ready WhatsApp message asking the owner for the original photos (with their personal upload link when we have one)."""
    txt = text or ("გამარჯობა! KEY GROUP-დან გწერთ. როგორც შევთანხმდით, გთხოვთ გამომიგზავნოთ ბინის ორიგინალი ფოტოები "
                   "(როგორც ტელეფონშია, ლოგოს გარეშე). მადლობა!")
    phone = re.sub(r"\D", "", str(d.get("phone") or ""))
    if phone and len(phone) == 9:
        phone = "995" + phone
    link = f"https://wa.me/{phone}?text={requests.utils.quote(txt)}" if len(phone) >= 11 and "*" not in str(d.get("phone")) else ""
    return txt, link
