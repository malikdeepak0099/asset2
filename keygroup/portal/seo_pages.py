"""Generates city / district / topic landing pages for search engines (static HTML with live listings).

Run:  python3 seo_pages.py   ->  writes site/<path>/index.html for every page below and prints the paths.
Market figures: tbilisihome.ge Q3 2026 (renovated asking prices by district), TBC Capital Mar 2026 (Tbilisi average),
Galt & Taggart via investor.ge (Batumi 2025). They are shown as approximate.
"""
import html
import json
import os

SITE = "https://keygroup.ge"
HERE = os.path.dirname(os.path.abspath(__file__))

PAGES = [
    {"path": "tbilisi/apartments-for-rent", "filter": {"deal": "rent", "type": "flat", "city": "tbilisi"}, "search": "deal=rent&type=flat",
     "facts": [("≈$9–11", "rent per m² a month"), ("6.6–8%", "gross rental yield"), ("6–12 months", "usual contract")],
     "en": ("Apartments for rent in Tbilisi", "Long-term apartments for rent in Tbilisi — Vake, Saburtalo, Old Tbilisi, Didube and more. Checked listings, local agents, WhatsApp replies in English, Georgian and Russian.",
            "Tbilisi has one of the most affordable rental markets in the region: a renovated 2-room flat in Vake or Saburtalo usually rents for about $700–1,100 a month, and older or outer districts start from about $400. Contracts run 6–12 months; you pay the first month plus a deposit, usually one month. Tell us your budget and district and our agents shortlist flats that are really available."),
     "ka": ("ბინები ქირით თბილისში", "გრძელვადიანი ქირა თბილისში — ვაკე, საბურთალო, ძველი თბილისი, დიდუბე და სხვა.",
            "თბილისში ქირა რეგიონში ერთ-ერთი ყველაზე ხელმისაწვდომია: რემონტით 2-ოთახიანი ვაკეში ან საბურთალოზე ჩვეულებრივ $700–1,100 ღირს, სხვა უბნებში — $400-დან. ხელშეკრულება 6–12 თვით, პირველი თვე + დეპოზიტი. მოგვწერეთ ბიუჯეტი და უბანი — აგენტები შეგირჩევენ რეალურად თავისუფალ ბინებს."),
     "ru": ("Аренда квартир в Тбилиси", "Долгосрочная аренда квартир в Тбилиси — Ваке, Сабуртало, Старый Тбилиси, Дидубе и другие районы.",
            "Аренда в Тбилиси — одна из самых доступных в регионе: 2-комнатная с ремонтом в Ваке или Сабуртало обычно стоит $700–1,100 в месяц, в других районах — от $400. Договор на 6–12 месяцев, первый месяц + депозит. Напишите бюджет и район — агенты подберут действительно свободные квартиры.")},
    {"path": "tbilisi/apartments-for-sale", "filter": {"deal": "sale", "type": "flat", "city": "tbilisi"}, "search": "deal=sale&type=flat",
     "facts": [("≈$1,340", "average asking price per m²"), ("+4%", "price change in a year"), ("8.1%", "average gross yield")],
     "en": ("Apartments for sale in Tbilisi", "Buy an apartment in Tbilisi: new builds and resale flats in Vake, Saburtalo, Old Tbilisi and other districts. Foreigners can buy with just a passport.",
            "The average asking price in Tbilisi is about $1,340 per m² (TBC Capital, March 2026), while renovated flats in Vake–Saburtalo are around $1,890 and in Old Tbilisi around $1,990 per m². Foreigners can buy freely with a passport; registration takes 1–4 working days and there is no stamp duty. Property worth $150,000+ can qualify you for a residence permit."),
     "ka": ("ბინები იყიდება თბილისში", "ბინის ყიდვა თბილისში: ახალი და ძველი აშენებული ბინები ვაკეში, საბურთალოზე, ძველ თბილისში.",
            "თბილისში საშუალო ფასი ≈$1,340/მ² (TBC Capital, მარტი 2026); რემონტით ვაკე–საბურთალოზე ≈$1,890, ძველ თბილისში ≈$1,990/მ². რეგისტრაცია 1–4 სამუშაო დღეში, ბაჟის გარეშე."),
     "ru": ("Продажа квартир в Тбилиси", "Купить квартиру в Тбилиси: новостройки и вторичка в Ваке, Сабуртало, Старом Тбилиси. Иностранцам — только паспорт.",
            "Средняя цена предложения в Тбилиси — около $1,340 за м² (TBC Capital, март 2026); с ремонтом в Ваке–Сабуртало ≈$1,890, в Старом Тбилиси ≈$1,990 за м². Регистрация 1–4 рабочих дня, без пошлины. Недвижимость от $150,000 может дать ВНЖ.")},
    {"path": "tbilisi/commercial-property", "filter": {"type": "commercial", "city": "tbilisi"}, "search": "type=commercial",
     "facts": [("Offices · shops · warehouses", "for rent and sale"), ("20%", "tax on commercial rent"), ("1–4 days", "registration")],
     "en": ("Commercial property in Tbilisi", "Offices, shops, restaurants and warehouses for rent and sale in Tbilisi. Street-front retail, business-centre offices and logistics space.",
            "From street-front shops on Chavchavadze and Pekini avenues to offices in Saburtalo business centres and warehouses on the city edge, we match space to your business. Tell us the size, district and budget — we check footfall, parking and the documents before you sign."),
     "ka": ("კომერციული ფართები თბილისში", "ოფისები, მაღაზიები, რესტორნები და საწყობები ქირით და იყიდება თბილისში.",
            "ქუჩის ფასადზე მაღაზიებიდან საბურთალოს ბიზნეს-ცენტრების ოფისებამდე — შეგირჩევთ ფართს თქვენი ბიზნესისთვის."),
     "ru": ("Коммерческая недвижимость в Тбилиси", "Офисы, магазины, рестораны и склады в аренду и на продажу в Тбилиси.",
            "От магазинов с фасадом на Чавчавадзе и Пекина до офисов в бизнес-центрах Сабуртало и складов на окраине — подберём помещение под ваш бизнес.")},
    {"path": "batumi/apartments-for-sale", "filter": {"deal": "sale", "kw": ["batumi", "ბათუმ"]}, "search": "deal=sale&district=Batumi",
     "facts": [("≈$1,865", "average price per m² (2025)"), ("≈7.4%", "gross rental yield"), ("52%", "of buyers are foreigners")],
     "en": ("Apartments for sale in Batumi", "Buy an apartment in Batumi by the Black Sea: new builds on the New Boulevard, sea-view flats and holiday-rental investments.",
            "Batumi prices averaged about $1,865 per m² in 2025, up roughly 10% in a year, and about half of all buyers are foreigners. Holiday and daily rentals bring a gross yield of about 7.4%, but income is seasonal, so building quality and management matter. Analysts expect price growth to slow to 4–6% in 2026."),
     "ka": ("ბინები იყიდება ბათუმში", "ბინის ყიდვა ბათუმში: ახალაშენები ახალ ბულვარზე, ზღვის ხედით.",
            "ბათუმში საშუალო ფასი 2025-ში ≈$1,865/მ² იყო (+≈10%); მყიდველების ნახევარი უცხოელია; შემოსავალი ≈7.4%, მაგრამ სეზონური."),
     "ru": ("Продажа квартир в Батуми", "Купить квартиру в Батуми у Чёрного моря: новостройки на Новом бульваре, вид на море, инвестиции в посуточную аренду.",
            "Средняя цена в Батуми в 2025 году — около $1,865 за м² (+≈10% за год), около половины покупателей — иностранцы. Посуточная аренда даёт ≈7.4% годовых, но доход сезонный. В 2026 году аналитики ждут роста цен на 4–6%.")},
    {"path": "batumi/apartments-for-rent", "filter": {"deal": "rent", "kw": ["batumi", "ბათუმ"]}, "search": "deal=rent&district=Batumi",
     "facts": [("Long-term & daily", "rentals"), ("Sea view", "New Boulevard"), ("WhatsApp", "replies the same day")],
     "en": ("Apartments for rent in Batumi", "Long-term and daily apartments for rent in Batumi — sea-view flats on the New Boulevard, Old Batumi and the city centre.",
            "Batumi offers both long-term rentals for families and remote workers and daily rentals near the beach. Winter long-term prices are much lower than summer daily rates — tell us your dates and budget and we suggest the best option."),
     "ka": ("ბინები ქირით ბათუმში", "გრძელვადიანი და დღიური ქირა ბათუმში — ზღვის ხედით, ახალ ბულვარზე და ცენტრში.",
            "ბათუმში არის როგორც გრძელვადიანი, ისე დღიური ქირა. მოგვწერეთ თარიღები და ბიუჯეტი."),
     "ru": ("Аренда квартир в Батуми", "Долгосрочная и посуточная аренда квартир в Батуми — вид на море, Новый бульвар, Старый Батуми.",
            "В Батуми есть и долгосрочная аренда для семей и удалёнщиков, и посуточная у моря. Зимой долгосрочная аренда намного дешевле летней посуточной — напишите даты и бюджет.")},
]
DISTRICTS = [
    ("vake", "Vake", "ვაკე", "Ваке", ["vake", "ვაკე"], ("≈$1,890", "renovated, per m²"), ("≈$10.5", "rent per m²"), ("≈6.7%", "gross yield"),
     "Tbilisi's most prestigious residential district: Vake Park, Chavchavadze Avenue, cafés, international schools and embassies. Popular with families and expats; strong rental demand all year."),
    ("saburtalo", "Saburtalo", "საბურთალო", "Сабуртало", ["saburtalo", "საბურთალო"], ("≈$1,890", "renovated, per m²"), ("≈$10.5", "rent per m²"), ("≈6.7%", "gross yield"),
     "Busy, modern district with metro, universities, the Tbilisi Mall area and many new builds. Good value for families, students and investors who want steady rental demand."),
    ("old-tbilisi", "Old Tbilisi", "ძველი თბილისი", "Старый Тбилиси", ["old tbilisi", "sololaki", "mtatsminda", "ძველი თბილისი", "სოლოლაკი", "მთაწმინდა", "ავლაბარ"],
     ("≈$1,990", "renovated, per m²"), ("≈$11.1", "rent per m²"), ("≈6.7%", "gross yield"),
     "Historic Sololaki, Mtatsminda and Abanotubani: balconied old houses, sulphur baths and the most tourist demand in the city — ideal for daily rentals and character homes."),
    ("didube", "Didube", "დიდუბე", "Дидубе", ["didube", "დიდუბე", "chugureti", "ჩუღურეთ"], ("≈$1,730", "renovated, per m²"), ("≈$9.5", "rent per m²"), ("≈6.6%", "gross yield"),
     "Well-connected district with metro stations and new residential complexes at lower prices than Vake and Saburtalo."),
    ("isani", "Isani–Samgori", "ისანი–სამგორი", "Исани–Самгори", ["isani", "samgori", "ისან", "სამგორ", "varketili", "ვარკეთილ"], ("≈$1,480", "renovated, per m²"), ("≈$8.8", "rent per m²"), ("≈7.1%", "gross yield"),
     "Large residential districts on the left bank with the city's most affordable prices and the highest gross yields — popular with first-time buyers and investors."),
    ("digomi", "Digomi", "დიღომი", "Дигоми", ["digomi", "დიღომ", "დიღმ"], ("≈$1,340", "Tbilisi average per m²"), ("New builds", "many projects"), ("Green", "near the river"),
     "Didi Digomi and Digomi Massive: fast-growing areas of new residential complexes, parks and wide streets, with good value for families."),
]
INVEST = {"path": "invest-in-georgia", "filter": {"deal": "sale"}, "search": "deal=sale",
          "facts": [("$150,000", "property for a residence permit"), ("6.5–8%", "Tbilisi rental yield"), ("<1%", "buying costs"), ("7.5%", "GDP growth 2025")],
          "en": ("Invest in real estate in Georgia", "Why foreigners invest in Georgian property: low prices, 6.5–8% rental yields, no stamp duty, residence permit from $150,000 and simple registration.",
                 "Foreigners can buy apartments, houses and commercial property in Georgia with just a passport. Buying costs are under 1% (no stamp duty; registration about 50–350 GEL in 1–4 days), rental income is taxed at 5% for registered landlords and resale after 2 years is tax-free. Tbilisi yields are about 6.5–8%, entry prices are 3–5 times lower than Dubai, and property worth $150,000+ can qualify you for a renewable residence permit. Figures are approximate; our agents confirm the details for your case."),
          "ka": ("ინვესტიცია საქართველოს უძრავ ქონებაში", "რატომ ყიდულობენ უცხოელები ქონებას საქართველოში.",
                 "უცხოელს შეუძლია ქონების ყიდვა მხოლოდ პასპორტით. ხარჯი 1%-ზე ნაკლებია, ქირაზე გადასახადი 5%, 2 წლის შემდეგ გაყიდვა გადასახადის გარეშეა. თბილისში შემოსავალი ≈6.5–8%, $150,000+ ქონებამ შეიძლება ბინადრობა მოგცეთ."),
          "ru": ("Инвестиции в недвижимость Грузии", "Почему иностранцы покупают недвижимость в Грузии: низкие цены, доходность 6.5–8%, ВНЖ от $150,000.",
                 "Иностранцы покупают недвижимость в Грузии только по паспорту. Расходы на покупку меньше 1%, налог на жилую аренду 5%, продажа после 2 лет без налога. Доходность в Тбилиси ≈6.5–8%, цены в 3–5 раз ниже Дубая, а недвижимость от $150,000 может дать ВНЖ.")}

