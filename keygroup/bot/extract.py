"""Extract listing data from a MyHome.ge or SS.ge listing page.

Both sites are Next.js apps: the full listing is embedded in the page as JSON
(<script id="__NEXT_DATA__"> or self.__next_f chunks). We search that JSON for
the listing fields by key names, so small layout changes on the sites do not
break the bot. Visible page text and <meta> tags are used as a fallback.
"""
import html as htmllib
import json
import re

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

URL_RE = re.compile(r"https?://[^\s<>]*(?:myhome\.ge|ss\.ge)[^\s<>]*", re.I)


def find_url(text):
    m = URL_RE.search(text or "")
    return m.group(0).rstrip(").,") if m else None


def site_of(url):
    return "myhome" if "myhome.ge" in url.lower() else "ss"


def is_private_link(url):
    """The agent's own MyHome / SS.ge cabinet (my statements, profile settings) — not a public listing."""
    u = (url or "").lower()
    return "statements.myhome.ge" in u or "my-statements" in u or "user-profile" in u or "/cabinet" in u or "/myaccount" in u


def listing_id(url):
    u = (url or "").split("#")[0]
    m = re.search(r"/pr/(\d{5,})", u)
    if m:
        return m.group(1)
    if is_private_link(u):
        return ""
    m = re.search(r"(\d{6,})", u.split("?")[0])   # never read numbers from tracking parameters (?_ga=…)
    return m.group(1) if m else ""


# ---------------------------------------------------------------- fetching

BROWSER_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ka-GE,ka;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache", "Pragma": "no-cache", "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "none", "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"', "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}


class Blocked(Exception):
    """The site refused the server (status code in .status)."""
    def __init__(self, status):
        super().__init__(f"HTTP {status}")
        self.status = status


def fetch(url, timeout=25):
    """Fetch like a normal browser; one retry with a session (cookies) if the site refuses the first time."""
    last = None
    for attempt in range(2):
        try:
            sess = requests.Session()
            if attempt:
                host = re.match(r"https?://[^/]+", url)
                if host:   # visit the home page first to pick up cookies, as a person would
                    sess.get(host.group(0) + "/", headers=BROWSER_HEADERS, timeout=timeout)
            r = sess.get(url, headers=dict(BROWSER_HEADERS, Referer="https://www.google.com/"), timeout=timeout)
            if r.status_code < 400:
                return r.text
            last = r.status_code
        except requests.RequestException:
            if attempt:
                raise
    raise Blocked(last)


SLUG_DEAL = {"qiravdeba": "rent", "iyideba": "sale", "giravdeba": "rent", "qiravdeba-dgiurad": "daily"}
SLUG_TYPE = {"bina": "flat", "saxli": "house", "kerdzo-saxli": "house", "agaraki": "house", "komerciuli": "commercial",
             "farti": "commercial", "mitsa": "land", "miwa": "land", "sastumro": "hotel"}


def from_slug(url):
    """When the site blocks the server: what the link itself says
    (…/qiravdeba-3-otaxiani-bina-chughuretshi-37165239 -> rent, 3 rooms, flat, Chughureti)."""
    path = (url or "").split("?")[0].rstrip("/").rsplit("/", 1)[-1].lower()
    words = path.split("-")
    d = {"source": site_of(url), "url": url, "id": listing_id(url), "title": "", "description": "", "deal": "", "type": "",
         "price": "", "price_usd": "", "currency": "", "area": "", "rooms": "", "bedrooms": "", "floor": "", "total_floors": "",
         "city": "", "district": "", "address": "", "phone": "", "owner": "", "images": [], "features": [], "details": [],
         "from_link_only": True}
    for w in words:
        if w in SLUG_DEAL and not d["deal"]:
            d["deal"] = SLUG_DEAL[w]
        if w in SLUG_TYPE and not d["type"]:
            d["type"] = SLUG_TYPE[w]
    m = re.search(r"(\d+)-otaxiani", path)
    if m:
        d["rooms"] = int(m.group(1))
    for w in words:   # "chughuretshi" / "saburtaloze" / "vakeshi" -> district
        if re.search(r"(shi|ze|tan)$", w) and not w.isdigit() and len(w) > 5:
            base = re.sub(r"(shi|ze|tan)$", "", w)
            d["district"] = base[:1].upper() + base[1:] + ("i" if not base.endswith(("i", "o", "a", "e")) else "")
            break
    if "batum" in path:
        d["city"] = "Batumi"
    return d


