"""KEY GROUP owner portal — owners list their property for sale or rent on keygroup.ge.

Accounts: phone + password (no SMS). Every new or edited listing waits for admin approval.
Plans: Free (30 days), VIP, Super VIP (top of the list for N days, badge) and Boost (one bump to the top).
Payment is manual for now: the owner orders a plan, pays by bank transfer / cash, the admin marks the
order paid and the plan starts. Data lives in SQLite + photo files under DATA_DIR.
"""
import asyncio
import base64
import csv
import struct
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
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route

import chatbot

DATA_DIR = os.environ.get("DATA_DIR", "/data")
UPLOADS = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "portal.db")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ALERT_CHATS = [c.strip() for c in os.environ.get("ALERT_CHATS", "").split(",") if c.strip()]
SITE = os.environ.get("SITE_URL", "https://keygroup.ge")
CRM_URL = os.environ.get("CRM_URL", "")
CRM_SECRET = os.environ.get("CRM_SECRET", "")
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
    "role_limits": {"agent": 50, "agency": 200, "developer": 300},
    "founding_days": 90,
    "reconfirm_days": 15,
}
CONSENT_VERSION = "2026-11-01"
PARTNER_ROLES = ("agent", "agency", "developer")
STAFF_ROLES = ("admin", "moderator", "finance")
ROLES = ("owner",) + PARTNER_ROLES + STAFF_ROLES
# what each staff role may open in the admin panel ("*" = everything)
STAFF_PERMS = {"admin": {"*"}, "moderator": {"stats", "listings", "reports", "chats", "leads", "partners", "analytics", "crm"},
               "finance": {"stats", "orders", "analytics"}}
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
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY, listing_id INTEGER, owner_id INTEGER, name TEXT, phone TEXT, message TEXT, source TEXT,
            consent_at REAL DEFAULT 0, stage TEXT DEFAULT 'new', note TEXT DEFAULT '', created REAL, updated REAL);
        CREATE INDEX IF NOT EXISTS idx_leads_owner ON leads(owner_id);
        CREATE TABLE IF NOT EXISTS partner_apps (
            id INTEGER PRIMARY KEY, user_id INTEGER DEFAULT 0, name TEXT, company TEXT, phone TEXT, email TEXT, ptype TEXT, city TEXT,
            listings_est TEXT, website TEXT, message TEXT, status TEXT DEFAULT 'new', consent_at REAL DEFAULT 0, created REAL, decided REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY, user_id INTEGER, name TEXT, city TEXT, district TEXT, address TEXT, description TEXT,
            completion TEXT, status TEXT DEFAULT 'active', lat REAL DEFAULT 0, lon REAL DEFAULT 0, cover TEXT DEFAULT '', created REAL, updated REAL);
        CREATE TABLE IF NOT EXISTS login_tokens (token TEXT PRIMARY KEY, user_id INTEGER, expires REAL, used REAL DEFAULT 0, purpose TEXT DEFAULT 'login');
        CREATE TABLE IF NOT EXISTS bot_outbox (id INTEGER PRIMARY KEY, tg_id TEXT, text TEXT, button_url TEXT DEFAULT '', button_text TEXT DEFAULT '', created REAL, sent REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS publish_codes (code TEXT PRIMARY KEY, listing_id INTEGER, user_id INTEGER, expires REAL, used INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS ext_posts (
            id INTEGER PRIMARY KEY, listing_id INTEGER, site TEXT, ext_id TEXT, url TEXT DEFAULT '', promo TEXT DEFAULT '',
            account TEXT DEFAULT '', user_id INTEGER, source TEXT DEFAULT '', created REAL, UNIQUE(listing_id, site));
        CREATE TABLE IF NOT EXISTS imports (
            id INTEGER PRIMARY KEY, user_id INTEGER, filename TEXT, total INTEGER, imported INTEGER, errors TEXT DEFAULT '[]',
            status TEXT DEFAULT 'imported', created REAL);
        """)
        for table, col, typ in (("users", "consent_at", "REAL DEFAULT 0"), ("users", "consent_ver", "TEXT DEFAULT ''"),
                                ("users", "contact_verified", "INTEGER DEFAULT 0"),
                                ("listings", "verify_level", "INTEGER DEFAULT 0"), ("listings", "confirmed", "REAL DEFAULT 0"),
                                ("listings", "dup_of", "TEXT DEFAULT ''"), ("listings", "photo_hashes", "TEXT DEFAULT '{}'"),
                                ("chats", "consent_at", "REAL DEFAULT 0"),
                                ("users", "company", "TEXT DEFAULT ''"), ("users", "partner_until", "REAL DEFAULT 0"),
                                ("users", "listing_limit", "INTEGER DEFAULT 0"), ("users", "totp_secret", "TEXT DEFAULT ''"),
                                ("users", "totp_on", "INTEGER DEFAULT 0"), ("listings", "batch_id", "INTEGER DEFAULT 0"),
                                ("listings", "lat", "REAL DEFAULT 0"), ("listings", "lon", "REAL DEFAULT 0"),
                                ("listings", "project_id", "INTEGER DEFAULT 0"), ("listings", "building", "TEXT DEFAULT ''"),
                                ("listings", "unit_no", "TEXT DEFAULT ''"), ("users", "org_id", "INTEGER DEFAULT 0"),
                                ("leads", "viewing_at", "REAL DEFAULT 0"), ("leads", "assigned_to", "INTEGER DEFAULT 0"),
                                ("leads", "first_action_at", "REAL DEFAULT 0"),
                                ("listings", "video_url", "TEXT DEFAULT ''"), ("listings", "price_history", "TEXT DEFAULT '[]'"),
                                ("listings", "prev_price", "REAL DEFAULT 0"), ("listings", "price_drop_at", "REAL DEFAULT 0"),
                                ("projects", "frame", "TEXT DEFAULT ''"), ("projects", "handover", "TEXT DEFAULT ''"),
                                ("projects", "down_pct", "REAL DEFAULT 0"), ("projects", "inst_months", "INTEGER DEFAULT 0"),
                                ("projects", "inst_note", "TEXT DEFAULT ''"), ("listings", "source_url", "TEXT DEFAULT ''"),
                                ("listings", "agent_name", "TEXT DEFAULT ''"), ("users", "slug", "TEXT DEFAULT ''"),
                                ("users", "links", "TEXT DEFAULT '{}'"), ("users", "pw_set", "INTEGER DEFAULT 1"),
                                ("login_tokens", "purpose", "TEXT DEFAULT 'login'"), ("publish_codes", "promo", "TEXT DEFAULT ''"), ("users", "tg_id", "TEXT DEFAULT ''"), ("users", "email", "TEXT DEFAULT ''"), ("users", "bio", "TEXT DEFAULT ''"), ("users", "last_login", "REAL DEFAULT 0")):
            have = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
            if col not in have:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        con.execute("UPDATE listings SET verify_level=2 WHERE verified=1 AND verify_level=0")
        con.execute("UPDATE listings SET confirmed=COALESCE(NULLIF(approved,0), created) WHERE confirmed=0")
        # listings imported from a MyHome / SS link before ext_posts existed: remember where they came from
        for r in con.execute("SELECT l.id, l.user_id, l.source_url FROM listings l WHERE l.source_url!='' AND l.status!='deleted' "
                             "AND NOT EXISTS (SELECT 1 FROM ext_posts x WHERE x.listing_id=l.id)").fetchall():
            xs, xid = ext_from_url(r["source_url"])
            if xs:
                save_ext(con, r["id"], xs, xid, r["user_id"], source="import", url=r["source_url"].split("?")[0])


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
            elif k == "role_limits" and isinstance(v, dict):
                s["role_limits"].update(v)
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


def need_user(request, admin=False, perm=None):
    """admin=True -> full admin only; perm='listings' etc. -> admin or a staff role allowed to do that."""
    u = current_user(request)
    if not u:
        return None, err("Please log in", 401)
    if admin and u["role"] != "admin":
        return None, err("Admins only", 403)
    if perm:
        perms = STAFF_PERMS.get(u["role"], set())
        if "*" not in perms and perm not in perms:
            return None, err("Your staff role cannot open this", 403)
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


def listing_limit(u, s=None):
    s = s or get_settings()
    if u.get("listing_limit"):
        return int(u["listing_limit"])
    if u["role"] in PARTNER_ROLES:
        return int(s["role_limits"].get(u["role"], 50))
    return int(s.get("free_listing_limit", 2) or 0)


def live_count(con, uid):
    now = time.time()
    return con.execute("""SELECT COUNT(*) FROM listings WHERE user_id=? AND status IN ('pending','active','paused','changes')
                          AND vip_until<? AND super_until<?""", (uid, now, now)).fetchone()[0]


# ---- TOTP (RFC 6238) for admin 2-step login
def totp_code(secret_b32, t=None, step=30):
    key = base64.b32decode(secret_b32.upper() + "=" * (-len(secret_b32) % 8))
    counter = int((t or time.time()) // step)
    h = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    o = h[-1] & 15
    return "%06d" % ((struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % 1000000)


def totp_ok(secret_b32, code):
    code = re.sub(r"\D", "", str(code or ""))
    if len(code) != 6 or not secret_b32:
        return False
    now = time.time()
    return any(hmac.compare_digest(totp_code(secret_b32, now + d * 30), code) for d in (-1, 0, 1))


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
    try:
        d["price_history"] = json.loads(d.get("price_history") or "[]")[-12:]
    except ValueError:
        d["price_history"] = []
    pp, pd = d.pop("prev_price", 0) or 0, d.pop("price_drop_at", 0) or 0
    d["price_drop"] = None
    if pp and d.get("price") and d["price"] < pp and pd > time.time() - 45 * 86400:
        d["price_drop"] = {"from": pp, "pct": round((pp - d["price"]) / pp * 100), "at": pd}
    if not admin_view:
        d.pop("dup_of", None)
        d.pop("source_url", None)
    if not (owner_view or admin_view) and d.get("lat"):
        d["lat"], d["lon"] = round(d["lat"], 3), round(d["lon"], 3)   # ~100 m: never publish an exact door location
    if not (owner_view or admin_view or settings.get("show_owner_phone")):
        d["contact_phone"] = ""
        d["contact_name"] = (d.get("contact_name") or "").split(" ")[0]
    if not admin_view:
        d.pop("user_id", None)
    return d


def check_project(con, u, f):
    if f.get("project_id"):
        p = con.execute("SELECT user_id FROM projects WHERE id=? AND status!='deleted'", (f["project_id"],)).fetchone()
        if not p or (p["user_id"] != u["id"] and u["role"] != "admin"):
            f["project_id"] = 0


_VIDEO_RE = re.compile(r"^https://(www\.|m\.)?(youtube\.com/(watch\?v=|shorts/|embed/)|youtu\.be/|vimeo\.com/)[\w\-?=&/.]{4,120}$")


def clean_video(v):
    v = str(v or "").strip()[:200]
    return v if _VIDEO_RE.match(v) else ""


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
        "lat": num("lat"), "lon": num("lon"), "building": s("building", 40), "unit_no": s("unit_no", 40),
        "project_id": num("project_id", int), "video_url": clean_video(data.get("video_url")),
    }
    if not (41.0 <= f["lat"] <= 43.7 and 40.0 <= f["lon"] <= 46.8):   # inside Georgia, else drop
        f["lat"], f["lon"] = 0, 0
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
    if u["totp_on"]:
        if not d.get("code"):
            return JSONResponse({"ok": False, "need_code": True, "error": "Enter the 6-digit code from your authenticator app"}, status_code=401)
        if not totp_ok(u["totp_secret"], d.get("code")):
            return JSONResponse({"ok": False, "need_code": True, "error": "Wrong code — check the time on your phone and try again"}, status_code=401)
    with _LOCK, db() as con:
        con.execute("UPDATE users SET last_login=? WHERE id=?", (time.time(), u["id"]))
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
    out = {k: u[k] for k in ("id", "name", "phone", "role", "company", "partner_until", "totp_on", "org_id", "slug", "pw_set")}
    out["limit"] = listing_limit(u)
    with db() as con:
        out["live"] = live_count(con, u["id"])
        ids = team_ids(con, u)
        out["new_leads"] = con.execute(f"SELECT COUNT(*) FROM leads WHERE owner_id IN ({','.join('?' * len(ids))}) AND stage='new'", ids).fetchone()[0]
    return ok(user=out, settings=public_settings())


async def change_password(request):
    u, e = need_user(request)
    if e:
        return e
    d = await body_json(request)
    if u.get("pw_set", 1) and not check_pw(str(d.get("old") or ""), u["pw"]):   # an agent opening the bot link sets the first one freely
        return err("Current password is wrong")
    if len(str(d.get("new") or "")) < 6:
        return err("New password must be at least 6 characters")
    with _LOCK, db() as con:
        con.execute("UPDATE users SET pw=?, pw_set=1 WHERE id=?", (hash_pw(str(d["new"])), u["id"]))
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
        limit = listing_limit(u, s)
        with _LOCK, db() as con:
            if limit and u["role"] != "admin":
                n = live_count(con, u["id"])
                if n >= limit:
                    if u["role"] in PARTNER_ROLES:
                        return err(f"Your plan allows {limit} active listings. Contact KEY GROUP to raise the limit.")
                    return err(f"A free account can have up to {limit} active listings. Delete or promote one (VIP), or join as an agent / agency partner.")
            check_project(con, u, f)
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
        ids = team_ids(con, u)
        rows = con.execute(f"""SELECT l.*, u.name AS agent_name FROM listings l LEFT JOIN users u ON u.id=l.user_id
                               WHERE l.user_id IN ({','.join('?' * len(ids))}) AND l.status!='deleted' ORDER BY l.id DESC""", ids).fetchall()
        orders = con.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 50", (u["id"],)).fetchall()
        ext = ext_map(con, [r["id"] for r in rows])
    s = get_settings()
    out = [listing_out(r, owner_view=True, settings=s) for r in rows]
    for o in out:
        o["ext"] = ext.get(o["id"], {})
    return ok(listings=out, orders=[dict(o) for o in orders])


def record_price(con, row, new_price, new_cur):
    """Keep a short price history; a cut in the same currency shows a 'price reduced' badge for 45 days."""
    old, cur = row["price"] or 0, row["currency"]
    if not old or (old == new_price and cur == new_cur):
        return
    now = time.time()
    try:
        hist = json.loads(row["price_history"] or "[]")
    except (ValueError, IndexError, KeyError):
        hist = []
    if not hist:
        hist.append({"p": old, "c": cur, "t": row["approved"] or row["created"] or now})
    hist.append({"p": new_price, "c": new_cur, "t": now})
    if new_cur == cur and new_price < old:
        con.execute("UPDATE listings SET price_history=?, prev_price=?, price_drop_at=? WHERE id=?", (json.dumps(hist[-20:]), old, now, row["id"]))
    else:
        con.execute("UPDATE listings SET price_history=?, prev_price=0, price_drop_at=0 WHERE id=?", (json.dumps(hist[-20:]), row["id"]))


def own_listing(u, lid, con):
    row = con.execute("SELECT * FROM listings WHERE id=? AND status!='deleted'", (lid,)).fetchone()
    if not row:
        return None
    if row["user_id"] != u["id"] and u["role"] != "admin" and row["user_id"] not in team_ids(con, u):
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
    with _LOCK, db() as con:
        check_project(con, u, f)
        sets = ",".join(f"{k}=?" for k in f)
        # an edit goes back to the approval queue (admins' own edits stay live)
        kg_agent = u["role"] == "agent" and (u.get("company") or "").upper() == "KEY GROUP"
        status = row["status"] if (u["role"] == "admin" or (kg_agent and row["status"] == "active")) else ("pending" if row["status"] in ("active", "rejected", "changes") else row["status"])
        con.execute(f"UPDATE listings SET {sets}, status=?, updated=?, confirmed=? WHERE id=?", (*f.values(), status, time.time(), time.time(), lid))
        record_price(con, row, f["price"], f["currency"])
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


# ---------------------------------------------------------------- market comparison, trusted agents

def norm_district(d):
    d = str(d or "").strip()
    if not d or d.startswith("#"):
        return ""
    low = d.lower()
    for en, ka, words in chatbot.DISTRICTS:
        if d == ka or low == en.lower() or any(w.strip() and w.strip() in low for w in words):
            return en.lower()
    return low


_CRM_TYPE = {"Flat": "flat", "House": "house", "Commercial": "commercial", "Land": "land"}


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    return 0 if not n else (xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2)


def market_pool(con):
    """(deal, type, currency, district, city, price_per_m2) for every active listing with an area — ours + KEY GROUP CRM."""
    pool = []
    for r in con.execute("SELECT deal, type, currency, district, city, price, area FROM listings WHERE status='active' AND area>5 AND price>0"):
        pool.append((r["deal"], r["type"], r["currency"], norm_district(r["district"]), (r["city"] or "tbilisi").lower(), r["price"] / r["area"]))
    for r in chatbot._crm_listings():
        try:
            area, price = float(r.get("area") or 0), float(r.get("price") or 0)
        except (TypeError, ValueError):
            continue
        if area > 5 and price > 0:
            city = "batumi" if "ბათუმ" in str(r.get("city") or "") + str(r.get("d") or "") or "atumi" in str(r.get("city") or "") else "tbilisi"
            pool.append(("rent" if r.get("deal") == "Rent" else "sale", _CRM_TYPE.get(r.get("cat"), "flat"), r.get("cur") or "USD",
                         norm_district(r.get("d")), city, price / area))
    return pool


def market_for(con, l, pool=None):
    """Median asking price per m² for comparable listings (same district, else same city)."""
    if not l.get("area") or l["deal"] not in ("sale", "rent"):
        return None
    pool = pool if pool is not None else market_pool(con)
    dist, city = norm_district(l.get("district")), (l.get("city") or "tbilisi").lower()

    def med(deal, scope):
        xs = [x[5] for x in pool if x[0] == deal and x[1] == l["type"] and x[2] == l["currency"] and (x[3] == dist if scope == "district" else x[4] == city)]
        return (_median(xs), len(xs)) if len(xs) >= (3 if scope == "district" else 5) else (0, len(xs))
    out = {"currency": l["currency"]}
    for scope in ("district", "city"):
        m, n = med(l["deal"], scope) if (scope == "city" or dist) else (0, 0)
        if m:
            ppm = l["price"] / l["area"]
            out.update(scope=scope, median_ppm=round(m, 1), n=n, diff_pct=round((ppm - m) / m * 100))
            break
    if l["deal"] == "sale":
        for scope in ("district", "city"):
            m, n = med("rent", scope) if (scope == "city" or dist) else (0, 0)
            if m:
                out.update(rent_ppm=round(m, 2), rent_n=n, rent_scope=scope)
                break
    return out if len(out) > 1 else None


TRUSTED_RULES = {"min_listings": 3, "min_verified_share": 0.6, "min_leads": 3, "max_avg_hours": 4, "min_answered_share": 0.8, "max_open_reports": 0, "days": 90}
_TRUST_CACHE = {"at": 0, "data": {}}


def agent_stats(con, uid):
    since = time.time() - TRUSTED_RULES["days"] * 86400
    l = con.execute("SELECT COUNT(*) AS n, SUM(verify_level>=2) AS v FROM listings WHERE user_id=? AND status='active'", (uid,)).fetchone()
    d = con.execute("""SELECT COUNT(*) AS n, SUM(first_action_at>0) AS answered,
                              AVG(CASE WHEN first_action_at>0 THEN (first_action_at-created)/3600.0 END) AS hours
                       FROM leads WHERE COALESCE(NULLIF(assigned_to,0), owner_id)=? AND created>?""", (uid, since)).fetchone()
    rep = con.execute("""SELECT COUNT(*) FROM reports r JOIN listings x ON x.id=r.listing_id
                         WHERE x.user_id=? AND r.status='open' AND r.created>?""", (uid, since)).fetchone()[0]
    st = {"listings": l["n"] or 0, "verified": l["v"] or 0, "leads": d["n"] or 0, "answered": d["answered"] or 0,
          "avg_hours": round(d["hours"], 1) if d["hours"] is not None else None, "open_reports": rep}
    R = TRUSTED_RULES
    st["checks"] = {
        "listings": st["listings"] >= R["min_listings"],
        "verified": st["listings"] > 0 and st["verified"] / st["listings"] >= R["min_verified_share"],
        "response": st["leads"] >= R["min_leads"] and st["avg_hours"] is not None and st["avg_hours"] <= R["max_avg_hours"]
                    and st["answered"] / max(st["leads"], 1) >= R["min_answered_share"],
        "reports": rep <= R["max_open_reports"],
    }
    st["trusted"] = all(st["checks"].values())
    return st


def trusted_map(con):
    """{user_id: True} for partner accounts that pass every Trusted Agent check (refreshed every 10 minutes)."""
    if time.time() - _TRUST_CACHE["at"] > 600:
        ids = [r[0] for r in con.execute(f"SELECT id FROM users WHERE blocked=0 AND role IN ({','.join('?' * len(PARTNER_ROLES))})", PARTNER_ROLES)]
        _TRUST_CACHE["data"] = {i: True for i in ids if agent_stats(con, i)["trusted"]}
        _TRUST_CACHE["at"] = time.time()
    return _TRUST_CACHE["data"]


def attach_agents(con, rows, outs):
    """Public listings by partner accounts get a link to the agent profile and the Trusted badge."""
    uids = {r["user_id"] for r in rows if r["user_id"]}
    if not uids:
        return
    users = {u["id"]: u for u in con.execute(f"SELECT id, name, company, role, slug FROM users WHERE id IN ({','.join('?' * len(uids))})", tuple(uids))}
    tm = trusted_map(con)
    for r, o in zip(rows, outs):
        u = users.get(r["user_id"])
        if u and u["role"] in PARTNER_ROLES:
            kg = (u["company"] or "").upper() == "KEY GROUP" and u["role"] == "agent"
            o["agent"] = {"id": u["id"], "name": (u["name"] + " · KEY GROUP") if kg else (u["company"] or u["name"]), "role": u["role"],
                          "trusted": bool(tm.get(u["id"])), "slug": u["slug"] or ""}
            if u["slug"]:
                o["path"] = f"/{u['slug']}/{listing_slug(o)}-{o['id']}"
            if kg:   # KEY GROUP agents: their own business number is the contact (never the owner's)
                o["contact_phone"], o["contact_name"] = r["contact_phone"], u["name"]


async def public_agent(request):
    """Public agent / agency / developer profile, or (no id) the Trusted Agent rules and the list of trusted partners."""
    aid = request.query_params.get("id", "")
    slug = request.query_params.get("slug", "").strip().lower()[:40]
    with db() as con:
        if slug and not aid.isdigit():
            r = con.execute("SELECT id FROM users WHERE slug=?", (slug,)).fetchone()
            if not r:
                return err("Profile not found", 404)
            aid = str(r["id"])
        if not aid.isdigit():
            tm = trusted_map(con)
            rows = con.execute(f"SELECT id, name, company, role FROM users WHERE id IN ({','.join('?' * len(tm)) or '0'})", tuple(tm)).fetchall()
            return ok(rules=TRUSTED_RULES, trusted=[{"id": r["id"], "name": r["company"] or r["name"], "role": r["role"]} for r in rows])
        u = con.execute("SELECT id, name, company, role, created, blocked, slug, links, phone, bio FROM users WHERE id=?", (int(aid),)).fetchone()
        if not u or u["blocked"] or u["role"] not in PARTNER_ROLES:
            return err("Profile not found", 404)
        st = agent_stats(con, u["id"])
        rows = con.execute("SELECT * FROM listings WHERE user_id=? AND status='active' ORDER BY MAX(boosted_at, approved) DESC LIMIT 60", (u["id"],)).fetchall()
        s = get_settings()
        st.pop("open_reports", None)
        kg = (u["company"] or "").upper() == "KEY GROUP" and u["role"] == "agent"
        try:
            links = json.loads(u["links"] or "{}")
        except ValueError:
            links = {}
        outs = [listing_out(r, settings=s) for r in rows]
        attach_agents(con, rows, outs)
        return ok(agent={"id": u["id"], "name": u["name"] if kg else (u["company"] or u["name"]), "person": "" if kg else (u["name"] if u["company"] else ""),
                         "company": "KEY GROUP" if kg else "", "role": u["role"], "since": u["created"], "slug": u["slug"] or "", "links": links,
                         "phone": u["phone"] if kg else "", "bio": u["bio"] or "", **st}, rules=TRUSTED_RULES, listings=outs)


# ---------------------------------------------------------------- staff Telegram bot -> KEY GROUP listing on the website

KA_LAT = dict(zip("აბგდევზთიკლმნოპჟრსტუფქღყშჩცძწჭხჯჰ",
                  ["a", "b", "g", "d", "e", "v", "z", "t", "i", "k", "l", "m", "n", "o", "p", "zh", "r", "s", "t", "u", "p", "k", "gh", "q",
                   "sh", "ch", "ts", "dz", "ts", "ch", "kh", "j", "h"]))
RESERVED_SLUGS = {"account", "admin", "agent", "api", "assets", "batumi", "compare", "invest-in-georgia", "ka", "ru", "en", "p", "partners",
                  "privacy", "project", "search", "tbilisi", "uploads", "img", "_staging", "kutaisi"}


def slugify(text, n=60):
    t = "".join(KA_LAT.get(ch, ch) for ch in str(text or "").lower())
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:n].strip("-")


def unique_slug(con, base, uid=0):
    base = slugify(base, 30) or "agent"
    slug, n = base, 1
    while slug in RESERVED_SLUGS or con.execute("SELECT 1 FROM users WHERE slug=? AND id!=?", (slug, uid)).fetchone():
        n += 1
        slug = f"{base}-{n}"
    return slug


def listing_slug(d):
    deal = {"sale": "sale", "rent": "rent", "daily": "daily-rent"}.get(d.get("deal"), "")
    typ = {"flat": "apartment", "house": "house", "commercial": "commercial", "land": "land", "hotel": "hotel"}.get(d.get("type"), "")
    rooms = f"{int(d['rooms'])}-room" if d.get("rooms") else ""
    return slugify(" ".join(x for x in (deal, rooms, typ, d.get("district") or d.get("city")) if x), 70) or "listing"


def agent_user(con, name, phone, links=None):
    """KEY GROUP agent account for the Telegram bot: found by phone, created on first listing (role agent, no password login)."""
    phone = norm_phone(phone)
    if len(phone) < 12:
        return None
    u = con.execute("SELECT * FROM users WHERE phone=?", (phone,)).fetchone()
    if u and u["role"] not in PARTNER_ROLES:   # never turn an admin / owner / staff account into an agent profile
        return None
    if not u:
        cur = con.execute("INSERT INTO users (phone, name, pw, role, company, created, contact_verified, pw_set) VALUES (?,?,?,?,?,?,1,0)",
                          (phone, name or "Agent", hash_pw(secrets.token_urlsafe(16)), "agent", "KEY GROUP", time.time()))
        u = con.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
    if not u["slug"]:
        con.execute("UPDATE users SET slug=? WHERE id=?", (unique_slug(con, name or u["name"], u["id"]), u["id"]))
    if links:
        try:
            cur_links = json.loads(u["links"] or "{}")
        except ValueError:
            cur_links = {}
        cur_links.update({k: v for k, v in links.items() if isinstance(v, str) and v.startswith("https://") and k in ("myhome", "ss")})
        con.execute("UPDATE users SET links=? WHERE id=?", (json.dumps(cur_links), u["id"]))
    return con.execute("SELECT * FROM users WHERE id=?", (u["id"],)).fetchone()


PHOTO_HOSTS = ("static.my.ge", "myhome.ge", "ss.ge", "static.ss.ge", "tnet.ge")
CITY_KA = {"თბილისი": "Tbilisi", "ბათუმი": "Batumi", "ქუთაისი": "Kutaisi"}


def bot_photo(url):
    """Download one listing photo from the MyHome / SS.ge image servers only (no other hosts)."""
    try:
        host = (urllib.parse.urlparse(url).hostname or "").lower()
        if not url.startswith("https://") or not any(host == h or host.endswith("." + h) for h in PHOTO_HOSTS):
            return ""
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 KEYGROUP"})
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read(12 * 1024 * 1024)
        return save_photo(raw)
    except Exception:
        return ""


async def bot_listing(request):
    """The staff Telegram bot posts a listing after the agent confirmed the owner's consent.
    It goes live at once under KEY GROUP (company phone, never the owner's), verified level 2."""
    sec = request.headers.get("x-bot-secret", "")
    if not CRM_SECRET or not hmac.compare_digest(sec, CRM_SECRET):
        return err("unauthorized", 401)
    uploads = []
    if request.headers.get("content-type", "").startswith("multipart/"):
        form_ = await request.form()
        try:
            d = json.loads(form_.get("data") or "{}")
        except ValueError:
            return err("bad data")
        for up in form_.getlist("photos")[:15]:
            uploads.append(await up.read())
    else:
        d = await body_json(request)
    st = get_settings()
    deal = {"pledge": "rent"}.get(d.get("deal"), d.get("deal"))
    price, cur = d.get("price_usd") or d.get("price"), "USD" if d.get("price_usd") else (str(d.get("currency") or "USD").upper())
    cur = {"$": "USD", "₾": "GEL", "€": "EUR", "LARI": "GEL"}.get(cur, cur)
    dist = str(d.get("district") or "").strip()
    city = str(d.get("city") or "").strip()
    agent = str(d.get("agent") or "").strip()[:40]
    form = {
        "deal": deal, "type": d.get("type") if d.get("type") in TYPES else "flat", "city": CITY_KA.get(city, city) or "Tbilisi",
        "district": chatbot.KA_TO_EN.get(dist, dist), "address": d.get("address"), "rooms": d.get("rooms"), "bedrooms": d.get("bedrooms"),
        "area": d.get("area"), "floor": d.get("floor"), "total_floors": d.get("total_floors"), "price": price, "currency": cur,
        "title": d.get("title"), "description": d.get("description"),
        "contact_name": ("KEY GROUP" + (" · " + agent if agent else ""))[:80],
        "contact_phone": norm_phone(d.get("contact_phone")) if len(norm_phone(d.get("contact_phone"))) >= 12 else (st.get("company_phone") or "+995577114118"),
        "video_url": d.get("video_url"), "lat": d.get("lat"), "lon": d.get("lon"),
    }
    f, msg = clean_listing(form)
    if msg:
        return err(msg)
    src = str(d.get("url") or "").split("?")[0][:300]
    with _LOCK, db() as con:
        owner = agent_user(con, agent, d.get("contact_phone"), d.get("profiles") or {}) if d.get("contact_phone") else None
        if owner and str(d.get("tg") or "").isdigit():
            con.execute("UPDATE users SET tg_id=? WHERE id=?", (str(d["tg"]), owner["id"]))
        if not owner:
            owner = con.execute("SELECT id FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone()
        old = con.execute("SELECT id FROM listings WHERE source_url=? AND source_url!='' AND status!='deleted'", (src,)).fetchone() if src else None
        if not old and src:   # same MyHome / SS listing reached by another link form (/pr/123/ vs /udzravi-qoneba/...-123/)
            xs_, xid_ = ext_from_url(src)
            if xs_:
                old = con.execute("SELECT l.id FROM ext_posts x JOIN listings l ON l.id=x.listing_id WHERE x.site=? AND x.ext_id=? "
                                  "AND l.status!='deleted' ORDER BY l.id LIMIT 1", (xs_, xid_)).fetchone()
    if not owner:
        return err("no admin account", 500)
    adm = owner
    photos = []
    loop = asyncio.get_running_loop()
    for raw in uploads:   # originals sent by the agent; the website keeps web-size copies
        try:
            photos.append(await loop.run_in_executor(None, save_photo, raw))
        except Exception:
            pass
    want_photos = [str(x) for x in (d.get("photos") or [])][:12]
    if old and d.get("own") and want_photos:      # daily re-sync of the agent's own listing: keep photos we already have
        with db() as con:
            have = json.loads((con.execute("SELECT photos FROM listings WHERE id=?", (old["id"],)).fetchone() or {"photos": "[]"})["photos"] or "[]")
        if len(have) == len(want_photos):
            want_photos = []
    if d.get("with_photos") and not photos:
        for u in want_photos:
            name = await loop.run_in_executor(None, bot_photo, u)
            if name:
                photos.append(name)
    now = time.time()
    exp = now + st["plans"]["free"]["days"] * 86400
    with _LOCK, db() as con:
        if old:
            lid = old["id"]
            sets = ",".join(f"{k}=?" for k in f)
            con.execute(f"UPDATE listings SET {sets}, status='active', updated=?, confirmed=?, agent_name=?, user_id=? WHERE id=?", (*f.values(), now, now, agent, adm["id"], lid))
            if photos:
                con.execute("UPDATE listings SET photos=? WHERE id=?", (json.dumps(photos), lid))
        else:
            cols = ",".join(f.keys())
            cur_ = con.execute(f"""INSERT INTO listings (user_id,{cols},status,created,updated,approved,expires,confirmed,verify_level,photos,source_url,agent_name)
                                   VALUES (?,{','.join('?' * len(f))},'active',?,?,?,?,?,2,?,?,?)""",
                               (adm["id"], *f.values(), now, now, now, exp, now, json.dumps(photos), src, agent))
            lid = cur_.lastrowid
        find_duplicates(con, lid)
        xs, xid = ext_from_url(src)
        if xs:   # "agent" = the agent's own listing on their MyHome / SS account; "import" = copied from someone else's link
            save_ext(con, lid, xs, xid, adm["id"], source="agent" if d.get("own") else "import", url=src)
        audit(con, {"id": 0, "name": "Telegram bot · " + agent}, "bot_listing", "listing", lid, src)
        if not old:
            track(con, "listing_submitted", props={"deal": f["deal"], "type": f["type"], "source": "sync" if d.get("own") else "bot"})
    if not d.get("quiet"):
        notify(f"🤖 {esc(agent or 'Agent')} listed #{lid} on the website via the bot\n{esc(f['deal'])} · {esc(f['district'] or f['address'])} · "
               f"{f['price']:,.0f} {esc(f['currency'])} · {len(photos)} photos\n{SITE}/p/?id={lid}")
    with db() as con:
        u = con.execute("SELECT slug, role FROM users WHERE id=?", (adm["id"],)).fetchone()
    path = f"/{u['slug']}/{listing_slug(f)}-{lid}" if u and u["slug"] and u["role"] in PARTNER_ROLES else f"/p/?id={lid}"
    return ok(id=lid, url=SITE + path, profile=(f"{SITE}/{u['slug']}/" if u and u["slug"] and u["role"] in PARTNER_ROLES else ""),
              photos=len(photos), updated=bool(old))



def daily_report_text(con, hours=24):
    """Evening summary for the admin: per KEY GROUP agent — new listings, leads (and unanswered), clicks, SS / paid coverage."""
    since = time.time() - hours * 3600
    agents = con.execute("SELECT id, name, last_login FROM users WHERE role='agent' AND UPPER(company)='KEY GROUP' AND blocked=0 ORDER BY name").fetchall()
    clicks = {}
    for r in con.execute("SELECT name, props FROM events WHERE ts>? AND name IN ('call_click','whatsapp_click')", (since,)):
        try:
            lid_ = int(json.loads(r["props"] or "{}").get("listing_id") or 0)
        except (ValueError, TypeError):
            lid_ = 0
        if lid_:
            clicks[lid_] = clicks.get(lid_, 0) + 1
    owner_of = {r["id"]: r["user_id"] for r in con.execute("SELECT id, user_id FROM listings WHERE id IN (%s)" % (",".join(str(k) for k in clicks) or "0"))}
    lines = [f"🏢 <b>KEY GROUP — დღის ანგარიში / daily report</b> · {time.strftime('%d.%m %H:%M', time.gmtime(time.time() + 4 * 3600))}", ""]
    tot = {"new": 0, "leads": 0, "open": 0, "clicks": 0, "live": 0}
    for a in agents:
        live = con.execute("SELECT COUNT(*) AS n FROM listings WHERE user_id=? AND status='active'", (a["id"],)).fetchone()["n"]
        new = con.execute("SELECT COUNT(*) AS n FROM listings WHERE user_id=? AND created>? AND status!='deleted'", (a["id"], since)).fetchone()["n"]
        ld = con.execute("SELECT COUNT(*) AS n FROM leads WHERE COALESCE(NULLIF(assigned_to,0), owner_id)=? AND created>?", (a["id"], since)).fetchone()["n"]
        op = con.execute("SELECT COUNT(*) AS n FROM leads WHERE COALESCE(NULLIF(assigned_to,0), owner_id)=? AND stage='new' AND created<?", (a["id"], time.time() - 2 * 3600)).fetchone()["n"]
        ck = sum(v for k, v in clicks.items() if owner_of.get(k) == a["id"])
        x = con.execute("""SELECT SUM(x.site='ss') AS ss, SUM(x.promo!='') AS paid FROM ext_posts x JOIN listings l ON l.id=x.listing_id
                           WHERE l.user_id=? AND l.status='active'""", (a["id"],)).fetchone()
        seen = "" if a["last_login"] and a["last_login"] > since else " · 💤"
        lines.append(f"• <b>{esc(a['name'])}</b>: {live} live · 🆕 {new} · 📞 {ld} " + ("ლიდი" if True else "") +
                     (f" (⚠️ {op} უპასუხო)" if op else "") + f" · 👆 {ck} · SS {x['ss'] or 0} · VIP {x['paid'] or 0}{seen}")
        tot["new"] += new; tot["leads"] += ld; tot["open"] += op; tot["clicks"] += ck; tot["live"] += live
    lines += ["", f"სულ / total: {tot['live']} live · 🆕 {tot['new']} · 📞 {tot['leads']} · 👆 {tot['clicks']}" + (f" · ⚠️ {tot['open']} უპასუხო ლიდი" if tot["open"] else ""),
              "🆕 ახალი განცხადება / new · 📞 ლიდი / leads · 👆 ზარი+WhatsApp დაჭერა / call+WhatsApp clicks · 💤 დღეს არ შესულა / no login today",
              f"{SITE}/admin/#agents"]
    return "\n".join(lines)


async def bot_daily_report(request):
    """The bot asks for the evening report and sends it to the admins."""
    sec = request.headers.get("x-bot-secret", "")
    if not CRM_SECRET or not hmac.compare_digest(sec, CRM_SECRET):
        return err("unauthorized", 401)
    with db() as con:
        return ok(text=daily_report_text(con))


SEO_PAGES = ("/", "/search/", "/tbilisi/", "/batumi/", "/invest-in-georgia/", "/partners/", "/ka/", "/ru/")


async def sitemap_xml(request):
    """Every live listing (at its agent URL when it has one), agent profiles and the main pages — for Google / Bing."""
    def x(u):
        return u.replace("&", "&amp;").replace("<", "&lt;")
    urls = [(SITE + pg, None, "daily" if pg in ("/", "/search/") else "weekly") for pg in SEO_PAGES]
    with db() as con:
        users = {r["id"]: r for r in con.execute("SELECT id, slug, role FROM users")}
        for r in con.execute("SELECT id, user_id, deal, type, rooms, district, city, updated FROM listings WHERE status='active' ORDER BY id DESC LIMIT 45000"):
            u = users.get(r["user_id"])
            path = f"/{u['slug']}/{listing_slug(dict(r))}-{r['id']}" if u and u["slug"] and u["role"] in PARTNER_ROLES else f"/p/?id={r['id']}"
            urls.append((SITE + path, r["updated"], "weekly"))
        for u in users.values():
            if u["slug"] and u["role"] in PARTNER_ROLES:
                urls.append((f"{SITE}/{u['slug']}/", None, "daily"))
    body = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, mod, freq in urls:
        body.append(f"<url><loc>{x(loc)}</loc>" + (f"<lastmod>{time.strftime('%Y-%m-%d', time.gmtime(mod))}</lastmod>" if mod else "") + f"<changefreq>{freq}</changefreq></url>")
    body.append("</urlset>")
    return Response("\n".join(body), media_type="application/xml", headers={"Cache-Control": "public, max-age=3600"})


async def robots_txt(request):
    return Response("User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /account/\nDisallow: /api/\nDisallow: /compare/\nDisallow: /publish/\n\n"
                    f"Sitemap: {SITE}/sitemap.xml\n", media_type="text/plain")


async def bot_source_gone(request):
    """The daily MyHome sync saw an agent remove a listing from their account: pause the copy on keygroup.ge (not deleted)."""
    sec = request.headers.get("x-bot-secret", "")
    if not CRM_SECRET or not hmac.compare_digest(sec, CRM_SECRET):
        return err("unauthorized", 401)
    d = await body_json(request)
    src = str(d.get("url") or "").split("?")[0][:300]
    if not src:
        return err("url required")
    with _LOCK, db() as con:
        rows = con.execute("SELECT id FROM listings WHERE source_url=? AND status='active'", (src,)).fetchall()
        for r in rows:
            con.execute("UPDATE listings SET status='paused', updated=? WHERE id=?", (time.time(), r["id"]))
            audit(con, {"id": 0, "name": "MyHome sync"}, "source_gone", "listing", r["id"], src)
    return ok(paused=[r["id"] for r in rows])


async def bot_agent_access(request):
    """Staff bot /login: makes sure the agent has a keygroup.ge account, moves their bot listings into it,
    and returns a one-time login link (15 minutes) that the bot sends to the agent privately."""
    sec = request.headers.get("x-bot-secret", "")
    if not CRM_SECRET or not hmac.compare_digest(sec, CRM_SECRET):
        return err("unauthorized", 401)
    d = await body_json(request)
    name = str(d.get("agent") or "").strip()[:40]
    with _LOCK, db() as con:
        u = agent_user(con, name, d.get("phone"), d.get("profiles") or {})
        if not u:
            return err("No agent account for this phone (it may belong to an admin or owner account)")
        if str(d.get("tg") or "").isdigit():
            con.execute("UPDATE users SET tg_id=? WHERE id=?", (str(d["tg"]), u["id"]))
        names = [x for x in {name, u["name"]} if x]
        moved = con.execute(f"""UPDATE listings SET user_id=? WHERE agent_name IN ({','.join('?' * len(names))})
                                AND user_id IN (SELECT id FROM users WHERE role='admin') AND status!='deleted'""", (u["id"], *names)).rowcount
        tok = secrets.token_urlsafe(24)
        con.execute("DELETE FROM login_tokens WHERE expires<?", (time.time(),))
        con.execute("INSERT INTO login_tokens (token, user_id, expires) VALUES (?,?,?)", (tok, u["id"], time.time() + 900))
        n = con.execute("SELECT COUNT(*) FROM listings WHERE user_id=? AND status!='deleted'", (u["id"],)).fetchone()[0]
        audit(con, {"id": 0, "name": "Telegram bot"}, "agent_login_link", "user", u["id"], name)
    return ok(url=f"{SITE}/api/login/link?t={tok}", profile=f"{SITE}/{u['slug']}/" if u["slug"] else "", listings=n, moved=moved,
              phone=u["phone"], pw_set=bool(u["pw_set"]))


LINK_PAGE = """<!doctype html><html lang="ka"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>KEY GROUP — login</title>
<style>body{margin:0;font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#F7F9FC;color:#0F1E33;display:grid;place-items:center;min-height:100vh;padding:16px}
.c{background:#fff;border:1px solid #E4E9F0;border-radius:18px;padding:28px;max-width:420px;width:100%;box-shadow:0 10px 30px rgba(8,26,48,.08)}
h1{font-size:22px;margin:0 0 8px}p{color:#5E6E82;margin:0 0 18px;line-height:1.5}button{width:100%;border:0;border-radius:12px;padding:14px;font-size:16px;font-weight:700;background:#0D2847;color:#fff;cursor:pointer}
.err{background:#FFEDEA;color:#B5475E;border-radius:10px;padding:12px;margin-bottom:14px}a{color:#2F6FED}</style></head><body><div class="c">{{BODY}}</div></body></html>"""


async def bot_reset_link(request):
    """Self-service password reset: the Telegram bot sends the phone number Telegram verified for this user.
    If a keygroup.ge account has that phone, a one-time link (30 min) is returned to the bot, which sends it only to that user."""
    sec = request.headers.get("x-bot-secret", "")
    if not CRM_SECRET or not hmac.compare_digest(sec, CRM_SECRET):
        return err("unauthorized", 401)
    d = await body_json(request)
    phone = norm_phone(d.get("phone"))
    with _LOCK, db() as con:
        u = con.execute("SELECT id, name, role, blocked FROM users WHERE phone=?", (phone,)).fetchone()
        if not u:
            return ok(found=False)
        if str(d.get("tg") or "").isdigit():   # Telegram verified this phone for this Telegram user
            con.execute("UPDATE users SET tg_id=? WHERE id=?", (str(d["tg"]), u["id"]))
        if u["role"] == "admin":
            return ok(found=True, admin=True)
        if u["blocked"]:
            return ok(found=True, blocked=True)
        recent = con.execute("SELECT COUNT(*) FROM login_tokens WHERE user_id=? AND purpose='reset' AND expires>?", (u["id"], time.time() + 1800 - 3600)).fetchone()[0]
        if recent >= 5:
            return err("Too many reset requests — try again in an hour", 429)
        tok = secrets.token_urlsafe(24)
        con.execute("INSERT INTO login_tokens (token, user_id, expires, purpose) VALUES (?,?,?,'reset')", (tok, u["id"], time.time() + 1800))
        audit(con, {"id": 0, "name": "Telegram bot (self-service)"}, "password_reset_link", "user", u["id"], str(d.get("tg") or "")[:30])
    return ok(found=True, name=u["name"], url=f"{SITE}/api/login/link?t={tok}")


async def bot_outbox(request):
    """The staff bot collects messages the website wants delivered (e.g. password resets) and sends them."""
    sec = request.headers.get("x-bot-secret", "")
    if not CRM_SECRET or not hmac.compare_digest(sec, CRM_SECRET):
        return err("unauthorized", 401)
    with _LOCK, db() as con:
        rows = [dict(r) for r in con.execute("SELECT id, tg_id, text, button_url, button_text FROM bot_outbox WHERE sent=0 ORDER BY id LIMIT 30")]
        if rows:
            con.execute(f"UPDATE bot_outbox SET sent=? WHERE id IN ({','.join('?' * len(rows))})", (time.time(), *[r["id"] for r in rows]))
        con.execute("DELETE FROM bot_outbox WHERE sent>0 AND sent<?", (time.time() - 30 * 86400,))
    return ok(messages=rows)


async def login_link(request):
    """GET shows a confirm page (link previews in WhatsApp / Telegram must not use up the one-time link); POST logs in."""
    tok = (request.query_params.get("t", "") if request.method == "GET" else (await request.form()).get("t", ""))[:64]
    with _LOCK, db() as con:
        r = con.execute("SELECT t.*, u.name, u.phone, u.blocked FROM login_tokens t JOIN users u ON u.id=t.user_id WHERE t.token=?", (tok,)).fetchone()
        valid = bool(r and not r["used"] and r["expires"] > time.time() and not r["blocked"])
        if valid and request.method == "POST":
            con.execute("UPDATE login_tokens SET used=? WHERE token=?", (time.time(), tok))
            if r["purpose"] == "reset":
                con.execute("UPDATE users SET pw_set=0 WHERE id=?", (r["user_id"],))
            con.execute("UPDATE users SET last_login=? WHERE id=?", (time.time(), r["user_id"]))
    if not valid:
        body = ('<div class="err">ბმულს ვადა გაუვიდა ან უკვე გამოყენებულია.<br>This login link has expired or was already used.</div>'
                '<p>KEY GROUP-ის აგენტებო: გაუგზავნეთ ბოტს <b>/login</b>. სხვებმა მოგვწერეთ WhatsApp-ზე: <a href="https://wa.me/995577114118">+995 577 114 118</a></p>'
                '<p><a href="/account/">keygroup.ge/account</a></p>')
        return Response(LINK_PAGE.replace("{{BODY}}", body), media_type="text/html", status_code=410, headers={"Cache-Control": "no-store"})
    if request.method == "GET":
        masked = r["phone"][:4] + " ••• " + r["phone"][-4:]
        body = (f'<h1>KEY GROUP</h1><p>შესვლა როგორც / Log in as<br><b style="color:#0F1E33;font-size:18px">{esc(r["name"])}</b><br>{esc(masked)}</p>'
                f'<form method="post" action="/api/login/link"><input type="hidden" name="t" value="{esc(tok)}"><button type="submit">შესვლა · Continue</button></form>'
                '<p style="font-size:12px;margin:14px 0 0">ბმული მუშაობს ერთხელ. This link works once.</p>')
        return Response(LINK_PAGE.replace("{{BODY}}", body), media_type="text/html", headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})
    return with_session(RedirectResponse("/account/?welcome=1", status_code=303), new_session(r["user_id"]))


# ---------------------------------------------------------------- KEY GROUP agents: profile, MyHome/SS link, admin overview

LINK_HOSTS = {"myhome": ("myhome.ge",), "ss": ("ss.ge",)}
EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")
NAME_ALIAS = {"dato": "davit", "daviti": "davit", "demetre": "deme", "demeti": "deme", "demetri": "deme", "gio": "giorgi", "anna": "ana"}


def name_key(name):
    n = slugify(str(name or "").strip().split(" ")[0], 30).replace("-", "")
    return NAME_ALIAS.get(n, n)


def clean_links(d, cur=None):
    out = dict(cur or {})
    for k, hosts in LINK_HOSTS.items():
        if k in d:
            v = str(d.get(k) or "").strip()[:300]
            host = (urllib.parse.urlparse(v).hostname or "").lower()
            if not v:
                out.pop(k, None)
            elif v.startswith("https://") and any(host == h or host.endswith("." + h) for h in hosts):
                out[k] = v
    return out


def is_kg_agent(u):
    return u and u["role"] == "agent" and (u["company"] or "").upper() == "KEY GROUP"


def crm_rows_for(name):
    """The agent's own rows from the Master CRM (their MyHome / SS listings collected from their Google Sheet)."""
    if not CRM_URL:
        return [], None
    try:
        data, warn = fetch_crm()
    except Exception:
        return [], None
    t = ((data or {}).get("tabs") or {}).get("Master Listings") or {}
    H, rows = t.get("headers") or [], t.get("rows") or []
    if "Agent" not in H:
        return [], None
    ai, key = H.index("Agent"), name_key(name)
    mine = [r for r in rows if name_key(r[ai]) == key]
    keep = [h for h in ("KG Key", "Deal", "Category", "District", "Address", "Rooms", "Area m2", "Floor", "Price", "Currency", "Status", "Listing Link", "First Seen") if h in H]
    return [{h: r[H.index(h)] for h in keep} for r in mine], (data or {}).get("updated")


def save_profile(con, u, d):
    """Name, company, public link (slug), email, bio, MyHome/SS links. Returns an error text or None."""
    name = str(d.get("name") or u["name"]).strip()[:60] or u["name"]
    email = str(d.get("email") or "").strip()[:120]
    if email and not EMAIL_RE.match(email):
        return "Check the email address"
    try:
        cur = json.loads(u.get("links") or "{}")
    except ValueError:
        cur = {}
    links = clean_links(d.get("links") or {}, cur)
    company = u.get("company") or ""
    if "company" in d and not is_kg_agent(u):   # KEY GROUP agents always show KEY GROUP
        company = str(d.get("company") or "").strip()[:80]
    slug = u.get("slug") or ""
    if "slug" in d and u["role"] in PARTNER_ROLES:
        want = slugify(str(d.get("slug") or ""), 30)
        if want and want != slug:
            if len(want) < 2 or want in RESERVED_SLUGS or con.execute("SELECT 1 FROM users WHERE slug=? AND id!=?", (want, u["id"])).fetchone():
                return f"The link keygroup.ge/{want}/ is taken — choose another"
            slug = want
    if u["role"] in PARTNER_ROLES and not slug:
        slug = unique_slug(con, company or name, u["id"])
    con.execute("UPDATE users SET name=?, email=?, bio=?, links=?, company=?, slug=? WHERE id=?",
                (name, email, str(d.get("bio") if "bio" in d else (u.get("bio") or "")).strip()[:600], json.dumps(links), company, slug, u["id"]))
    return None


async def my_profile(request):
    u, e = need_user(request)
    if e:
        return e
    if request.method == "POST":
        d = await body_json(request)
        with _LOCK, db() as con:
            msg = save_profile(con, u, d)
            if msg:
                return err(msg)
            audit(con, u, "profile_save", "user", u["id"], "")
        return ok()
    try:
        links = json.loads(u.get("links") or "{}")
    except ValueError:
        links = {}
    out = {"name": u["name"], "email": u.get("email") or "", "bio": u.get("bio") or "", "links": links, "slug": u.get("slug") or "",
           "phone": u["phone"], "kg_agent": bool(is_kg_agent(u)), "company": u.get("company") or "", "role": u["role"]}
    if is_kg_agent(u):
        loop = asyncio.get_running_loop()
        rows, updated = await loop.run_in_executor(None, crm_rows_for, u["name"])
        out.update(crm_listings=rows[:300], crm_total=len(rows), crm_updated=updated)
    return ok(profile=out)


async def admin_agents(request):
    """Central view of every KEY GROUP agent; create accounts (one or a pasted list), login links, block."""
    u, e = need_user(request, perm="*")
    if e:
        return e
    if request.method == "POST":
        d = await body_json(request)
        act = d.get("action")
        with _LOCK, db() as con:
            if act == "create":
                lines = str(d.get("text") or "").splitlines() or [""]
                rows = []
                if d.get("phone"):
                    rows = [(d.get("phone"), d.get("name"), d.get("email"))]
                for line in lines:
                    m = re.search(r"((?:\+?995[\s-]?)?5\d{2}(?:[\s-]?\d){6})\s+([^\s\d@]+)(?:\s+([\w.+-]+@[\w-]+\.[\w.]+))?", line)
                    if m:
                        rows.append(m.groups())
                made = []
                for ph, nm, mail in rows:
                    a = agent_user(con, str(nm or "").strip(), ph)
                    if not a:
                        made.append({"name": nm, "error": "phone belongs to another account type"})
                        continue
                    if mail and EMAIL_RE.match(mail.strip()):
                        con.execute("UPDATE users SET email=? WHERE id=?", (mail.strip(), a["id"]))
                    if nm and a["name"] != nm.strip():
                        con.execute("UPDATE users SET name=? WHERE id=? AND pw_set=0", (nm.strip(), a["id"]))
                    made.append({"name": nm, "phone": a["phone"], "slug": a["slug"]})
                audit(con, u, "agents_create", "user", 0, json.dumps(made, ensure_ascii=False)[:900])
                return ok(created=made)
            if act == "send_links":
                # every KEY GROUP agent with a known Telegram id gets a one-time login link from the bot (24 h)
                sent, missing = [], []
                ids = [int(x) for x in d.get("ids") or [] if str(x).isdigit()]
                for a in con.execute("SELECT * FROM users WHERE role='agent' AND UPPER(company)='KEY GROUP' AND blocked=0").fetchall():
                    if ids and a["id"] not in ids:
                        continue
                    if not str(a["tg_id"] or "").isdigit():
                        missing.append(a["name"])
                        continue
                    tok = secrets.token_urlsafe(24)
                    con.execute("INSERT INTO login_tokens (token, user_id, expires) VALUES (?,?,?)", (tok, a["id"], time.time() + 86400))
                    first = not a["last_login"]
                    text = (f"👋 {a['name']}, " + ("შენი KEY GROUP ანგარიში keygroup.ge-ზე მზადაა" if first else "შენი keygroup.ge ანგარიშის ბმული") +
                            " — შენი განცხადებები (MyHome-დან), ლიდები და MyHome / SS-ზე გამოქვეყნება ერთ ადგილას.\n"
                            "დააჭირე ღილაკს (ბმული 24 საათი მოქმედებს)" + (" და შესვლის შემდეგ დააყენე პაროლი." if not a["pw_set"] else ".") +
                            "\n\n👋 Your keygroup.ge account: your listings, leads and MyHome / SS publishing in one place. Tap the button (valid 24 h).")
                    con.execute("INSERT INTO bot_outbox (tg_id, text, button_url, button_text, created) VALUES (?,?,?,?,?)",
                                (a["tg_id"], text, f"{SITE}/api/login/link?t={tok}", "🔑 შესვლა keygroup.ge", time.time()))
                    sent.append(a["name"])
                audit(con, u, "agents_send_links", "user", 0, f"sent={len(sent)} missing={len(missing)}")
                return ok(sent=sent, missing=missing)
            aid = int(d.get("id") or 0)
            a = con.execute("SELECT * FROM users WHERE id=?", (aid,)).fetchone()
            if not is_kg_agent(a):
                return err("Not a KEY GROUP agent", 404)
            if act == "link":
                tok = secrets.token_urlsafe(24)
                con.execute("INSERT INTO login_tokens (token, user_id, expires) VALUES (?,?,?)", (tok, aid, time.time() + 86400))
                audit(con, u, "agent_login_link", "user", aid, a["name"])
                return ok(url=f"{SITE}/api/login/link?t={tok}", hours=24)
            if act in ("block", "unblock"):
                con.execute("UPDATE users SET blocked=? WHERE id=?", (1 if act == "block" else 0, aid))
                if act == "block":
                    con.execute("DELETE FROM sessions WHERE user_id=?", (aid,))
                audit(con, u, "agent_" + act, "user", aid, a["name"])
                return ok()
            if act == "links":
                try:
                    cur = json.loads(a["links"] or "{}")
                except ValueError:
                    cur = {}
                con.execute("UPDATE users SET links=? WHERE id=?", (json.dumps(clean_links(d.get("links") or {}, cur)), aid))
                return ok()
        return err("Unknown action")
    since30 = time.time() - 30 * 86400
    with db() as con:
        rows = con.execute("SELECT * FROM users WHERE role='agent' AND UPPER(company)='KEY GROUP' ORDER BY name").fetchall()
        out = []
        for a in rows:
            st = agent_stats(con, a["id"])
            l = con.execute("""SELECT SUM(status='active') AS active, SUM(status='pending') AS pending, COUNT(*) AS total, MAX(created) AS last_listing,
                                      SUM(status='active' AND (photos='[]' OR photos='')) AS no_photos FROM listings WHERE user_id=? AND status!='deleted'""", (a["id"],)).fetchone()
            ld = con.execute("SELECT COUNT(*) AS n, SUM(stage='new') AS new FROM leads WHERE COALESCE(NULLIF(assigned_to,0), owner_id)=? AND created>?", (a["id"], since30)).fetchone()
            try:
                links = json.loads(a["links"] or "{}")
            except ValueError:
                links = {}
            x = con.execute("""SELECT SUM(x.site='myhome') AS mh, SUM(x.site='ss') AS ss, SUM(x.promo!='') AS paid
                               FROM ext_posts x JOIN listings l ON l.id=x.listing_id WHERE l.user_id=? AND l.status='active'""", (a["id"],)).fetchone()
            dup = con.execute("SELECT COUNT(*) AS n FROM listings WHERE user_id=? AND status='active' AND dup_of!=''", (a["id"],)).fetchone()["n"]
            out.append({"id": a["id"], "name": a["name"], "phone": a["phone"], "email": a["email"] or "", "slug": a["slug"] or "", "links": links,
                        "tg": bool(str(a["tg_id"] or "").isdigit()), "on_myhome": x["mh"] or 0, "on_ss": x["ss"] or 0, "paid": x["paid"] or 0, "dups": dup,
                        "blocked": a["blocked"], "pw_set": a["pw_set"], "last_login": a["last_login"] or 0, "created": a["created"],
                        "active": l["active"] or 0, "pending": l["pending"] or 0, "total": l["total"] or 0, "last_listing": l["last_listing"] or 0,
                        "no_photos": l["no_photos"] or 0, "leads30": ld["n"] or 0, "leads_new": ld["new"] or 0, "avg_hours": st["avg_hours"], "trusted": st["trusted"]})
    crm = {}
    loop = asyncio.get_running_loop()
    if CRM_URL:
        try:
            data, _ = await loop.run_in_executor(None, fetch_crm)
            t = ((data or {}).get("tabs") or {}).get("Master Listings") or {}
            H = t.get("headers") or []
            if "Agent" in H:
                ai, si = H.index("Agent"), (H.index("Status") if "Status" in H else -1)
                for r in t.get("rows") or []:
                    if si < 0 or r[si] == "Active":
                        k = name_key(r[ai]); crm[k] = crm.get(k, 0) + 1
        except Exception:
            pass
    for a in out:
        a["crm_active"] = crm.get(name_key(a["name"]), 0)
    return ok(agents=out)


# ---------------------------------------------------------------- publish to MyHome.ge / SS.ge from the user's own logged-in browser

KA_RE = re.compile(r"[\u10A0-\u10FF]")
PUBLISH_ORIGINS = ("https://statements.myhome.ge", "https://home.ss.ge", "https://www.myhome.ge", "https://ss.ge")


def district_ka(d):
    d = str(d or "").strip()
    if not d or KA_RE.search(d):
        return d
    low = d.lower()
    for en, ka, words in chatbot.DISTRICTS:
        if low == en.lower() or any(w.strip() and w.strip() == low for w in words):
            return ka
    return d


def split_address(addr):
    a = str(addr or "").strip()
    m = re.match(r"^(.*?)[\s,]*(?:N|№|#)?\s*(\d+[\w/-]*)$", a)
    return (m.group(1).strip(" ,"), m.group(2)) if m and m.group(1).strip() else (a, "")


def split_desc(text):
    """Bot listings keep EN and KA paragraphs together; MyHome / SS have one box per language."""
    ka, en, ru = [], [], []
    for para in re.split(r"\n\s*\n", str(text or "")):
        p = para.strip()
        if not p:
            continue
        if KA_RE.search(p):
            ka.append(p)
        elif re.search(r"[\u0400-\u04FF]", p):
            ru.append(p)
        else:
            en.append(p)
    return "\n\n".join(ka), "\n\n".join(en), "\n\n".join(ru)


EXT_RE = (("myhome", re.compile(r"myhome\.ge/(?:[a-z]{2}/)?(?:pr/(\d{5,10})|[^?#]*?-(\d{5,10})/?(?:[?#]|$))")),
          ("ss", re.compile(r"ss\.ge/[^?#]*?-(\d{5,10})/?(?:[?#]|$)")))


def ext_from_url(url):
    """MyHome / SS listing link -> (site, id) or (None, None)."""
    url = str(url or "").strip()
    for site, rx in EXT_RE:
        m = rx.search(url)
        if m:
            return site, next(g for g in m.groups() if g)
    return None, None


def ext_url(site, ext_id):
    return f"https://www.myhome.ge/pr/{ext_id}/" if site == "myhome" else f"https://home.ss.ge/ka/udzravi-qoneba/{ext_id}"


def save_ext(con, lid, site, ext_id, user_id=None, promo="", account="", source="", url=""):
    """Remember that a keygroup.ge listing is live on MyHome / SS (one row per site; the newest wins)."""
    if site not in ("myhome", "ss") or not re.fullmatch(r"[0-9a-f-]{5,40}", str(ext_id)):
        return False
    url = url if str(ext_id).isdigit() and url else (ext_url(site, ext_id) if str(ext_id).isdigit() else "")
    con.execute("""INSERT INTO ext_posts (listing_id, site, ext_id, url, promo, account, user_id, source, created) VALUES (?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(listing_id, site) DO UPDATE SET ext_id=excluded.ext_id, url=excluded.url, promo=excluded.promo,
                   account=excluded.account, source=excluded.source, created=excluded.created""",
                (lid, site, str(ext_id), url, promo or "", str(account or "")[-9:], user_id, source, time.time()))
    return True


def ext_map(con, ids):
    """{listing_id: {"myhome": {...}, "ss": {...}}} for the account / admin tables."""
    out = {}
    ids = list(ids)
    for i in range(0, len(ids), 500):
        part = ids[i:i + 500]
        if not part:
            continue
        for r in con.execute(f"SELECT * FROM ext_posts WHERE listing_id IN ({','.join('?' * len(part))})", part):
            out.setdefault(r["listing_id"], {})[r["site"]] = {"id": r["ext_id"], "url": r["url"], "promo": r["promo"], "account": r["account"],
                                                               "source": r["source"], "at": r["created"]}
    return out


PROMO_TIERS = ("vip", "vipplus", "supervip")


def clean_promo(p):
    """Paid option chosen on keygroup.ge: {tier: vip|vipplus|supervip, days: 1-30}. The publisher only pre-selects it — the person presses Pay."""
    if not isinstance(p, dict) or p.get("tier") not in PROMO_TIERS:
        return None
    try:
        days = int(p.get("days") or 1)
    except (TypeError, ValueError):
        days = 1
    cap = 30 if p["tier"] == "vip" else 4      # MyHome sells VIP+ / Super VIP for 1-4 days at a time
    return {"tier": p["tier"], "days": max(1, min(days, 30)), "myhome_days": max(1, min(days, cap))}


async def publish_code(request):
    """Owner / agent / admin asks to publish a listing to their own MyHome / SS account: a short code valid 2 hours."""
    u, e = need_user(request)
    if e:
        return e
    lid = int(request.path_params["lid"])
    try:
        body = await request.json()
    except Exception:
        body = {}
    promo = clean_promo((body or {}).get("promo") if isinstance(body, dict) else None)
    with _LOCK, db() as con:
        row = own_listing(u, lid, con)
        if not row:
            return err("Not found", 404)
        code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8))
        con.execute("DELETE FROM publish_codes WHERE expires<?", (time.time(),))
        con.execute("INSERT INTO publish_codes (code, listing_id, user_id, expires, promo) VALUES (?,?,?,?,?)",
                    (code, lid, u["id"], time.time() + 7200, json.dumps(promo) if promo else ""))
        audit(con, u, "publish_code", "listing", lid, json.dumps(promo) if promo else "")
    return ok(code=code, promo=promo, myhome=f"https://statements.myhome.ge/ka/statement/create?referrer=myhome#kgpub={code}",
              ss=f"https://home.ss.ge/ka/udzravi-qoneba/create#kgpub={code}")


async def publish_data(request):
    """Read by the KEY GROUP publisher script on the MyHome / SS add-listing page (CORS, code-protected, 2 hours)."""
    code = str(request.path_params["code"]).upper()[:12]
    origin = request.headers.get("origin", "")
    hdr = {"Access-Control-Allow-Origin": origin if origin in PUBLISH_ORIGINS else "https://statements.myhome.ge", "Vary": "Origin",
           "Cache-Control": "no-store"}
    with db() as con:
        c = con.execute("SELECT * FROM publish_codes WHERE code=? AND expires>?", (code, time.time())).fetchone()
        row = con.execute("SELECT * FROM listings WHERE id=? AND status!='deleted'", (c["listing_id"],)).fetchone() if c else None
        owner = con.execute("SELECT name, phone, company FROM users WHERE id=?", (row["user_id"],)).fetchone() if row else None
    if not row:
        return JSONResponse({"ok": False, "error": "Code expired — press the MyHome / SS button on keygroup.ge again"}, status_code=404, headers=hdr)
    street, number = split_address(row["address"])
    ka, en, ru = split_desc(row["description"])
    if len(ka) < 80:   # short or missing text: write a clear one from the listing facts
        deal_ka = {"sale": "იყიდება", "rent": "ქირავდება", "daily": "ქირავდება დღიურად"}.get(row["deal"], "")
        type_ka = {"flat": "ბინა", "house": "კერძო სახლი", "commercial": "კომერციული ფართი", "land": "მიწის ნაკვეთი", "hotel": "სასტუმრო"}.get(row["type"], "")
        cur = {"USD": "$", "GEL": "₾", "EUR": "€"}.get(row["currency"], "")
        parts = [f"{deal_ka} {str(row['rooms']) + ' ოთახიანი ' if row['rooms'] else ''}{type_ka} — {district_ka(row['district']) or ''}{', ' + row['address'] if row['address'] else ''}.".strip(),
                 f"ფართი: {row['area']:g} მ²." if row["area"] else "", f"სართული: {row['floor']}{'/' + row['total_floors'] if row['total_floors'] else ''}." if row["floor"] else "",
                 f"ფასი: {row['price']:,.0f} {cur}{' / თვე' if row['deal'] == 'rent' else ''}.", ka if ka and ka not in (deal_ka, type_ka) else "",
                 "დათვალიერება ნებისმიერ დროს — KEY GROUP Real Estate."]
        ka = "\n".join(x for x in parts if x)
    if len(en) < 60:
        deal_en = {"sale": "For sale", "rent": "For rent", "daily": "Daily rent"}.get(row["deal"], "")
        type_en = {"flat": "apartment", "house": "house", "commercial": "commercial space", "land": "land plot", "hotel": "hotel"}.get(row["type"], "")
        en = "\n".join(x for x in [f"{deal_en}: {str(row['rooms']) + '-room ' if row['rooms'] else ''}{type_en} in {row['district'] or row['city']}.",
                                    f"Area: {row['area']:g} m²." if row["area"] else "", f"Floor: {row['floor']}{'/' + row['total_floors'] if row['total_floors'] else ''}." if row["floor"] else "",
                                    "Viewings any time — KEY GROUP Real Estate."] if x)
    photos = [f"{SITE}/uploads/{p}" for p in json.loads(row["photos"] or "[]")][:16]
    d = {"ok": True, "id": row["id"], "url": f"{SITE}/p/?id={row['id']}", "deal": row["deal"], "type": row["type"],
         "city": row["city"] or "Tbilisi", "city_ka": {"Tbilisi": "თბილისი", "Batumi": "ბათუმი", "Kutaisi": "ქუთაისი"}.get(row["city"] or "Tbilisi", row["city"]),
         "district": row["district"], "district_ka": district_ka(row["district"]), "address": row["address"], "street": street, "number": number,
         "area": row["area"], "rooms": row["rooms"], "bedrooms": row["bedrooms"], "floor": row["floor"], "total_floors": row["total_floors"],
         "price": row["price"], "currency": row["currency"], "title": row["title"], "desc_ka": ka, "desc_en": en, "desc_ru": ru,
         "photos": photos, "video_url": row["video_url"] or "", "contact_name": (owner["name"] if owner else "") or "KEY GROUP",
         "contact_phone": row["contact_phone"],
         "promo": json.loads(c["promo"]) if c["promo"] else None}
    if not d["bedrooms"] and d["rooms"] and d["type"] == "flat":
        d["bedrooms"] = max(1, int(d["rooms"]) - 1)
    return JSONResponse(d, headers=hdr)


SS_DEAL = (("დღიურად", "daily"), ("ქირავდება", "rent"), ("იყიდება", "sale"), ("გირავდება", "rent"))
SS_TYPE = (("ბინა", "flat"), ("სახლ", "house"), ("აგარაკ", "house"), ("მიწ", "land"), ("სასტუმრო", "hotel"),
           ("კომერც", "commercial"), ("ფართ", "commercial"), ("ობიექტ", "commercial"), ("ოფის", "commercial"), ("საწყობ", "commercial"))


def ss_title_facts(title):
    """'ქირავდება 2 ოთახიანი ბინა სამგორში' -> deal, rooms, type (what an SS.ge list card says)."""
    t = str(title or "")
    deal = next((v for k, v in SS_DEAL if k in t), "")
    typ = next((v for k, v in SS_TYPE if k in t), "")
    m = re.search(r"(\d+)\s*ოთახ", t)
    return deal, (int(m.group(1)) if m else 0), typ


def match_ss_items(con, user_id, items):
    """Link the agent's SS.ge listings (from their 'my listings' page) to their keygroup.ge listings.
    Only a single clear candidate is linked (same deal, type, rooms, price ±1%; district breaks ties); the rest is reported."""
    rows = con.execute("SELECT * FROM listings WHERE user_id=? AND status IN ('active','paused')", (user_id,)).fetchall()
    have = {r["listing_id"] for r in con.execute(f"SELECT listing_id FROM ext_posts WHERE site='ss' AND listing_id IN ({','.join('?' * len(rows)) or '0'})",
                                                     [r["id"] for r in rows])}
    linked_ss = {r["ext_id"] for r in con.execute("SELECT ext_id FROM ext_posts WHERE site='ss'")}
    out = {"matched": [], "already": 0, "ambiguous": [], "unmatched": []}
    for it in items[:500]:
        sid = str(it.get("id") or "")
        if not re.fullmatch(r"\d{6,10}", sid):
            continue
        if sid in linked_ss:
            out["already"] += 1
            continue
        title = str(it.get("title") or "")[:200]
        deal, rooms, typ = ss_title_facts(title)
        try:
            price = float(str(it.get("price") or "0").replace(",", "").replace(" ", ""))
        except ValueError:
            price = 0
        cur = {"$": "USD", "₾": "GEL", "€": "EUR"}.get(str(it.get("currency") or "$"), "USD")
        cands = []
        for r in rows:
            if r["id"] in have or not price:
                continue
            if deal and r["deal"] != deal or typ and r["type"] != typ or rooms and r["rooms"] and int(r["rooms"]) != rooms:
                continue
            if r["currency"] != cur or abs(float(r["price"] or 0) - price) > max(1.0, price * 0.01):
                continue
            cands.append(r)
        if len(cands) > 1:
            stem = lambda w: (w or "")[:-1] if len(w or "") > 4 else (w or "")
            near = [r for r in cands if district_ka(r["district"]) and stem(district_ka(r["district"])) in title]
            cands = near if near else cands
        if len(cands) == 1:
            r = cands[0]
            save_ext(con, r["id"], "ss", sid, user_id, source="agent")
            have.add(r["id"]); linked_ss.add(sid)
            out["matched"].append({"ss": sid, "listing": r["id"], "title": title})
        else:
            (out["ambiguous"] if cands else out["unmatched"]).append({"ss": sid, "title": title, "price": it.get("price")})
    return out


async def ss_link_code(request):
    """An agent asks to link their SS.ge listings: a short code for the bookmark on the SS 'my listings' page (2 hours)."""
    u, e = need_user(request)
    if e:
        return e
    code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8))
    with _LOCK, db() as con:
        con.execute("INSERT INTO publish_codes (code, listing_id, user_id, expires, promo) VALUES (?,?,?,?,?)", (code, 0, u["id"], time.time() + 7200, "ss-link"))
    return ok(code=code, url=f"https://home.ss.ge/ka/user/my-applications#kgss={code}")


