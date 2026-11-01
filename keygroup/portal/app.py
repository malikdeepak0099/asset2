"""KEY GROUP owner portal — owners list their property for sale or rent on keygroup.ge.

Accounts: phone + password (no SMS). Every new or edited listing waits for admin approval.
Plans: Free (30 days), VIP, Super VIP (top of the list for N days, badge) and Boost (one bump to the top).
Payment is manual for now: the owner orders a plan, pays by bank transfer / cash, the admin marks the
order paid and the plan starts. Data lives in SQLite + photo files under DATA_DIR.
"""
import base64
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import urllib.parse
import urllib.request

from PIL import Image, ImageOps
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route

import chatbot

DATA_DIR = os.environ.get("DATA_DIR", "/data")
UPLOADS = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "portal.db")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ALERT_CHATS = [c.strip() for c in os.environ.get("ALERT_CHATS", "").split(",") if c.strip()]
SITE = os.environ.get("SITE_URL", "https://keygroup.ge")
CRM_URL = os.environ.get("CRM_URL", "")
MAX_PHOTOS = 15
MAX_PHOTO_BYTES = 12 * 1024 * 1024
SESSION_DAYS = 30
os.makedirs(UPLOADS, exist_ok=True)

DEFAULT_SETTINGS = {
    "plans": {
        "free": {"name": "Free", "price": 0, "days": 30},
        "vip": {"name": "VIP", "price": 10, "days": 7},
        "super": {"name": "Super VIP", "price": 25, "days": 7},
        "boost": {"name": "Boost", "price": 3, "days": 0},
    },
    "currency": "GEL",
    "payment_info": ("Pay by bank transfer to KEY GROUP and write your order number in the comment, "
                     "or pay in our office (Richard Holbrooke St. 4, Tbilisi). WhatsApp +995 577 114 118."),
    "show_owner_phone": False,
    "company_phone": "+995577114118",
    "free_listing_limit": 2,
    "reconfirm_days": 15,
}
CONSENT_VERSION = "2026-11-01"
VERIFY_LABELS = {0: "", 1: "Contact verified", 2: "Verified listing", 3: "Inspected"}

DEALS = {"sale", "rent", "daily"}
TYPES = {"flat", "house", "commercial", "land", "hotel"}
CURRENCIES = {"USD", "GEL", "EUR"}

# ---------------------------------------------------------------- database

_LOCK = threading.Lock()