def json_blobs(page):
    """All JSON objects embedded in the page."""
    blobs = []
    m = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if m:
        try:
            blobs.append(json.loads(m.group(1)))
        except ValueError:
            pass
    # Next.js app-router streaming chunks: self.__next_f.push([1,"..."])
    for chunk in re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', page, re.S):
        try:
            text = json.loads('"' + chunk + '"')
        except ValueError:
            continue
        for part in re.findall(r'(\{.*\})', text, re.S):
            try:
                blobs.append(json.loads(part))
            except ValueError:
                continue
    for ld in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.S):
        try:
            blobs.append(json.loads(ld))
        except ValueError:
            pass
    return blobs


def walk(obj, depth=0):
    """Yield every dict inside a JSON structure."""
    if depth > 40:
        return
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v, depth + 1)


def meta(page, prop):
    m = re.search(r'<meta[^>]+(?:property|name)="%s"[^>]+content="([^"]*)"' % re.escape(prop), page)
    return htmllib.unescape(m.group(1)).strip() if m else ""


# ---------------------------------------------------------------- field search

KEYS = {
    "title": ["dynamic_title", "dynamicTitle", "title", "name"],
    "description": ["comment", "description", "descriptionText", "text"],
    "price_usd": ["price_usd", "priceUsd", "usd", "total_price_usd"],
    "price": ["price", "totalPrice", "price_total", "priceGel"],
    "currency": ["currency", "currency_id", "priceCurrency"],
    "area": ["area", "totalArea", "area_total", "square", "space"],
    "rooms": ["room", "rooms", "roomsCount", "room_type_id", "numberOfRooms"],
    "bedrooms": ["bedroom", "bedrooms", "bedroomsCount", "bedroom_type_id"],
    "floor": ["floor", "floorNumber"],
    "total_floors": ["total_floors", "totalFloors", "floors", "totalAmountOfFloor"],
    "district": ["district_name", "districtName", "district", "subdistrict_name", "subDistrictTitle", "urban_name"],
    "city": ["city_name", "cityName", "city", "cityTitle"],
    "address": ["address", "street_address", "streetAddress", "address_name", "street"],
    "phone": ["user_phone_number", "phone_number", "phoneNumber", "phone", "contactPhone"],
    "owner": ["user_name", "username", "owner_name", "contactName", "applicantName"],
    "deal": ["deal_type_id", "dealType", "deal_type", "transactionType"],
    "type": ["real_estate_type_id", "realEstateType", "type_name", "estateType"],
}

DEAL_WORDS = {"sale": ["იყიდება", "sale", "продается", "1"], "rent": ["ქირავდება", "rent", "аренда", "2"]}


def scalar(v):
    if isinstance(v, (str, int, float)) and not isinstance(v, bool):
        s = str(v).strip()
        return s if s and s.lower() not in ("null", "none", "0", "") else ""
    if isinstance(v, dict):
        for k in ("title", "name", "value", "text", "ka", "en"):
            if k in v and isinstance(v[k], (str, int, float)):
                return str(v[k]).strip()
    return ""


def best_listing_dict(blobs, lid):
    """The dict that most looks like the listing (has the most known keys)."""
    want = {k for ks in KEYS.values() for k in ks}
    best, score = None, 0
    for b in blobs:
        for d in walk(b):
            s = len(want.intersection(d.keys()))
            if lid and str(d.get("id", "")) == lid:
                s += 5
            if s > score:
                best, score = d, s
    return best or {}


def pick(d, field):
    for k in KEYS[field]:
        if k in d:
            v = scalar(d[k])
            if v:
                return v
    return ""


def images(blobs, page):
    out = []
    for b in blobs:
        for d in walk(b):
            for k in ("large", "large_url", "blur", "image", "url", "thumb", "src"):
                v = d.get(k)
                if isinstance(v, str) and re.search(r"\.(jpe?g|png|webp)(\?|$)", v, re.I) and v.startswith("http"):
                    if "large" in k or "image" in k or "url" in k:
                        out.append(v)
                    break
    if not out:
        out = re.findall(r'https://[^"\s]+?(?:static\.my\.ge|static\.ss\.ge|ss\.ge/Photos)[^"\s]+?\.(?:jpe?g|webp|png)', page)
    og = meta(page, "og:image")
    if og:
        out.insert(0, og)
    seen, uniq = set(), []
    for u in out:
        key = re.sub(r"/(thumbs|small|medium|large|blur)/", "/", u.split("?")[0])
        if key not in seen:
            seen.add(key)
            uniq.append(u)
    return uniq[:20]