FAQ = {
    "en": [("Can foreigners buy property in Georgia?", "Yes. Foreigners can buy apartments, houses and commercial property with just a passport, with the same rights as locals; agricultural land is restricted."),
           ("How long does registration take?", "Usually 1–4 working days at the Public Service Hall, at a cost of about 50–350 GEL depending on speed. There is no stamp duty."),
           ("Do you charge buyers or tenants?", "Searching on keygroup.ge is free. If you work with a KEY GROUP agent, the agent tells you the exact terms before you agree to anything.")],
    "ka": [("შეუძლია უცხოელს ქონების ყიდვა?", "დიახ, მხოლოდ პასპორტით, ადგილობრივის თანაბარი უფლებით; სასოფლო-სამეურნეო მიწაზე შეზღუდვაა."),
           ("რამდენ ხანს გრძელდება რეგისტრაცია?", "ჩვეულებრივ 1–4 სამუშაო დღე, ≈50–350 ლარი. ბაჟი არ არის."),
           ("იხდის თუ არა მყიდველი?", "keygroup.ge-ზე ძიება უფასოა. აგენტი პირობებს წინასწარ გეტყვით.")],
    "ru": [("Могут ли иностранцы покупать недвижимость в Грузии?", "Да, только по паспорту, с теми же правами, что и местные; на сельхозземлю есть ограничения."),
           ("Сколько длится регистрация?", "Обычно 1–4 рабочих дня в Доме юстиции, ≈50–350 лари. Пошлины нет."),
           ("Платят ли покупатели и арендаторы?", "Поиск на keygroup.ge бесплатный. Агент заранее назовёт условия.")],
}


