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


def render(pg, all_pages):
    e = html.escape
    url = f"{SITE}/{pg['path']}/"
    title_en, desc_en, body_en = pg["en"]
    crumbs = [("KEY GROUP", SITE + "/")]
    parts = pg["path"].split("/")
    if len(parts) > 1:
        crumbs.append((parts[0].capitalize(), SITE + "/search/"))
    crumbs.append((title_en, url))
    ld = [{"@context": "https://schema.org", "@type": "BreadcrumbList",
           "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(crumbs)]},
          {"@context": "https://schema.org", "@type": "FAQPage",
           "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ["en"]]}]
    facts = "".join(f'<div class="card"><b>{e(v)}</b><span>{e(lbl)}</span></div>' for v, lbl in pg["facts"])
    langs = ""
    for lg in ("en", "ka", "ru"):
        t, d, b = pg[lg]
        faq = "".join(f"<details><summary>{e(q)}</summary><p>{e(a)}</p></details>" for q, a in FAQ[lg])
        langs += f'<section data-lang="{lg}"{"" if lg == "en" else " hidden"}><h1>{e(t)}</h1><p class="lead">{e(b)}</p><div class="faqh" data-faq>{faq}</div></section>'
    links = "".join(f'<a href="/{p["path"]}/">{e(p["en"][0])}</a>' for p in all_pages if p["path"] != pg["path"])
    flt = json.dumps(pg["filter"], ensure_ascii=False)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title_en)} | KEY GROUP Real Estate</title>
<meta name="description" content="{e(desc_en)}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{e(title_en)} — KEY GROUP">
<meta property="og:description" content="{e(desc_en)}">
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
.lt{{display:flex;gap:6px;margin:6px 0 10px}}.lt button{{border:1px solid var(--line);background:#fff;border-radius:999px;padding:5px 12px;font:700 12px var(--display);cursor:pointer}}.lt button[aria-pressed="true"]{{background:var(--navy);color:#fff}}
.faqh details{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:12px 16px;margin-bottom:8px;max-width:900px}}.faqh summary{{font:700 15px var(--display);cursor:pointer}}
.more-links{{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}}.more-links a{{background:#fff;border:1px solid var(--line);border-radius:999px;padding:7px 12px;font:600 13px var(--display)}}
</style>
</head>
<body>
<main class="wrap pg">
  <div class="crumb"><a href="/">KEY GROUP</a> › {e(title_en)}</div>
  <div class="lt" role="group" aria-label="Language"><button data-l="en" aria-pressed="true">EN</button><button data-l="ka">ქარ</button><button data-l="ru">RU</button></div>
  {langs}
  <div class="facts">{facts}</div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:22px">
    <a class="btn b-coral" href="/search/?{pg['search']}" id="all">See all listings →</a>
    <a class="btn b-wa" target="_blank" rel="noopener" href="https://wa.me/995577114118?text={e('Hello KEY GROUP! ' + title_en)}">WhatsApp</a>
    <a class="btn b-ghost" href="/search/?{pg['search']}&view=map">🗺 Map</a>
  </div>
  <h2 style="margin-bottom:12px" id="lh">Current listings</h2>
  <div class="lgrid" id="grid"><div class="empty">…</div></div>
  <h2 style="margin:34px 0 8px">More</h2><div class="more-links">{links}<a href="/invest-in-georgia/">Invest in Georgia</a><a href="/project/">New build projects</a><a href="/partners/">For agents & developers</a></div>
</main>
<script src="/assets/portal.js"></script>
<script src="/assets/chat.js" defer></script>
<script>
(function () {{
  KG.header('search');
  var F = {flt};
  var lang = 'en'; try {{ lang = localStorage.getItem('kg_lang') || (KG.lang === 'ka' ? 'ka' : 'en'); }} catch (e) {{}}
  var L = {{en: ['Current listings', 'See all listings →'], ka: ['აქტუალური განცხადებები', 'ყველა განცხადება →'], ru: ['Актуальные объявления', 'Все объявления →']}};
  function show(l) {{
    if (!L[l]) l = 'en';
    KG.$$('[data-lang]').forEach(function (s) {{ s.hidden = s.dataset.lang !== l; }});
    KG.$$('.lt button').forEach(function (b) {{ b.setAttribute('aria-pressed', b.dataset.l === l); }});
    KG.$('#lh').textContent = L[l][0]; KG.$('#all').textContent = L[l][1]; document.documentElement.lang = l;
  }}
  KG.$$('.lt button').forEach(function (b) {{ b.onclick = function () {{ try {{ localStorage.setItem('kg_lang', b.dataset.l); }} catch (e) {{}} show(b.dataset.l); }}; }});
  show(lang);
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
    KG.$('#grid').innerHTML = res.length ? res.slice(0, 12).map(KG.card).join('') : '<div class="empty">' + ({{en: 'New listings are added every day — message us and an agent will send you options.', ka: 'ახალი განცხადებები ყოველდღე ემატება — მოგვწერეთ.', ru: 'Новые объявления каждый день — напишите нам.'}})[lang] + '</div>';
  }});
}})();
</script>
</body>
</html>
"""


def main():
    pages = PAGES + district_pages() + [INVEST]
    for pg in pages:
        d = os.path.join(HERE, "site", pg["path"])
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "index.html"), "w").write(render(pg, pages))
    print("\n".join(SITE + "/" + p["path"] + "/" for p in pages))


if __name__ == "__main__":
    main()