def norm_deal(v, text):
    s = str(v).lower()
    for deal, words in DEAL_WORDS.items():
        if s in words or any(w in s for w in words[:3]):
            return deal
    t = text.lower()
    if "ქირავდება" in t or "for rent" in t:
        return "rent"
    if "იყიდება" in t or "for sale" in t:
        return "sale"
    return ""


def norm_type(v, text):
    s = (str(v) + " " + text).lower()
    for word, t in (("კერძო სახლ", "house"), ("აგარაკ", "house"), ("house", "house"), ("მიწ", "land"), ("land", "land"),
                    ("კომერც", "commercial"), ("commercial", "commercial"), ("ოფის", "commercial"),
                    ("სასტუმრ", "hotel"), ("ბინა", "flat"), ("apartment", "flat"), ("flat", "flat")):
        if word in s:
            return t
    return "flat"


def num(v):
    m = re.search(r"\d[\d\s.,]*", str(v or ""))
    if not m:
        return ""
    s = m.group(0).replace(" ", "").replace(",", "")
    try:
        f = float(s)
        return str(int(f)) if f == int(f) else str(f)
    except ValueError:
        return ""


NO_AGENCY_RE = re.compile(
    r"(სააგენტ[ოე][^\n.!]{0,40}(არ|ნუ)\b|(არ|ნუ)[^\n.!]{0,25}სააგენტ|"
    r"agenc(y|ies)[^\n.!]{0,30}(not|don.?t|no)\b|(no|not)[^\n.!]{0,15}agenc|"
    r"агентств[^\n.!]{0,30}не\b|без\s+агентств|не\s+беспоко)", re.I)


def refuses_agencies(text):
    return bool(NO_AGENCY_RE.search(text or ""))


def first(*vals):
    for v in vals:
        if v not in (None, "", 0, [], {}):
            return v
    return ""


MH_DEAL = {1: "sale", 2: "rent", 3: "pledge", 7: "rent"}
MH_TYPE = {1: "flat", 2: "house", 3: "house", 4: "land", 5: "commercial", 6: "hotel"}


def parse_myhome(page, url):
    m = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not m:
        return None
    try:
        nd = json.loads(m.group(1))
        queries = nd["props"]["pageProps"]["dehydratedState"]["queries"]
    except (ValueError, KeyError, TypeError):
        return None
    st = None
    for q in queries:
        data = (q.get("state") or {}).get("data")
        if isinstance(data, dict) and isinstance(data.get("data"), dict) and data["data"].get("statement"):
            st = data["data"]["statement"]
            break
    if not st:
        return None
    price = st.get("price") or {}
    usd = (price.get("2") or {}).get("price_total")
    gel = (price.get("1") or {}).get("price_total")
    comment = re.sub(r"<br\s*/?>", "\n", str(st.get("comment") or ""))
    title = st.get("dynamic_title") or ""
    return {
        "source": "myhome", "url": url, "id": str(st.get("id") or listing_id(url)),
        "title": title, "description": htmllib.unescape(comment).strip(),
        "deal": MH_DEAL.get(st.get("deal_type_id"), norm_deal("", title)),
        "type": MH_TYPE.get(st.get("real_estate_type_id"), norm_type("", title)),
        "price_usd": num(usd), "price": num(gel), "currency": "GEL" if gel else "",
        "area": num(st.get("area")), "rooms": num(st.get("room_type_id")), "bedrooms": num(st.get("bedroom_type_id")),
        "floor": num(st.get("floor")), "total_floors": num(st.get("total_floors")),
        "city": st.get("city_name") or "", "district": first(st.get("urban_name"), st.get("district_name")),
        "address": st.get("address") or "",
        "phone": str(st.get("user_phone_number") or ""), "phone_masked": "*" in str(st.get("user_phone_number") or ""),
        "owner": st.get("owner_name") or "",
        "posted_by_agency": str((st.get("user_type") or {}).get("type") or "physical").lower() != "physical",
        "images": [i.get("large") for i in (st.get("images") or []) if isinstance(i, dict) and i.get("large")][:20],
        "user_id": str(st.get("user_id") or ""),
        "features": mh_features(st), "details": mh_details(st),
        "lat": num(st.get("lat")), "lon": num(st.get("lng")), "posted_at": str(st.get("created_at") or ""),
        "video_url": str(st.get("youtube_link") or ""),
    }


def mh_features(st):
    """Amenities ticked on MyHome (internet, gas, furniture, conditioner…) — Georgian display names."""
    out = []
    for p in st.get("parameters") or []:
        if isinstance(p, dict) and p.get("display_name"):
            v = p.get("parameter_value")
            out.append(p["display_name"] + (f": {v}" if v not in (None, "", True) else ""))
    return out[:40]