async def ss_match(request):
    """The bookmark posts the cards from the agent's SS.ge 'my listings' page (CORS, code-protected, text/plain body)."""
    code = str(request.path_params["code"]).upper()[:12]
    origin = request.headers.get("origin", "")
    hdr = {"Access-Control-Allow-Origin": origin if origin in PUBLISH_ORIGINS else "https://home.ss.ge", "Vary": "Origin"}
    if request.method == "OPTIONS":
        hdr.update({"Access-Control-Allow-Methods": "POST", "Access-Control-Allow-Headers": "Content-Type"})
        return Response("", headers=hdr)
    try:
        d = json.loads((await request.body())[:400000] or b"{}")
    except Exception:
        d = {}
    with _LOCK, db() as con:
        c = con.execute("SELECT * FROM publish_codes WHERE code=? AND expires>? AND promo='ss-link'", (code, time.time())).fetchone()
        if not c:
            return JSONResponse({"ok": False, "error": "Code expired — press “Link my SS.ge listings” on keygroup.ge again"}, status_code=404, headers=hdr)
        res = match_ss_items(con, c["user_id"], d.get("items") if isinstance(d.get("items"), list) else [])
        audit(con, {"id": c["user_id"], "name": "SS link bookmark"}, "ss_match", "user", c["user_id"],
              f"matched={len(res['matched'])} ambiguous={len(res['ambiguous'])} unmatched={len(res['unmatched'])}")
    return JSONResponse(dict(ok=True, **res), headers=hdr)


