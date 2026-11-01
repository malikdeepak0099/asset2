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


def template(d, lang, company_phone, agent):
    t = TYPE[lang].get(d.get("type", "flat"), TYPE[lang]["flat"])
    deal = DEAL[lang].get(d.get("deal", ""), DEAL[lang][""])
    loc = place(d, lang)
    rooms, area, floor, tf = d.get("rooms"), d.get("area"), d.get("floor"), d.get("total_floors")
    lines = []
    if lang == "ka":
        head = f"{deal} {rooms + ' ოთახიანი ' if rooms else ''}{t}{' — ' + loc if loc else ''}"
        lines.append(head)
        facts = []
        if area: facts.append(f"ფართი: {area} მ²")
        if rooms: facts.append(f"ოთახები: {rooms}")
        if d.get("bedrooms"): facts.append(f"საძინებელი: {d['bedrooms']}")
        if floor: facts.append(f"სართული: {floor}{'/' + tf if tf else ''}")
        pr = price_line(d, lang)
        if pr: facts.append(f"ფასი: {pr}")
        lines += ["• " + f for f in facts]
        lines.append("")
        lines.append("დათვალიერება ნებისმიერ დროს. დამატებითი ინფორმაციისთვის დაგვიკავშირდით.")
        lines.append(f"KEY GROUP Real Estate — {agent}: {company_phone}")
    elif lang == "en":
        head = f"{deal}: {rooms + '-room ' if rooms else ''}{t}{' in ' + loc if loc else ''}"
        lines.append(head)
        if area: lines.append(f"• Area: {area} m²")
        if rooms: lines.append(f"• Rooms: {rooms}")
        if d.get("bedrooms"): lines.append(f"• Bedrooms: {d['bedrooms']}")
        if floor: lines.append(f"• Floor: {floor}{'/' + tf if tf else ''}")
        pr = price_line(d, lang)
        if pr: lines.append(f"• Price: {pr}")
        lines.append("")
        lines.append("Viewings any time. Contact us for details.")
        lines.append(f"KEY GROUP Real Estate — {agent}: {company_phone}")
    else:
        head = f"{deal} {rooms + '-комнатная ' if rooms and d.get('type','flat') == 'flat' else ''}{t}{', ' + loc if loc else ''}"
        lines.append(head)
        if area: lines.append(f"• Площадь: {area} м²")
        if rooms: lines.append(f"• Комнат: {rooms}")
        if d.get("bedrooms"): lines.append(f"• Спален: {d['bedrooms']}")
        if floor: lines.append(f"• Этаж: {floor}{'/' + tf if tf else ''}")
        pr = price_line(d, lang)
        if pr: lines.append(f"• Цена: {pr}")
        lines.append("")
        lines.append("Показ в любое время. Звоните для подробностей.")
        lines.append(f"KEY GROUP Real Estate — {agent}: {company_phone}")
    return "\n".join(lines)


def with_claude(d, company_phone, agent):
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    facts = {k: v for k, v in d.items() if k not in ("images", "phone", "owner", "url") and v}
    prompt = (
        "You write real estate listings for KEY GROUP Real Estate, an agency in Tbilisi and Batumi. "
        "Using ONLY these facts, write a new listing description (do not copy the original wording, never invent facts, "
        "never include the owner's name or phone). Return JSON with keys title_ka, ka, title_en, en, title_ru, ru. "
        "Each description: 4-7 short lines, key facts as bullet lines starting with '• ', end with the contact line "
        f"'KEY GROUP Real Estate — {agent}: {company_phone}'. Titles under 70 characters.\n\nFacts:\n"
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