def district_pages():
    out = []
    for slug, en, ka, ru, kw, f1, f2, f3, about in DISTRICTS:
        out.append({"path": f"tbilisi/{slug}", "filter": {"kw": kw}, "search": "district=" + en.split("–")[0], "facts": [f1, f2, f3],
                    "en": (f"Property in {en}, Tbilisi — rent & sale", f"Apartments and houses for rent and sale in {en}, Tbilisi: prices per m², rental yields and current listings from KEY GROUP.",
                           about + " Prices shown are approximate asking prices for renovated flats (Q3 2026)."),
                    "ka": (f"უძრავი ქონება — {ka}, თბილისი", f"ბინები ქირით და იყიდება — {ka}: ფასები და აქტუალური განცხადებები.",
                           f"{ka} — აქტუალური განცხადებები, ფასები მ²-ზე და შემოსავლიანობა. ფასები მიახლოებითია (Q3 2026)."),
                    "ru": (f"Недвижимость в районе {ru}, Тбилиси", f"Квартиры в аренду и на продажу в районе {ru}: цены за м², доходность и актуальные объявления.",
                           f"{ru} — актуальные объявления, цены за м² и доходность. Цены ориентировочные (Q3 2026)."),
                    "name": en})
    return out


LBL = {
    "rent per m² a month": ("ქირა მ²-ზე თვეში", "аренда за м² в месяц"), "gross rental yield": ("წლიური შემოსავალი ქირიდან", "доходность аренды"),
    "usual contract": ("ჩვეულებრივი ხელშეკრულება", "обычный договор"), "average asking price per m²": ("საშუალო ფასი მ²-ზე", "средняя цена за м²"),
    "price change in a year": ("ფასის ცვლილება წელიწადში", "изменение цены за год"), "average gross yield": ("საშუალო შემოსავალი", "средняя доходность"),
    "for rent and sale": ("ქირით და იყიდება", "аренда и продажа"), "tax on commercial rent": ("კომერციული ქირის გადასახადი", "налог на коммерческую аренду"),
    "registration": ("რეგისტრაცია", "регистрация"), "average price per m² (2025)": ("საშუალო ფასი მ²-ზე (2025)", "средняя цена за м² (2025)"),
    "of buyers are foreigners": ("მყიდველები — უცხოელები", "покупателей — иностранцы"), "rentals": ("ქირა", "аренда"), "New Boulevard": ("ახალი ბულვარი", "Новый бульвар"),
    "replies the same day": ("პასუხი იმავე დღეს", "ответ в тот же день"), "renovated, per m²": ("რემონტით, მ²-ზე", "с ремонтом, за м²"), "rent per m²": ("ქირა მ²-ზე", "аренда за м²"),
    "gross yield": ("შემოსავალი", "доходность"), "Tbilisi average per m²": ("თბილისის საშუალო მ²-ზე", "средняя по Тбилиси за м²"), "many projects": ("ბევრი პროექტი", "много проектов"),
    "near the river": ("მდინარესთან", "у реки"), "property for a residence permit": ("ქონება ბინადრობისთვის", "недвижимость для ВНЖ"), "Tbilisi rental yield": ("შემოსავალი თბილისში", "доходность в Тбилиси"),
    "buying costs": ("ყიდვის ხარჯი", "расходы на покупку"), "GDP growth 2025": ("მშპ-ს ზრდა 2025", "рост ВВП 2025"),
}
UI = {"en": ("Current listings", "See all listings →", "Map", "More", "New listings are added every day — message us and an agent will send you options."),
      "ka": ("აქტუალური განცხადებები", "ყველა განცხადება →", "რუკა", "მეტი", "ახალი განცხადებები ყოველდღე ემატება — მოგვწერეთ და აგენტი შეგირჩევთ."),
      "ru": ("Актуальные объявления", "Все объявления →", "Карта", "Ещё", "Новые объявления каждый день — напишите нам, и агент подберёт варианты.")}


