"""KEY GROUP website assistant — rule-based auto replies in Georgian / English / Russian.

Skills: property search (rent / buy / daily, type, rooms, district, budget) over owner listings + KEY GROUP CRM
listings, listing your property and plans, payment, free valuation, viewing requests, buying as a foreigner,
residence permit, mortgage, renting documents, fees, office contact and hours.
Anything it cannot answer (or when the visitor asks) goes to a human agent: it collects name + phone,
then the conversation appears in the admin panel and on Telegram, and the agent replies from the admin panel.
"""
import difflib
import json
import os
import re
import time

import kb

SITE_DIR = os.environ.get("SITE_DIR", "/site")
OFFICE = {"en": "Richard Holbrooke St. 4, Tbilisi", "ka": "რიჩარდ ჰოლბრუკის ქ. 4, თბილისი", "ru": "ул. Ричарда Холбрука 4, Тбилиси"}
PHONE = "+995 577 114 118"
WA = "https://wa.me/995577114118"

# ------------------------------------------------------------------ text helpers

def detect_lang(text, fallback="en"):
    if re.search(r"[Ⴀ-ჿ]", text or ""):
        return "ka"
    if re.search(r"[Ѐ-ӿ]", text or ""):
        return "ru"
    if re.search(r"[a-zA-Z]", text or ""):
        return "en"
    return fallback


def T(lang, en, ka, ru):
    return {"ka": ka, "ru": ru}.get(lang, en)


def has(text, words):
    return any(w in text for w in words)


# ------------------------------------------------------------------ vocab

DISTRICTS = [  # canonical English, Georgian, words that match
    ("Vake", "ვაკე", ["vake", "ვაკე", "ваке"]),
    ("Saburtalo", "საბურთალო", ["saburtalo", "საბურთალო", "сабуртало"]),
    ("Vera", "ვერა", ["vera ", " vera", "ვერა", "вера"]),
    ("Mtatsminda", "მთაწმინდა", ["mtatsminda", "მთაწმინდა", "мтацминда"]),
    ("Sololaki", "სოლოლაკი", ["sololaki", "სოლოლაკი", "сололаки"]),
    ("Old Tbilisi", "ძველი თბილისი", ["old tbilisi", "old town", "ძველი თბილისი", "старый тбилиси"]),
    ("Didube", "დიდუბე", ["didube", "დიდუბე", "дидубе"]),
    ("Digomi", "დიღომი", ["digomi", "დიღომ", "დიღმ", "дигоми"]),
    ("Chugureti", "ჩუღურეთი", ["chugureti", "ჩუღურეთ", "чугурети"]),
    ("Nadzaladevi", "ნაძალადევი", ["nadzaladevi", "ნაძალადევ", "надзаладеви"]),
    ("Gldani", "გლდანი", ["gldani", "გლდან", "глдани"]),
    ("Mukhiani", "მუხიანი", ["mukhiani", "მუხიან", "мухиани"]),
    ("Isani", "ისანი", ["isani", "ისან", "исани"]),
    ("Samgori", "სამგორი", ["samgori", "სამგორ", "самгори"]),
    ("Varketili", "ვარკეთილი", ["varketili", "ვარკეთილ", "варкетили"]),
    ("Krtsanisi", "კრწანისი", ["krtsanisi", "კრწანის", "крцаниси"]),
    ("Ortachala", "ორთაჭალა", ["ortachala", "ორთაჭალ", "ортачала"]),
    ("Avlabari", "ავლაბარი", ["avlabari", "ავლაბარ", "авлабари"]),
    ("Lisi", "ლისი", [" lisi", "ლისის ტბ", " лиси "]),
    ("Tskneti", "წყნეთი", ["tskneti", "წყნეთ", "цкнети"]),
    ("Bagebi", "ბაგები", ["bagebi", "ბაგებ", "багеби"]),
    ("Vazisubani", "ვაზისუბანი", ["vazisubani", "ვაზისუბან", "вазисубани"]),
    ("Batumi", "ბათუმი", ["batumi", "ბათუმ", "батуми"]),
]

RENT_W = ["rent", "rental", "lease", "kiray", "аренд", "снять", "сним", "сдает", "сдаёт", "ქირა", "ქირავ", "ქირით", "qira", "kira"]
SALE_W = ["buy", "sale", "purchase", "invest", "kharid", "купить", "покуп", "продаж", "продаёт", "ყიდვ", "იყიდ", "შეძენ", "viyidi", "iyideba"]
DAILY_W = ["daily", "per day", "short term", "short-term", "посуточ", "на день", "დღიურ", "დღეღამ"]
TYPE_W = {
    "flat": ["apartment", "flat", "studio", "квартир", "студи", " ბინა ", " ბინა,", "ბინის", "ბინებ", "ბინას", "ბინაზე", "ბინით", " bina "],
    "house": ["house", "villa", "cottage", "дом", "вилл", "коттедж", "სახლ", "აგარაკ"],
    "commercial": ["office", "shop", "commercial", "store", "warehouse", "restaurant", "офис", "магазин", "коммерч", "склад",
                   "ოფის", "კომერც", "მაღაზი", "საწყობ"],
    "land": ["land", "plot", "участ", "земл", "მიწა", "მიწის", "ნაკვეთ"],
    "hotel": ["hotel", "guesthouse", "отел", "гостиниц", "სასტუმრ"],
}