async def publish_done(request):
    """The publisher reports back after MyHome / SS accepted the listing (CORS, code-protected; text/plain body to skip preflight)."""
    code = str(request.path_params["code"]).upper()[:12]
    origin = request.headers.get("origin", "")
    hdr = {"Access-Control-Allow-Origin": origin if origin in PUBLISH_ORIGINS else "https://statements.myhome.ge", "Vary": "Origin"}
    if request.method == "OPTIONS":
        hdr.update({"Access-Control-Allow-Methods": "POST", "Access-Control-Allow-Headers": "Content-Type"})
        return Response("", headers=hdr)
    try:
        d = json.loads((await request.body())[:4000] or b"{}")
    except Exception:
        d = {}
    with _LOCK, db() as con:
        c = con.execute("SELECT * FROM publish_codes WHERE code=? AND expires>?", (code, time.time() - 6 * 3600)).fetchone()
        okk = bool(c) and bool(c["listing_id"]) and save_ext(con, c["listing_id"], d.get("site"), d.get("ext_id"), c["user_id"],
                                   json.dumps(d.get("promo")) if d.get("promo") else "", d.get("account"), "publisher")
        if okk:
            con.execute("UPDATE publish_codes SET used=1 WHERE code=?", (code,))
    return JSONResponse({"ok": okk}, headers=hdr, status_code=200 if okk else 400)


