"""Listing descriptions in Georgian, English and Russian.

With ANTHROPIC_API_KEY set, Claude writes fresh, natural descriptions.
Without it, clean templates are used, so the bot always works.
"""
import json
import os

import requests

TYPE = {
    "ka": {"flat": "ბინა", "house": "კერძო სახლი", "land": "მიწის ნაკვეთი", "commercial": "კომერციული ფართი", "hotel": "სასტუმრო"},
    "en": {"flat": "apartment", "house": "house", "land": "land plot", "commercial": "commercial space", "hotel": "hotel"},
    "ru": {"flat": "квартира", "house": "частный дом", "land": "земельный участок", "commercial": "коммерческое помещение", "hotel": "гостиница"},
}
DEAL = {
    "ka": {"sale": "იყიდება", "rent": "ქირავდება", "": "იყიდება / ქირავდება"},
    "en": {"sale": "For sale", "rent": "For rent", "": "For sale / rent"},
    "ru": {"sale": "Продается", "rent": "Сдается", "": "Продается / сдается"},
}


KA_LAT = dict(zip("აბგდევზთიკლმნოპჟრსტუფქღყშჩცძწჭხჯჰ",
    ["a","b","g","d","e","v","z","t","i","k","l","m","n","o","p","zh","r","s","t","u","p","k","gh","q","sh","ch","ts","dz","ts","ch","kh","j","h"]))
KA_CYR = dict(zip("აბგდევზთიკლმნოპჟრსტუფქღყშჩცძწჭხჯჰ",
    ["а","б","г","д","е","в","з","т","и","к","л","м","н","о","п","ж","р","с","т","у","п","к","г","к","ш","ч","ц","дз","ц","ч","х","дж","х"]))


def translit(text, lang):
    table = KA_LAT if lang == "en" else KA_CYR
    out = "".join(table.get(ch, ch) for ch in str(text or ""))
    return out[:1].upper() + out[1:] if out else out


def place(d, lang):
    parts = [x for x in (d.get("district"), d.get("address")) if x]
    if lang == "ka":
        return ", ".join(parts)
    return ", ".join(translit(x, lang) for x in parts)


def price_line(d, lang):
    p = d.get("price_usd") or d.get("price")
    if not p:
        return ""
    cur = "$" if d.get("price_usd") or "usd" in str(d.get("currency", "")).lower() or d.get("currency") in ("1", "2") else "₾"
    try:
        p = f"{int(float(p)):,}"
    except ValueError:
        pass
    per = {"ka": " / თვე", "en": " / month", "ru": " / месяц"}[lang] if d.get("deal") == "rent" else ""
    return f"{p} {cur}{per}"


COND = {   # MyHome / SS condition (Georgian) → English / Russian
    "ახალი გარემონტებული": ("Newly renovated", "Свежий ремонт"), "ძველი გარემონტებული": ("Old renovation", "Старый ремонт"),
    "მიმდინარე რემონტი": ("Renovation in progress", "Идёт ремонт"), "სარემონტო": ("Needs renovation", "Требует ремонта"),
    "თეთრი კარკასი": ("White frame", "Белый каркас"), "შავი კარკასი": ("Black frame", "Чёрный каркас"),
    "მწვანე კარკასი": ("Green frame", "Зелёный каркас"), "თეთრი პლიუსი": ("White plus", "Белый плюс"),
}
LABELS = {   # one sticker per line: condition first, then the space, price last
    "ka": {"cond": "✨ მდგომარეობა", "area": "📐 ფართი", "rooms": "🚪 ოთახები", "bed": "🛏 საძინებელი", "floor": "🪜 სართული", "price": "💵 ფასი",
           "view": "📅 დათვალიერება ნებისმიერ დროს. დამატებითი ინფორმაციისთვის დაგვიკავშირდით.", "unit": "მ²"},
    "en": {"cond": "✨ Condition", "area": "📐 Area", "rooms": "🚪 Rooms", "bed": "🛏 Bedrooms", "floor": "🪜 Floor", "price": "💵 Price",
           "view": "📅 Viewings any time. Contact us for details.", "unit": "m²"},
    "ru": {"cond": "✨ Состояние", "area": "📐 Площадь", "rooms": "🚪 Комнат", "bed": "🛏 Спален", "floor": "🪜 Этаж", "price": "💵 Цена",
           "view": "📅 Показ в любое время. Звоните для подробностей.", "unit": "м²"},
}


def condition(d, lang):
    v = next((str(x[1]).strip() for x in (d.get("details") or []) if isinstance(x, (list, tuple)) and len(x) > 1 and x[0] == "მდგომარეობა"), "")
    v = v or str(d.get("condition") or "").strip()
    if not v or v.isdigit():
        return ""
    if lang == "ka":
        return v
    return COND.get(v, ("", ""))[0 if lang == "en" else 1]


def contact_line(company_phone, agent):
    return f"🏢 KEY GROUP Real Estate — {agent}: {company_phone}"