INTENTS = [  # order matters: first match wins
    ("agent", ["agent", "human", "operator", "manager", "real person", "talk to someone", "call me", "callback", "call back",
               "оператор", "менеджер", "человек", "агент", "позвон", "აგენტ", "ოპერატორ", "მენეჯერ", "დამირეკ", "ადამიან"]),
    ("valuation", ["valuation", "value my", "my property worth", "my flat worth", "my apartment worth", "evaluate my", "appraisal", "оцен", "сколько стоит моя", "შეფასებ", "რა ღირს ჩემი"]),
    ("list", ["list my", "add my", "add listing", "post my", "sell my", "rent out", "i am owner", "i'm owner", "my property", "my apartment",
              "my flat", "landlord", "разместить", "сдать мою", "сдать свою", "продать мою", "продать свою", "моя квартира", "я собственник",
              "განცხადების დამატ", "ჩემი ბინ", "მესაკუთრე", "გავყიდო", "გავაქირავო", "დავდო განცხადება"]),
    ("plans", ["vip", "boost", "promot", "sponsor", "top of", "plans", "tariff", "продвиж", "поднять", "реклам", "ტოპ", "პაკეტ", "რეკლამ"]),
    ("payment", ["payment", "how to pay", "how do i pay", "how can i pay", "iban", "bank transfer", "оплат", "как платить", "გადახდ", "ანგარიშ", "ჩარიცხ"]),
    ("viewing", ["viewing", "book a visit", "visit the flat", "visit the apartment", "see the flat", "see the apartment", "show me the", "appointment", "просмотр", "посмотреть", "ნახვა", "დათვალიერ", "ვნახო"]),
    ("foreigner", ["foreigner", "foreign", "forner", "foriner", "forigner", "foreiner", "forener", "expat", "non resident", "not citizen", "non-resident", "citizen", "иностран", "нерезидент", "უცხოელ", "უცხო ქვეყნ"]),
    ("residence", ["residen", "permit", "visa", "внж", "вид на жительство", "резидент", "ბინადრ", "ვიზა"]),
    ("mortgage", ["mortgage", "loan", "installment", "credit", "ипотек", "кредит", "рассроч", "იპოთეკ", "სესხ", "განვადებ"]),
    ("documents", ["document", "contract", "deposit", "registration", "registry", "докум", "договор", "депозит", "залог", "регистрац",
                   "დოკუმენტ", "ხელშეკრულებ", "დეპოზიტ", "რეგისტრაც"]),
    ("fees", ["commission", "fee", "how much do you charge", "your price", "комисси", "сколько берете", "საკომისიო", "მომსახურების ფას"]),
    ("contact", ["share me number", "your number", "share number", "contact details", "contact number", "address", "office", "where are you", "location", "phone", "number", "whatsapp", "email", "hours", "open", "working time",
                 "адрес", "офис", "где вы", "телефон", "номер", "часы", "график", "მისამართ", "ოფის", "სად ხართ", "ტელეფონ", "ნომერ", "სამუშაო საათ"]),
    ("services", ["what do you do", "services", "about you", "who are you", "услуг", "кто вы", "чем занимаетесь", "სერვის", "მომსახურებ", "ვინ ხართ"]),
    ("thanks", ["thank", "thx", "спасибо", "благодар", "მადლობ", "გმადლობ"]),
    ("bye", ["bye", "goodbye", "see you", "пока", "до свидан", "ნახვამდის", "კარგად"]),
    ("hello", ["hello", "hi", "hey", "good morning", "good evening", "привет", "здравств", "добрый", "გამარჯობ", "სალამ", "გაუმარჯ", "namaste"]),
]

# ------------------------------------------------------------------ parsing

def parse_search(text):
    t = " " + text.lower() + " "
    out = {}
    if has(t, DAILY_W):
        out["deal"] = "daily"
    elif has(t, RENT_W):
        out["deal"] = "rent"
    elif has(t, SALE_W):
        out["deal"] = "sale"
    for k, words in TYPE_W.items():
        if has(t, words):
            out["type"] = k
            break
    m = re.search(r"(\d)\s*[-+]?\s*(?:room|rm|bed|br\b|комн|к\b|ოთახ|ოთ\b)", t)
    if m:
        out["rooms"] = int(m.group(1))
    elif has(t, ["studio", "студи", "სტუდიო"]):
        out["rooms"] = 1
    for en, ka, words in DISTRICTS:
        if has(t, words):
            out["district"] = en
            break
    nums = [int(n.replace(",", "").replace(" ", "")) for n in re.findall(r"\d[\d, ]{1,9}\d|\d{3,}", t)]
    nums = [n for n in nums if n >= 100]
    k = re.search(r"(\d+(?:[.,]\d+)?)\s*k\b", t)
    if k:
        nums.append(int(float(k.group(1).replace(",", ".")) * 1000))
    if nums:
        out["max_price"] = max(nums)
        if has(t, ["₾", "gel", "lari", "лар", "ლარ"]):
            out["cur"] = "GEL"
    return out


def intent_of(text):
    t = " " + text.lower() + " "
    for name, words in INTENTS:
        if name == "hello":
            if re.search(r"(^|\W)(hello|hi|hey|hii+|salam|namaste|привет|здравствуй\w*|добрый \w+|გამარჯობა|სალამი)(\W|$)", t):
                return name
            continue
        if has(t, words):
            return name
    return None



# ------------------------------------------------------------------ knowledge base topics

_WORD = re.compile(r"[a-zA-ZႠ-ჿЀ-ӿ]{3,}")


def match_topic(text):
    """Best knowledge-base topic for a free-text question -> (topic_id, score)."""
    t = " " + text.lower().strip() + " "
    words = _WORD.findall(t)
    best, best_score = None, 0.0
    for tid, tp in kb.TOPICS.items():
        score = 0.0
        for k in tp.get("kw", []):
            if k in t:
                score += 1 + 0.08 * len(k)
            elif " " not in k.strip() and len(k) >= 6:
                for w in words:
                    if len(w) >= 5 and abs(len(w) - len(k)) <= 2 and difflib.SequenceMatcher(None, w, k).ratio() >= 0.84:
                        score += 0.8
                        break
        if score > best_score:
            best, best_score = tid, score
    return best, best_score


ACTION_LABELS = {
    "__rent": ("🔑 Find a rental", "🔑 ქირით ძიება", "🔑 Найти аренду"),
    "__buy": ("🏠 Properties for sale", "🏠 იყიდება", "🏠 Объекты на продажу"),
    "__agent": ("👤 Talk to an expert", "👤 ექსპერტთან საუბარი", "👤 Связаться с экспертом"),
    "__valuation": ("💰 Free valuation", "💰 უფასო შეფასება", "💰 Бесплатная оценка"),
    "__sellforme": ("🤝 KEY GROUP sells it for me", "🤝 KEY GROUP-მა გაყიდოს", "🤝 Пусть KEY GROUP продаст"),
    "__guide": ("🇬🇪 More about Georgia", "🇬🇪 მეტი საქართველოზე", "🇬🇪 Ещё о Грузии"),
}