async def listing_ext(request):
    """Owner / agent / admin attaches (or removes) the MyHome / SS link of a listing by hand."""
    u, e = need_user(request)
    if e:
        return e
    lid = int(request.path_params["lid"])
    d = await body_json(request)
    with _LOCK, db() as con:
        if not own_listing(u, lid, con):
            return err("Not found", 404)
        if d.get("remove") in ("myhome", "ss"):
            con.execute("DELETE FROM ext_posts WHERE listing_id=? AND site=?", (lid, d["remove"]))
            return ok(ext=ext_map(con, [lid]).get(lid, {}))
        site, ext_id = ext_from_url(d.get("url"))
        if not site:
            return err("Paste the full MyHome.ge or SS.ge link of this listing")
        save_ext(con, lid, site, ext_id, u["id"], source="manual", url=str(d.get("url")).split("?")[0][:300])
        audit(con, u, "listing_ext", "listing", lid, f"{site}:{ext_id}")
        return ok(ext=ext_map(con, [lid]).get(lid, {}))


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
    if q.get("project", "").isdigit():
        where.append("project_id=?"); args.append(int(q["project"]))
    if q.get("ids"):
        ids = [int(x) for x in q["ids"].split(",")[:10] if x.strip().isdigit()] or [0]
        where.append(f"id IN ({','.join('?' * len(ids))})"); args += ids
    if q.get("verified") == "1":
        where.append("verify_level>=2")
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
        outs = [listing_out(r, settings=s) for r in rows]
        attach_agents(con, rows, outs)
        if q.get("ids"):   # compare page: add the market comparison too
            pool = market_pool(con)
            for o in outs:
                o["market"] = market_for(con, o, pool)
    return ok(listings=outs)


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
    out = listing_out(row)
    with db() as con:
        attach_agents(con, [row], [out])
        out["market"] = market_for(con, out)
        if row["project_id"]:
            p = con.execute("SELECT id, name, frame, handover, down_pct, inst_months FROM projects WHERE id=? AND status='active'", (row["project_id"],)).fetchone()
            out["project"] = dict(p) if p else None
    return ok(listing=out, settings=public_settings())


