"""Read every listing from an agent's own MyHome.ge / SS.ge profile.

MyHome.ge: the public profile page  https://www.myhome.ge/udzravi-qoneba/?users=<ID>&page=N
is server-rendered; its __NEXT_DATA__ holds 24 full listings per page (price, rooms,
area, address, description, photos ...). We read pages until a page has < 24 items.

SS.ge: the profile list is loaded by a logged-in API, so for SS.ge we keep the
profile link and read SS.ge listings one by one when the agent sends them.
"""
import hashlib
import html as htmllib
import json
import re
import time

import extract

MH_PROFILE = "https://www.myhome.ge/udzravi-qoneba/?users={uid}&page={page}"
PAGE_SIZE = 24
MAX_PAGES = 60

MH_DEAL = {1: "sale", 2: "rent", 3: "pledge", 7: "daily"}
MH_TYPE = {1: "flat", 2: "house", 3: "house", 4: "land", 5: "commercial", 6: "hotel"}


def parse_profile_input(text):
    """Return ('myhome', user_id) / ('ss', user_uuid) / ('myhome-listing', listing_url) or None."""
    t = text or ""
    m = re.search(r"myhome\.ge/[^\s]*[?&]users=(\d+)", t)
    if m:
        return "myhome", m.group(1)
    m = re.search(r"ss\.ge/[^\s]*userlist\?userId=([0-9a-f-]{36})", t, re.I)
    if m:
        return "ss", m.group(1).lower()
    url = extract.find_url(t)
    if url and "myhome.ge" in url and extract.listing_id(url):
        return "myhome-listing", url
    if url and "ss.ge" in url and extract.listing_id(url):
        return "ss-listing", url
    return None


def myhome_user_from_listing(url):
    """Open one of the agent's own MyHome listings and read its owner user_id."""
    page = extract.fetch(url)
    m = re.search(r'"user_id"\s*:\s*(\d+)', page)
    return m.group(1) if m else None


def ss_user_from_listing(url):
    page = extract.fetch(url)
    m = re.search(r'"userId"\s*:\s*"([0-9a-f-]{36})"', page, re.I)
    return m.group(1).lower() if m else None


def _statements(page_html):
    m = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', page_html, re.S)
    if not m:
        raise ValueError("MyHome page has no data block (site changed or blocked)")
    nd = json.loads(m.group(1))
    for q in nd["props"]["pageProps"]["dehydratedState"]["queries"]:
        key = json.dumps(q.get("queryKey"))
        if '"statements"' in key and '"list"' in key:
            data = (q.get("state") or {}).get("data") or {}
            inner = data.get("data") or {}
            items = inner.get("data") if isinstance(inner, dict) else None
            return items if isinstance(items, list) else []
    return []


def _clean(text):
    t = re.sub(r"<br\s*/?>\s*\n?", "\n", str(text or ""), flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = htmllib.unescape(t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def map_myhome_item(it):
    price = it.get("price") or {}
    usd = (price.get("2") or {}).get("price_total")
    gel = (price.get("1") or {}).get("price_total")
    title = it.get("dynamic_title") or ""
    deal = MH_DEAL.get(it.get("deal_type_id")) or extract.norm_deal("", title)
    typ = MH_TYPE.get(it.get("real_estate_type_id")) or extract.norm_type("", title)
    if "კომერც" in title or "ფართ" in title:
        typ = "commercial"
    images = [im.get("large") for im in (it.get("images") or []) if im.get("large")]
    rec = {
        "source": "myhome", "id": str(it.get("id")),
        "url": f"https://www.myhome.ge/pr/{it.get('id')}/",
        "title": title, "deal": deal, "type": typ,
        "city": it.get("city_name") or "", "district": it.get("urban_name") or it.get("district_name") or "",
        "address": it.get("address") or "",
        "rooms": str(it.get("room") or ""), "bedrooms": str(it.get("bedroom") or ""),
        "floor": str(it.get("floor") or ""), "total_floors": str(it.get("total_floors") or ""),
        "area": str(it.get("area") or ""), "price_usd": str(usd or ""), "price_gel": str(gel or ""),
        "description": _clean(it.get("comment"))[:3000],
        "images": images, "photos": len(images),
        "updated_on_site": it.get("last_updated") or "",
        "status_on_site": "hidden" if it.get("hidden") else "active",
    }
    rec["hash"] = fingerprint(rec)
    return rec


def fingerprint(rec):
    keys = ("title", "deal", "type", "address", "rooms", "bedrooms", "floor", "total_floors", "area",
            "price_usd", "price_gel", "description", "photos", "status_on_site")
    raw = json.dumps([rec.get(k) for k in keys], ensure_ascii=False)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]


def myhome_profile(user_id, fetch=extract.fetch, pause=1.0):
    """All listings on a MyHome profile, as mapped records."""
    out, seen = [], set()
    for page in range(1, MAX_PAGES + 1):
        items = _statements(fetch(MH_PROFILE.format(uid=user_id, page=page)))
        for it in items:
            if str(it.get("user_id")) != str(user_id):
                continue
            rec = map_myhome_item(it)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                out.append(rec)
        if len(items) < PAGE_SIZE:
            break
        time.sleep(pause)
    return out


def from_single_listing(d):
    """Convert an extract.extract() result (one MyHome/SS.ge listing) into a profile record."""
    rec = {
        "source": d.get("source"), "id": str(d.get("id")), "url": d.get("url"),
        "title": d.get("title") or "", "deal": d.get("deal") or "", "type": d.get("type") or "",
        "city": d.get("city") or "", "district": d.get("district") or "", "address": d.get("address") or "",
        "rooms": str(d.get("rooms") or ""), "bedrooms": str(d.get("bedrooms") or ""),
        "floor": str(d.get("floor") or ""), "total_floors": str(d.get("total_floors") or ""),
        "area": str(d.get("area") or ""), "price_usd": str(d.get("price_usd") or ""),
        "price_gel": str(d.get("price") if (d.get("currency") or "").upper() in ("GEL", "₾") else ""),
        "description": (d.get("description") or "")[:3000],
        "images": d.get("images") or [], "photos": len(d.get("images") or []),
        "updated_on_site": "", "status_on_site": "active",
    }
    rec["hash"] = fingerprint(rec)
    return rec