def topic_buttons(ids, lang):
    out = []
    for i in ids:
        if i.startswith("__"):
            lab = ACTION_LABELS.get(i)
            if lab:
                out.append({"label": T(lang, *lab), "value": i})
        elif i in kb.TOPICS:
            out.append({"label": kb.TOPICS[i]["label"][lang], "value": "__t_" + i})
    return out


def topic_reply(tid, state, lang, settings, site):
    tp = kb.TOPICS[tid]
    if tp.get("dynamic"):
        msg = answer(tp["dynamic"], state, lang, settings, site)
        msg = dict(msg)
    else:
        msg = {"text": tp[lang] + (kb.NOTE[lang] if tp.get("note") else "")}
    btn = []
    if tp.get("url"):
        btn.append({"label": T(lang, "➡ Open my account", "➡ ჩემი ანგარიში", "➡ Мой кабинет"), "url": site + tp["url"]})
    btn += topic_buttons(tp.get("next", []), lang)
    if "__agent" not in tp.get("next", []) and tid not in ("owner",):
        btn += topic_buttons(["__agent"], lang)
    msg["buttons"] = (msg.get("buttons") or []) + btn
    state["last_topic"] = tid
    return msg


def guide(lang):
    return {"text": T(lang, "What would you like to know about property in Georgia? 🇬🇪",
                      "რა გაინტერესებთ საქართველოში უძრავ ქონებაზე? 🇬🇪",
                      "Что вас интересует о недвижимости в Грузии? 🇬🇪"),
            "buttons": topic_buttons(kb.GUIDE, lang)}


# ------------------------------------------------------------------ listings

def _crm_listings():
    path = os.path.join(SITE_DIR, "listings.json")
    try:
        st = os.stat(path)
    except OSError:
        return []
    if _CRM.get("mtime") != st.st_mtime:
        try:
            raw = json.load(open(path, encoding="utf-8"))
            _CRM["rows"] = raw.get("listings", raw) if isinstance(raw, dict) else raw
            _CRM["mtime"] = st.st_mtime
        except Exception:
            return _CRM.get("rows", [])
    return _CRM.get("rows", [])


_CRM = {}
KA_TO_EN = {ka: en for en, ka, _ in DISTRICTS}


def search(con, q, site, limit=3):
    """Returns (total, top) where top is a list of cards {title, price, url, photo, src}."""
    now = time.time()
    res = []
    for r in con.execute("SELECT * FROM listings WHERE status='active'").fetchall():
        rank = 2 if r["super_until"] > now else 1 if r["vip_until"] > now else 0
        photos = json.loads(r["photos"] or "[]")
        res.append({"deal": r["deal"], "type": r["type"], "rooms": r["rooms"] or 0, "district": (r["district"] or "") + " " + (r["city"] or "") + " " + (r["address"] or ""),
                    "price": r["price"] or 0, "cur": r["currency"] or "USD", "area": r["area"] or 0, "rank": rank + 0.5,
                    "url": f"{site}/p/?id={r['id']}", "photo": f"/uploads/t_{photos[0]}" if photos else "", "title": r["title"] or "", "src": "owner"})
    for r in _crm_listings():
        try:
            price = float(r.get("price") or 0)
        except (TypeError, ValueError):
            price = 0
        if price <= 0 or (r.get("deal") == "Rent" and price > 30000):
            continue
        d = str(r.get("d") or "").strip()
        cat = r.get("cat")
        res.append({"deal": "rent" if r.get("deal") == "Rent" else "sale",
                    "type": {"Commercial": "commercial", "House": "house", "Land": "land"}.get(cat, "flat"),
                    "rooms": int(r.get("rooms") or 0) if str(r.get("rooms") or "0").isdigit() else 0,
                    "district": d + " " + KA_TO_EN.get(d, "") + " " + str(r.get("a") or ""), "price": price, "cur": r.get("cur") or "USD",
                    "area": r.get("area") or 0, "rank": 0, "url": r.get("link") or WA, "photo": "", "title": "", "src": "crm",
                    "dname": KA_TO_EN.get(d, d), "dka": d})
    want_d = q.get("district")
    words = []
    if want_d:
        for en, ka, w in DISTRICTS:
            if en == want_d:
                words = [x.strip() for x in w] + [en.lower(), ka]
    out = []
    for l in res:
        if q.get("deal") and l["deal"] != q["deal"]:
            continue
        if q.get("type") and l["type"] != q["type"]:
            continue
        if q.get("rooms") and l["rooms"] and l["rooms"] < q["rooms"]:
            continue
        if words and not any(w and w in l["district"].lower() for w in words):
            continue
        if q.get("max_price") and l["price"] > q["max_price"] * 1.05:
            continue
        out.append(l)
    out.sort(key=lambda l: (-l["rank"], abs(q["max_price"] - l["price"]) if q.get("max_price") else l["price"]))
    return len(out), out[:limit]


def card_of(l, lang):
    TY = {"flat": T(lang, "Apartment", "ბინა", "Квартира"), "house": T(lang, "House", "სახლი", "Дом"),
          "commercial": T(lang, "Commercial", "კომერციული", "Коммерция"), "land": T(lang, "Land", "მიწა", "Участок"),
          "hotel": T(lang, "Hotel", "სასტუმრო", "Отель")}
    sym = {"GEL": "₾", "EUR": "€"}.get(l["cur"], "$")
    per = "" if l["deal"] == "sale" else T(lang, " / month", " / თვე", " / мес") if l["deal"] == "rent" else T(lang, " / day", " / დღე", " / сутки")
    where = (l.get("dka") if lang == "ka" and l.get("dka") else l.get("dname")) or l["district"].split("  ")[0]
    specs = []
    if l["rooms"]:
        specs.append(f"{l['rooms']} " + T(lang, "rooms", "ოთახი", "комн."))
    if l["area"]:
        specs.append(f"{l['area']} m²")
    return {"title": l["title"] or (TY.get(l["type"], "") + (" · " + where.strip() if where.strip() else "")),
            "price": f"{sym}{int(l['price']):,}{per}", "specs": " · ".join(specs), "url": l["url"], "photo": l["photo"],
            "badge": "VIP" if l["rank"] >= 1.5 else ""}