def alert_owner(con, user_id, lid, row, name, phone, message, source):
    """Tell the listing's own agent / owner about a new lead in Telegram (if the bot knows them) — Georgian + English."""
    u = con.execute("SELECT name, tg_id, role FROM users WHERE id=?", (user_id,)).fetchone()
    if not u or not str(u["tg_id"] or "").isdigit():
        return False
    place = esc(row["district"] or row["address"] or "")
    price = f"{(row['price'] or 0):,.0f} {esc(row['currency'] or '')}"
    via = {"chat": "საიტის ჩატი / website chat", "callback": "ზარის მოთხოვნა / callback", "viewing": "ნახვის მოთხოვნა / viewing"}.get(source, esc(source))
    text = (f"📞 <b>ახალი ლიდი / New lead</b> — #{lid} {place} · {price}\n"
            f"👤 {esc(name or '—')}  📱 <b>{esc(phone)}</b>\n"
            + (f"💬 {esc(str(message)[:300])}\n" if message else "") +
            f"↪️ {via}\n\nდაურეკე რაც შეიძლება მალე / Please call back soon.")
    con.execute("INSERT INTO bot_outbox (tg_id, text, button_url, button_text, created) VALUES (?,?,?,?,?)",
                (u["tg_id"], text, f"{SITE}/account/#leads", "📋 ჩემი ლიდები / My leads", time.time()))
    return True