def lurl(path, lg):
    return f"{SITE}/{'' if lg == 'en' else lg + '/'}{path}/"


def render(pg, all_pages, lg):
    e = html.escape
    url = lurl(pg["path"], lg)
    title, desc, body = pg[lg]
    ld = [{"@context": "https://schema.org", "@type": "BreadcrumbList",
           "itemListElement": [{"@type": "ListItem", "position": 1, "name": "KEY GROUP", "item": SITE + "/"},
                               {"@type": "ListItem", "position": 2, "name": title, "item": url}]},
          {"@context": "https://schema.org", "@type": "FAQPage",
           "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ[lg]]}]
    li = {"en": 0, "ka": 1, "ru": 2}[lg]
    facts = "".join(f'<div class="card"><b>{e(v)}</b><span>{e(lbl if li == 0 else LBL.get(lbl, (lbl, lbl))[li - 1])}</span></div>' for v, lbl in pg["facts"])
    faq = "".join(f"<details><summary>{e(q)}</summary><p>{e(a)}</p></details>" for q, a in FAQ[lg])
    alts = "".join(f'<link rel="alternate" hreflang="{x}" href="{lurl(pg["path"], x)}">' for x in ("en", "ka", "ru")) + f'<link rel="alternate" hreflang="x-default" href="{lurl(pg["path"], "en")}">'
    langbtn = "".join(f'<a href="{lurl(pg["path"], x)}" data-l="{x}" aria-current="{"true" if x == lg else "false"}">{n}</a>' for x, n in (("en", "EN"), ("ka", "ქარ"), ("ru", "RU")))
    pre = "" if lg == "en" else "/" + lg
    links = "".join(f'<a href="{pre}/{p["path"]}/">{e(p[lg][0])}</a>' for p in all_pages if p["path"] != pg["path"])
    u = UI[lg]
    flt = json.dumps(pg["filter"], ensure_ascii=False)
    return f"""<!doctype html>
<html lang="{lg}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} | KEY GROUP Real Estate</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{url}">
{alts}
<meta property="og:title" content="{e(title)} — KEY GROUP">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}/img/hero.png">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&family=Noto+Sans+Georgian:wght@400;500;600;700&display=swap">
<link rel="stylesheet" href="/assets/portal.css">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
<style>
.pg{{padding:26px 0 64px}}.crumb{{font-size:13px;color:var(--muted)}}.crumb a{{color:var(--blue)}}
.lead{{font-size:17px;color:#33465c;max-width:900px}}
.facts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:18px 0}}.facts .card{{padding:16px}}.facts b{{display:block;font:800 22px var(--display)}}.facts span{{color:var(--muted);font-size:13px}}
.lt{{display:flex;gap:6px;margin:6px 0 10px}}.lt a{{border:1px solid var(--line);background:#fff;border-radius:999px;padding:5px 12px;font:700 12px var(--display)}}.lt a[aria-current="true"]{{background:var(--navy);color:#fff}}
.faqh details{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:12px 16px;margin-bottom:8px;max-width:900px}}.faqh summary{{font:700 15px var(--display);cursor:pointer}}
.more-links{{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}}.more-links a{{background:#fff;border:1px solid var(--line);border-radius:999px;padding:7px 12px;font:600 13px var(--display)}}
</style>
</head>
<body>
<main class="wrap pg">
  <div class="crumb"><a href="/">KEY GROUP</a> › {e(title)}</div>
  <nav class="lt" aria-label="Language">{langbtn}</nav>
  <h1>{e(title)}</h1><p class="lead">{e(body)}</p>
  <div class="facts">{facts}</div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:22px">
    <a class="btn b-coral" href="/search/?{pg['search']}">{e(u[1])}</a>
    <a class="btn b-wa" target="_blank" rel="noopener" href="https://wa.me/995577114118?text={e('KEY GROUP: ' + title)}">WhatsApp</a>
    <a class="btn b-ghost" href="/search/?{pg['search']}&view=map">🗺 {e(u[2])}</a>
  </div>
  <h2 style="margin-bottom:12px">{e(u[0])}</h2>
  <div class="lgrid" id="grid"><div class="empty">…</div></div>
  <div class="faqh" style="margin-top:30px">{faq}</div>
  <h2 style="margin:30px 0 8px">{e(u[3])}</h2><div class="more-links">{links}<a href="/project/">🏗 Projects</a><a href="/partners/">🤝 Partners</a></div>
</main>
<script src="/assets/portal.js"></script>
<script src="/assets/chat.js" defer></script>
<script>
(function () {{
  try {{ localStorage.setItem('kg_lang', '{lg}'); }} catch (e) {{}}
  KG.lang = '{'en' if lg == 'ru' else lg}';
  KG.header('search');
  KG.$$('.lt a').forEach(function (a) {{ a.addEventListener('click', function () {{ try {{ localStorage.setItem('kg_lang', a.dataset.l); }} catch (e) {{}} }}); }});
  var F = {flt};
  KG.bindFavs(document);
  KG.loadAll().then(function (all) {{
    var res = all.filter(function (x) {{
      var txt = ((x.district || '') + ' ' + (x.districtKa || '') + ' ' + (x.address || '') + ' ' + (x.city || '')).toLowerCase();
      if (F.deal && x.deal !== F.deal) return false;
      if (F.type && x.type !== F.type) return false;
      if (F.kw && !F.kw.some(function (k) {{ return txt.indexOf(k) >= 0; }})) return false;
      if (F.city === 'tbilisi' && /batumi|ბათუმ/.test(txt)) return false;
      return true;
    }});
    res.sort(function (a, b) {{ var r = function (l) {{ return l.tier === 'super' ? 2 : l.tier === 'vip' ? 1 : 0; }}; return r(b) - r(a) || (b.src === 'owner') - (a.src === 'owner'); }});
    KG.$('#grid').innerHTML = res.length ? res.slice(0, 12).map(KG.card).join('') : '<div class="empty">{e(u[4])}</div>';
  }});
}})();
</script>
</body>
</html>
"""


def main():
    pages = PAGES + district_pages() + [INVEST]
    urls = []
    for pg in pages:
        for lg in ("en", "ka", "ru"):
            d = os.path.join(HERE, "site", ("" if lg == "en" else lg + "/") + pg["path"])
            os.makedirs(d, exist_ok=True)
            open(os.path.join(d, "index.html"), "w").write(render(pg, pages, lg))
        urls.append(pg["path"])
    print("\n".join(urls))


if __name__ == "__main__":
    main()