def search_url(site, q):
    p = []
    for k, key in (("deal", "deal"), ("type", "type"), ("district", "district"), ("max_price", "max"), ("rooms", "rooms")):
        if q.get(k):
            p.append(f"{key}={q[k]}")
    return f"{site}/search/" + ("?" + "&".join(p) if p else "")


# ------------------------------------------------------------------ replies

def menu(lang):
    return [
        {"label": T(lang, "🔑 Rent", "🔑 ქირაობა", "🔑 Аренда"), "value": "__rent"},
        {"label": T(lang, "🏠 Buy", "🏠 ყიდვა", "🏠 Купить"), "value": "__buy"},
        {"label": T(lang, "🇬🇪 Invest in Georgia", "🇬🇪 ინვესტიცია საქართველოში", "🇬🇪 Инвестиции в Грузию"), "value": "__guide"},
        {"label": T(lang, "🏠 I'm an owner", "🏠 მესაკუთრე ვარ", "🏠 Я владелец"), "value": "__list"},
        {"label": T(lang, "💰 Free valuation", "💰 უფასო შეფასება", "💰 Бесплатная оценка"), "value": "__valuation"},
        {"label": T(lang, "👤 Talk to an agent", "👤 აგენტთან საუბარი", "👤 Связаться с агентом"), "value": "__agent"},
    ]


def welcome(lang):
    return {"text": T(lang,
                      "Hi! 👋 Welcome to KEY GROUP Real Estate.\nI can find you a flat or house in seconds, answer questions about buying in Georgia — residence permit, ROI, taxes — and help owners sell or rent out. How can I help?",
                      "გამარჯობა! 👋 მოგესალმებით KEY GROUP-ში.\nწამებში მოგიძებნით ბინას ან სახლს, გიპასუხებთ კითხვებზე ყიდვის, ბინადრობის, შემოსავლის და გადასახადების შესახებ და დავეხმარებით მესაკუთრეებს. რით დაგეხმაროთ?",
                      "Здравствуйте! 👋 Добро пожаловать в KEY GROUP.\nПодберу квартиру или дом за секунды, отвечу на вопросы о покупке в Грузии — ВНЖ, доходность, налоги — и помогу владельцам продать или сдать. Чем помочь?"),
            "buttons": menu(lang)}


def district_buttons(lang):
    names = [("Vake", "ვაკე", "Ваке"), ("Saburtalo", "საბურთალო", "Сабуртало"), ("Old Tbilisi", "ძველი თბილისი", "Старый Тбилиси"),
             ("Didube", "დიდუბე", "Дидубе"), ("Batumi", "ბათუმი", "Батуми")]
    b = [{"label": T(lang, *n), "value": n[0]} for n in names]
    b.append({"label": T(lang, "Any district", "ნებისმიერი უბანი", "Любой район"), "value": "__any"})
    return b


def done_msg(lang):
    return {"text": T(lang, "Done ✅ An agent has your request and will reply right here or contact you on WhatsApp / phone — usually within an hour during working time (Mon–Sat, 10:00–19:00). Meanwhile I can still answer questions here.",
                      "მზადაა ✅ აგენტმა მიიღო თქვენი მოთხოვნა და გიპასუხებთ აქვე ან WhatsApp-ით / ტელეფონით — ჩვეულებრივ ერთ საათში სამუშაო დროს (ორშ–შაბ, 10:00–19:00). მანამდე კითხვებს აქვე გიპასუხებთ.",
                      "Готово ✅ Агент получил ваш запрос и ответит здесь или свяжется по WhatsApp / телефону — обычно в течение часа в рабочее время (Пн–Сб, 10:00–19:00). А пока я отвечу на вопросы здесь.")}


def reply_waiting(con, state, text, settings, site):
    """Visitor is waiting for an agent: still answer what the bot knows, stay quiet otherwise."""
    raw = (text or "").strip()[:1000]
    lang = detect_lang(raw, state.get("lang") or "en") if raw and not raw.startswith("__") else state.get("lang") or "en"
    state["lang"] = lang
    it = intent_of(raw)
    if it in ("agent", "valuation", "viewing") or raw in ("__agent", "__valuation", "__viewing", "__findforme", "__sellforme"):
        return [{"text": T(lang, "Your request is already with our agents — they will answer here shortly.",
                           "თქვენი მოთხოვნა უკვე აგენტებთანაა — მალე გიპასუხებენ აქვე.",
                           "Ваш запрос уже у агентов — они скоро ответят здесь.")}]
    if it in ("thanks", "bye", "hello") or (not it and not parse_search(raw) and match_topic(raw)[1] < 0.8 and not raw.startswith("__")):
        return []
    st = dict(state); st["step"] = None
    msgs, event = reply(con, st, raw, settings, site)
    if event:
        return []
    state["search"] = st.get("search", state.get("search"))
    return msgs


def handoff_start(state, lang, topic):
    state["step"] = "ask_name"
    state["topic"] = topic
    return {"text": T(lang, "Sure — I'll connect you with an agent. What is your name?",
                      "რა თქმა უნდა — დაგაკავშირებთ აგენტთან. როგორ გქვიათ?",
                      "Конечно — соединю вас с агентом. Как вас зовут?")}


TOPIC_OF = {"list": "owner", "foreigner": "process", "residence": "trc", "mortgage": "mortgage", "documents": "process", "fees": "fees"}