def db():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, phone TEXT UNIQUE, name TEXT, pw TEXT, role TEXT DEFAULT 'owner',
            blocked INTEGER DEFAULT 0, created REAL);
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY, user_id INTEGER, status TEXT DEFAULT 'pending', reject_reason TEXT DEFAULT '',
            deal TEXT, type TEXT, city TEXT, district TEXT, address TEXT, rooms INTEGER, bedrooms INTEGER,
            area REAL, floor TEXT, total_floors TEXT, price REAL, currency TEXT, title TEXT, description TEXT,
            contact_name TEXT, contact_phone TEXT, photos TEXT DEFAULT '[]',
            plan TEXT DEFAULT 'free', vip_until REAL DEFAULT 0, super_until REAL DEFAULT 0, boosted_at REAL DEFAULT 0,
            expires REAL DEFAULT 0, views INTEGER DEFAULT 0, created REAL, updated REAL, approved REAL DEFAULT 0,
            verified INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY, listing_id INTEGER, reason TEXT, contact TEXT, status TEXT DEFAULT 'open', created REAL);
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY, user_id INTEGER, listing_id INTEGER, plan TEXT, amount REAL, currency TEXT,
            status TEXT DEFAULT 'awaiting_payment', note TEXT DEFAULT '', created REAL, paid REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER, expires REAL);
        CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT);
        CREATE INDEX IF NOT EXISTS idx_listings_status ON listings(status);
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY, token TEXT, status TEXT DEFAULT 'bot', name TEXT DEFAULT '', phone TEXT DEFAULT '',
            lang TEXT DEFAULT 'en', topic TEXT DEFAULT '', page TEXT DEFAULT '', state TEXT DEFAULT '{}', ip TEXT DEFAULT '',
            unread INTEGER DEFAULT 0, created REAL, updated REAL);
        CREATE TABLE IF NOT EXISTS chat_msgs (
            id INTEGER PRIMARY KEY, chat_id INTEGER, who TEXT, text TEXT, data TEXT DEFAULT '{}', ts REAL);
        CREATE INDEX IF NOT EXISTS idx_chat_msgs ON chat_msgs(chat_id, id);
        CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY, actor_id INTEGER, actor TEXT, action TEXT, entity TEXT, entity_id INTEGER, detail TEXT, ts REAL);
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY, name TEXT, sid TEXT, page TEXT, props TEXT DEFAULT '{}', ts REAL);
        CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
        """)
        for table, col, typ in (("users", "consent_at", "REAL DEFAULT 0"), ("users", "consent_ver", "TEXT DEFAULT ''"),
                                ("users", "contact_verified", "INTEGER DEFAULT 0"),
                                ("listings", "verify_level", "INTEGER DEFAULT 0"), ("listings", "confirmed", "REAL DEFAULT 0"),
                                ("listings", "dup_of", "TEXT DEFAULT ''"), ("listings", "photo_hashes", "TEXT DEFAULT '{}'"),
                                ("chats", "consent_at", "REAL DEFAULT 0")):
            have = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
            if col not in have:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        con.execute("UPDATE listings SET verify_level=2 WHERE verified=1 AND verify_level=0")
        con.execute("UPDATE listings SET confirmed=COALESCE(NULLIF(approved,0), created) WHERE confirmed=0")


def get_settings():
    with db() as con:
        row = con.execute("SELECT v FROM settings WHERE k='main'").fetchone()
    s = json.loads(json.dumps(DEFAULT_SETTINGS))
    if row:
        saved = json.loads(row["v"])
        for k, v in saved.items():
            if k == "plans":
                for p, cfg in v.items():
                    if p in s["plans"]:
                        s["plans"][p].update(cfg)
            else:
                s[k] = v
    return s


def save_settings(s):
    with _LOCK, db() as con:
        con.execute("INSERT OR REPLACE INTO settings VALUES ('main', ?)", (json.dumps(s, ensure_ascii=False),))


# ---------------------------------------------------------------- helpers

def norm_phone(p):
    d = re.sub(r"\D", "", str(p or ""))
    if d.startswith("00"):
        d = d[2:]
    if len(d) == 9 and d.startswith("5"):
        d = "995" + d
    return "+" + d if d else ""


def hash_pw(pw, salt=None):
    salt = salt or secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode("utf-8"), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return base64.b64encode(salt).decode() + "$" + base64.b64encode(h).decode()


def check_pw(pw, stored):
    try:
        salt_b64, h_b64 = stored.split("$", 1)
        salt = base64.b64decode(salt_b64)
        return hmac.compare_digest(hash_pw(pw, salt).split("$", 1)[1], h_b64)
    except Exception:
        return False


def err(msg, code=400):
    return JSONResponse({"ok": False, "error": msg}, status_code=code)


def ok(**kw):
    return JSONResponse({"ok": True, **kw})


async def body_json(request):
    try:
        data = await request.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def current_user(request):
    tok = request.cookies.get("kg_session") or request.headers.get("x-session", "")
    if not tok:
        return None
    with db() as con:
        row = con.execute("SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?",
                          (tok, time.time())).fetchone()
    if not row or row["blocked"]:
        return None
    return dict(row)


def need_user(request, admin=False):
    u = current_user(request)
    if not u:
        return None, err("Please log in", 401)
    if admin and u["role"] != "admin":
        return None, err("Admins only", 403)
    return u, None


def new_session(user_id):
    tok = secrets.token_urlsafe(32)
    with _LOCK, db() as con:
        con.execute("INSERT INTO sessions VALUES (?,?,?)", (tok, user_id, time.time() + SESSION_DAYS * 86400))
        con.execute("DELETE FROM sessions WHERE expires<?", (time.time(),))
    return tok


def with_session(resp, tok):
    resp.set_cookie("kg_session", tok, max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax",
                    secure=SITE.startswith("https"), path="/")
    return resp


def notify(text):
    if not BOT_TOKEN or not ALERT_CHATS:
        return

    def run():
        for chat in ALERT_CHATS:
            try:
                data = urllib.parse.urlencode({"chat_id": chat, "text": text, "parse_mode": "HTML",
                                               "disable_web_page_preview": "true"}).encode()
                urllib.request.urlopen(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data, timeout=20).read()
            except Exception as ex:
                print("telegram alert failed:", ex)
    threading.Thread(target=run, daemon=True).start()


def audit(con, user, action, entity, entity_id=0, detail=""):
    con.execute("INSERT INTO audit (actor_id, actor, action, entity, entity_id, detail, ts) VALUES (?,?,?,?,?,?,?)",
                (user["id"] if user else 0, (user or {}).get("name") or (user or {}).get("phone") or "system",
                 action, entity, entity_id, str(detail or "")[:1000], time.time()))


def track(con, name, page="", props=None, sid="server"):
    con.execute("INSERT INTO events (name, sid, page, props, ts) VALUES (?,?,?,?,?)",
                (name, sid[:40], page[:200], json.dumps(props or {}, ensure_ascii=False)[:1000], time.time()))


def ahash(path):
    """8x8 average hash of an image, as 16 hex chars (same photo re-uploaded -> same or very close hash)."""
    try:
        im = Image.open(path).convert("L").resize((8, 8))
        px = list(im.getdata())
        avg = sum(px) / 64
        return "%016x" % sum(1 << i for i, v in enumerate(px) if v > avg)
    except Exception:
        return ""


def _addr_key(row):
    return re.sub(r"[^0-9a-z\u10a0-\u10ff\u0400-\u04ff]", "", ((row["address"] or "") + (row["city"] or "")).lower())


def find_duplicates(con, lid):
    """Possible duplicates of listing lid among other live listings: same address + rooms, very similar specs, or a shared photo."""
    row = con.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone()
    if not row:
        return []
    hashes = set(json.loads(row["photo_hashes"] or "{}").values()) - {""}
    found = []
    for o in con.execute("SELECT * FROM listings WHERE id!=? AND status IN ('pending','active','paused','changes','expired')", (lid,)).fetchall():
        why = ""
        if o["deal"] == row["deal"] and (o["rooms"] or 0) == (row["rooms"] or 0) and _addr_key(o) and _addr_key(o) == _addr_key(row) \
                and len(_addr_key(row)) >= 6:
            why = "same address"
        elif (o["deal"] == row["deal"] and o["district"] and (o["district"] or "").lower() == (row["district"] or "").lower()
              and (o["rooms"] or 0) == (row["rooms"] or 0) and row["area"] and o["area"] and abs(o["area"] - row["area"]) <= row["area"] * 0.03
              and (o["floor"] or "") == (row["floor"] or "") and o["price"] and abs(o["price"] - row["price"]) <= row["price"] * 0.1):
            why = "same district, rooms, area and floor"
        if not why and hashes:
            oh = set(json.loads(o["photo_hashes"] or "{}").values()) - {""}
            if any(bin(int(a, 16) ^ int(b, 16)).count("1") <= 4 for a in hashes for b in oh):
                why = "same photo"
        if why:
            found.append(f"#{o['id']} ({why})")
    con.execute("UPDATE listings SET dup_of=? WHERE id=?", (", ".join(found[:5]), lid))
    return found


def esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def tier(row, now=None):
    now = now or time.time()
    if row["super_until"] and row["super_until"] > now:
        return "super"
    if row["vip_until"] and row["vip_until"] > now:
        return "vip"
    return "free"


def listing_out(row, owner_view=False, admin_view=False, settings=None):
    settings = settings or get_settings()
    d = dict(row)
    d["photos"] = json.loads(d.get("photos") or "[]")
    d["tier"] = tier(row)
    d["url"] = f"{SITE}/p/?id={d['id']}"
    lvl = d.get("verify_level") or 0
    d["verified"] = 1 if lvl >= 2 else 0
    d["verify_label"] = VERIFY_LABELS.get(lvl, "")
    d.pop("photo_hashes", None)
    if not admin_view:
        d.pop("dup_of", None)
    if not (owner_view or admin_view or settings.get("show_owner_phone")):
        d["contact_phone"] = ""
        d["contact_name"] = (d.get("contact_name") or "").split(" ")[0]
    if not admin_view:
        d.pop("user_id", None)
    return d


def clean_listing(data):
    """Validate the owner's form. Returns (fields, error)."""
    s = lambda k, n=200: str(data.get(k) or "").strip()[:n]

    def num(k, typ=float):
        try:
            v = typ(str(data.get(k) or "0").replace(",", "").strip() or 0)
            return v if v >= 0 else 0
        except ValueError:
            return 0
    f = {
        "deal": s("deal", 10), "type": s("type", 20), "city": s("city", 60) or "Tbilisi", "district": s("district", 80),
        "address": s("address", 160), "rooms": num("rooms", int), "bedrooms": num("bedrooms", int), "area": num("area"),
        "floor": s("floor", 10), "total_floors": s("total_floors", 10), "price": num("price"),
        "currency": s("currency", 5).upper() or "USD", "title": s("title", 140), "description": s("description", 5000),
        "contact_name": s("contact_name", 80), "contact_phone": norm_phone(data.get("contact_phone")),
    }
    if f["deal"] not in DEALS:
        return None, "Choose sale or rent"
    if f["type"] not in TYPES:
        return None, "Choose the property type"
    if f["currency"] not in CURRENCIES:
        return None, "Choose the currency"
    if not f["price"]:
        return None, "Enter the price"
    if not f["district"] and not f["address"]:
        return None, "Enter the district or address"
    if len(f["contact_phone"]) < 10:
        return None, "Enter a contact phone"
    return f, None


def save_photo(raw):
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((1600, 1600))
    name = secrets.token_hex(10) + ".jpg"
    img.save(os.path.join(UPLOADS, name), "JPEG", quality=82, optimize=True)
    thumb = img.copy()
    thumb.thumbnail((600, 600))
    thumb.save(os.path.join(UPLOADS, "t_" + name), "JPEG", quality=78, optimize=True)
    return name