async def listing_enquiry(request):
    """A buyer / tenant asks about a listing: saved as a lead for the listing's owner or agent, plus a Telegram alert."""
    if too_many(request, "enq", 8, 600):
        return err("Too many requests, try again later", 429)
    lid = int(request.path_params["lid"])
    d = await body_json(request)
    if d.get("website"):
        return ok()
    phone = str(d.get("phone") or "").strip()[:40]
    if len(re.sub(r"\D", "", phone)) < 9:
        return err("Enter your phone number")
    if not d.get("consent"):
        return err("Please agree to be contacted")
    with _LOCK, db() as con:
        row = con.execute("SELECT * FROM listings WHERE id=? AND status='active'", (lid,)).fetchone()
        if not row:
            return err("This listing is not available", 404)
        now = time.time()
        con.execute("INSERT INTO leads (listing_id, owner_id, name, phone, message, source, consent_at, created, updated) VALUES (?,?,?,?,?,?,?,?,?)",
                    (lid, row["user_id"], str(d.get("name") or "")[:80], phone, str(d.get("message") or "")[:1000], str(d.get("source") or "callback")[:20], now, now, now))
        track(con, "viewing_requested", f"/p/?id={lid}", {"listing_id": lid})
        alert_owner(con, row["user_id"], lid, row, str(d.get("name") or "")[:80], phone, str(d.get("message") or "")[:300], str(d.get("source") or "callback")[:20])
    notify(f"📞 New enquiry for listing #{lid} ({esc(row['district'] or row['address'])})\n{esc(d.get('name'))} {esc(phone)}\n{esc(str(d.get('message') or '')[:300])}\n{SITE}/admin/#leads")
    return ok()


async def my_leads(request):
    u, e = need_user(request)
    if e:
        return e
    if request.method == "POST":
        d = await body_json(request)
        lid = int(d.get("id") or 0)
        stage = d.get("stage")
        with _LOCK, db() as con:
            row = con.execute("SELECT * FROM leads WHERE id=?", (lid,)).fetchone()
            if not row or (u["role"] not in STAFF_ROLES and row["owner_id"] not in team_ids(con, u) and row["assigned_to"] != u["id"]):
                return err("Not found", 404)
            now = time.time()
            if stage in ("new", "contacted", "viewing", "offer", "closed", "lost"):
                con.execute("UPDATE leads SET stage=?, updated=? WHERE id=?", (stage, now, lid))
                if stage != "new" and not row["first_action_at"]:
                    con.execute("UPDATE leads SET first_action_at=? WHERE id=?", (now, lid))
            if "viewing_at" in d:
                try:
                    va = float(d.get("viewing_at") or 0)
                except (TypeError, ValueError):
                    va = 0
                con.execute("UPDATE leads SET viewing_at=?, updated=? WHERE id=?", (va, now, lid))
                if va and row["stage"] in ("new", "contacted"):
                    con.execute("UPDATE leads SET stage='viewing', first_action_at=COALESCE(NULLIF(first_action_at,0), ?) WHERE id=?", (now, lid))
            if "assigned_to" in d:
                to = int(d.get("assigned_to") or 0)
                if to and to not in team_ids(con, u) and u["role"] != "admin":
                    return err("You can assign only to your team")
                con.execute("UPDATE leads SET assigned_to=?, updated=? WHERE id=?", (to, now, lid))
            if "note" in d:
                con.execute("UPDATE leads SET note=?, updated=? WHERE id=?", (str(d["note"])[:1000], time.time(), lid))
        return ok()
    with db() as con:
        ids = team_ids(con, u)
        rows = con.execute(f"""SELECT d.*, l.title, l.district, l.address, l.price, l.currency, l.deal, o.name AS agent_name, a.name AS assigned_name
                               FROM leads d LEFT JOIN listings l ON l.id=d.listing_id LEFT JOIN users o ON o.id=d.owner_id LEFT JOIN users a ON a.id=d.assigned_to
                               WHERE d.owner_id IN ({','.join('?' * len(ids))}) OR d.assigned_to=? ORDER BY d.id DESC LIMIT 500""", (*ids, u["id"])).fetchall()
        team = [dict(r) for r in con.execute("SELECT id, name FROM users WHERE org_id=?", (u["id"],))] if u["role"] == "agency" else []
    return ok(leads=[dict(r) for r in rows], team=team)


async def admin_leads(request):
    u, e = need_user(request, perm="leads")
    if e:
        return e
    with db() as con:
        rows = con.execute("""SELECT d.*, l.title, l.district, l.address, l.price, l.currency, l.deal, o.name AS owner_name, o.phone AS owner_phone
                              FROM leads d LEFT JOIN listings l ON l.id=d.listing_id LEFT JOIN users o ON o.id=d.owner_id
                              ORDER BY d.id DESC LIMIT 1000""").fetchall()
    return ok(leads=[dict(r) for r in rows])


# ---------------------------------------------------------------- partners (agents, agencies, developers)