def answer(intent, state, lang, settings, site):
    s = settings
    if intent in TOPIC_OF:
        return topic_reply(TOPIC_OF[intent], state, lang, settings, site)
    if intent == "hello":
        return welcome(lang)
    if intent == "agent":
        return handoff_start(state, lang, "Talk to an agent")
    if intent == "valuation":
        r = handoff_start(state, lang, "Free valuation")
        r["text"] = T(lang, "We value your property for free, usually within 24 hours. An agent will contact you — what is your name?",
                      "თქვენს ქონებას უფასოდ შევაფასებთ, ჩვეულებრივ 24 საათში. აგენტი დაგიკავშირდებათ — როგორ გქვიათ?",
                      "Мы бесплатно оценим ваш объект, обычно в течение 24 часов. Агент свяжется с вами — как вас зовут?")
        return r
    if intent == "list":
        P = s["plans"]
        cur = "₾" if s.get("currency") == "GEL" else s.get("currency", "")
        return {"text": T(lang,
                          f"Two ways:\n1) Add it yourself — free for {P['free']['days']} days. Register with your phone at keygroup.ge/account, add photos and details; we check and publish it.\n2) Let KEY GROUP sell or rent it for you — we list it on MyHome.ge and SS.ge, take photos and bring clients.\nWant it seen first? VIP {cur}{P['vip']['price']:g} / Super VIP {cur}{P['super']['price']:g} for {P['vip']['days']} days, Boost {cur}{P['boost']['price']:g}.",
                          f"ორი გზა:\n1) დაამატეთ თავად — უფასოდ {P['free']['days']} დღით. დარეგისტრირდით ტელეფონით keygroup.ge/account-ზე, ატვირთეთ ფოტოები; შევამოწმებთ და გამოვაქვეყნებთ.\n2) KEY GROUP გაყიდის ან გააქირავებს თქვენ მაგივრად — MyHome.ge და SS.ge-ზე განთავსებით და კლიენტებით.\nგინდათ პირველ ადგილზე? VIP {cur}{P['vip']['price']:g} / Super VIP {cur}{P['super']['price']:g} {P['vip']['days']} დღით, Boost {cur}{P['boost']['price']:g}.",
                          f"Два варианта:\n1) Разместить самому — бесплатно на {P['free']['days']} дней. Регистрация по телефону на keygroup.ge/account, фото и описание; мы проверим и опубликуем.\n2) KEY GROUP продаст или сдаст за вас — размещение на MyHome.ge и SS.ge, фото и клиенты.\nХотите выше всех? VIP {cur}{P['vip']['price']:g} / Super VIP {cur}{P['super']['price']:g} на {P['vip']['days']} дней, Boost {cur}{P['boost']['price']:g}."),
                "buttons": [{"label": T(lang, "➕ Add my listing", "➕ განცხადების დამატება", "➕ Разместить"), "url": site + "/account/"},
                            {"label": T(lang, "🤝 KEY GROUP sells it for me", "🤝 KEY GROUP-მა გაყიდოს", "🤝 Пусть KEY GROUP продаст"), "value": "__sellforme"}]}
    if intent == "plans":
        P = s["plans"]
        cur = "₾" if s.get("currency") == "GEL" else s.get("currency", "")
        return {"text": T(lang,
                          f"Plans for owner listings:\n• Free — {P['free']['days']} days\n• VIP — {cur}{P['vip']['price']:g} for {P['vip']['days']} days, above free listings with a VIP badge\n• Super VIP — {cur}{P['super']['price']:g} for {P['super']['days']} days, top of the search and home page\n• Boost — {cur}{P['boost']['price']:g}, moves your listing back to the top\nYou can order a plan from your account after adding the listing.",
                          f"განცხადების პაკეტები:\n• უფასო — {P['free']['days']} დღე\n• VIP — {cur}{P['vip']['price']:g}, {P['vip']['days']} დღე, უფასოებზე მაღლა VIP ნიშნით\n• Super VIP — {cur}{P['super']['price']:g}, {P['super']['days']} დღე, ძიების და მთავარი გვერდის სათავეში\n• Boost — {cur}{P['boost']['price']:g}, განცხადება ისევ ზემოთ ადის\nპაკეტს შეუკვეთავთ თქვენი ანგარიშიდან.",
                          f"Тарифы для объявлений:\n• Бесплатно — {P['free']['days']} дней\n• VIP — {cur}{P['vip']['price']:g} на {P['vip']['days']} дней, выше бесплатных, значок VIP\n• Super VIP — {cur}{P['super']['price']:g} на {P['super']['days']} дней, в самом верху поиска и главной\n• Boost — {cur}{P['boost']['price']:g}, поднимает объявление наверх\nТариф заказывается в личном кабинете."),
                "buttons": [{"label": T(lang, "➕ Add my listing", "➕ განცხადების დამატება", "➕ Разместить"), "url": site + "/account/"}]}
    if intent == "payment":
        return {"text": T(lang, "How to pay for a plan:\n\n", "პაკეტის გადახდა:\n\n", "Как оплатить тариф:\n\n") + s.get("payment_info", "")}
    if intent == "viewing":
        r = handoff_start(state, lang, "Viewing request")
        r["text"] = T(lang, "Happy to arrange a viewing. An agent will confirm the time with you — what is your name?",
                      "სიამოვნებით მოვაწყობთ დათვალიერებას. აგენტი შეგითანხმებთ დროს — როგორ გქვიათ?",
                      "С удовольствием организуем просмотр. Агент согласует с вами время — как вас зовут?")
        return r
    if intent == "foreigner":
        return {"text": T(lang,
                          "Yes — foreigners can buy apartments, houses and commercial property in Georgia with just a passport, the same way as locals (agricultural land has restrictions). The purchase is registered at the Public Service Hall, usually within 1–4 working days. Our team helps with the search, the contract and the registration.",
                          "დიახ — უცხოელს შეუძლია საქართველოში ბინის, სახლის და კომერციული ფართის ყიდვა მხოლოდ პასპორტით (სასოფლო-სამეურნეო მიწაზე შეზღუდვებია). ნასყიდობა რეგისტრირდება იუსტიციის სახლში, ჩვეულებრივ 1–4 სამუშაო დღეში. ჩვენი გუნდი დაგეხმარებათ ძიებაში, ხელშეკრულებასა და რეგისტრაციაში.",
                          "Да — иностранцы могут покупать квартиры, дома и коммерческую недвижимость в Грузии только по паспорту, как и местные (на сельхозземлю есть ограничения). Сделка регистрируется в Доме юстиции, обычно за 1–4 рабочих дня. Наша команда поможет с подбором, договором и регистрацией."),
                "buttons": [{"label": T(lang, "🏠 Show properties for sale", "🏠 იყიდება", "🏠 Объекты на продажу"), "value": "__buy"},
                            {"label": T(lang, "👤 Ask an agent", "👤 კითხვა აგენტს", "👤 Спросить агента"), "value": "__agent"}]}
    if intent == "residence":
        return {"text": T(lang,
                          "Buying non-agricultural property in Georgia worth at least USD 100,000 can make you eligible for a residence permit. The exact rules and documents are checked case by case — an agent can explain the details for your situation.",
                          "საქართველოში მინიმუმ 100 000 აშშ დოლარის ღირებულების (არასასოფლო-სამეურნეო) უძრავი ქონების ყიდვამ შეიძლება ბინადრობის ნებართვის უფლება მოგცეთ. ზუსტ პირობებს და დოკუმენტებს აგენტი აგიხსნით.",
                          "Покупка в Грузии недвижимости (не сельхоз) стоимостью от 100 000 долларов США может дать право на вид на жительство. Точные условия и документы проверяются индивидуально — агент расскажет подробности."),
                "buttons": [{"label": T(lang, "👤 Ask an agent", "👤 კითხვა აგენტს", "👤 Спросить агента"), "value": "__agent"}]}
    if intent == "mortgage":
        return {"text": T(lang,
                          "Georgian banks offer mortgages, usually with a down payment of about 20–30%. Every listing page on our site has a mortgage calculator, and our agents can help you prepare for the bank.",
                          "ქართული ბანკები გასცემენ იპოთეკურ სესხს, ჩვეულებრივ 20–30%-იანი თანამონაწილეობით. ჩვენი საიტის ყველა განცხადებაზე არის იპოთეკის კალკულატორი, აგენტები კი დაგეხმარებიან ბანკისთვის მომზადებაში.",
                          "Грузинские банки выдают ипотеку, обычно с первым взносом около 20–30%. На странице каждого объекта есть ипотечный калькулятор, а агенты помогут подготовиться к банку."),
                "buttons": [{"label": T(lang, "👤 Talk to an agent", "👤 აგენტთან საუბარი", "👤 Связаться с агентом"), "value": "__agent"}]}
    if intent == "documents":
        return {"text": T(lang,
                          "Renting: you usually need your passport, a signed rental contract, and the first month's rent plus a deposit (often one month).\nBuying: passport, the purchase contract and registration at the Public Service Hall. We prepare and check the papers with you.",
                          "ქირაობა: ჩვეულებრივ საჭიროა პასპორტი, ხელმოწერილი ხელშეკრულება, პირველი თვის ქირა და დეპოზიტი (ხშირად ერთი თვის).\nყიდვა: პასპორტი, ნასყიდობის ხელშეკრულება და რეგისტრაცია იუსტიციის სახლში. საბუთებს ერთად მოვამზადებთ და შევამოწმებთ.",
                          "Аренда: обычно нужен паспорт, подписанный договор, оплата первого месяца и депозит (часто за один месяц).\nПокупка: паспорт, договор купли-продажи и регистрация в Доме юстиции. Документы подготовим и проверим вместе с вами.")}
    if intent == "fees":
        return {"text": T(lang,
                          "Adding your own listing on keygroup.ge is free. For deals done with KEY GROUP agents, the fee depends on the property and the type of deal — an agent will tell you the exact terms before you agree to anything.",
                          "keygroup.ge-ზე საკუთარი განცხადების დამატება უფასოა. KEY GROUP-ის აგენტებთან გარიგების საკომისიო დამოკიდებულია ქონებასა და გარიგების ტიპზე — ზუსტ პირობებს აგენტი წინასწარ გეტყვით.",
                          "Размещение своего объявления на keygroup.ge бесплатно. Комиссия при сделке с агентами KEY GROUP зависит от объекта и типа сделки — точные условия агент назовёт заранее."),
                "buttons": [{"label": T(lang, "👤 Ask an agent", "👤 კითხვა აგენტს", "👤 Спросить агента"), "value": "__agent"}]}
    if intent == "contact":
        return {"text": T(lang, f"📍 Office: {OFFICE['en']}\n📞 Phone / WhatsApp: {PHONE}\n✉️ info@keygroup.ge · owners: support@keygroup.ge\n🕙 Mon–Sat, 10:00–19:00",
                          f"📍 ოფისი: {OFFICE['ka']}\n📞 ტელეფონი / WhatsApp: {PHONE}\n✉️ info@keygroup.ge · მესაკუთრეებს: support@keygroup.ge\n🕙 ორშ–შაბ, 10:00–19:00",
                          f"📍 Офис: {OFFICE['ru']}\n📞 Телефон / WhatsApp: {PHONE}\n✉️ info@keygroup.ge · владельцам: support@keygroup.ge\n🕙 Пн–Сб, 10:00–19:00"),
                "buttons": [{"label": "WhatsApp", "url": WA},
                            {"label": T(lang, "🗺 Open map", "🗺 რუკა", "🗺 Карта"), "url": "https://maps.google.com/?q=" + "Richard+Holbrooke+St+4+Tbilisi"}]}
    if intent == "services":
        return {"text": T(lang,
                          "KEY GROUP is a real estate agency in Tbilisi and Batumi: long-term rentals, buying new-build and resale homes, commercial property, and selling or renting out your property (we list on MyHome.ge and SS.ge).",
                          "KEY GROUP — უძრავი ქონების სააგენტო თბილისსა და ბათუმში: გრძელვადიანი ქირა, ახალი და ძველი ბინების ყიდვა, კომერციული ფართები და თქვენი ქონების გაყიდვა/გაქირავება (MyHome.ge და SS.ge-ზე).",
                          "KEY GROUP — агентство недвижимости в Тбилиси и Батуми: долгосрочная аренда, покупка новостроек и вторички, коммерческая недвижимость, продажа и сдача вашего объекта (размещаем на MyHome.ge и SS.ge)."),
                "buttons": menu(lang)}
    if intent == "thanks":
        return {"text": T(lang, "You're welcome! Anything else I can help with?", "არაფრის! კიდევ რამეში დაგეხმაროთ?", "Пожалуйста! Чем ещё помочь?"), "buttons": menu(lang)}
    if intent == "bye":
        return {"text": T(lang, "Thanks for visiting KEY GROUP. Have a great day! 👋", "გმადლობთ, რომ გვეწვიეთ. კარგ დღეს გისურვებთ! 👋", "Спасибо, что заглянули в KEY GROUP. Хорошего дня! 👋")}
    return None