def remove_photo_files(name):
    for n in (name, "t_" + name):
        p = os.path.join(UPLOADS, os.path.basename(n))
        if os.path.exists(p):
            os.remove(p)


# ---------------------------------------------------------------- rate limit (login / register)

_HITS = {}


def too_many(request, key, limit=10, window=600):
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
    k = f"{key}:{ip}"
    now = time.time()
    hits = [t for t in _HITS.get(k, []) if t > now - window]
    hits.append(now)
    _HITS[k] = hits
    return len(hits) > limit


# ---------------------------------------------------------------- auth endpoints

async def register(request):
    if too_many(request, "reg", 8):
        return err("Too many attempts, try again later", 429)
    d = await body_json(request)
    phone, name, pw = norm_phone(d.get("phone")), str(d.get("name") or "").strip()[:80], str(d.get("password") or "")
    if len(phone) < 10:
        return err("Enter a valid phone number")
    if len(pw) < 6:
        return err("Password must be at least 6 characters")
    if not name:
        return err("Enter your name")
    if not d.get("consent"):
        return err("Please accept the terms and privacy policy")
    with _LOCK, db() as con:
        if con.execute("SELECT 1 FROM users WHERE phone=?", (phone,)).fetchone():
            return err("This phone is already registered — log in instead")
        cur = con.execute("INSERT INTO users (phone, name, pw, created, consent_at, consent_ver) VALUES (?,?,?,?,?,?)",
                          (phone, name, hash_pw(pw), time.time(), time.time(), CONSENT_VERSION))
        uid = cur.lastrowid
        track(con, "owner_registered")
    notify(f"👤 New owner account on keygroup.ge: <b>{esc(name)}</b> {esc(phone)}")
    return with_session(ok(user={"id": uid, "name": name, "phone": phone, "role": "owner"}), new_session(uid))


async def login(request):
    if too_many(request, "login", 15):
        return err("Too many attempts, try again later", 429)
    d = await body_json(request)
    phone, pw = norm_phone(d.get("phone")), str(d.get("password") or "")
    with db() as con:
        u = con.execute("SELECT * FROM users WHERE phone=?", (phone,)).fetchone()
    if not u or not check_pw(pw, u["pw"]):
        return err("Wrong phone or password", 401)
    if u["blocked"]:
        return err("This account is blocked. Contact KEY GROUP.", 403)
    return with_session(ok(user={"id": u["id"], "name": u["name"], "phone": u["phone"], "role": u["role"]}), new_session(u["id"]))


async def logout(request):
    tok = request.cookies.get("kg_session")
    if tok:
        with _LOCK, db() as con:
            con.execute("DELETE FROM sessions WHERE token=?", (tok,))
    resp = ok()
    resp.delete_cookie("kg_session", path="/")
    return resp


async def me(request):
    u = current_user(request)
    if not u:
        return ok(user=None, settings=public_settings())
    return ok(user={k: u[k] for k in ("id", "name", "phone", "role")}, settings=public_settings())


async def change_password(request):
    u, e = need_user(request)
    if e:
        return e
    d = await body_json(request)
    if not check_pw(str(d.get("old") or ""), u["pw"]):
        return err("Current password is wrong")
    if len(str(d.get("new") or "")) < 6:
        return err("New password must be at least 6 characters")
    with _LOCK, db() as con:
        con.execute("UPDATE users SET pw=? WHERE id=?", (hash_pw(str(d["new"])), u["id"]))
    return ok()


def public_settings():
    s = get_settings()
    return {"plans": s["plans"], "currency": s["currency"], "payment_info": s["payment_info"],
            "show_owner_phone": s["show_owner_phone"], "company_phone": s["company_phone"],
            "free_listing_limit": s.get("free_listing_limit", 2), "reconfirm_days": s.get("reconfirm_days", 15)}


# ---------------------------------------------------------------- owner endpoints

async def my_listings(request):
    u, e = need_user(request)
    if e:
        return e
    if request.method == "POST":
        d = await body_json(request)
        f, msg = clean_listing(d)
        if msg:
            return err(msg)
        now = time.time()
        s = get_settings()
        limit = int(s.get("free_listing_limit", 2) or 0)
        with _LOCK, db() as con:
            if limit and u["role"] != "admin":
                n = con.execute("""SELECT COUNT(*) FROM listings WHERE user_id=? AND status IN ('pending','active','paused','changes')
                                   AND vip_until<? AND super_until<?""", (u["id"], now, now)).fetchone()[0]
                if n >= limit:
                    return err(f"A free account can have up to {limit} active listings. Delete or promote one (VIP), or contact us for an agent account.")
            cols = ",".join(f.keys())
            cur = con.execute(f"INSERT INTO listings (user_id,{cols},status,created,updated,confirmed,verify_level) VALUES (?,{','.join('?' * len(f))},'pending',?,?,?,?)",
                              (u["id"], *f.values(), now, now, now, 1 if u.get("contact_verified") else 0))
            lid = cur.lastrowid
            dups = find_duplicates(con, lid)
            track(con, "listing_submitted", props={"deal": f["deal"], "type": f["type"]})
        notify(f"🏠 New owner listing #{lid} waiting for approval\n{esc(f['deal'])} · {esc(f['type'])} · {esc(f['district'] or f['address'])} · "
               f"{f['price']:,.0f} {esc(f['currency'])}\nOwner: {esc(u['name'])} {esc(u['phone'])}\n"
               + (f"⚠️ Possible duplicate of {esc(', '.join(dups))}\n" if dups else "") + f"{SITE}/admin/")
        return ok(id=lid)
    with db() as con:
        rows = con.execute("SELECT * FROM listings WHERE user_id=? AND status!='deleted' ORDER BY id DESC", (u["id"],)).fetchall()
        orders = con.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 50", (u["id"],)).fetchall()
    s = get_settings()
    return ok(listings=[listing_out(r, owner_view=True, settings=s) for r in rows], orders=[dict(o) for o in orders])


def own_listing(u, lid, con):
    row = con.execute("SELECT * FROM listings WHERE id=? AND status!='deleted'", (lid,)).fetchone()
    if not row or (row["user_id"] != u["id"] and u["role"] != "admin"):
        return None
    return row


async def my_listing(request):
    u, e = need_user(request)
    if e:
        return e
    lid = int(request.path_params["lid"])
    with db() as con:
        row = own_listing(u, lid, con)
    if not row:
        return err("Not found", 404)
    if request.method == "GET":
        return ok(listing=listing_out(row, owner_view=True))
    if request.method == "DELETE":
        with _LOCK, db() as con:
            con.execute("UPDATE listings SET status='deleted', updated=? WHERE id=?", (time.time(), lid))
        for p in json.loads(row["photos"] or "[]"):
            remove_photo_files(p)
        return ok()
    d = await body_json(request)
    f, msg = clean_listing(d)
    if msg:
        return err(msg)
    sets = ",".join(f"{k}=?" for k in f)
    with _LOCK, db() as con:
        # an edit goes back to the approval queue (admins' own edits stay live)
        status = row["status"] if u["role"] == "admin" else ("pending" if row["status"] in ("active", "rejected", "changes") else row["status"])
        con.execute(f"UPDATE listings SET {sets}, status=?, updated=?, confirmed=? WHERE id=?", (*f.values(), status, time.time(), time.time(), lid))
        find_duplicates(con, lid)
    if status == "pending" and row["status"] != "pending":
        notify(f"✏️ Owner listing #{lid} was edited and waits for approval again\n{SITE}/admin/")
    return ok(status=status)