async def partner_apply(request):
    if too_many(request, "papply", 5, 3600):
        return err("Too many applications, try again later", 429)
    d = await body_json(request)
    if d.get("website_hp"):
        return ok()
    f = {k: str(d.get(k) or "").strip()[:n] for k, n in (("name", 80), ("company", 120), ("email", 120), ("city", 60),
                                                         ("listings_est", 20), ("website", 200), ("message", 1500))}
    phone = norm_phone(d.get("phone"))
    ptype = d.get("ptype") if d.get("ptype") in PARTNER_ROLES else ""
    if not f["name"] or len(phone) < 10 or not ptype:
        return err("Enter your name, phone and partner type")
    if not d.get("consent"):
        return err("Please accept the partner terms and privacy policy")
    with _LOCK, db() as con:
        urow = con.execute("SELECT id FROM users WHERE phone=?", (phone,)).fetchone()
        cur = con.execute("""INSERT INTO partner_apps (user_id, name, company, phone, email, ptype, city, listings_est, website, message, consent_at, created)
                             VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (urow["id"] if urow else 0, f["name"], f["company"], phone, f["email"], ptype, f["city"],
                                                                  f["listings_est"], f["website"], f["message"], time.time(), time.time()))
        aid = cur.lastrowid
        track(con, "partner_application", "/partners/", {"ptype": ptype, "city": f["city"]})
    notify(f"🤝 New Founding Partner application #{aid}: <b>{esc(ptype)}</b>\n{esc(f['name'])} — {esc(f['company'])}\n{esc(phone)} {esc(f['email'])}\n"
           f"City: {esc(f['city'])} · listings: {esc(f['listings_est'])}\n{SITE}/admin/#partners")
    return ok(id=aid)


async def admin_partners(request):
    u, e = need_user(request, perm="partners")
    if e:
        return e
    with db() as con:
        apps = con.execute("SELECT * FROM partner_apps ORDER BY (status='new') DESC, id DESC LIMIT 500").fetchall()
        imps = con.execute("""SELECT i.*, u.name AS user_name, u.company, u.phone,
                                     (SELECT COUNT(*) FROM listings l WHERE l.batch_id=i.id AND l.status='pending') AS pending
                              FROM imports i LEFT JOIN users u ON u.id=i.user_id ORDER BY i.id DESC LIMIT 200""").fetchall()
        partners = con.execute(f"""SELECT u.id, u.name, u.company, u.phone, u.role, u.partner_until, u.listing_limit, u.created,
                                          (SELECT COUNT(*) FROM listings l WHERE l.user_id=u.id AND l.status='active') AS live
                                   FROM users u WHERE u.role IN ({','.join('?' * len(PARTNER_ROLES))}) ORDER BY u.id DESC""", PARTNER_ROLES).fetchall()
    return ok(applications=[dict(r) for r in apps], imports=[dict(r) for r in imps], partners=[dict(r) for r in partners])


async def admin_partner_action(request):
    u, e = need_user(request, perm="partners")
    if e:
        return e
    aid = int(request.path_params["aid"])
    d = await body_json(request)
    action = d.get("action")
    s = get_settings()
    password = None
    with _LOCK, db() as con:
        a = con.execute("SELECT * FROM partner_apps WHERE id=?", (aid,)).fetchone()
        if not a:
            return err("Not found", 404)
        if action == "approve":
            urow = con.execute("SELECT * FROM users WHERE phone=?", (a["phone"],)).fetchone()
            until = time.time() + int(s.get("founding_days", 90)) * 86400
            if urow:
                if urow["role"] == "admin":
                    return err("This phone belongs to an admin account")
                uid = urow["id"]
                con.execute("UPDATE users SET role=?, company=?, partner_until=? WHERE id=?", (a["ptype"], a["company"], until, uid))
            else:
                password = secrets.token_urlsafe(6)
                cur = con.execute("""INSERT INTO users (phone, name, pw, role, company, partner_until, created, consent_at, consent_ver)
                                     VALUES (?,?,?,?,?,?,?,?,?)""", (a["phone"], a["name"], hash_pw(password), a["ptype"], a["company"], until,
                                                                    time.time(), a["consent_at"], CONSENT_VERSION))
                uid = cur.lastrowid
            con.execute("UPDATE partner_apps SET status='approved', user_id=?, decided=? WHERE id=?", (uid, time.time(), aid))
        elif action == "reject":
            con.execute("UPDATE partner_apps SET status='rejected', decided=? WHERE id=?", (time.time(), aid))
        else:
            return err("Unknown action")
        audit(con, u, "partner_" + action, "partner_app", aid, f"{a['ptype']} {a['name']} {a['phone']}")
    return ok(password=password, phone=a["phone"])


# ---------------------------------------------------------------- agency teams

def team_ids(con, u):
    """User ids whose listings/leads this user may see: self, plus team members for an agency manager."""
    ids = [u["id"]]
    if u["role"] == "agency":
        ids += [r[0] for r in con.execute("SELECT id FROM users WHERE org_id=?", (u["id"],))]
    return ids


async def my_team(request):
    u, e = need_user(request)
    if e:
        return e
    if u["role"] != "agency":
        return err("Teams are for agency accounts", 403)
    if request.method == "POST":
        d = await body_json(request)
        phone, name = norm_phone(d.get("phone")), str(d.get("name") or "").strip()[:80]
        if len(phone) < 10 or not name:
            return err("Enter the agent's name and phone")
        password = None
        with _LOCK, db() as con:
            row = con.execute("SELECT * FROM users WHERE phone=?", (phone,)).fetchone()
            if row:
                if row["role"] == "admin" or (row["org_id"] and row["org_id"] != u["id"]):
                    return err("This phone belongs to another account")
                con.execute("UPDATE users SET org_id=?, role='agent', company=? WHERE id=?", (u["id"], u.get("company") or "", row["id"]))
            else:
                password = secrets.token_urlsafe(6)
                con.execute("""INSERT INTO users (phone, name, pw, role, company, org_id, partner_until, created, consent_at, consent_ver)
                               VALUES (?,?,?,?,?,?,?,?,?,?)""", (phone, name, hash_pw(password), "agent", u.get("company") or "", u["id"],
                                                                u.get("partner_until") or 0, time.time(), time.time(), CONSENT_VERSION))
            audit(con, u, "team_add", "user", 0, f"{name} {phone}")
        return ok(password=password, phone=phone)
    if request.method == "DELETE":
        uid = int(request.query_params.get("id") or 0)
        with _LOCK, db() as con:
            con.execute("UPDATE users SET org_id=0 WHERE id=? AND org_id=?", (uid, u["id"]))
            audit(con, u, "team_remove", "user", uid)
        return ok()
    with db() as con:
        rows = con.execute("""SELECT u.id, u.name, u.phone, u.created,
                                     (SELECT COUNT(*) FROM listings l WHERE l.user_id=u.id AND l.status='active') AS live,
                                     (SELECT COUNT(*) FROM leads d WHERE d.owner_id=u.id AND d.stage='new') AS new_leads
                              FROM users u WHERE u.org_id=? ORDER BY u.id""", (u["id"],)).fetchall()
    return ok(team=[dict(r) for r in rows])


# ---------------------------------------------------------------- developer projects

def clean_project(d):
    s = lambda k, n=200: str(d.get(k) or "").strip()[:n]
    try:
        lat, lon = float(d.get("lat") or 0), float(d.get("lon") or 0)
    except (TypeError, ValueError):
        lat, lon = 0, 0
    if not (41.0 <= lat <= 43.7 and 40.0 <= lon <= 46.8):
        lat, lon = 0, 0
    def num(k, lo, hi, typ=float):
        try:
            return min(max(typ(float(d.get(k) or 0)), lo), hi)
        except (TypeError, ValueError):
            return 0
    frame = s("frame", 10)
    handover = s("handover", 7)
    f = {"name": s("name", 120), "city": s("city", 60) or "Tbilisi", "district": s("district", 80), "address": s("address", 160),
         "description": s("description", 5000), "completion": s("completion", 40), "lat": lat, "lon": lon,
         "frame": frame if frame in ("black", "white", "green", "mixed") else "",
         "handover": handover if re.match(r"^20\d\d(-(0[1-9]|1[0-2]))?$", handover) else "",
         "down_pct": num("down_pct", 0, 100), "inst_months": num("inst_months", 0, 120, int), "inst_note": s("inst_note", 300)}
    return (None, "Enter the project name") if not f["name"] else (f, None)


def project_out(con, r):
    d = dict(r)
    stats = con.execute("""SELECT COUNT(*) AS units, MIN(price) AS min_price, MIN(CASE WHEN area>0 THEN price/area END) AS min_ppm,
                                  MAX(currency) AS currency FROM listings WHERE project_id=? AND status='active'""", (r["id"],)).fetchone()
    d.update(dict(stats))
    d["url"] = f"{SITE}/project/?id={r['id']}"
    return d


async def my_projects(request):
    u, e = need_user(request)
    if e:
        return e
    if u["role"] not in ("developer", "admin"):
        return err("Projects are for developer accounts", 403)
    if request.method == "POST":
        d = await body_json(request)
        f, msg = clean_project(d)
        if msg:
            return err(msg)
        now = time.time()
        with _LOCK, db() as con:
            pid = int(d.get("id") or 0)
            if pid:
                row = con.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
                if not row or (row["user_id"] != u["id"] and u["role"] != "admin"):
                    return err("Not found", 404)
                con.execute(f"UPDATE projects SET {','.join(k + '=?' for k in f)}, updated=? WHERE id=?", (*f.values(), now, pid))
            else:
                cur = con.execute(f"INSERT INTO projects (user_id,{','.join(f)},created,updated) VALUES (?,{','.join('?' * len(f))},?,?)",
                                  (u["id"], *f.values(), now, now))
                pid = cur.lastrowid
            audit(con, u, "project_save", "project", pid, f["name"])
        return ok(id=pid)
    if request.method == "DELETE":
        pid = int(request.query_params.get("id") or 0)
        with _LOCK, db() as con:
            con.execute("UPDATE projects SET status='deleted' WHERE id=? AND (user_id=? OR ?)", (pid, u["id"], 1 if u["role"] == "admin" else 0))
        return ok()
    with db() as con:
        rows = con.execute("SELECT * FROM projects WHERE user_id=? AND status!='deleted' ORDER BY id DESC", (u["id"],)).fetchall()
        out = []
        for r in rows:
            d = project_out(con, r)
            d["all_units"] = con.execute("SELECT COUNT(*) FROM listings WHERE project_id=? AND status!='deleted'", (r["id"],)).fetchone()[0]
            out.append(d)
    return ok(projects=out)


async def public_projects(request):
    with db() as con:
        pid = request.query_params.get("id", "")
        if pid.isdigit():
            r = con.execute("SELECT p.*, u.company FROM projects p LEFT JOIN users u ON u.id=p.user_id WHERE p.id=? AND p.status='active'", (int(pid),)).fetchone()
            if not r:
                return err("Project not found", 404)
            units = con.execute("SELECT * FROM listings WHERE project_id=? AND status='active' ORDER BY building, CAST(floor AS INTEGER), unit_no", (r["id"],)).fetchall()
            s = get_settings()
            return ok(project=project_out(con, r), units=[listing_out(x, settings=s) for x in units])
        rows = con.execute("SELECT p.*, u.company FROM projects p LEFT JOIN users u ON u.id=p.user_id WHERE p.status='active' ORDER BY p.id DESC LIMIT 100").fetchall()
        return ok(projects=[project_out(con, r) for r in rows if True])


# ---------------------------------------------------------------- CSV bulk import (partners)

IMPORT_COLS = ["deal", "type", "city", "district", "address", "rooms", "bedrooms", "area", "floor", "total_floors", "price", "currency",
               "title", "description", "contact_name", "contact_phone", "project_id", "building", "unit_no", "lat", "lon"]
DEAL_ALIASES = {"sale": "sale", "sell": "sale", "buy": "sale", "rent": "rent", "lease": "rent", "daily": "daily",
                "იყიდება": "sale", "ქირავდება": "rent", "продажа": "sale", "аренда": "rent"}
TYPE_ALIASES = {"flat": "flat", "apartment": "flat", "house": "house", "villa": "house", "commercial": "commercial", "office": "commercial",
                "shop": "commercial", "land": "land", "plot": "land", "hotel": "hotel", "ბინა": "flat", "სახლი": "house", "квартира": "flat", "дом": "house"}


def parse_csv(raw):
    text = raw.decode("utf-8-sig", errors="replace")
    sample = text[:4000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.DictReader(io.StringIO(text), dialect=dialect))
    out = []
    for r in rows[:1000]:
        r = {str(k or "").strip().lower().replace(" ", "_"): (v or "").strip() for k, v in r.items()}
        if not any(r.values()):
            continue
        r["deal"] = DEAL_ALIASES.get(r.get("deal", "").lower(), r.get("deal", "").lower())
        r["type"] = TYPE_ALIASES.get(r.get("type", "").lower(), r.get("type", "").lower())
        out.append(r)
    return out


async def my_import(request):
    u, e = need_user(request)
    if e:
        return e
    if u["role"] not in PARTNER_ROLES + ("admin",):
        return err("Bulk upload is for agent, agency and developer accounts. Apply at keygroup.ge/partners", 403)
    if request.method == "GET":
        with db() as con:
            rows = con.execute("SELECT * FROM imports WHERE user_id=? ORDER BY id DESC LIMIT 50", (u["id"],)).fetchall()
        return ok(imports=[dict(r) for r in rows], columns=IMPORT_COLS)
    form = await request.form(max_files=1, max_part_size=5 * 1024 * 1024)
    f = form.get("csv")
    if not f:
        return err("Choose a CSV file")
    raw = await f.read()
    rows = parse_csv(raw)
    if not rows:
        return err("The file is empty or not a CSV")
    mode = form.get("mode") or "preview"
    good, errors = [], []
    for i, r in enumerate(rows, start=2):
        if not r.get("contact_phone"):
            r["contact_phone"] = u["phone"]
        if not r.get("contact_name"):
            r["contact_name"] = u.get("company") or u["name"]
        fields, msg = clean_listing(r)
        if msg:
            errors.append({"row": i, "error": msg})
        else:
            good.append(fields)
    s = get_settings()
    limit = listing_limit(u, s)
    with _LOCK, db() as con:
        room = (limit - live_count(con, u["id"])) if limit and u["role"] != "admin" else 10 ** 6
        if mode == "preview":
            return ok(total=len(rows), valid=len(good), errors=errors[:100], room=max(0, room),
                      sample=[{k: g[k] for k in ("deal", "type", "district", "address", "rooms", "area", "price", "currency")} for g in good[:5]])
        if not good:
            return err("No valid rows to import")
        if len(good) > room:
            return err(f"Your plan has room for {max(0, room)} more listings; the file has {len(good)} valid rows.")
        now = time.time()
        cur = con.execute("INSERT INTO imports (user_id, filename, total, imported, errors, created) VALUES (?,?,?,?,?,?)",
                          (u["id"], str(getattr(f, "filename", "") or "upload.csv")[:120], len(rows), len(good), json.dumps(errors[:200]), now))
        bid = cur.lastrowid
        level = 1 if u.get("contact_verified") else 0
        for g in good:
            check_project(con, u, g)
            cols = ",".join(g.keys())
            c2 = con.execute(f"INSERT INTO listings (user_id,{cols},status,created,updated,confirmed,verify_level,batch_id) VALUES (?,{','.join('?' * len(g))},'pending',?,?,?,?,?)",
                             (u["id"], *g.values(), now, now, now, level, bid))
            find_duplicates(con, c2.lastrowid)
        audit(con, u, "bulk_import", "import", bid, f"{len(good)} listings, {len(errors)} rows with errors")
    notify(f"📦 Bulk upload #{bid}: {len(good)} listings from {esc(u.get('company') or u['name'])} ({esc(u['role'])}) waiting for review\n{SITE}/admin/#partners")
    return ok(batch=bid, imported=len(good), errors=errors[:100])


async def admin_import_action(request):
    u, e = need_user(request, perm="partners")
    if e:
        return e
    bid = int(request.path_params["bid"])
    d = await body_json(request)
    action = d.get("action")
    s = get_settings()
    now = time.time()
    with _LOCK, db() as con:
        imp = con.execute("SELECT * FROM imports WHERE id=?", (bid,)).fetchone()
        if not imp:
            return err("Not found", 404)
        if action == "approve_all":
            exp = now + s["plans"]["free"]["days"] * 86400
            n = con.execute("UPDATE listings SET status='active', approved=?, expires=?, reject_reason='' WHERE batch_id=? AND status='pending' AND dup_of=''",
                            (now, exp, bid)).rowcount
            con.execute("UPDATE imports SET status='approved' WHERE id=?", (bid,))
        elif action == "rollback":
            n = con.execute("UPDATE listings SET status='deleted', updated=? WHERE batch_id=? AND status!='deleted'", (now, bid)).rowcount
            con.execute("UPDATE imports SET status='rolled_back' WHERE id=?", (bid,))
        else:
            return err("Unknown action")
        audit(con, u, "import_" + action, "import", bid, f"{n} listings")
    return ok(count=n)


# ---------------------------------------------------------------- admin 2-step login

async def admin_2fa(request):
    u, e = need_user(request, perm="stats")
    if e:
        return e
    d = await body_json(request)
    action = d.get("action")
    with _LOCK, db() as con:
        if action == "setup":
            secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
            con.execute("UPDATE users SET totp_secret=?, totp_on=0 WHERE id=?", (secret, u["id"]))
            label = urllib.parse.quote(f"KEY GROUP admin:{u['phone']}")
            return ok(secret=secret, uri=f"otpauth://totp/{label}?secret={secret}&issuer=KEY%20GROUP&digits=6&period=30")
        if action == "enable":
            if not totp_ok(u["totp_secret"], d.get("code")):
                return err("Wrong code — scan again and enter the current 6-digit code")
            con.execute("UPDATE users SET totp_on=1 WHERE id=?", (u["id"],))
            audit(con, u, "2fa_enabled", "user", u["id"])
            return ok()
        if action == "disable":
            if u["totp_on"] and not totp_ok(u["totp_secret"], d.get("code")):
                return err("Enter the current code from your app to turn it off")
            con.execute("UPDATE users SET totp_on=0, totp_secret='' WHERE id=?", (u["id"],))
            audit(con, u, "2fa_disabled", "user", u["id"])
            return ok()
    return err("Unknown action")


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
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=31536000, immutable",
                                                                "Access-Control-Allow-Origin": "*"})   # the MyHome / SS publisher reads photos


# ---------------------------------------------------------------- admin endpoints

async def admin_stats(request):
    u, e = need_user(request, perm="stats")
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
        leads_new = con.execute("SELECT COUNT(*) FROM leads WHERE stage='new'").fetchone()[0]
        no_photos = con.execute("SELECT COUNT(*) FROM listings WHERE status IN ('pending','active') AND (photos='[]' OR photos='')").fetchone()[0]
        viewings_soon = con.execute("SELECT COUNT(*) FROM leads WHERE viewing_at BETWEEN ? AND ?", (now, now + 7 * 86400)).fetchone()[0]
        apps_new = con.execute("SELECT COUNT(*) FROM partner_apps WHERE status='new'").fetchone()[0]
        partners = con.execute(f"SELECT COUNT(*) FROM users WHERE role IN ({','.join('?' * len(PARTNER_ROLES))})", PARTNER_ROLES).fetchone()[0]
        dups = con.execute("SELECT COUNT(*) FROM listings WHERE dup_of!='' AND status IN ('pending','active','changes')").fetchone()[0]
        chats_waiting = con.execute("SELECT COUNT(*) FROM chats WHERE status IN ('waiting','agent') AND unread>0").fetchone()[0]
        chats_today = con.execute("SELECT COUNT(DISTINCT chat_id) FROM chat_msgs WHERE who='visitor' AND ts>?", (now - 86400,)).fetchone()[0]
    return ok(stats={"no_photos": no_photos, "viewings_soon": viewings_soon, "role": u["role"], "leads_new": leads_new, "apps_new": apps_new, "partners": partners, "duplicates": dups, "chats_waiting": chats_waiting, "chats_today": chats_today, "listings": by_status, "owners": users, "orders_waiting": await_pay, "revenue_30d": paid_30,
                     "vip_active": vip, "reports_open": reports, "currency": get_settings()["currency"]})


async def admin_listings(request):
    u, e = need_user(request, perm="listings")
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
        ext = ext_map(con, [r["id"] for r in rows])
    s = get_settings()
    out = [listing_out(r, admin_view=True, settings=s) for r in rows]
    for o in out:
        o["ext"] = ext.get(o["id"], {})
    return ok(listings=out)


async def admin_listing_action(request):
    u, e = need_user(request, perm="listings")
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
    u, e = need_user(request, perm="reports")
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
    u, e = need_user(request, perm="orders")
    if e:
        return e
    with db() as con:
        rows = con.execute("""SELECT o.*, u.name AS owner_name, u.phone AS owner_phone, l.district, l.address, l.status AS listing_status
                              FROM orders o LEFT JOIN users u ON u.id=o.user_id LEFT JOIN listings l ON l.id=o.listing_id
                              ORDER BY o.id DESC LIMIT 300""").fetchall()
    return ok(orders=[dict(r) for r in rows])


async def admin_order_action(request):
    u, e = need_user(request, perm="orders")
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
                # temporary password + one-time login link (24 h); the user must choose a new password after logging in
                t = con.execute("SELECT role, phone, name, tg_id FROM users WHERE id=?", (uid,)).fetchone()
                if not t:
                    return err("User not found", 404)
                if t["role"] == "admin":
                    return err("Admin passwords are changed with reset.sh on the server")
                pw = "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz23456789") for _ in range(8))
                con.execute("UPDATE users SET pw=?, pw_set=0 WHERE id=?", (hash_pw(pw), uid))
                con.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
                tok = secrets.token_urlsafe(24)
                con.execute("INSERT INTO login_tokens (token, user_id, expires) VALUES (?,?,?)", (tok, uid, time.time() + 86400))
                con.execute("UPDATE login_tokens SET purpose='reset' WHERE token=?", (tok,))
                sent_tg = False
                if t["tg_id"]:
                    con.execute("INSERT INTO bot_outbox (tg_id, text, button_url, button_text, created) VALUES (?,?,?,?,?)",
                                (t["tg_id"], f"🔑 <b>KEY GROUP</b> — შენი keygroup.ge პაროლი განულდა.\n\nდროებითი პაროლი: <code>{pw}</code>\n"
                                 f"ან დააჭირე ღილაკს (მუშაობს 24 საათი, ერთხელ) და დააყენე ახალი პაროლი.\n\nYour keygroup.ge password was reset. Tap the button and set a new one.",
                                 f"{SITE}/api/login/link?t={tok}", "🔐 შესვლა · Log in", time.time()))
                    sent_tg = True
                audit(con, u, "reset_password", "user", uid, t["name"] + (" (sent to Telegram)" if sent_tg else ""))
                return ok(password=pw, phone=t["phone"], name=t["name"], link=f"{SITE}/api/login/link?t={tok}", telegram=sent_tg)
            elif action == "set_role":
                role = d.get("role")
                if role not in ("owner",) + PARTNER_ROLES + ("moderator", "finance"):
                    return err("Unknown role")
                con.execute("UPDATE users SET role=? WHERE id=? AND role!='admin'", (role, uid))
            elif action == "get_profile":
                t = con.execute("SELECT id, name, company, slug, email, bio, links, role, phone FROM users WHERE id=?", (uid,)).fetchone()
                if not t:
                    return err("User not found", 404)
                out = dict(t)
                try:
                    out["links"] = json.loads(out["links"] or "{}")
                except ValueError:
                    out["links"] = {}
                return ok(profile=out)
            elif action == "edit_profile":
                t = con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
                if not t:
                    return err("User not found", 404)
                msg = save_profile(con, dict(t), d.get("profile") or {})
                if msg:
                    return err(msg)
            elif action == "set_limit":
                con.execute("UPDATE users SET listing_limit=? WHERE id=?", (max(0, min(100000, int(d.get("limit") or 0))), uid))
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
        rows = con.execute("""SELECT u.id, u.phone, u.name, u.role, u.blocked, u.created, u.contact_verified, u.consent_at, u.company, u.listing_limit, u.partner_until, u.last_login, u.pw_set,
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
        for r, v in (d.get("role_limits") or {}).items():
            if r in PARTNER_ROLES:
                try:
                    s["role_limits"][r] = max(0, min(100000, int(v)))
                except (TypeError, ValueError):
                    pass
        for k in ("free_listing_limit", "reconfirm_days", "founding_days"):
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
                m = re.search(r"/p/\?id=(\d+)", chat["page"] or "")
                lrow = con.execute("SELECT * FROM listings WHERE id=?", (int(m.group(1)),)).fetchone() if m else None
                if lrow:
                    con.execute("INSERT INTO leads (listing_id, owner_id, name, phone, message, source, consent_at, created, updated) VALUES (?,?,?,?,?,?,?,?,?)",
                                (lrow["id"], lrow["user_id"], state.get("name", ""), state.get("phone", ""), state.get("topic", ""), "chat", time.time(), time.time(), time.time()))
                    alert_owner(con, lrow["user_id"], lrow["id"], lrow, state.get("name", ""), state.get("phone", ""), state.get("topic", ""), "chat")
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
    u, e = need_user(request, perm="chats")
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
    u, e = need_user(request, perm="chats")
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
               "chat_opened", "chat_question", "valuation_requested", "share_click", "favorite_added", "partner_application",
               "yield_calc", "compare_opened", "search_saved", "video_played", "agent_profile_viewed"}


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
    u, e = need_user(request, perm="analytics")
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