def do_search(con, state, lang, site):
    q = state.get("search") or {}
    total, top = search(con, q, site)
    cards = [card_of(l, lang) for l in top]
    url = search_url(site, q)
    if total:
        text = T(lang, f"I found {total} matching listings. Here are the best ones:",
                 f"ვიპოვე {total} შესაფერისი განცხადება. აი საუკეთესოები:",
                 f"Нашёл {total} подходящих объявлений. Вот лучшие:")
        btn = [{"label": T(lang, f"See all {total}", f"ყველა ({total})", f"Все {total}"), "url": url},
               {"label": T(lang, "📅 Arrange a viewing", "📅 დათვალიერება", "📅 Просмотр"), "value": "__viewing"},
               {"label": T(lang, "🔄 New search", "🔄 ახალი ძიება", "🔄 Новый поиск"), "value": "__reset"}]
    else:
        text = T(lang, "Nothing matches exactly right now — but new properties come in every day and our agents know many that are not online yet. Leave your contact and an agent will find options for you.",
                 "ზუსტად ასეთი ახლა არ გვაქვს — მაგრამ ახალი ქონება ყოველდღე ემატება და აგენტებმა ბევრი ისეთიც იციან, რაც ჯერ საიტზე არაა. დაგვიტოვეთ კონტაქტი და აგენტი მოგიძებნით.",
                 "Точно такого сейчас нет — но новые объекты появляются каждый день, а агенты знают много вариантов, которых ещё нет на сайте. Оставьте контакт — агент подберёт для вас.")
        btn = [{"label": T(lang, "👤 Find it for me", "👤 მომიძებნეთ", "👤 Подберите мне"), "value": "__findforme"},
               {"label": T(lang, "🔄 Change search", "🔄 ძიების შეცვლა", "🔄 Изменить поиск"), "value": "__reset"}]
    return {"text": text, "cards": cards, "buttons": btn}