async def listing_photos(request):
    u, e = need_user(request)
    if e:
        return e
    lid = int(request.path_params["lid"])
    with db() as con:
        row = own_listing(u, lid, con)
    if not row:
        return err("Not found", 404)
    photos = json.loads(row["photos"] or "[]")
    if request.method == "DELETE":
        name = request.query_params.get("name", "")
        if name in photos:
            photos.remove(name)
            remove_photo_files(name)
    elif request.method == "PUT":
        d = await body_json(request)
        order = [p for p in d.get("photos", []) if p in photos]
        photos = order + [p for p in photos if p not in order]
    else:
        form = await request.form(max_files=MAX_PHOTOS, max_part_size=MAX_PHOTO_BYTES)
        files = form.getlist("photos")
        added = 0
        for f in files:
            if len(photos) >= MAX_PHOTOS:
                break
            raw = await f.read()
            if not raw or len(raw) > MAX_PHOTO_BYTES:
                continue
            try:
                photos.append(save_photo(raw))
                added += 1
            except Exception as ex:
                print("bad image:", ex)
        if files and not added:
            return err("Could not read the photos. Use JPG or PNG under 12 MB.")
    hashes = json.loads(row["photo_hashes"] or "{}")
    hashes = {p: hashes.get(p) or ahash(os.path.join(UPLOADS, "t_" + p)) for p in photos}
    with _LOCK, db() as con:
        con.execute("UPDATE listings SET photos=?, photo_hashes=?, updated=? WHERE id=?", (json.dumps(photos), json.dumps(hashes), time.time(), lid))
        dups = find_duplicates(con, lid) if request.method == "POST" else []
    if dups and request.method == "POST":
        notify(f"⚠️ Listing #{lid}: photos look like {esc(', '.join(dups))}\n{SITE}/admin/")
    return ok(photos=photos)


async def confirm_listing(request):
    """Owner confirms the property is still available (and renews an expired free listing)."""
    u, e = need_user(request)
    if e:
        return e
    lid = int(request.path_params["lid"])
    s = get_settings()
    now = time.time()
    with _LOCK, db() as con:
        row = own_listing(u, lid, con)
        if not row:
            return err("Not found", 404)
        if row["status"] == "expired":
            con.execute("UPDATE listings SET status='active', expires=?, confirmed=? WHERE id=?", (now + s["plans"]["free"]["days"] * 86400, now, lid))
        else:
            con.execute("UPDATE listings SET confirmed=?, expires=MAX(expires, ?) WHERE id=?",
                        (now, now + s["plans"]["free"]["days"] * 86400 if row["status"] == "active" else 0, lid))
        audit(con, u, "confirm_available", "listing", lid)
        row = con.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone()
    return ok(listing=listing_out(row, owner_view=True))


async def order_plan(request):
    u, e = need_user(request)
    if e:
        return e
    lid = int(request.path_params["lid"])
    d = await body_json(request)
    plan = str(d.get("plan") or "")
    s = get_settings()
    if plan not in ("vip", "super", "boost"):
        return err("Choose a plan")
    with db() as con:
        row = own_listing(u, lid, con)
    if not row:
        return err("Not found", 404)
    cfg = s["plans"][plan]
    with _LOCK, db() as con:
        cur = con.execute("INSERT INTO orders (user_id, listing_id, plan, amount, currency, created) VALUES (?,?,?,?,?,?)",
                          (u["id"], lid, plan, cfg["price"], s["currency"], time.time()))
        oid = cur.lastrowid
    notify(f"💳 New plan order #{oid}: <b>{esc(cfg['name'])}</b> for listing #{lid} — {cfg['price']} {esc(s['currency'])}\n"
           f"Owner: {esc(u['name'])} {esc(u['phone'])}\nMark it paid in {SITE}/admin/ after the payment arrives.")
    return ok(order={"id": oid, "plan": plan, "amount": cfg["price"], "currency": s["currency"],
                     "payment_info": s["payment_info"]})


# ---------------------------------------------------------------- public endpoints

def expire_old(con):
    now = time.time()
    con.execute("UPDATE listings SET status='expired' WHERE status='active' AND expires>0 AND expires<? AND super_until<? AND vip_until<?",
                (now, now, now))


async def public_listings(request):
    q = request.query_params
    now = time.time()
    where, args = ["status='active'"], []
    if q.get("deal") in DEALS:
        where.append("deal=?"); args.append(q["deal"])
    if q.get("type") in TYPES:
        where.append("type=?"); args.append(q["type"])
    if q.get("district"):
        where.append("(district LIKE ? OR address LIKE ? OR city LIKE ?)"); args += ["%" + q["district"][:60] + "%"] * 3
    for key, col, op in (("min_price", "price", ">="), ("max_price", "price", "<="), ("min_area", "area", ">="),
                         ("max_area", "area", "<="), ("rooms", "rooms", ">=")):
        try:
            v = float(q.get(key) or 0)
        except ValueError:
            v = 0
        if v:
            where.append(f"{col}{op}?"); args.append(v)
    if q.get("currency") in CURRENCIES:
        where.append("currency=?"); args.append(q["currency"])
    if q.get("exclude"):
        where.append("id!=?"); args.append(int(q["exclude"]) if q["exclude"].isdigit() else 0)
    sort = {"price_asc": "price ASC", "price_desc": "price DESC", "area_desc": "area DESC"}.get(q.get("sort", ""), "")
    limit = min(max(int(q.get("limit", 60) or 60), 1), 200)
    with _LOCK, db() as con:
        expire_old(con)
        rows = con.execute(
            f"""SELECT * FROM listings WHERE {' AND '.join(where)}
                ORDER BY (CASE WHEN super_until>? THEN 2 WHEN vip_until>? THEN 1 ELSE 0 END) DESC,
                         {sort + ',' if sort else ''} MAX(boosted_at, approved) DESC LIMIT ?""", (*args, now, now, limit)).fetchall()
    s = get_settings()
    return ok(listings=[listing_out(r, settings=s) for r in rows])


async def public_listing(request):
    lid = int(request.path_params["lid"])
    with _LOCK, db() as con:
        row = con.execute("SELECT * FROM listings WHERE id=? AND status='active'", (lid,)).fetchone()
        if row:
            con.execute("UPDATE listings SET views=views+1 WHERE id=?", (lid,))
            track(con, "listing_viewed", f"/p/?id={lid}", {"listing_id": lid, "district": row["district"]},
                  sid=request.headers.get("x-kg-sid", "")[:40] or "server")
    if not row:
        return err("This listing is not available", 404)
    return ok(listing=listing_out(row), settings=public_settings())