def mh_details(st):
    """Extra specifications as (Georgian label, value) pairs."""
    rows = [("მდგომარეობა", st.get("condition")), ("აშენების წელი", st.get("build_year")),
            ("აივანი", st.get("balconies") and f"{st.get('balconies')}" + (f" ({st.get('balcony_area')} მ²)" if st.get("balcony_area") else "")),
            ("ჭერის სიმაღლე", st.get("height") and f"{st.get('height')} მ"), ("ცხელი წყალი", st.get("hot_water_type")),
            ("კარ-ფანჯარა", st.get("door_window_type")), ("მისაღები", st.get("living_room_type")),
            ("ეზო", st.get("yard_area") and f"{st.get('yard_area')} მ²"), ("სათავსო", st.get("storeroom_area") and f"{st.get('storeroom_area')} მ²"),
            ("ლოჯი", st.get("loggia_area") and f"{st.get('loggia_area')} მ²"), ("აუზი", st.get("swimming_pool_type")),
            ("ფასი შეთანხმებით", "კი" if st.get("price_negotiable") else ""), ("გაცვლა", "შესაძლებელია" if st.get("can_exchanged") else "")]
    return [[k, str(v)] for k, v in rows if v not in (None, "", 0, False)]


SS_DEAL = {1: "rent", 2: "pledge", 4: "sale"}  # fallback only; the deal text is used first


def parse_ss(page, url):
    m = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not m:
        return None
    try:
        a = json.loads(m.group(1))["props"]["pageProps"]["applicationData"]
    except (ValueError, KeyError, TypeError):
        return None
    if not isinstance(a, dict) or not a.get("applicationId"):
        return None
    addr = a.get("address") or {}
    price = a.get("price") or {}
    desc = a.get("description") or {}
    desc_ka = desc.get("ka") if isinstance(desc, dict) else str(desc)
    phones = a.get("applicationPhones") or []
    phone = next((p.get("phoneNumber") for p in phones if p.get("isMain")), phones[0].get("phoneNumber") if phones else "")
    title = a.get("title") or ""
    street = " ".join(x for x in (addr.get("streetTitle"), addr.get("streetNumber")) if x)
    dt = a.get("realEstateDealTypeId")
    entity = str(a.get("userEntityType") or "")
    return {
        "source": "ss", "url": url, "id": str(a.get("applicationId")),
        "title": title, "description": (desc_ka or "").strip(),
        "deal": norm_deal(a.get("realEstateDealType") or "", title) or SS_DEAL.get(dt, ""),
        "type": norm_type(a.get("realEstateType") or "", title),
        "price_usd": num(price.get("priceUsd")), "price": num(price.get("priceGeo")), "currency": "GEL",
        "area": num(first(a.get("totalArea"), a.get("areaOfHouse"))), "rooms": num(a.get("rooms")),
        "bedrooms": num(a.get("bedrooms")), "floor": num(a.get("floor")), "total_floors": num(a.get("floors")),
        "city": addr.get("cityTitle") or "", "district": first(addr.get("subdistrictTitle"), addr.get("districtTitle")),
        "address": street,
        "phone": re.sub(r"[^\d+]", "", str(phone or "")), "phone_masked": False,
        "owner": a.get("contactPerson") or "",
        "posted_by_agency": bool(a.get("agencyId") or a.get("agencyName")) or entity.lower() in ("broker", "agency", "company"),
        "refuses_partnership": bool(a.get("refusesPartnership")),
        "user_uuid": str(a.get("userId") or "").lower(),
        "images": [i.get("fileName") for i in sorted(a.get("appImages") or [], key=lambda x: x.get("orderNo") or 0)
                   if isinstance(i, dict) and i.get("fileName")][:20],
        "features": ss_features(a), "details": ss_details(a),
        "lat": num(a.get("locationLatitude") or addr.get("latitude")), "lon": num(a.get("locationLongitude") or addr.get("longitude")),
        "posted_at": str(a.get("orderDate") or ""),
        "video_url": str(a.get("applicationVideoLink") or a.get("uploadVideoLink") or ""),
    }