def describe(q, lang):
    parts = []
    if q.get("deal"):
        parts.append({"rent": T(lang, "rent", "ქირა", "аренда"), "sale": T(lang, "buy", "ყიდვა", "покупка"), "daily": T(lang, "daily rent", "დღიური", "посуточно")}[q["deal"]])
    if q.get("type"):
        parts.append(q["type"])
    if q.get("rooms"):
        parts.append(f"{q['rooms']}+ " + T(lang, "rooms", "ოთახი", "комн."))
    if q.get("district"):
        parts.append(q["district"])
    if q.get("max_price"):
        parts.append(T(lang, "up to ", "მდე ", "до ") + f"{q['max_price']:,}")
    return ", ".join(parts)


def reply(con, state, text, settings, site):
    """Main entry: returns (messages:list[dict], event:str|None). event = 'handoff' when contact collected."""
    raw = (text or "").strip()[:1000]
    lang = state.get("lang") or "en"
    if raw and not raw.startswith("__"):
        lang = detect_lang(raw, lang)
        state["lang"] = lang
    low = raw.lower()

    # ---- collecting contact for an agent
    step = state.get("step")
    if step in ("ask_name", "ask_phone") and not raw.startswith("__"):
        digits = re.sub(r"\D", "", raw)
        if len(digits) >= 9:
            if step == "ask_name":
                left = re.sub(r"[+\d()\-\s]{9,}", " ", raw).strip(" ,.-")
                state["name"] = left[:80] if left and len(left.split()) <= 3 and not intent_of(left) else ""
            state["phone"] = re.search(r"[+\d][\d()\-\s]{7,}\d", raw).group(0).strip()[:40]
            state["step"] = None
            return [done_msg(lang)], "handoff"
        it = intent_of(raw)
        looks_like_name = step == "ask_name" and not it and match_topic(raw)[1] < 0.8 and "?" not in raw and 0 < len(raw.split()) <= 3 and not parse_search(raw)
        if looks_like_name:
            state["name"] = raw[:80]
            state["step"] = "ask_phone"
            return [{"text": T(lang, f"Thanks, {state['name']}! Your phone or WhatsApp number?",
                               f"გმადლობთ, {state['name']}! თქვენი ტელეფონი ან WhatsApp ნომერი?",
                               f"Спасибо, {state['name']}! Ваш телефон или WhatsApp?")}], None
        ask = (T(lang, "To connect you with an agent, please write your name or phone number.",
                 "აგენტთან დასაკავშირებლად მოგვწერეთ სახელი ან ტელეფონის ნომერი.",
                 "Чтобы соединить вас с агентом, напишите имя или номер телефона.") if step == "ask_name" else
               T(lang, "To connect you with an agent, please send your phone or WhatsApp number (for example 5XX XXX XXX).",
                 "აგენტთან დასაკავშირებლად გამოგვიგზავნეთ ტელეფონის ან WhatsApp ნომერი (მაგ. 5XX XXX XXX).",
                 "Чтобы соединить вас с агентом, отправьте номер телефона или WhatsApp (например +995 5XX XXX XXX)."))
        out = []
        tid, tscore = match_topic(raw)
        if tid and tscore >= 0.8 and it not in ("agent", "valuation", "viewing", "contact"):
            out.append(topic_reply(tid, {}, lang, settings, site))
        elif it and it not in ("agent", "valuation", "viewing", "hello", "thanks"):
            a = answer(it, {}, lang, settings, site)
            if a:
                out.append(a)
        elif not it and parse_search(raw):
            st2 = dict(state); st2["search"] = dict(state.get("search") or {}, **parse_search(raw))
            if st2["search"].get("deal"):
                state["search"] = st2["search"]
                out.append(do_search(con, state, lang, site))
        out.append({"text": ask, "buttons": [{"label": T(lang, "↩ Not now", "↩ ახლა არა", "↩ Не сейчас"), "value": "__cancel"},
                                             {"label": "WhatsApp", "url": WA}]})
        return out, None
    if raw == "__cancel":
        state["step"] = None
        return [welcome(lang)], None

    # ---- buttons
    if raw == "__start":
        return [welcome(lang)], None
    if raw in ("__rent", "__buy", "__daily"):
        state["search"] = {"deal": {"__rent": "rent", "__buy": "sale", "__daily": "daily"}[raw]}
        state["step"] = "district"
        return [{"text": T(lang, "Which district? You can also write budget and rooms, e.g. “Vake, 2 rooms, up to 1000$”.",
                           "რომელ უბანში? შეგიძლიათ ბიუჯეტი და ოთახებიც მიწეროთ, მაგ. „ვაკე, 2 ოთახი, 1000$-მდე“.",
                           "Какой район? Можно сразу бюджет и комнаты, например «Ваке, 2 комнаты, до 1000$»."),
                 "buttons": district_buttons(lang)}], None
    if raw == "__any":
        state["step"] = None
        return [do_search(con, state, lang, site)], None
    if raw == "__reset":
        state["search"] = {}
        state["step"] = None
        return [welcome(lang)], None
    if raw == "__list":
        return [topic_reply("owner", state, lang, settings, site)], None
    if raw == "__guide":
        return [guide(lang)], None
    if raw.startswith("__t_") and raw[4:] in kb.TOPICS:
        state["step"] = None
        return [topic_reply(raw[4:], state, lang, settings, site)], None
    if raw in ("__valuation", "__agent", "__viewing"):
        return [answer(raw[2:], state, lang, settings, site)], None
    if raw in ("__rent_keep", "__buy_keep"):
        q = dict(state.get("search") or {})
        q["deal"] = "rent" if raw == "__rent_keep" else "sale"
        state["search"] = q
        return [do_search(con, state, lang, site)], None
    if raw == "__findforme":
        return [handoff_start(state, lang, "Find a property: " + describe(state.get("search") or {}, lang))], None
    if raw == "__sellforme":
        return [handoff_start(state, lang, "Owner wants KEY GROUP to sell / rent out")], None
    if raw.startswith("__"):
        return [welcome(lang)], None

    # ---- free text
    intent = intent_of(raw)
    found = parse_search(raw)
    tid0, ts0 = match_topic(raw)
    if intent == "list" and tid0 and tid0.startswith("o_") and ts0 >= 1:
        return [topic_reply(tid0, state, lang, settings, site)], None
    if intent in ("agent", "valuation", "viewing", "list"):
        state["misses"] = 0
        return [answer(intent, state, lang, settings, site)], None
    tid, tscore = match_topic(raw)
    specific = bool(set(found) & {"district", "rooms", "max_price"})
    if tid and intent not in ("contact",) and (tscore >= 3 or (tscore >= 1 and not specific)):
        state["misses"] = 0
        return [topic_reply(tid, state, lang, settings, site)], None
    if intent and set(found) <= {"type"} and state.get("step") != "district":
        found = {}
    if found:
        q = dict(state.get("search") or {})
        if found.get("deal") and q.get("deal") and found["deal"] != q["deal"]:
            q = {}
        q.update(found)
        state["search"] = q
        state["step"] = None
        state["misses"] = 0
        if not q.get("deal"):
            return [{"text": T(lang, "Rent or buy?", "ქირა თუ ყიდვა?", "Аренда или покупка?"),
                     "buttons": [{"label": T(lang, "🔑 Rent", "🔑 ქირა", "🔑 Аренда"), "value": "__rent_keep"},
                                 {"label": T(lang, "🏠 Buy", "🏠 ყიდვა", "🏠 Купить"), "value": "__buy_keep"}]}], None
        return [do_search(con, state, lang, site)], None
    if intent:
        state["misses"] = 0
        return [answer(intent, state, lang, settings, site)], None
    if tid and tscore >= 0.8:
        state["misses"] = 0
        return [topic_reply(tid, state, lang, settings, site)], None
    if state.get("step") == "district":
        state["step"] = None
        return [do_search(con, state, lang, site)], None

    # ---- not understood
    state["misses"] = state.get("misses", 0) + 1
    if state["misses"] >= 2:
        state["misses"] = 0
        return [{"text": T(lang, "I'm not sure I understood. Let me connect you with a human agent who can help.",
                           "ვერ დავრწმუნდი, რომ სწორად გავიგე. დაგაკავშირებთ აგენტთან, რომელიც დაგეხმარებათ.",
                           "Кажется, я не совсем понял. Давайте соединю вас с агентом."),
                 "buttons": [{"label": T(lang, "👤 Yes, connect me", "👤 დიახ, დამაკავშირეთ", "👤 Да, соедините"), "value": "__agent"},
                             {"label": "WhatsApp", "url": WA}]}], None
    return [{"text": T(lang, "Sorry, I didn't quite get that. You can write, for example, “2-room flat in Saburtalo up to 800$” or “residence permit” — or pick an option:",
                       "ბოდიში, ვერ გავიგე. მაგალითად მომწერეთ „2 ოთახიანი ბინა საბურთალოზე 800$-მდე“ — ან აირჩიეთ:",
                       "Извините, не совсем понял. Напишите, например, «2-комнатная в Сабуртало до 800$» — или выберите вариант:"),
             "buttons": menu(lang)}], None