async def report_listing(request):
    if too_many(request, "report", 10, 3600):
        return err("Too many reports, try later", 429)
    lid = int(request.path_params["lid"])
    d = await body_json(request)
    reason = str(d.get("reason") or "").strip()[:500]
    if not reason:
        return err("Write what is wrong")
    with _LOCK, db() as con:
        if not con.execute("SELECT 1 FROM listings WHERE id=?", (lid,)).fetchone():
            return err("Not found", 404)
        con.execute("INSERT INTO reports (listing_id, reason, contact, created) VALUES (?,?,?,?)",
                    (lid, reason, str(d.get("contact") or "")[:100], time.time()))
    notify(f"🚩 Listing #{lid} was reported: {esc(reason[:200])}\n{SITE}/admin/")
    return ok()


async def uploads(request):
    name = os.path.basename(request.path_params["name"])
    path = os.path.join(UPLOADS, name)
    if not re.fullmatch(r"(t_)?[0-9a-f]{20}\.jpg", name) or not os.path.exists(path):
        return Response(status_code=404)
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=31536000, immutable"})


# ---------------------------------------------------------------- admin endpoints

async def admin_stats(request):
    u, e = need_user(request, admin=True)
    if e:
        return e
    now = time.time()
    with _LOCK, db() as con:
        expire_old(con)
        by_status = {r[0]: r[1] for r in con.execute("SELECT status, COUNT(*) FROM listings GROUP BY status")}
        users = con.execute("SELECT COUNT(*) FROM users WHERE role='owner'").fetchone()[0]
        await_pay = con.execute("SELECT COUNT(*) FROM orders WHERE status='awaiting_payment'").fetchone()[0]
        paid_30 = con.execute("SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='paid' AND paid>?", (now - 30 * 86400,)).fetchone()[0]
        reports = con.execute("SELECT COUNT(*) FROM reports WHERE status='open'").fetchone()[0]
        vip = con.execute("SELECT COUNT(*) FROM listings WHERE status='active' AND (vip_until>? OR super_until>?)", (now, now)).fetchone()[0]
        dups = con.execute("SELECT COUNT(*) FROM listings WHERE dup_of!='' AND status IN ('pending','active','changes')").fetchone()[0]
        chats_waiting = con.execute("SELECT COUNT(*) FROM chats WHERE status IN ('waiting','agent') AND unread>0").fetchone()[0]
        chats_today = con.execute("SELECT COUNT(DISTINCT chat_id) FROM chat_msgs WHERE who='visitor' AND ts>?", (now - 86400,)).fetchone()[0]
    return ok(stats={"duplicates": dups, "chats_waiting": chats_waiting, "chats_today": chats_today, "listings": by_status, "owners": users, "orders_waiting": await_pay, "revenue_30d": paid_30,
                     "vip_active": vip, "reports_open": reports, "currency": get_settings()["currency"]})


async def admin_listings(request):
    u, e = need_user(request, admin=True)
    if e:
        return e
    status = request.query_params.get("status", "pending")
    with db() as con:
        if status == "all":
            rows = con.execute("SELECT l.*, u.name AS owner_name, u.phone AS owner_phone FROM listings l LEFT JOIN users u ON u.id=l.user_id "
                               "WHERE l.status!='deleted' ORDER BY l.id DESC LIMIT 500").fetchall()
        else:
            rows = con.execute("SELECT l.*, u.name AS owner_name, u.phone AS owner_phone FROM listings l LEFT JOIN users u ON u.id=l.user_id "
                               "WHERE l.status=? ORDER BY l.id DESC LIMIT 500", (status,)).fetchall()
    s = get_settings()
    return ok(listings=[listing_out(r, admin_view=True, settings=s) for r in rows])


async def admin_listing_action(request):
    u, e = need_user(request, admin=True)
    if e:
        return e
    lid = int(request.path_params["lid"])
    d = await body_json(request)
    action = d.get("action")
    s = get_settings()
    now = time.time()
    with _LOCK, db() as con:
        row = con.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone()
        if not row:
            return err("Not found", 404)
        if action == "approve":
            exp = row["expires"] if row["expires"] and row["expires"] > now else now + s["plans"]["free"]["days"] * 86400
            con.execute("UPDATE listings SET status='active', reject_reason='', approved=?, expires=? WHERE id=?",
                        (row["approved"] or now, exp, lid))
        elif action == "reject":
            con.execute("UPDATE listings SET status='rejected', reject_reason=? WHERE id=?", (str(d.get("reason") or "")[:300], lid))
        elif action == "changes":
            con.execute("UPDATE listings SET status='changes', reject_reason=? WHERE id=?", (str(d.get("reason") or "")[:300], lid))
        elif action == "level":
            lvl = max(0, min(3, int(d.get("level") or 0)))
            con.execute("UPDATE listings SET verify_level=?, verified=? WHERE id=?", (lvl, 1 if lvl >= 2 else 0, lid))
        elif action == "not_duplicate":
            con.execute("UPDATE listings SET dup_of='' WHERE id=?", (lid,))
        elif action == "check_duplicates":
            find_duplicates(con, lid)
        elif action == "pause":
            con.execute("UPDATE listings SET status='paused' WHERE id=?", (lid,))
        elif action == "renew":
            con.execute("UPDATE listings SET status='active', expires=? WHERE id=?", (now + s["plans"]["free"]["days"] * 86400, lid))
        elif action == "delete":
            con.execute("UPDATE listings SET status='deleted' WHERE id=?", (lid,))
        elif action in ("verify", "unverify"):
            con.execute("UPDATE listings SET verified=?, verify_level=? WHERE id=?", (1 if action == "verify" else 0, 2 if action == "verify" else 0, lid))
        elif action in ("vip", "super", "boost", "clear_plan"):
            apply_plan(con, lid, action, s)
        else:
            return err("Unknown action")
        audit(con, u, action, "listing", lid, d.get("reason") or (f"level {d.get('level')}" if action == "level" else ""))
    return ok()


def apply_plan(con, lid, plan, s):
    now = time.time()
    row = con.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone()
    if plan == "clear_plan":
        con.execute("UPDATE listings SET vip_until=0, super_until=0, plan='free' WHERE id=?", (lid,))
        return
    days = s["plans"][plan]["days"]
    if plan == "boost":
        con.execute("UPDATE listings SET boosted_at=? WHERE id=?", (now, lid))
        return
    col = "super_until" if plan == "super" else "vip_until"
    start = max(now, row[col] or 0)
    until = start + days * 86400
    con.execute(f"UPDATE listings SET {col}=?, plan=?, boosted_at=?, expires=MAX(expires, ?) WHERE id=?",
                (until, plan, now, until, lid))