SS_AMENITIES = [("airConditioning", "კონდიციონერი"), ("balcony", "აივანი"), ("basement", "სარდაფი"), ("cableTelevision", "საკაბელო ტელევიზია"),
                ("drinkingWater", "სასმელი წყალი"), ("electricity", "ელექტროენერგია"), ("elevator", "ლიფტი"), ("fridge", "მაცივარი"),
                ("furniture", "ავეჯი"), ("garage", "გარაჟი"), ("glazedWindows", "მინაპაკეტი"), ("heating", "გათბობა"), ("hotWater", "ცხელი წყალი"),
                ("internet", "ინტერნეტი"), ("ironDoor", "რკინის კარი"), ("naturalGas", "ბუნებრივი აირი"), ("securityAlarm", "სიგნალიზაცია"),
                ("sewage", "კანალიზაცია"), ("storage", "სათავსო"), ("telephone", "ტელეფონი"), ("tv", "ტელევიზორი"),
                ("washingMachine", "სარეცხი მანქანა"), ("water", "წყალი"), ("wiFi", "Wi-Fi"), ("withPool", "აუზი"), ("viewOnYard", "ხედი ეზოში"),
                ("viewOnStreet", "ხედი ქუჩაზე"), ("withBuiltInKitchen", "ჩაშენებული სამზარეულო"), ("isPetFriendly", "შინაური ცხოველები დაშვებულია"),
                ("lastFloor", "ბოლო სართული")]


def ss_details(a):
    rows = [("მდგომარეობა", a.get("state") if isinstance(a.get("state"), str) else ""), ("სტატუსი", a.get("realEstateStatus")),
            ("სამზარეულო", a.get("kitchenArea") and f"{a.get('kitchenArea')} მ²"), ("ეზო", a.get("areaOfYard") and f"{a.get('areaOfYard')} მ²"),
            ("სველი წერტილი", a.get("toilet")), ("საკადასტრო კოდი", a.get("cadastralCode")), ("პროექტი", a.get("projectName"))]
    return [[k, str(v)] for k, v in rows if v not in (None, "", 0, False) and not isinstance(v, (dict, list))]


def ss_features(a):
    """SS.ge amenities: top-level true/false fields, plus any ticked {title, isChecked} lists (best effort)."""
    out = [label for key, label in SS_AMENITIES if a.get(key) is True]
    for d in walk(a):
        title = d.get("title") or d.get("name") or d.get("displayName")
        flag = d.get("isChecked", d.get("checked", d.get("value", d.get("isSelected"))))
        if isinstance(title, str) and 1 < len(title) < 40 and flag is True and title not in out:
            out.append(title)
    return out[:40]


def extract(url):
    page = fetch(url)
    parsed = parse_myhome(page, url) if site_of(url) == "myhome" else parse_ss(page, url)
    if parsed:
        parsed["refuses_agencies"] = parsed.pop("refuses_partnership", False) or refuses_agencies(parsed["description"])
        return parsed
    data = extract_generic(page, url)
    data["refuses_agencies"] = refuses_agencies(data["description"])
    return data


def extract_generic(page, url):
    blobs = json_blobs(page)
    lid = listing_id(url)
    d = best_listing_dict(blobs, lid)
    title = pick(d, "title") or meta(page, "og:title")
    desc = pick(d, "description") or meta(page, "og:description")
    text_all = " ".join([title, desc])
    data = {
        "source": site_of(url),
        "url": url,
        "id": lid,
        "title": title,
        "description": desc,
        "deal": norm_deal(pick(d, "deal"), text_all),
        "type": norm_type(pick(d, "type"), text_all),
        "price_usd": num(pick(d, "price_usd")),
        "price": num(pick(d, "price")),
        "currency": pick(d, "currency"),
        "area": num(pick(d, "area")),
        "rooms": num(pick(d, "rooms")),
        "bedrooms": num(pick(d, "bedrooms")),
        "floor": num(pick(d, "floor")),
        "total_floors": num(pick(d, "total_floors")),
        "city": pick(d, "city"),
        "district": pick(d, "district"),
        "address": pick(d, "address"),
        "phone": re.sub(r"[^\d+]", "", pick(d, "phone")),
        "owner": pick(d, "owner"),
        "images": images(blobs, page),
    }
    # Fallbacks from the title, e.g. "იყიდება 3 ოთახიანი ბინა ვაკეში"
    if not data["rooms"]:
        m = re.search(r"(\d+)\s*ოთახ", title)
        if m:
            data["rooms"] = m.group(1)
    if not data["area"]:
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:მ²|m²|კვ)", page)
        if m:
            data["area"] = num(m.group(1))
    return data


def missing_fields(d):
    need = {"deal": "გარიგება", "price": "ფასი", "area": "ფართი", "rooms": "ოთახები", "address": "მისამართი"}
    out = []
    for k, label in need.items():
        if k == "price" and (d.get("price") or d.get("price_usd")):
            continue
        if k == "address" and (d.get("address") or d.get("district")):
            continue
        if not d.get(k):
            out.append(label)
    return out
