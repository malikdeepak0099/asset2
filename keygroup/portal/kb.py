"""KEY GROUP assistant — knowledge base about buying, renting, investing and owning property in Georgia.

Figures researched November 2026 (sources: TBC Capital Tbilisi monthly watch Mar 2026, tbilisihome.ge Q3 2026 report,
Galt & Taggart via investor.ge Apr 2026, Geostat / IMF Jun 2026, EIG law & YB Case on the residence-permit change,
expathub.ge and pbservices.ge on costs and remote purchase, getwherenext.com on Dubai costs).
They are approximate and rules can change, so answers say so and offer an agent.
Each topic: keywords (any language, a few common typos), answers in en/ka/ru, follow-up buttons (topic ids or '__' actions).
"""

NOTE = {
    "en": "\n\nFigures are approximate and rules can change — our agent will confirm for your case.",
    "ka": "\n\nციფრები მიახლოებითია და წესები შეიძლება შეიცვალოს — თქვენს შემთხვევას აგენტი დაგიზუსტებთ.",
    "ru": "\n\nЦифры приблизительные, правила могут меняться — агент уточнит для вашего случая.",
}

TOPICS = {
    # ------------------------------------------------------------------ investing
    "why": {
        "label": {"en": "🇬🇪 Why invest in Georgia?", "ka": "🇬🇪 რატომ საქართველო?", "ru": "🇬🇪 Почему Грузия?"},
        "kw": ["why georgia", "why invest", "invest in georgia", "investment", "worth investing", "good investment", "should i invest", "benefits",
               "advantages", "почему грузия", "инвест", "стоит ли", "преимущест", "ინვესტ", "რატომ საქართველო", "რატომ უნდა", "უპირატეს"],
        "en": ("Why investors choose Georgia:\n"
               "• Foreigners buy freely with just a passport — same rights as locals (except agricultural land)\n"
               "• Fast and cheap: no stamp duty, registration costs about 50–350 GEL and takes 1–4 days\n"
               "• Low entry price: Tbilisi averages about $1,350/m², renovated flats in Vake/Saburtalo about $1,900/m²\n"
               "• Good rental yields: roughly 6.5–8% gross in Tbilisi, about 7.4% in Batumi\n"
               "• Low taxes: 5% on residential rent (registered landlord), 0% on resale after 2 years\n"
               "• Strong economy: GDP grew 7.5% in 2025; IMF expects about 6.5% in 2026\n"
               "• Property worth $150,000+ can qualify you for a residence permit\n"
               "• Citizens of ~94 countries can stay up to a year without a visa"),
        "ka": ("რატომ ირჩევენ ინვესტორები საქართველოს:\n"
               "• უცხოელი ყიდულობს მხოლოდ პასპორტით — ადგილობრივის თანაბარი უფლებით (გარდა სასოფლო-სამეურნეო მიწისა)\n"
               "• სწრაფი და იაფი: ბაჟი არ არის, რეგისტრაცია დაახლ. 50–350 ლარი, 1–4 დღე\n"
               "• დაბალი ფასი: თბილისში საშუალოდ ≈$1,350/მ², ვაკე/საბურთალოში რემონტით ≈$1,900/მ²\n"
               "• კარგი შემოსავალი ქირიდან: თბილისში ≈6.5–8%, ბათუმში ≈7.4% წლიური\n"
               "• დაბალი გადასახადი: საცხოვრებლის ქირაზე 5% (რეგისტრირებული), გაყიდვაზე 2 წლის შემდეგ 0%\n"
               "• ძლიერი ეკონომიკა: მშპ 2025-ში +7.5%, სსფ 2026-ში ≈6.5%-ს ელის\n"
               "• $150,000+ ღირებულების ქონებამ შეიძლება ბინადრობის ნებართვა მოგცეთ"),
        "ru": ("Почему инвесторы выбирают Грузию:\n"
               "• Иностранцы покупают только по паспорту — с теми же правами, что и местные (кроме сельхозземли)\n"
               "• Быстро и дёшево: нет пошлины на покупку, регистрация ≈50–350 лари за 1–4 дня\n"
               "• Низкий порог входа: Тбилиси в среднем ≈$1,350/м², ремонт в Ваке/Сабуртало ≈$1,900/м²\n"
               "• Хорошая доходность аренды: ≈6.5–8% годовых в Тбилиси, ≈7.4% в Батуми\n"
               "• Низкие налоги: 5% с жилой аренды (зарегистрированный арендодатель), 0% при продаже после 2 лет\n"
               "• Сильная экономика: ВВП +7.5% в 2025, МВФ ждёт ≈6.5% в 2026\n"
               "• Недвижимость от $150,000 может дать вид на жительство\n"
               "• Граждане ≈94 стран могут жить до года без визы"),
        "next": ["roi", "dubai", "trc", "process"],
    },
    "roi": {
        "label": {"en": "📈 ROI & prices", "ka": "📈 შემოსავალი და ფასები", "ru": "📈 Доходность и цены"},
        "kw": ["roi", "return", "yield", "profit", "income from rent", "rental income", "appreciation", "price growth", "grow", "how much per", "price per",
               "per sqm", "per m2", "market", "future", "forecast", "доходн", "окупаем", "рост цен", "прогноз", "цена за метр", "рынок", "будущ",
               "შემოსავ", "ამონაგ", "ფასის ზრდ", "პროგნოზ", "კვადრატ", "ბაზარ", "მომავალ"],
        "en": ("Returns in Georgia (approximate, 2026):\n"
               "• Rental yield: Tbilisi ≈6.5–8% gross per year (TBC Capital: 8.1% average, Mar 2026); Batumi ≈7.4%\n"
               "• Prices, Tbilisi: average asking ≈$1,340/m² (+4% a year). Renovated flats: Old Tbilisi ≈$1,990, Vake–Saburtalo ≈$1,890, Didube ≈$1,730, Isani–Samgori ≈$1,480 per m²\n"
               "• Prices, Batumi: ≈$1,865/m² in 2025, up ≈10%; analysts expect slower growth of 4–6% in 2026\n"
               "• Example: a $100,000 flat renting for $650/month earns ≈$7,800 a year (≈7.8% gross) before costs and 5% tax\n"
               "• Drivers: 7.5% GDP growth, tourism, relocation demand, limited new supply in central districts\n"
               "Prices can also fall — choose location and building quality carefully; our agents help compare."),
        "ka": ("შემოსავლიანობა საქართველოში (მიახლ., 2026):\n"
               "• ქირის შემოსავალი: თბილისი ≈6.5–8% წელიწადში (TBC Capital: საშუალოდ 8.1%, მარტი 2026); ბათუმი ≈7.4%\n"
               "• ფასები თბილისში: საშუალო ≈$1,340/მ² (+4% წლიურად). რემონტით: ძველი თბილისი ≈$1,990, ვაკე–საბურთალო ≈$1,890, დიდუბე ≈$1,730, ისანი–სამგორი ≈$1,480/მ²\n"
               "• ბათუმი: ≈$1,865/მ² 2025-ში (+≈10%); 2026-ში ზრდა ≈4–6%-მდე შენელდება\n"
               "• მაგალითი: $100,000-იანი ბინა $650/თვე ქირით ≈$7,800 წელიწადში (≈7.8%)\n"
               "ფასი შეიძლება დაეცეს კიდეც — მდებარეობა და შენობის ხარისხი მნიშვნელოვანია; აგენტები შედარებაში დაგეხმარებიან."),
        "ru": ("Доходность в Грузии (ориентировочно, 2026):\n"
               "• Аренда: Тбилиси ≈6.5–8% годовых (TBC Capital: в среднем 8.1%, март 2026); Батуми ≈7.4%\n"
               "• Цены, Тбилиси: в среднем ≈$1,340/м² (+4% за год). С ремонтом: Старый Тбилиси ≈$1,990, Ваке–Сабуртало ≈$1,890, Дидубе ≈$1,730, Исани–Самгори ≈$1,480 за м²\n"
               "• Батуми: ≈$1,865/м² в 2025 (+≈10%); в 2026 аналитики ждут замедления роста до 4–6%\n"
               "• Пример: квартира за $100,000 и аренда $650/мес ≈$7,800 в год (≈7.8%) до расходов и налога 5%\n"
               "Цены могут и снижаться — важны район и качество дома; агенты помогут сравнить."),
        "next": ["dubai", "batumi", "tax", "__buy"],
        "note": True,
    },
    "dubai": {
        "label": {"en": "🆚 Georgia vs Dubai", "ka": "🆚 საქართველო თუ დუბაი", "ru": "🆚 Грузия или Дубай"},
        "kw": ["dubai", "uae", "emirates", "compare", "comparison", "vs ", "versus", "turkey", "europe", "дубай", "оаэ", "сравн", "дубаი", "დუბაი", "შედარ"],
        "en": ("Georgia vs Dubai (approximate):\n"
               "• Entry price: Tbilisi ≈$1,300–2,000/m² vs Dubai ≈$4,300–10,000/m² (AED 1,470–3,500/ft²)\n"
               "• Buying costs: Georgia under 1% (no stamp duty) vs Dubai ≈7–8% (4% DLD fee + agency etc.)\n"
               "• Residence through property: Georgia from $150,000 vs Dubai Golden Visa from AED 2M (≈$545,000)\n"
               "• Rental yield: Tbilisi ≈6.5–8% vs Dubai ≈6–7% gross\n"
               "• Service charges: usually low in Georgia vs AED 10–35/ft² a year in Dubai\n"
               "• Taxes: Georgia 5% on residential rent, 0% resale tax after 2 years; Dubai 0% on rent and resale\n"
               "• Dubai is a bigger, more liquid global market; Georgia lets you start with a much smaller budget and own outright faster."),
        "ka": ("საქართველო თუ დუბაი (მიახლ.):\n"
               "• ფასი: თბილისი ≈$1,300–2,000/მ², დუბაი ≈$4,300–10,000/მ²\n"
               "• ყიდვის ხარჯი: საქართველოში 1%-ზე ნაკლები, დუბაიში ≈7–8% (4% DLD + სხვა)\n"
               "• ბინადრობა ქონებით: საქართველო $150,000-დან, დუბაის Golden Visa ≈$545,000-დან\n"
               "• ქირის შემოსავალი: თბილისი ≈6.5–8%, დუბაი ≈6–7%\n"
               "• გადასახადი: საქართველოში ქირაზე 5%, 2 წლის შემდეგ გაყიდვაზე 0%; დუბაიში 0%\n"
               "• დუბაი უფრო დიდი ბაზარია; საქართველოში ბევრად მცირე ბიუჯეტით დაიწყებთ."),
        "ru": ("Грузия или Дубай (ориентировочно):\n"
               "• Цена входа: Тбилиси ≈$1,300–2,000/м², Дубай ≈$4,300–10,000/м²\n"
               "• Расходы на покупку: Грузия меньше 1% (нет пошлины), Дубай ≈7–8% (4% DLD + агентство и др.)\n"
               "• ВНЖ через недвижимость: Грузия от $150,000, Golden Visa Дубая от AED 2 млн (≈$545,000)\n"
               "• Доходность аренды: Тбилиси ≈6.5–8%, Дубай ≈6–7%\n"
               "• Обслуживание: в Грузии обычно недорого, в Дубае AED 10–35/фут² в год\n"
               "• Налоги: Грузия 5% с жилой аренды, 0% при продаже после 2 лет; Дубай 0%\n"
               "• Дубай — более крупный и ликвидный рынок; в Грузии можно начать с гораздо меньшим бюджетом."),
        "next": ["roi", "trc", "why", "__agent"],
        "note": True,
    },
    "batumi": {
        "label": {"en": "🌊 Tbilisi or Batumi?", "ka": "🌊 თბილისი თუ ბათუმი?", "ru": "🌊 Тбилиси или Батуми?"},
        "kw": ["batumi", "sea", "beach", "seaside", "black sea", "tbilisi or", "батуми", "море", "ბათუმ", "ზღვ"],
        "en": ("Tbilisi or Batumi?\n"
               "• Tbilisi: capital, year-round long-term rentals (families, expats, students), most stable demand; yields ≈6.5–8%\n"
               "• Batumi: Black Sea resort, strong short-term/holiday rental, about half of buyers are foreigners; ≈$1,865/m², yield ≈7.4% but more seasonal\n"
               "• For steady monthly income — Tbilisi; for a holiday home plus daily rental — Batumi.\n"
               "We work in both cities."),
        "ka": ("თბილისი თუ ბათუმი?\n"
               "• თბილისი: დედაქალაქი, მთელი წლის გრძელვადიანი ქირა, ყველაზე სტაბილური მოთხოვნა; ≈6.5–8%\n"
               "• ბათუმი: საკურორტო ქალაქი, დღიური ქირა, მყიდველების ნახევარი უცხოელია; ≈$1,865/მ², ≈7.4%, მაგრამ სეზონური\n"
               "ორივე ქალაქში ვმუშაობთ."),
        "ru": ("Тбилиси или Батуми?\n"
               "• Тбилиси: столица, долгосрочная аренда круглый год, самый стабильный спрос; ≈6.5–8%\n"
               "• Батуми: курорт на Чёрном море, посуточная аренда, около половины покупателей — иностранцы; ≈$1,865/м², ≈7.4%, но сезонно\n"
               "Мы работаем в обоих городах."),
        "next": ["roi", "__buy", "__agent"],
        "note": True,
    },
    # ------------------------------------------------------------------ residence / visa
    "trc": {
        "label": {"en": "🪪 Residence permit (TRC)", "ka": "🪪 ბინადრობის ნებართვა", "ru": "🪪 ВНЖ через недвижимость"},
        "kw": ["trc", "residen", "residence permit", "residency", "resident card", "permit", "golden visa", "temporary residence", "id card",
               "внж", "вид на жительство", "резиденц", "ბინადრ", "ნებართვ", "რეზიდენ"],
        "en": ("Residence permit (TRC) through property:\n"
               "• Buy non-agricultural property with a market value of at least $150,000 (since 1 March 2026; it was $100,000 before). Several properties can be combined\n"
               "• Value is confirmed by an accredited appraiser — market value counts, not just the price paid\n"
               "• Permit: 1 year, renewable every year while you keep the property\n"
               "• Spouse and minor children can be included\n"
               "• No minimum stay, no language test, no income proof\n"
               "• Apply at the Public Service Hall with passport, ownership extract, appraisal and photos; decisions usually take about 1–3 weeks, plus a small state fee\n"
               "• Larger investments (about $300,000) can lead to a longer investment residence permit and later permanent residence\n"
               "We help with choosing a qualifying property, the appraisal and the application."),
        "ka": ("ბინადრობის ნებართვა ქონების ყიდვით:\n"
               "• არასასოფლო-სამეურნეო ქონება, საბაზრო ღირებულებით მინ. $150,000 (2026 წლის 1 მარტიდან; მანამდე $100,000). რამდენიმე ქონების გაერთიანება შეიძლება\n"
               "• ღირებულებას ადასტურებს აკრედიტებული შემფასებელი\n"
               "• ნებართვა: 1 წელი, ყოველწლიურად გრძელდება, სანამ ქონება გეკუთვნით\n"
               "• მეუღლე და არასრულწლოვანი შვილები ერთვება\n"
               "• მინიმალური ყოფნა, ენის გამოცდა და შემოსავლის დადასტურება არ სჭირდება\n"
               "• განაცხადი — იუსტიციის სახლში; გადაწყვეტილება ჩვეულებრივ ≈1–3 კვირაში\n"
               "• ≈$300,000-იანი ინვესტიცია გრძელვადიან ნებართვამდე მიგიყვანთ\n"
               "დაგეხმარებით შესაფერისი ქონების შერჩევაში, შეფასებასა და განაცხადში."),
        "ru": ("ВНЖ через покупку недвижимости:\n"
               "• Несельскохозяйственная недвижимость рыночной стоимостью от $150,000 (с 1 марта 2026; раньше $100,000). Можно суммировать несколько объектов\n"
               "• Стоимость подтверждает аккредитованный оценщик — считается рыночная цена\n"
               "• ВНЖ на 1 год, продлевается ежегодно, пока объект в собственности\n"
               "• Супруг(а) и несовершеннолетние дети — вместе с вами\n"
               "• Без минимального срока проживания, экзамена по языку и подтверждения дохода\n"
               "• Подача в Доме юстиции: паспорт, выписка о собственности, оценка, фото; решение обычно за ≈1–3 недели\n"
               "• Инвестиция ≈$300,000 открывает путь к инвестиционному ВНЖ и затем постоянному\n"
               "Поможем подобрать подходящий объект, оценку и подачу документов."),
        "next": ["visa", "process", "__buy", "__agent"],
        "note": True,
    },
    "visa": {
        "label": {"en": "✈️ Visa & stay", "ka": "✈️ ვიზა და ყოფნა", "ru": "✈️ Виза и пребывание"},
        "kw": ["visa", "visa free", "visa-free", "how long can i stay", "stay in georgia", "evisa", "e-visa", "entry", "виза", "безвиз", "сколько можно находиться",
               "ვიზ", "უვიზო"],
        "en": ("Visa & stay:\n"
               "• Citizens of about 94 countries (EU, US, UK, Gulf states, Israel, Ukraine and many more) can stay in Georgia up to 1 year without a visa\n"
               "• Others may need an e-visa — or can enter visa-free with a valid visa/residence permit of certain countries (EU, US, UAE etc.)\n"
               "• Buying property does not require residency or a visa\n"
               "Tell me your citizenship and an agent can check the exact rule for you."),
        "ka": ("ვიზა და ყოფნა:\n"
               "• ≈94 ქვეყნის მოქალაქეს შეუძლია საქართველოში 1 წლამდე უვიზოდ დარჩენა\n"
               "• სხვებს შეიძლება ელექტრონული ვიზა დასჭირდეთ\n"
               "• ქონების ყიდვას ბინადრობა ან ვიზა არ სჭირდება"),
        "ru": ("Виза и пребывание:\n"
               "• Граждане ≈94 стран (ЕС, США, Великобритания, страны Залива, Израиль, Украина и др.) могут находиться в Грузии до 1 года без визы\n"
               "• Остальным может понадобиться e-visa — или въезд по действующей визе/ВНЖ ряда стран (ЕС, США, ОАЭ и др.)\n"
               "• Для покупки недвижимости ВНЖ и виза не нужны\n"
               "Напишите гражданство — агент уточнит правила для вас."),
        "next": ["trc", "remote", "__agent"],
        "note": True,
    },
    # ------------------------------------------------------------------ buying
    "process": {
        "label": {"en": "📝 How to buy (documents)", "ka": "📝 ყიდვის პროცესი", "ru": "📝 Как купить (документы)"},
        "kw": ["document", "documents", "how to buy", "buying process", "process", "steps", "what do i need", "papers", "requirements for buying",
               "foreigner", "foreign", "forner", "foriner", "forigner", "foreiner", "non-resident", "non resident", "can i buy", "can foreigners", "allowed to buy",
               "докум", "как купить", "процесс", "иностран", "нерезидент", "могу ли я купить", "დოკუმენტ", "როგორ ვიყიდო", "პროცეს", "უცხოელ"],
        "en": ("Buying property in Georgia — foreigners welcome:\n"
               "1) Only your passport is needed. Foreigners can buy flats, houses and commercial property (agricultural land is restricted)\n"
               "2) Choose the property — we check the ownership extract (Public Registry) for owners, mortgages and bans\n"
               "3) Sign the purchase agreement and pay — bank transfer is safest; a Georgian bank account helps but is not required\n"
               "4) Register at the Public Service Hall: about 50–350 GEL depending on speed, usually 1–4 working days. No stamp duty\n"
               "5) You receive the electronic ownership extract — the property is yours\n"
               "Can't come? You can buy remotely with a notarized power of attorney."),
        "ka": ("ქონების ყიდვა საქართველოში:\n"
               "1) საჭიროა მხოლოდ პასპორტი. უცხოელს შეუძლია ბინის, სახლის და კომერციული ფართის ყიდვა (სას.-სამ. მიწაზე შეზღუდვაა)\n"
               "2) ვამოწმებთ საჯარო რეესტრის ამონაწერს — მესაკუთრე, იპოთეკა, ყადაღა\n"
               "3) ხელშეკრულება და გადახდა — უმჯობესია საბანკო გადარიცხვით\n"
               "4) რეგისტრაცია იუსტიციის სახლში: ≈50–350 ლარი სისწრაფის მიხედვით, 1–4 სამუშაო დღე\n"
               "5) იღებთ ელექტრონულ ამონაწერს — ქონება თქვენია\n"
               "ჩამოსვლა არ შეგიძლიათ? შეიძენთ დისტანციურად, მინდობილობით."),
        "ru": ("Покупка недвижимости в Грузии — иностранцам можно:\n"
               "1) Нужен только паспорт. Иностранцы покупают квартиры, дома и коммерцию (на сельхозземлю ограничения)\n"
               "2) Проверяем выписку из Публичного реестра — собственник, ипотека, запреты\n"
               "3) Договор и оплата — надёжнее банковским переводом; грузинский счёт удобен, но не обязателен\n"
               "4) Регистрация в Доме юстиции: ≈50–350 лари в зависимости от срока, обычно 1–4 рабочих дня. Пошлины на покупку нет\n"
               "5) Вы получаете электронную выписку о собственности\n"
               "Не можете приехать? Покупка удалённо по нотариальной доверенности."),
        "next": ["remote", "tax", "trc", "__buy"],
        "note": True,
    },
    "remote": {
        "label": {"en": "🌍 Buy remotely", "ka": "🌍 დისტანციური ყიდვა", "ru": "🌍 Купить удалённо"},
        "kw": ["remote", "remotely", "without coming", "without visiting", "power of attorney", "from abroad", "online", "online viewing", "video tour",
               "удалённо", "удаленно", "доверенност", "не приезжая", "онлайн", "дистанц", "მინდობილ", "დისტანც", "ონლაინ"],
        "en": ("Buying from abroad:\n"
               "• We send video tours and documents of the property\n"
               "• You sign a power of attorney at a notary (or Georgian consulate) in your country — usually with apostille and translation\n"
               "• Our team/lawyer signs and registers the purchase for you; you can follow the status online\n"
               "• Payment goes by international bank transfer (SWIFT) or via a Georgian bank account, which many banks open remotely"),
        "ka": ("ყიდვა საზღვარგარეთიდან:\n"
               "• გიგზავნით ვიდეოს და დოკუმენტებს\n"
               "• ნოტარიუსთან ადგენთ მინდობილობას (როგორც წესი აპოსტილით და თარგმანით)\n"
               "• ჩვენი გუნდი ხელს აწერს და არეგისტრირებს ნასყიდობას\n"
               "• გადახდა — საერთაშორისო გადარიცხვით ან ქართულ ანგარიშზე"),
        "ru": ("Покупка из-за рубежа:\n"
               "• Присылаем видеообзор и документы объекта\n"
               "• Вы оформляете доверенность у нотариуса (или в консульстве Грузии) — обычно с апостилем и переводом\n"
               "• Наша команда/юрист подписывает и регистрирует сделку; статус видно онлайн\n"
               "• Оплата — международным переводом (SWIFT) или через грузинский счёт, который многие банки открывают удалённо"),
        "next": ["process", "__agent"],
        "note": True,
    },
    "tax": {
        "label": {"en": "💼 Taxes & costs", "ka": "💼 გადასახადები", "ru": "💼 Налоги и расходы"},
        "kw": ["tax", "taxes", "cost of buying", "fees", "stamp duty", "capital gain", "property tax", "hidden cost", "налог", "пошлин", "расход",
               "გადასახად", "მოსაკრებ", "ხარჯ"],
        "en": ("Taxes & costs for property owners:\n"
               "• Buying: no stamp duty; registration ≈50–350 GEL; optional lawyer/notary\n"
               "• Rental income: 5% of residential rent if you register as a landlord with the Revenue Service (otherwise 20%); commercial rent 20%\n"
               "• Selling: 0% tax after owning 2+ years; 5% if sold earlier\n"
               "• Annual property tax: none for households with income under 40,000 GEL a year; above that 0.05–1% of value\n"
               "• Utilities and building fees are usually modest."),
        "ka": ("გადასახადები და ხარჯები:\n"
               "• ყიდვა: ბაჟი არ არის; რეგისტრაცია ≈50–350 ლარი\n"
               "• ქირის შემოსავალი: საცხოვრებელზე 5% (რეგისტრირებული), სხვა შემთხვევაში 20%; კომერციულზე 20%\n"
               "• გაყიდვა: 2+ წლის ფლობის შემდეგ 0%, ადრე — 5%\n"
               "• ქონების გადასახადი: ოჯახის წლიური შემოსავალი 40,000 ლარამდე — არ არის; ზემოთ 0.05–1%"),
        "ru": ("Налоги и расходы владельца:\n"
               "• Покупка: пошлины нет; регистрация ≈50–350 лари\n"
               "• Аренда: 5% с жилой аренды при регистрации арендодателем в Налоговой (иначе 20%); коммерция 20%\n"
               "• Продажа: 0% после 2+ лет владения; 5% при более ранней продаже\n"
               "• Налог на имущество: нет при доходе семьи до 40,000 лари в год; выше — 0.05–1% стоимости"),
        "next": ["roi", "process", "__agent"],
        "note": True,
    },
    "mortgage": {
        "label": {"en": "🏦 Mortgage", "ka": "🏦 იპოთეკა", "ru": "🏦 Ипотека"},
        "kw": ["mortgage for foreign", "mortgage for non", "mortgage", "loan", "installment", "instalment", "credit", "payment plan", "ипотек", "кредит", "рассроч", "იპოთეკ", "სესხ", "განვადებ"],
        "en": ("Financing options:\n"
               "• Georgian banks give mortgages, usually with a 20–30% down payment; residents and people with Georgian income get approved most easily\n"
               "• Many new-build developers offer interest-free installment plans during construction — popular with foreign buyers\n"
               "• Every listing page on our site has a mortgage calculator, and our agents help you prepare for the bank."),
        "ka": ("დაფინანსება:\n"
               "• ქართული ბანკები გასცემენ იპოთეკას, ჩვეულებრივ 20–30%-იანი შენატანით\n"
               "• ბევრი დეველოპერი სთავაზობს უპროცენტო განვადებას მშენებლობის პერიოდში\n"
               "• საიტზე ყველა განცხადებას აქვს იპოთეკის კალკულატორი."),
        "ru": ("Финансирование:\n"
               "• Грузинские банки дают ипотеку, обычно с первым взносом 20–30%; проще одобряют резидентам и людям с доходом в Грузии\n"
               "• Многие застройщики дают беспроцентную рассрочку на время строительства — популярно у иностранцев\n"
               "• На странице каждого объекта есть ипотечный калькулятор."),
        "next": ["__buy", "__agent"],
        "note": True,
    },
    "newbuild": {
        "label": {"en": "🏗 New build or resale?", "ka": "🏗 ახალი თუ ძველი?", "ru": "🏗 Новостройка или вторичка?"},
        "kw": ["new build", "newbuild", "off plan", "off-plan", "under construction", "developer", "white frame", "black frame", "green frame", "resale", "secondary",
               "новострой", "застройщик", "белый каркас", "черный каркас", "вторичк", "ახალაშენ", "დეველოპერ", "თეთრი კარკას", "შავი კარკას", "მწვანე კარკას"],
        "en": ("New build or resale?\n"
               "• Georgian new builds are sold as black frame (bare walls), white frame (plastered, ready for finishing) or green frame/renovated (ready to live)\n"
               "• Off-plan is cheaper and often has installment plans, but check the developer's track record and the construction permit\n"
               "• Resale is ready now and can be rented immediately — best for quick income\n"
               "We check developers and documents before you pay."),
        "ka": ("ახალი თუ ძველი?\n"
               "• ახალაშენი იყიდება შავი, თეთრი ან მწვანე კარკასით/რემონტით\n"
               "• მშენებარე უფრო იაფია და ხშირად განვადებით, მაგრამ შეამოწმეთ დეველოპერი და ნებართვა\n"
               "• ძველი ბინა მზადაა და მაშინვე გაქირავდება\n"
               "დეველოპერს და საბუთებს გადახდამდე ვამოწმებთ."),
        "ru": ("Новостройка или вторичка?\n"
               "• Новостройки продаются в чёрном каркасе (голые стены), белом (под чистовую) или зелёном/с ремонтом\n"
               "• На этапе строительства дешевле и часто с рассрочкой, но проверьте застройщика и разрешение\n"
               "• Вторичка готова сразу и сразу сдаётся\n"
               "Проверяем застройщика и документы до оплаты."),
        "next": ["process", "mortgage", "__buy"],
    },
    # ------------------------------------------------------------------ renting
    "renting": {
        "label": {"en": "🔑 Renting rules", "ka": "🔑 ქირაობის წესები", "ru": "🔑 Правила аренды"},
        "kw": ["deposit", "rental contract", "lease contract", "how to rent", "renting rules", "pets", "pet", "utilities", "bills", "minimum term", "how long contract",
               "депозит", "залог", "договор аренды", "коммунал", "животн", "დეპოზიტ", "ქირის ხელშეკრულ", "კომუნალ", "ცხოველ"],
        "en": ("Renting in Tbilisi — usual terms:\n"
               "• Contract usually 6–12 months; shorter is possible at a higher price\n"
               "• Pay the first month plus a deposit (often one month's rent), returned at the end if there is no damage\n"
               "• Utilities (electricity, gas, water, internet) are usually paid by the tenant — about $50–120 a month for a typical flat, more in winter with gas heating\n"
               "• Pets: depends on the owner — tell us and we filter for pet-friendly flats\n"
               "• You need just your passport"),
        "ka": ("ქირაობა თბილისში — ჩვეულებრივი პირობები:\n"
               "• ხელშეკრულება ხშირად 6–12 თვით\n"
               "• პირველი თვე + დეპოზიტი (ხშირად ერთი თვის), ბრუნდება ბოლოს\n"
               "• კომუნალურებს ჩვეულებრივ დამქირავებელი იხდის\n"
               "• შინაური ცხოველები — მესაკუთრეზეა დამოკიდებული\n"
               "• საჭიროა მხოლოდ პასპორტი"),
        "ru": ("Аренда в Тбилиси — обычные условия:\n"
               "• Договор чаще на 6–12 месяцев; короче — дороже\n"
               "• Первый месяц + депозит (часто за месяц), возвращается в конце\n"
               "• Коммунальные услуги обычно платит арендатор — ≈$50–120 в месяц, зимой с газовым отоплением больше\n"
               "• Животные — по согласованию с владельцем, подберём подходящие варианты\n"
               "• Нужен только паспорт"),
        "next": ["__rent", "__agent"],
        "note": True,
    },
    "fees": {
        "label": {"en": "🤝 Our fees", "ka": "🤝 საკომისიო", "ru": "🤝 Комиссия"},
        "kw": ["commission", "your fee", "agency fee", "how much do you charge", "do you charge", "комисси", "сколько берете", "საკომისიო", "მომსახურების ფას"],
        "en": ("Adding your own listing on keygroup.ge is free. For deals done with KEY GROUP agents, the fee depends on the property and the type of deal — "
               "the agent tells you the exact terms before you agree to anything. No surprises."),
        "ka": ("keygroup.ge-ზე საკუთარი განცხადების დამატება უფასოა. აგენტთან გარიგების საკომისიო დამოკიდებულია ქონებასა და გარიგების ტიპზე — "
               "ზუსტ პირობებს აგენტი წინასწარ გეტყვით."),
        "ru": ("Размещение своего объявления на keygroup.ge бесплатно. Комиссия при сделке с агентами KEY GROUP зависит от объекта и типа сделки — "
               "точные условия агент назовёт заранее."),
        "next": ["__agent"],
    },
    # ------------------------------------------------------------------ owner help
    "owner": {
        "label": {"en": "🏠 Owner help", "ka": "🏠 დახმარება მესაკუთრეს", "ru": "🏠 Помощь владельцу"},
        "kw": ["owner help", "help owner", "i am owner", "i'm owner", "im owner", "landlord", "how to add", "add listing", "add my", "list my", "post my", "sell my", "rent out",
               "my property", "my apartment", "my flat", "собственник", "владелец", "разместить", "сдать мою", "продать мою", "добавить объявление",
               "მესაკუთრე", "განცხადების დამატ", "ჩემი ბინ", "გავყიდო", "გავაქირავო"],
        "en": ("Happy to help owners 🏠 Two ways to sell or rent out:\n"
               "1) Add it yourself on keygroup.ge — free\n"
               "2) Let KEY GROUP agents do everything: photos, MyHome.ge + SS.ge, viewings and negotiation\n"
               "What do you need help with?"),
        "ka": ("სიამოვნებით დაგეხმარებით 🏠 გაყიდვის ან გაქირავების ორი გზა:\n"
               "1) დაამატეთ თავად keygroup.ge-ზე — უფასოდ\n"
               "2) ყველაფერს KEY GROUP-ის აგენტები გააკეთებენ: ფოტო, MyHome.ge + SS.ge, ჩვენებები\n"
               "რაში დაგეხმაროთ?"),
        "ru": ("С радостью поможем владельцу 🏠 Два способа продать или сдать:\n"
               "1) Разместить самому на keygroup.ge — бесплатно\n"
               "2) Доверить всё агентам KEY GROUP: фото, MyHome.ge + SS.ge, показы и переговоры\n"
               "С чем помочь?"),
        "next": ["o_add", "o_photos", "o_price", "o_promote", "o_pending", "o_sell_docs", "o_tax", "__sellforme"],
    },
    "o_add": {
        "label": {"en": "➕ How to add a listing", "ka": "➕ როგორ დავამატო", "ru": "➕ Как разместить"},
        "kw": ["how to add", "how do i add", "how to post", "register account", "create account", "sign up", "registration", "как разместить", "как добавить", "регистрац",
               "როგორ დავამატო", "რეგისტრაც"],
        "en": ("Adding your listing takes about 5 minutes:\n"
               "1) Open keygroup.ge/account and register with your phone number and a password\n"
               "2) Press “Add listing”: sale or rent, type, district, address, rooms, area, floor, price\n"
               "3) Upload up to 15 photos — the first photo is the cover\n"
               "4) Save — our team checks it (usually the same day) and it goes live\n"
               "5) Want more calls? Order VIP, Super VIP or Boost in your account"),
        "ka": ("განცხადების დამატება ≈5 წუთია:\n"
               "1) გახსენით keygroup.ge/account და დარეგისტრირდით ტელეფონით და პაროლით\n"
               "2) „განცხადების დამატება“: გაყიდვა/ქირა, ტიპი, უბანი, მისამართი, ოთახები, ფართი, სართული, ფასი\n"
               "3) ატვირთეთ 15-მდე ფოტო — პირველი მთავარია\n"
               "4) შეინახეთ — ვამოწმებთ (ჩვეულებრივ იმავე დღეს) და ქვეყნდება\n"
               "5) მეტი ზარი გინდათ? შეუკვეთეთ VIP, Super VIP ან Boost"),
        "ru": ("Размещение занимает ≈5 минут:\n"
               "1) Откройте keygroup.ge/account и зарегистрируйтесь по телефону и паролю\n"
               "2) «Добавить объявление»: продажа/аренда, тип, район, адрес, комнаты, площадь, этаж, цена\n"
               "3) Загрузите до 15 фото — первое станет обложкой\n"
               "4) Сохраните — мы проверим (обычно в тот же день) и опубликуем\n"
               "5) Нужно больше звонков? Закажите VIP, Super VIP или Boost"),
        "next": ["o_photos", "o_promote", "owner"],
        "url": "/account/",
    },
    "o_photos": {
        "label": {"en": "📸 Photo tips", "ka": "📸 ფოტოს რჩევები", "ru": "📸 Советы по фото"},
        "kw": ["photo", "photos", "pictures", "images", "upload photo", "фото", "снимк", "ფოტო", "სურათ"],
        "en": ("Photos that get more calls:\n"
               "• Shoot in daylight with lights on and curtains open; hold the phone horizontally at chest height\n"
               "• Tidy up first; show every room, kitchen, bathroom, balcony and the view\n"
               "• Put the best photo first — it becomes the cover\n"
               "• Up to 15 photos; JPG/PNG from your phone is fine — we resize automatically\n"
               "• Prefer professional photos and video? Our team can shoot them when you list with KEY GROUP."),
        "ka": ("ფოტოები, რომლებიც მეტ ზარს მოიტანს:\n"
               "• გადაიღეთ დღისით, ფარდები გაწეული; ტელეფონი ჰორიზონტალურად\n"
               "• დაალაგეთ; აჩვენეთ ყველა ოთახი, სამზარეულო, აბაზანა, აივანი და ხედი\n"
               "• საუკეთესო ფოტო პირველი დადეთ\n"
               "• 15 ფოტომდე; ტელეფონის ფოტო საკმარისია"),
        "ru": ("Фото, которые приносят звонки:\n"
               "• Снимайте днём, шторы открыты, свет включён; телефон горизонтально\n"
               "• Наведите порядок; покажите все комнаты, кухню, ванную, балкон и вид\n"
               "• Лучшее фото — первым, оно станет обложкой\n"
               "• До 15 фото; фото с телефона подойдут — мы уменьшим автоматически\n"
               "• Нужны профессиональные фото и видео? Сделаем при работе с KEY GROUP."),
        "next": ["o_add", "o_price", "owner"],
    },
    "o_price": {
        "label": {"en": "💲 What price to ask?", "ka": "💲 რა ფასი დავადო?", "ru": "💲 Какую цену ставить?"},
        "kw": ["what price", "how much is my", "price my", "how much should i ask", "right price", "сколько стоит моя", "какую цену", "რა ფასი", "რა ღირს ჩემი"],
        "en": ("Pricing your property:\n"
               "• Compare similar flats in the same district on our Search page (same rooms, floor, renovation)\n"
               "• Typical Tbilisi asking prices (renovated): Old Tbilisi ≈$1,990/m², Vake–Saburtalo ≈$1,890/m², Didube ≈$1,730/m², Isani–Samgori ≈$1,480/m²; rent ≈$9–11 per m² a month\n"
               "• Overpriced listings sit for months — a fair price brings calls in the first week\n"
               "• Want an exact figure? We do a free valuation within 24 hours."),
        "ka": ("ფასის განსაზღვრა:\n"
               "• შეადარეთ მსგავსი ბინები იმავე უბანში ძიების გვერდზე\n"
               "• საორიენტაციო ფასები (რემონტით): ძველი თბილისი ≈$1,990/მ², ვაკე–საბურთალო ≈$1,890/მ², დიდუბე ≈$1,730/მ², ისანი–სამგორი ≈$1,480/მ²; ქირა ≈$9–11/მ² თვეში\n"
               "• გაბერილი ფასი თვეობით რჩება — სამართლიანი ფასი პირველივე კვირაში მოიტანს ზარებს\n"
               "• ზუსტი ციფრი? უფასო შეფასება 24 საათში."),
        "ru": ("Как назначить цену:\n"
               "• Сравните похожие квартиры в том же районе на странице поиска\n"
               "• Ориентиры (с ремонтом): Старый Тбилиси ≈$1,990/м², Ваке–Сабуртало ≈$1,890/м², Дидубе ≈$1,730/м², Исани–Самгори ≈$1,480/м²; аренда ≈$9–11 за м² в месяц\n"
               "• Завышенная цена — объявление висит месяцами; честная цена даёт звонки в первую неделю\n"
               "• Нужна точная цифра? Бесплатная оценка за 24 часа."),
        "next": ["__valuation", "o_add", "owner"],
        "note": True,
    },
    "o_promote": {
        "label": {"en": "🚀 VIP / Boost", "ka": "🚀 VIP / Boost", "ru": "🚀 VIP / Boost"},
        "kw": ["vip", "super vip", "boost", "promot", "sponsor", "top of", "plans", "tariff", "more views", "more calls", "продвиж", "поднять", "реклам", "тариф",
               "ტოპ", "პაკეტ", "რეკლამ"],
        "dynamic": "plans",
        "next": ["payment", "o_add", "owner"],
    },
    "payment": {
        "label": {"en": "💳 How to pay", "ka": "💳 გადახდა", "ru": "💳 Оплата"},
        "kw": ["payment", "how to pay", "how do i pay", "how can i pay", "iban", "bank transfer", "bank details", "оплат", "как платить", "реквизит", "გადახდ", "ანგარიშ", "ჩარიცხ", "რეკვიზიტ"],
        "dynamic": "payment",
        "next": ["o_promote", "__agent"],
    },
    "o_pending": {
        "label": {"en": "⏳ Listing not visible?", "ka": "⏳ განცხადება არ ჩანს?", "ru": "⏳ Объявление не видно?"},
        "kw": ["not visible", "not showing", "pending", "rejected", "not approved", "where is my listing", "expired", "renew", "edit my listing", "change price",
               "не видно", "не показывается", "на проверке", "отклон", "продлить", "изменить цену", "არ ჩანს", "შემოწმებაზე", "უარყოფ", "განახლ", "ფასის შეცვლ"],
        "en": ("If your listing is not visible:\n"
               "• Pending — new and edited listings are checked by our team first, usually the same day\n"
               "• Rejected — the reason is shown in your account; fix it and save again\n"
               "• Expired — free listings stay 30 days; press Renew in your account\n"
               "• To change the price or photos, open the listing in your account and edit — it goes live again after a quick check\n"
               "• Forgot your password? Write to support@keygroup.ge or WhatsApp and we reset it."),
        "ka": ("თუ განცხადება არ ჩანს:\n"
               "• შემოწმებაზეა — ახალ და შეცვლილ განცხადებას ვამოწმებთ, ჩვეულებრივ იმავე დღეს\n"
               "• უარყოფილია — მიზეზი ანგარიშში ჩანს; გაასწორეთ და შეინახეთ\n"
               "• ვადაგასულია — უფასო განცხადება 30 დღეა; დააჭირეთ „განახლებას“\n"
               "• პაროლი დაგავიწყდათ? მოგვწერეთ support@keygroup.ge-ზე ან WhatsApp-ზე."),
        "ru": ("Если объявление не видно:\n"
               "• На проверке — новые и изменённые объявления проверяем, обычно в тот же день\n"
               "• Отклонено — причина указана в кабинете; исправьте и сохраните\n"
               "• Истекло — бесплатное объявление живёт 30 дней; нажмите «Продлить»\n"
               "• Цену и фото меняйте в кабинете — после быстрой проверки снова в эфире\n"
               "• Забыли пароль? Напишите на support@keygroup.ge или в WhatsApp — сбросим."),
        "next": ["o_add", "__agent", "owner"],
        "url": "/account/",
    },
    "o_sell_docs": {
        "label": {"en": "📄 Documents to sell", "ka": "📄 საბუთები გასაყიდად", "ru": "📄 Документы для продажи"},
        "kw": ["documents to sell", "to sell my", "selling documents", "sell documents", "extract", "cadastral", "ownership document", "документы для продажи", "выписк",
               "საბუთები გასაყიდ", "ამონაწერ", "საკადასტრო"],
        "en": ("To sell your property you usually need:\n"
               "• Your ID card/passport (all owners, or a notarized power of attorney)\n"
               "• A fresh Public Registry extract showing you as owner — we can pull it online with the cadastral code\n"
               "• If there is a mortgage: the bank's consent or loan closure at the deal\n"
               "• No mandatory notary — the deal is registered at the Public Service Hall in 1–4 days\n"
               "• Selling after 2+ years of ownership is tax-free for individuals."),
        "ka": ("ქონების გასაყიდად ჩვეულებრივ საჭიროა:\n"
               "• პირადობა/პასპორტი (ყველა მესაკუთრის, ან მინდობილობა)\n"
               "• საჯარო რეესტრის ამონაწერი — საკადასტრო კოდით ონლაინ ამოვიღებთ\n"
               "• იპოთეკის შემთხვევაში — ბანკის თანხმობა\n"
               "• რეგისტრაცია იუსტიციის სახლში 1–4 დღეში\n"
               "• 2+ წლის ფლობის შემდეგ გაყიდვა ფიზიკური პირისთვის გადასახადის გარეშეა."),
        "ru": ("Для продажи обычно нужны:\n"
               "• ID/паспорт (всех собственников или нотариальная доверенность)\n"
               "• Свежая выписка из Публичного реестра — можем получить онлайн по кадастровому коду\n"
               "• При ипотеке — согласие банка или погашение при сделке\n"
               "• Нотариус не обязателен — регистрация в Доме юстиции за 1–4 дня\n"
               "• Продажа после 2+ лет владения для физлиц без налога."),
        "next": ["o_tax", "__sellforme", "owner"],
        "note": True,
    },
    "o_tax": {
        "label": {"en": "🧾 Landlord tax (5%)", "ka": "🧾 ქირის გადასახადი 5%", "ru": "🧾 Налог 5% с аренды"},
        "kw": ["landlord tax", "rental tax", "tax on rent", "5%", "register as landlord", "налог с аренды", "налог на аренду", "ქირის გადასახად"],
        "en": ("Tax on rental income (individuals):\n"
               "• Register your residential rental income with the Revenue Service (rs.ge) to pay a flat 5% of the rent instead of 20%\n"
               "• Declare and pay by the deadlines shown on rs.ge (usually monthly or yearly depending on your setup)\n"
               "• Commercial rentals are taxed at 20%\n"
               "An accountant can set it up in one visit — ask us for a contact."),
        "ka": ("ქირის შემოსავლის გადასახადი:\n"
               "• დაარეგისტრირეთ საცხოვრებლის ქირა შემოსავლების სამსახურში (rs.ge) — 20%-ის ნაცვლად 5%\n"
               "• დეკლარირება და გადახდა rs.ge-ზე მითითებულ ვადებში\n"
               "• კომერციულ ქირაზე — 20%"),
        "ru": ("Налог с аренды (физлица):\n"
               "• Зарегистрируйте доход от жилой аренды в Налоговой (rs.ge) — 5% вместо 20%\n"
               "• Декларируйте и платите в сроки, указанные на rs.ge\n"
               "• Коммерческая аренда — 20%\n"
               "Бухгалтер оформит за один визит — дадим контакт."),
        "next": ["tax", "owner"],
        "note": True,
    },
}

# order of the "Ask about Georgia" menu
GUIDE = ["why", "roi", "trc", "dubai", "process", "tax", "batumi", "visa", "renting", "mortgage", "newbuild", "remote"]