async def admin_reports(request):
    u, e = need_user(request, admin=True)
    if e:
        return e
    if request.method == "POST":
        d = await body_json(request)
        with _LOCK, db() as con:
            con.execute("UPDATE reports SET status='closed' WHERE id=?", (int(d.get("id") or 0),))
        return ok()
    with db() as con:
        rows = con.execute("""SELECT r.*, l.district, l.address, l.status AS listing_status FROM reports r
                              LEFT JOIN listings l ON l.id=r.listing_id ORDER BY (r.status='open') DESC, r.id DESC LIMIT 300""").fetchall()
    return ok(reports=[dict(r) for r in rows])


async def admin_orders(request):
    u, e = need_user(request, admin=True)
    if e:
        return e
    with db() as con:
        rows = con.execute("""SELECT o.*, u.name AS owner_name, u.phone AS owner_phone, l.district, l.address, l.status AS listing_status
                              FROM orders o LEFT JOIN users u ON u.id=o.user_id LEFT JOIN listings l ON l.id=o.listing_id
                              ORDER BY o.id DESC LIMIT 300""").fetchall()
    return ok(orders=[dict(r) for r in rows])


async def admin_order_action(request):
    u, e = need_user(request, admin=True)
    if e:
        return e
    oid = int(request.path_params["oid"])
    d = await body_json(request)
    action = d.get("action")
    s = get_settings()
    with _LOCK, db() as con:
        o = con.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
        if not o:
            return err("Not found", 404)
        if action == "paid" and o["status"] != "paid":
            apply_plan(con, o["listing_id"], o["plan"], s)
            con.execute("UPDATE orders SET status='paid', paid=?, note=? WHERE id=?", (time.time(), str(d.get("note") or "")[:200], oid))
        elif action == "cancel":
            con.execute("UPDATE orders SET status='cancelled', note=? WHERE id=?", (str(d.get("note") or "")[:200], oid))
        else:
            return err("Unknown action")
        audit(con, u, "order_" + action, "order", oid, f"{o['plan']} {o['amount']} {o['currency']} listing #{o['listing_id']}")
    return ok()


async def admin_users(request):
    u, e = need_user(request, admin=True)
    if e:
        return e
    if request.method == "POST":
        d = await body_json(request)
        uid = int(d.get("id") or 0)
        action = d.get("action")
        with _LOCK, db() as con:
            if action in ("block", "unblock"):
                con.execute("UPDATE users SET blocked=? WHERE id=? AND role!='admin'", (1 if action == "block" else 0, uid))
                if action == "block":
                    con.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
            elif action == "reset_password":
                pw = secrets.token_urlsafe(6)
                con.execute("UPDATE users SET pw=? WHERE id=? AND role!='admin'", (hash_pw(pw), uid))
                audit(con, u, "reset_password", "user", uid)
                return ok(password=pw)
            elif action in ("verify_contact", "unverify_contact"):
                on = action == "verify_contact"
                con.execute("UPDATE users SET contact_verified=? WHERE id=?", (1 if on else 0, uid))
                if on:
                    con.execute("UPDATE listings SET verify_level=1 WHERE user_id=? AND verify_level=0", (uid,))
            else:
                return err("Unknown action")
            audit(con, u, action, "user", uid)
        return ok()
    with db() as con:
        rows = con.execute("""SELECT u.id, u.phone, u.name, u.role, u.blocked, u.created, u.contact_verified, u.consent_at,
                                     (SELECT COUNT(*) FROM listings l WHERE l.user_id=u.id AND l.status!='deleted') AS listings
                              FROM users u ORDER BY u.id DESC LIMIT 1000""").fetchall()
    return ok(users=[dict(r) for r in rows])


async def admin_settings(request):
    u, e = need_user(request, admin=True)
    if e:
        return e
    s = get_settings()
    if request.method == "POST":
        d = await body_json(request)
        for p, cfg in (d.get("plans") or {}).items():
            if p in s["plans"]:
                for k in ("price", "days"):
                    if k in cfg:
                        try:
                            s["plans"][p][k] = max(0, float(cfg[k]) if k == "price" else int(cfg[k]))
                        except (TypeError, ValueError):
                            pass
        if "payment_info" in d:
            s["payment_info"] = str(d["payment_info"])[:1000]
        if "show_owner_phone" in d:
            s["show_owner_phone"] = bool(d["show_owner_phone"])
        for k in ("free_listing_limit", "reconfirm_days"):
            if k in d:
                try:
                    s[k] = max(0, min(1000, int(d[k])))
                except (TypeError, ValueError):
                    pass
        if d.get("currency") in CURRENCIES:
            s["currency"] = d["currency"]
        save_settings(s)
        with _LOCK, db() as con:
            audit(con, u, "settings", "settings", 0, json.dumps({k: d[k] for k in d if k != "payment_info"}, ensure_ascii=False)[:500])
    return ok(settings=s)



# ---------------------------------------------------------------- website chat (assistant + human agents)

def client_ip(request):
    return request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()


def msg_out(r):
    d = json.loads(r["data"] or "{}")
    return {"id": r["id"], "who": r["who"], "text": r["text"], "buttons": d.get("buttons", []), "cards": d.get("cards", []), "ts": r["ts"]}


def add_msg(con, chat_id, who, m):
    data = {k: m[k] for k in ("buttons", "cards") if m.get(k)}
    con.execute("INSERT INTO chat_msgs (chat_id, who, text, data, ts) VALUES (?,?,?,?,?)",
                (chat_id, who, str(m.get("text") or "")[:4000], json.dumps(data, ensure_ascii=False), time.time()))
    con.execute("UPDATE chats SET updated=? WHERE id=?", (time.time(), chat_id))


def load_chat(con, data):
    try:
        cid = int(data.get("chat_id") or 0)
    except (TypeError, ValueError):
        return None
    row = con.execute("SELECT * FROM chats WHERE id=?", (cid,)).fetchone()
    if not row or not hmac.compare_digest(row["token"], str(data.get("token") or "")):
        return None
    return row


def chat_payload(con, chat, after=0):
    rows = con.execute("SELECT * FROM chat_msgs WHERE chat_id=? AND id>? ORDER BY id", (chat["id"], after)).fetchall()
    return {"chat_id": chat["id"], "status": chat["status"], "messages": [msg_out(r) for r in rows]}


def send_crm_lead(payload):
    if not CRM_URL:
        return

    def run():
        try:
            req = urllib.request.Request(CRM_URL, json.dumps(payload).encode(), {"Content-Type": "text/plain;charset=utf-8"})
            urllib.request.urlopen(req, timeout=30).read()
        except Exception as ex:
            print("crm lead failed:", ex)
    threading.Thread(target=run, daemon=True).start()


def transcript(con, chat_id, n=8):
    rows = con.execute("SELECT who, text FROM chat_msgs WHERE chat_id=? AND who IN ('visitor','agent') ORDER BY id DESC LIMIT ?", (chat_id, n)).fetchall()
    return "\n".join(("👤 " if r["who"] == "visitor" else "🏢 ") + r["text"][:200] for r in reversed(rows))