async def admin_performance(request):
    """Who answers leads how fast, and where the supply is."""
    u, e = need_user(request, perm="analytics")
    if e:
        return e
    since = time.time() - 90 * 86400
    with db() as con:
        agents = [dict(r) for r in con.execute("""
            SELECT COALESCE(a.id, o.id) AS uid, COALESCE(a.name, o.name) AS name, COALESCE(a.company, o.company) AS company, COALESCE(a.role, o.role) AS role,
                   COUNT(*) AS leads, SUM(d.stage='new') AS untouched, SUM(d.stage IN ('viewing','offer','closed')) AS viewings, SUM(d.stage='closed') AS closed,
                   AVG(CASE WHEN d.first_action_at>0 THEN (d.first_action_at-d.created)/3600.0 END) AS avg_hours
            FROM leads d LEFT JOIN users o ON o.id=d.owner_id LEFT JOIN users a ON a.id=d.assigned_to
            WHERE d.created>? GROUP BY uid ORDER BY leads DESC LIMIT 50""", (since,))]
        supply = [dict(r) for r in con.execute("""SELECT COALESCE(NULLIF(city,''),'Tbilisi') AS city, COALESCE(NULLIF(district,''),'—') AS district,
                    SUM(deal='rent') AS rent, SUM(deal='sale') AS sale, SUM(deal='daily') AS daily, COUNT(*) AS total
                    FROM listings WHERE status='active' GROUP BY city, district ORDER BY total DESC LIMIT 40""")]
        viewings = [dict(r) for r in con.execute("""SELECT d.id, d.name, d.phone, d.viewing_at, d.listing_id, l.title, l.district, o.name AS agent
                    FROM leads d LEFT JOIN listings l ON l.id=d.listing_id LEFT JOIN users o ON o.id=COALESCE(NULLIF(d.assigned_to,0), d.owner_id)
                    WHERE d.viewing_at>? ORDER BY d.viewing_at LIMIT 50""", (time.time() - 3600,))]
        quality = con.execute("""SELECT SUM(photos='[]' OR photos='') AS no_photos, SUM(lat=0) AS no_pin, SUM(verify_level>=2) AS verified, COUNT(*) AS total
                                 FROM listings WHERE status='active'""").fetchone()
    crm = {}
    for r in chatbot._crm_listings():
        d = str(r.get("d") or "").strip()
        if d and not d.startswith("#"):
            name = chatbot.KA_TO_EN.get(d, d)
            crm[name] = crm.get(name, 0) + 1
    return ok(agents=agents, supply=supply, viewings=viewings, quality=dict(quality),
              crm_supply=sorted(({"district": k, "total": v} for k, v in crm.items()), key=lambda x: -x["total"])[:25])


_CRM_CACHE = {"at": 0, "data": None}


def fetch_crm(force=False):
    """CRM tabs from the Google Apps Script web app (private, secret-protected); cached 10 minutes in memory + on disk."""
    path = os.path.join(DATA_DIR, "crm_cache.json")
    if not force and _CRM_CACHE["data"] and time.time() - _CRM_CACHE["at"] < 600:
        return _CRM_CACHE["data"], None
    if not CRM_URL or not CRM_SECRET:
        return None, "CRM connection is not configured on the server (CRM_URL / CRM_SECRET)."
    try:
        url = CRM_URL + ("&" if "?" in CRM_URL else "?") + urllib.parse.urlencode({"action": "crmExport", "secret": CRM_SECRET})
        raw = urllib.request.urlopen(url, timeout=60).read()
        data = json.loads(raw.decode("utf-8"))
        if not data.get("ok"):
            raise ValueError(data.get("error") or "CRM refused the request")
        data["fetched"] = time.time()
        _CRM_CACHE.update(at=time.time(), data=data)
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False)
        except OSError:
            pass
        return data, None
    except Exception as ex:
        msg = str(ex)
        if "unauthorized" in msg:
            msg = "The CRM did not accept the secret key."
        elif "Unexpected" in msg or "Expecting value" in msg:
            msg = "The CRM web app does not have the export yet — publish a new version of the Apps Script deployment."
        if os.path.exists(path):
            try:
                old = json.load(open(path, encoding="utf-8"))
                return old, f"Showing the last saved copy — live refresh failed: {msg}"
            except Exception:
                pass
        return None, msg


async def admin_crm(request):
    u, e = need_user(request, perm="crm")
    if e:
        return e
    import asyncio
    data, warn = await asyncio.get_running_loop().run_in_executor(None, fetch_crm, request.query_params.get("refresh") == "1")
    if not data:
        return err(warn or "CRM unavailable", 502)
    return ok(crm=data, warning=warn)


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
    Route("/sitemap.xml", sitemap_xml),
    Route("/robots.txt", robots_txt),
    Route("/api/sitemap.xml", sitemap_xml),
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
    Route("/api/listings/{lid:int}/enquiry", listing_enquiry, methods=["POST"]),
    Route("/api/my/leads", my_leads, methods=["GET", "POST"]),
    Route("/api/my/import", my_import, methods=["GET", "POST"]),
    Route("/api/my/team", my_team, methods=["GET", "POST", "DELETE"]),
    Route("/api/my/projects", my_projects, methods=["GET", "POST", "DELETE"]),
    Route("/api/projects", public_projects),
    Route("/api/agents", public_agent),
    Route("/api/bot/listing", bot_listing, methods=["POST"]),
    Route("/api/bot/agent-access", bot_agent_access, methods=["POST"]),
    Route("/api/bot/reset-link", bot_reset_link, methods=["POST"]),
    Route("/api/my/listings/{lid:int}/publish-code", publish_code, methods=["POST"]),
    Route("/api/my/listings/{lid:int}/ext", listing_ext, methods=["POST"]),
    Route("/api/publish/{code}/done", publish_done, methods=["POST", "OPTIONS"]),
    Route("/api/my/ss-link-code", ss_link_code, methods=["POST"]),
    Route("/api/ss-match/{code}", ss_match, methods=["POST", "OPTIONS"]),
    Route("/api/publish/{code}", publish_data),
    Route("/api/bot/outbox", bot_outbox, methods=["POST"]),
    Route("/api/bot/source-gone", bot_source_gone, methods=["POST"]),
    Route("/api/bot/daily-report", bot_daily_report, methods=["POST"]),
    Route("/api/my/profile", my_profile, methods=["GET", "POST"]),
    Route("/api/admin/agents", admin_agents, methods=["GET", "POST"]),
    Route("/api/login/link", login_link, methods=["GET", "POST"]),
    Route("/api/partners/apply", partner_apply, methods=["POST"]),
    Route("/api/admin/leads", admin_leads),
    Route("/api/admin/partners", admin_partners),
    Route("/api/admin/partners/{aid:int}", admin_partner_action, methods=["POST"]),
    Route("/api/admin/imports/{bid:int}", admin_import_action, methods=["POST"]),
    Route("/api/admin/2fa", admin_2fa, methods=["POST"]),
    Route("/api/admin/analytics", admin_analytics),
    Route("/api/admin/audit", admin_audit),
    Route("/api/admin/performance", admin_performance),
    Route("/api/admin/crm", admin_crm),
    Route("/api/my/listings/{lid:int}/confirm", confirm_listing, methods=["POST"]),
    Route("/api/chat/send", chat_send, methods=["POST"]),
    Route("/api/chat/poll", chat_poll),
    Route("/api/admin/chats", admin_chats),
    Route("/api/admin/chats/{cid:int}", admin_chat, methods=["GET", "POST"]),
]

init_db()
ensure_admin()
app = Starlette(routes=routes)