def fact_lines(d, lang):
    L = LABELS[lang]
    rooms, area, floor, tf = d.get("rooms"), d.get("area"), d.get("floor"), d.get("total_floors")
    out = []
    c = condition(d, lang)
    if c: out.append(f"{L['cond']}: {c}")
    if area: out.append(f"{L['area']}: {area} {L['unit']}")
    if rooms: out.append(f"{L['rooms']}: {rooms}")
    if d.get("bedrooms"): out.append(f"{L['bed']}: {d['bedrooms']}")
    if floor: out.append(f"{L['floor']}: {floor}{'/' + str(tf) if tf else ''}")
    pr = price_line(d, lang)
    if pr: out.append(f"{L['price']}: {pr}")
    return out


DETAIL_ICON = {"აშენების წელი": "🏗", "აივანი": "🌇", "ჭერის სიმაღლე": "↕️", "ცხელი წყალი": "🔥", "კარ-ფანჯარა": "🪟", "მისაღები": "🛋",
               "ეზო": "🌳", "სათავსო": "📦", "ლოჯი": "🌿", "აუზი": "🏊", "ფასი შეთანხმებით": "🤝", "გაცვლა": "🔁", "სტატუსი": "🏷",
               "სამზარეულო": "🍳", "სველი წერტილი": "🚿", "საკადასტრო კოდი": "📄", "პროექტი": "🏢"}


def extra_lines(d, lang):
    """Georgian text only: the other MyHome / SS details (each with its sticker) and the amenities."""
    if lang != "ka":
        return []
    out = [f"{DETAIL_ICON.get(k, '▫️')} {k}: {v}" for k, v in (d.get("details") or [])
           if k != "მდგომარეობა" and v and k in DETAIL_ICON]
    feats = [str(x) for x in (d.get("features") or [])][:20]
    if feats:
        out.append("✔️ " + ", ".join(feats))
    return out


def template(d, lang, company_phone, agent):
    t = TYPE[lang].get(d.get("type", "flat"), TYPE[lang]["flat"])
    deal = DEAL[lang].get(d.get("deal", ""), DEAL[lang][""])
    loc = place(d, lang)
    rooms = d.get("rooms")
    if lang == "ka":
        head = f"{deal} {rooms + ' ოთახიანი ' if rooms else ''}{t}{' — ' + loc if loc else ''}"
    elif lang == "en":
        head = f"{deal}: {rooms + '-room ' if rooms else ''}{t}{' in ' + loc if loc else ''}"
    else:
        head = f"{deal} {rooms + '-комнатная ' if rooms and d.get('type','flat') == 'flat' else ''}{t}{', ' + loc if loc else ''}"
    more = extra_lines(d, lang)
    lines = [head, ""] + fact_lines(d, lang) + ([""] + more if more else []) + ["", LABELS[lang]["view"], contact_line(company_phone, agent)]
    return "\n".join(lines)


def tidy(body, d, lang, company_phone, agent):
    """Same order for every text (also Claude's): facts with stickers, then the viewing line, KEY GROUP agent + phone last."""
    drop = ("დათვალიერ", "viewing", "показ", "key group", "დაგვიკავშირდით", "contact us", "звоните")
    keep = [x for x in str(body or "").split("\n") if not any(w in x.lower() for w in drop)]
    while keep and not keep[-1].strip():
        keep.pop()
    more = [x for x in extra_lines(d, lang) if x not in keep]
    if more:
        keep += [""] + more
    return "\n".join(keep + ["", LABELS[lang]["view"], contact_line(company_phone, agent)])


def with_claude(d, company_phone, agent):
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    facts = {k: v for k, v in d.items() if k not in ("images", "phone", "owner", "url") and v}
    prompt = (
        "You write real estate listings for KEY GROUP Real Estate, an agency in Tbilisi and Batumi. "
        "Using ONLY these facts, write a new listing description (do not copy the original wording, never invent facts, "
        "never include the owner's name or phone). Return JSON with keys title_ka, ka, title_en, en, title_ru, ru. "
        "Each description: a first line (deal, rooms, type, place), an empty line, then the key facts one per line in this order "
        "and with these stickers: '✨ Condition' (the renovation state, e.g. 'ახალი გარემონტებული' — always first), '📐 Area', '🚪 Rooms', "
        "'🛏 Bedrooms', '🪜 Floor', '💵 Price' (labels in the description's language), then at most 2 short lines about the best features "
        "with a fitting sticker each. Do NOT add a viewing line or contact line — they are added after your text. "
        "Titles under 70 characters.\n\nFacts:\n"
        + json.dumps(facts, ensure_ascii=False)
    )
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5"), "max_tokens": 1500,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=60,
        )
        r.raise_for_status()
        text = "".join(b.get("text", "") for b in r.json().get("content", []))
        text = text[text.find("{"): text.rfind("}") + 1]
        out = json.loads(text)
        if all(out.get(k) for k in ("ka", "en", "ru")):
            for lang in ("ka", "en", "ru"):
                out[lang] = tidy(out[lang], d, lang, company_phone, agent)
            return out
    except Exception:
        return None
    return None


def build(d, company_phone, agent):
    ai = with_claude(d, company_phone, agent)
    if ai:
        return ai, True
    out = {}
    for lang in ("ka", "en", "ru"):
        body = template(d, lang, company_phone, agent)
        out[lang] = body
        out["title_" + lang] = body.split("\n", 1)[0][:70]
    return out, False