async def chat_start(request):
    d = await body_json(request)
    with _LOCK, db() as con:
        chat = load_chat(con, d)
        if chat and chat["status"] != "closed":
            return ok(**chat_payload(con, chat), token=chat["token"])
    if too_many(request, "chatstart", 20, 600):
        return err("Too many chats, try later", 429)
    lang = d.get("lang") if d.get("lang") in ("en", "ka", "ru") else "ka"
    tok = secrets.token_urlsafe(24)
    now = time.time()
    with _LOCK, db() as con:
        cur = con.execute("INSERT INTO chats (token, lang, page, state, ip, created, updated) VALUES (?,?,?,?,?,?,?)",
                          (tok, lang, str(d.get("page") or "")[:300], json.dumps({"lang": lang}), client_ip(request), now, now))
        cid = cur.lastrowid
        add_msg(con, cid, "bot", chatbot.welcome(lang))
        chat = con.execute("SELECT * FROM chats WHERE id=?", (cid,)).fetchone()
        return ok(**chat_payload(con, chat), token=tok)


async def chat_send(request):
    d = await body_json(request)
    text = str(d.get("text") or "").strip()[:1000]
    if not text:
        return err("Empty message")
    if too_many(request, "chatsend", 40, 60):
        return err("Too many messages, slow down a little", 429)
    after = int(d.get("after") or 0)
    alert = None
    with _LOCK, db() as con:
        chat = load_chat(con, d)
        if not chat:
            return err("Chat not found", 404)
        shown = text
        if text.startswith("__"):
            shown = str(d.get("label") or "")[:200]
        if shown:
            add_msg(con, chat["id"], "visitor", {"text": shown})
        if chat["status"] in ("waiting", "agent"):
            con.execute("UPDATE chats SET unread=unread+1 WHERE id=?", (chat["id"],))
            if not text.startswith("__"):
                alert = f"💬 <b>Website chat #{chat['id']}</b> — {esc(chat['name'])} {esc(chat['phone'])}\n{esc(shown[:500])}\n\nReply: {SITE}/admin/#chats"
            if chat["status"] == "waiting":
                state = json.loads(chat["state"] or "{}")
                for m in chatbot.reply_waiting(con, state, text, get_settings(), SITE):
                    add_msg(con, chat["id"], "bot", m)
                con.execute("UPDATE chats SET state=? WHERE id=?", (json.dumps(state, ensure_ascii=False), chat["id"]))
        else:
            state = json.loads(chat["state"] or "{}")
            msgs, event = chatbot.reply(con, state, text, get_settings(), SITE)
            for m in msgs:
                add_msg(con, chat["id"], "bot", m)
            con.execute("UPDATE chats SET state=?, lang=? WHERE id=?", (json.dumps(state, ensure_ascii=False), state.get("lang", chat["lang"]), chat["id"]))
            if event == "handoff":
                con.execute("UPDATE chats SET status='waiting', name=?, phone=?, topic=?, unread=unread+1, consent_at=? WHERE id=?",
                            (state.get("name", ""), state.get("phone", ""), state.get("topic", ""), time.time(), chat["id"]))
                track(con, "lead_submitted", chat["page"], {"channel": "chat", "topic": state.get("topic", "")[:60]})
                tr = transcript(con, chat["id"])
                alert = (f"🙋 <b>Website chat #{chat['id']} — visitor wants an agent</b>\n"
                         f"Name: {esc(state.get('name'))}\nPhone: {esc(state.get('phone'))}\nTopic: {esc(state.get('topic'))}\n"
                         f"Language: {state.get('lang')}\nPage: {esc(chat['page'])}\n\n{esc(tr)}\n\nReply here: {SITE}/admin/#chats")
                send_crm_lead({"action": "lead", "type": "Website chat: " + state.get("topic", ""), "name": state.get("name", ""),
                               "phone": state.get("phone", ""), "message": tr[:1500], "lang": state.get("lang", "")})
        chat = con.execute("SELECT * FROM chats WHERE id=?", (chat["id"],)).fetchone()
        out = chat_payload(con, chat, after)
    if alert:
        notify(alert)
    return ok(**out)


async def chat_poll(request):
    q = request.query_params
    with db() as con:
        chat = load_chat(con, {"chat_id": q.get("chat_id"), "token": q.get("token")})
        if not chat:
            return err("Chat not found", 404)
        try:
            after = int(q.get("after") or 0)
        except ValueError:
            after = 0
        return ok(**chat_payload(con, chat, after))


async def admin_chats(request):
    u, e = need_user(request, admin=True)
    if e:
        return e
    st = request.query_params.get("status", "open")
    where = "status IN ('waiting','agent')" if st == "open" else "status='bot'" if st == "bot" else "status='closed'" if st == "closed" else "1=1"
    with db() as con:
        rows = con.execute(f"""SELECT c.*, (SELECT text FROM chat_msgs m WHERE m.chat_id=c.id AND m.who IN ('visitor','agent') ORDER BY id DESC LIMIT 1) AS last,
                               (SELECT COUNT(*) FROM chat_msgs m WHERE m.chat_id=c.id AND m.who='visitor') AS n
                               FROM chats c WHERE {where} ORDER BY (status='waiting') DESC, updated DESC LIMIT 200""").fetchall()
    out = []
    for r in rows:
        if st == "bot" and not r["n"]:
            continue
        d = dict(r)
        d.pop("token", None); d.pop("state", None)
        out.append(d)
    return ok(chats=out)


async def admin_chat(request):
    u, e = need_user(request, admin=True)
    if e:
        return e
    cid = int(request.path_params["cid"])
    with _LOCK, db() as con:
        chat = con.execute("SELECT * FROM chats WHERE id=?", (cid,)).fetchone()
        if not chat:
            return err("Chat not found", 404)
        if request.method == "POST":
            d = await body_json(request)
            act = d.get("action")
            if act == "reply":
                text = str(d.get("text") or "").strip()[:2000]
                if not text:
                    return err("Write a message")
                add_msg(con, cid, "agent", {"text": text})
                con.execute("UPDATE chats SET status='agent', unread=0 WHERE id=?", (cid,))
                audit(con, u, "chat_reply", "chat", cid)
            elif act == "close":
                lang = chat["lang"] or "en"
                add_msg(con, cid, "system", {"text": chatbot.T(lang, "The agent closed this chat. Write again any time!",
                                                               "აგენტმა ჩატი დახურა. მოგვწერეთ ნებისმიერ დროს!",
                                                               "Агент завершил чат. Пишите в любое время!")})
                con.execute("UPDATE chats SET status='closed', unread=0 WHERE id=?", (cid,))
            elif act == "take":
                con.execute("UPDATE chats SET status='agent' WHERE id=?", (cid,))
            elif act == "bot":
                con.execute("UPDATE chats SET status='bot', unread=0 WHERE id=?", (cid,))
            else:
                return err("Unknown action")
        else:
            con.execute("UPDATE chats SET unread=0 WHERE id=?", (cid,))
        chat = dict(con.execute("SELECT * FROM chats WHERE id=?", (cid,)).fetchone())
        msgs = [msg_out(r) for r in con.execute("SELECT * FROM chat_msgs WHERE chat_id=? ORDER BY id", (cid,)).fetchall()]
    chat.pop("token", None); chat.pop("state", None)
    return ok(chat=chat, messages=msgs)


# ---------------------------------------------------------------- analytics (first-party, anonymous) + audit log

TRACK_NAMES = {"page_view", "search_performed", "listing_click", "lead_submitted", "viewing_requested", "whatsapp_click", "call_click",
               "chat_opened", "chat_question", "valuation_requested", "share_click", "favorite_added", "partner_application"}


async def track_event(request):
    if too_many(request, "track", 120, 60):
        return ok()
    d = await body_json(request)
    name = str(d.get("name") or "")
    if name not in TRACK_NAMES:
        return err("unknown event")
    props = d.get("props") if isinstance(d.get("props"), dict) else {}
    props = {str(k)[:30]: (v if isinstance(v, (int, float)) else str(v)[:120]) for k, v in list(props.items())[:12]}
    ref = str(d.get("ref") or "")
    if ref:
        props["ref"] = urllib.parse.urlparse(ref).netloc[:80]
    with _LOCK, db() as con:
        track(con, name, str(d.get("page") or "")[:200], props, re.sub(r"[^a-zA-Z0-9]", "", str(d.get("sid") or ""))[:40] or "anon")
        con.execute("DELETE FROM events WHERE ts<?", (time.time() - 400 * 86400,))
    return ok()


async def admin_analytics(request):
    u, e = need_user(request, admin=True)
    if e:
        return e
    try:
        days = max(1, min(365, int(request.query_params.get("days", 30))))
    except ValueError:
        days = 30
    since = time.time() - days * 86400
    with db() as con:
        totals = {r[0]: r[1] for r in con.execute("SELECT name, COUNT(*) FROM events WHERE ts>? GROUP BY name", (since,))}
        visitors = con.execute("SELECT COUNT(DISTINCT sid) FROM events WHERE ts>? AND name='page_view'", (since,)).fetchone()[0]
        daily = [dict(r) for r in con.execute("""SELECT date(ts,'unixepoch','+4 hours') AS day,
                    COUNT(DISTINCT CASE WHEN name='page_view' THEN sid END) AS visitors,
                    SUM(name='page_view') AS views, SUM(name='search_performed') AS searches,
                    SUM(name IN ('lead_submitted','viewing_requested','valuation_requested')) AS leads,
                    SUM(name IN ('whatsapp_click','call_click')) AS contacts, SUM(name='chat_opened') AS chats
                    FROM events WHERE ts>? GROUP BY day ORDER BY day""", (since,))]
        pages = [dict(r) for r in con.execute("SELECT page, COUNT(*) AS n FROM events WHERE ts>? AND name='page_view' GROUP BY page ORDER BY n DESC LIMIT 10", (since,))]
        refs = [dict(r) for r in con.execute("""SELECT json_extract(props,'$.ref') AS ref, COUNT(*) AS n FROM events
                    WHERE ts>? AND name='page_view' AND json_extract(props,'$.ref') IS NOT NULL AND json_extract(props,'$.ref')!=''
                    GROUP BY ref ORDER BY n DESC LIMIT 10""", (since,))]
        searches = [dict(r) for r in con.execute("""SELECT COALESCE(json_extract(props,'$.district'),'') AS district, COALESCE(json_extract(props,'$.deal'),'') AS deal,
                    COUNT(*) AS n FROM events WHERE ts>? AND name='search_performed' GROUP BY district, deal ORDER BY n DESC LIMIT 10""", (since,))]
        listings = [dict(r) for r in con.execute("""SELECT json_extract(e.props,'$.listing_id') AS lid, COUNT(*) AS n, l.title, l.district, l.price, l.currency
                    FROM events e LEFT JOIN listings l ON l.id=json_extract(e.props,'$.listing_id')
                    WHERE e.ts>? AND e.name='listing_viewed' GROUP BY lid ORDER BY n DESC LIMIT 10""", (since,))]
    return ok(days=days, totals=totals, visitors=visitors, daily=daily, pages=pages, refs=refs, searches=searches, listings=listings)


async def admin_audit(request):
    u, e = need_user(request, admin=True)
    if e:
        return e
    with db() as con:
        rows = con.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 300").fetchall()
    return ok(log=[dict(r) for r in rows])


# ---------------------------------------------------------------- app

def ensure_admin():
    """First start: create the admin account from ADMIN_PHONE / ADMIN_PASSWORD (set by the installer)."""
    phone, pw = norm_phone(os.environ.get("ADMIN_PHONE", "")), os.environ.get("ADMIN_PASSWORD", "")
    if not phone or not pw:
        return
    with _LOCK, db() as con:
        row = con.execute("SELECT id FROM users WHERE phone=?", (phone,)).fetchone()
        if row:
            con.execute("UPDATE users SET role='admin' WHERE id=?", (row["id"],))
        else:
            con.execute("INSERT INTO users (phone, name, pw, role, created) VALUES (?,?,?,?,?)",
                        (phone, "KEY GROUP Admin", hash_pw(pw), "admin", time.time()))


async def health(request):
    return ok(service="keygroup-portal")


routes = [
    Route("/api/health", health),
    Route("/api/register", register, methods=["POST"]),
    Route("/api/login", login, methods=["POST"]),
    Route("/api/logout", logout, methods=["POST"]),
    Route("/api/me", me),
    Route("/api/password", change_password, methods=["POST"]),
    Route("/api/my/listings", my_listings, methods=["GET", "POST"]),
    Route("/api/my/listings/{lid:int}", my_listing, methods=["GET", "PUT", "DELETE"]),
    Route("/api/my/listings/{lid:int}/photos", listing_photos, methods=["POST", "PUT", "DELETE"]),
    Route("/api/my/listings/{lid:int}/order", order_plan, methods=["POST"]),
    Route("/api/listings", public_listings),
    Route("/api/listings/{lid:int}", public_listing),
    Route("/api/listings/{lid:int}/report", report_listing, methods=["POST"]),
    Route("/uploads/{name}", uploads),
    Route("/api/admin/reports", admin_reports, methods=["GET", "POST"]),
    Route("/api/admin/stats", admin_stats),
    Route("/api/admin/listings", admin_listings),
    Route("/api/admin/listings/{lid:int}", admin_listing_action, methods=["POST"]),
    Route("/api/admin/orders", admin_orders),
    Route("/api/admin/orders/{oid:int}", admin_order_action, methods=["POST"]),
    Route("/api/admin/users", admin_users, methods=["GET", "POST"]),
    Route("/api/admin/settings", admin_settings, methods=["GET", "POST"]),
    Route("/api/chat/start", chat_start, methods=["POST"]),
    Route("/api/track", track_event, methods=["POST"]),
    Route("/api/admin/analytics", admin_analytics),
    Route("/api/admin/audit", admin_audit),
    Route("/api/my/listings/{lid:int}/confirm", confirm_listing, methods=["POST"]),
    Route("/api/chat/send", chat_send, methods=["POST"]),
    Route("/api/chat/poll", chat_poll),
    Route("/api/admin/chats", admin_chats),
    Route("/api/admin/chats/{cid:int}", admin_chat, methods=["GET", "POST"]),
]

init_db()
ensure_admin()
app = Starlette(routes=routes)
