/* KEY GROUP website assistant — floating chat. Bot answers instantly; a human agent takes over when needed. */
(function () {
  if (window.__kgChat) return; window.__kgChat = 1;
  var store = {get: function (k, d) { try { var v = localStorage.getItem(k); return v == null ? d : v; } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} }};
  // ---- first-party anonymous analytics (no cookies, no personal data)
  var SID = store.get('kg_sid', '');
  if (!SID) { SID = Math.random().toString(36).slice(2) + Date.now().toString(36); store.set('kg_sid', SID); }
  window.kgTrack = function (name, props) {
    try {
      var body = JSON.stringify({name: name, props: props || {}, page: location.pathname + location.search.slice(0, 40), sid: SID, ref: name === 'page_view' && document.referrer.indexOf(location.host) < 0 ? document.referrer : ''});
      if (navigator.sendBeacon) navigator.sendBeacon('/api/track', new Blob([body], {type: 'application/json'}));
      else fetch('/api/track', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: body, keepalive: true});
    } catch (e) {}
  };
  if (location.pathname.indexOf('/admin') !== 0) window.kgTrack('page_view');
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a'); if (!a) return;
    var h = a.getAttribute('href') || '';
    if (/myhome\.ge\/pr\/|\/p\/\?id=/.test(h) && !a.closest('.kgc-p')) window.kgTrack('listing_click', {href: h.slice(0, 80)});
    else if (h.indexOf('wa.me/995') >= 0 && location.pathname.indexOf('/p/') !== 0) window.kgTrack('whatsapp_click');
    else if (h.indexOf('tel:') === 0 && location.pathname.indexOf('/p/') !== 0) window.kgTrack('call_click');
  }, true);

  function lang() {
    var l = store.get('kg_lang', '') || (document.documentElement.lang || 'ka').slice(0, 2);
    return l === 'ru' || l === 'en' ? l : 'ka';
  }
  var L = lang();
  var TX = {
    en: {title: 'KEY GROUP assistant', bot: 'Online · replies instantly', wait: 'Connecting you to an agent…', agent: 'Agent is in the chat', ph: 'Write a message…',
      send: 'Send', open: 'Chat with us', close: 'Close chat', teaser: 'Hi! 👋 Looking for a flat? I can help in seconds.', agentL: 'Agent', err: 'Message not sent — check your internet.', wa: 'Prefer WhatsApp?'},
    ka: {title: 'KEY GROUP ასისტენტი', bot: 'ონლაინ · პასუხობს მყისიერად', wait: 'გიკავშირებთ აგენტს…', agent: 'აგენტი ჩატშია', ph: 'დაწერეთ შეტყობინება…',
      send: 'გაგზავნა', open: 'მოგვწერეთ', close: 'ჩატის დახურვა', teaser: 'გამარჯობა! 👋 ბინას ეძებთ? წამებში დაგეხმარებით.', agentL: 'აგენტი', err: 'ვერ გაიგზავნა — შეამოწმეთ ინტერნეტი.', wa: 'გირჩევნიათ WhatsApp?'},
    ru: {title: 'Ассистент KEY GROUP', bot: 'Онлайн · отвечает сразу', wait: 'Соединяем с агентом…', agent: 'Агент в чате', ph: 'Напишите сообщение…',
      send: 'Отправить', open: 'Напишите нам', close: 'Закрыть чат', teaser: 'Здравствуйте! 👋 Ищете квартиру? Помогу за секунды.', agentL: 'Агент', err: 'Не отправлено — проверьте интернет.', wa: 'Удобнее WhatsApp?'}
  }[L];

  var path = location.pathname;
  var PAGE = path.indexOf('/account') === 0 ? 'owner' : path.indexOf('/p/') === 0 ? 'listing' : path.indexOf('/search') === 0 ? 'search' : 'home';
  var TEASE = {
    home: {en: 'Thinking of buying in Georgia? 🇬🇪 Ask me about prices, ROI or the residence permit.', ka: 'ფიქრობთ საქართველოში ყიდვაზე? 🇬🇪 მკითხეთ ფასებზე, შემოსავალზე ან ბინადრობაზე.', ru: 'Думаете о покупке в Грузии? 🇬🇪 Спросите о ценах, доходности или ВНЖ.'},
    search: {en: 'Can’t find the right place? Tell me what you need — I search 480+ listings in seconds.', ka: 'ვერ პოულობთ? მომწერეთ რა გჭირდებათ — 480+ განცხადებაში წამებში მოვძებნი.', ru: 'Не нашли подходящее? Напишите, что нужно — найду среди 480+ объявлений.'},
    listing: {en: 'Questions about this property? I can answer or book a viewing for you.', ka: 'კითხვები გაქვთ ამ ქონებაზე? გიპასუხებთ ან დათვალიერებას დაგინიშნავთ.', ru: 'Вопросы по объекту? Отвечу или запишу на просмотр.'},
    owner: {en: 'Need help adding your listing? I can guide you step by step. 🏠', ka: 'გჭირდებათ დახმარება განცხადების დამატებაში? ნაბიჯ-ნაბიჯ დაგეხმარებით. 🏠', ru: 'Нужна помощь с объявлением? Подскажу шаг за шагом. 🏠'}
  }[PAGE][L];
  var CH = {
    why: {en: '🇬🇪 Why Georgia?', ka: '🇬🇪 რატომ საქართველო?', ru: '🇬🇪 Почему Грузия?'}, trc: {en: '🪪 Residence permit', ka: '🪪 ბინადრობა', ru: '🪪 ВНЖ'},
    roi: {en: '📈 ROI & prices', ka: '📈 შემოსავალი', ru: '📈 Доходность'}, dubai: {en: '🆚 vs Dubai', ka: '🆚 დუბაი', ru: '🆚 Дубай'},
    process: {en: '📝 How to buy', ka: '📝 როგორ ვიყიდო', ru: '📝 Как купить'}, rent: {en: '🔑 Rent a flat', ka: '🔑 ქირა', ru: '🔑 Аренда'},
    buy: {en: '🏠 Buy', ka: '🏠 ყიდვა', ru: '🏠 Купить'}, owner: {en: '🏠 Owner help', ka: '🏠 მესაკუთრეს', ru: '🏠 Владельцу'},
    o_add: {en: '➕ How to add', ka: '➕ როგორ დავამატო', ru: '➕ Как разместить'}, o_photos: {en: '📸 Photo tips', ka: '📸 ფოტო', ru: '📸 Фото'},
    o_price: {en: '💲 Right price', ka: '💲 ფასი', ru: '💲 Цена'}, o_promote: {en: '🚀 VIP / Boost', ka: '🚀 VIP', ru: '🚀 VIP'},
    viewing: {en: '📅 Book a viewing', ka: '📅 დათვალიერება', ru: '📅 Просмотр'}, agent: {en: '👤 Agent', ka: '👤 აგენტი', ru: '👤 Агент'},
    mortgage: {en: '🏦 Mortgage', ka: '🏦 იპოთეკა', ru: '🏦 Ипотека'}, tax: {en: '💼 Taxes', ka: '💼 გადასახადი', ru: '💼 Налоги'}
  };
  var VAL = {rent: '__rent', buy: '__buy', owner: '__list', viewing: '__viewing', agent: '__agent'};
  var STRIP = {home: ['why', 'trc', 'roi', 'dubai', 'rent', 'buy', 'owner', 'agent'], search: ['rent', 'buy', 'roi', 'trc', 'process', 'agent'],
    listing: ['viewing', 'mortgage', 'process', 'tax', 'trc', 'agent'], owner: ['o_add', 'o_photos', 'o_price', 'o_promote', 'owner', 'agent']}[PAGE];
  function chip(k) { return {v: VAL[k] || ('__t_' + k), l: CH[k][L]}; }

  var css = '' +
    '.kgc-l{position:fixed;right:20px;bottom:20px;z-index:2147483000;width:62px;height:62px;border-radius:50%;border:0;cursor:pointer;background:#0D2847;color:#fff;display:grid;place-items:center;box-shadow:0 14px 34px rgba(8,26,48,.35);transition:transform .15s}' +
    '.kgc-l:hover{transform:scale(1.06)}.kgc-l svg{width:28px;height:28px}' +
    '.kgc-l::after{content:"";position:absolute;inset:-6px;border-radius:50%;border:2px solid #D4A853;opacity:0;animation:kgcP 2.4s ease-out 3}' +
    '@keyframes kgcP{0%{transform:scale(.85);opacity:.9}100%{transform:scale(1.35);opacity:0}}' +
    '.kgc-tc{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.kgc-tc button{border:1.5px solid #0D2847;background:#fff;color:#0D2847;border-radius:999px;padding:6px 10px;font:600 12px "Noto Sans Georgian",Sora,system-ui,sans-serif;cursor:pointer;position:static}' +
    '.kgc-tc button:hover{background:#0D2847;color:#fff}' +
    '.kgc-s{display:flex;gap:6px;overflow-x:auto;padding:8px 12px 0;background:#fff;border-top:1px solid #E4E9F0;scrollbar-width:none}.kgc-s::-webkit-scrollbar{display:none}' +
    '.kgc-s button{flex:none;border:1px solid #E4E9F0;background:#F7F9FC;color:#0D2847;border-radius:999px;padding:6px 11px;font:600 12px "Noto Sans Georgian",Sora,system-ui,sans-serif;cursor:pointer;white-space:nowrap}' +
    '.kgc-s button:hover{border-color:#0D2847;background:#fff}' +
    '.kgc-l .kgc-dot{position:absolute;top:4px;right:4px;min-width:18px;height:18px;border-radius:9px;background:#F45D48;color:#fff;font:700 11px/18px Sora,system-ui,sans-serif;padding:0 5px;border:2px solid #fff}' +
    '.kgc-t{position:fixed;right:20px;z-index:2147483000;max-width:300px;background:#fff;color:#0F1E33;border-radius:16px 16px 4px 16px;padding:12px 34px 12px 14px;font:600 14px/1.4 "Noto Sans Georgian",Sora,system-ui,sans-serif;box-shadow:0 14px 34px rgba(8,26,48,.2);cursor:pointer;animation:kgcIn .3s}' +
    '.kgc-t .kgc-tx{position:absolute;top:6px;right:6px;border:0;background:none;font-size:16px;cursor:pointer;color:#5E6E82}' +
    '.kgc-p{box-sizing:border-box;margin:0;padding:0;text-align:left;position:fixed;right:20px;z-index:2147483001;width:380px;max-width:calc(100vw - 24px);height:600px;max-height:calc(100vh - 110px);background:#F7F9FC;border-radius:22px;box-shadow:0 24px 60px rgba(8,26,48,.35);display:flex;flex-direction:column;overflow:hidden;font-family:"Noto Sans Georgian",Sora,system-ui,sans-serif;color:#0F1E33;animation:kgcIn .2s}' +
    '@keyframes kgcIn{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}' +
    '.kgc-h{background:linear-gradient(120deg,#0D2847,#163E6B);color:#fff;padding:14px 16px;display:flex;gap:12px;align-items:center}' +
    '.kgc-av{width:40px;height:40px;border-radius:50%;background:#D4A853;color:#081A30;display:grid;place-items:center;font:800 14px Sora,system-ui,sans-serif;flex:none}' +
    '.kgc-h b{display:block;font:700 15px Sora,system-ui,sans-serif}.kgc-h small{font-size:12px;opacity:.85;display:flex;align-items:center;gap:6px}' +
    '.kgc-h small i{width:8px;height:8px;border-radius:50%;background:#25D366;display:inline-block}' +
    '.kgc-x{margin-left:auto;border:0;background:rgba(255,255,255,.12);color:#fff;width:34px;height:34px;border-radius:50%;cursor:pointer;font-size:18px}' +
    '.kgc-b{position:relative;flex:1;overflow-y:auto;padding:16px 14px;display:flex;flex-direction:column;gap:10px}' +
    '.kgc-m{text-align:left;max-width:84%;padding:10px 13px;border-radius:16px;font-size:14px;line-height:1.45;white-space:pre-wrap;word-wrap:break-word}' +
    '.kgc-m.bot,.kgc-m.agent{background:#fff;border:1px solid #E4E9F0;border-bottom-left-radius:4px;align-self:flex-start}' +
    '.kgc-m.agent{border-color:#9FDCD6;background:#ECFAF8}.kgc-m.agent em{display:block;font:700 11px Sora,system-ui,sans-serif;color:#0E9F9A;font-style:normal;margin-bottom:2px;text-transform:uppercase;letter-spacing:.05em}' +
    '.kgc-m.visitor{background:#0D2847;color:#fff;border-bottom-right-radius:4px;align-self:flex-end}' +
    '.kgc-m.system{align-self:center;background:none;color:#5E6E82;font-size:12px;text-align:center}' +
    '.kgc-bt{display:flex;flex-wrap:wrap;gap:6px;align-self:flex-start;max-width:100%}' +
    '.kgc-bt button,.kgc-bt a{border:1.5px solid #0D2847;background:#fff;color:#0D2847;border-radius:999px;padding:7px 12px;font:600 13px "Noto Sans Georgian",Sora,system-ui,sans-serif;cursor:pointer;text-decoration:none}' +
    '.kgc-bt button:hover,.kgc-bt a:hover{background:#0D2847;color:#fff}' +
    '.kgc-cs{display:flex;flex-direction:column;gap:8px;align-self:stretch}' +
    '.kgc-c{display:flex;gap:10px;background:#fff;border:1px solid #E4E9F0;border-radius:14px;overflow:hidden;text-decoration:none;color:inherit}' +
    '.kgc-c:hover{border-color:#0D2847}' +
    '.kgc-c .im{width:88px;flex:none;background:linear-gradient(135deg,#7FD3CF,#1F6F86) center/cover}' +
    '.kgc-c .tx{padding:9px 10px 9px 0;min-width:0}.kgc-c b{display:block;font:800 15px Sora,system-ui,sans-serif}' +
    '.kgc-c span{display:block;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kgc-c small{color:#5E6E82;font-size:12px}' +
    '.kgc-c .vip{display:inline-block;background:#7C5CFF;color:#fff;border-radius:6px;padding:0 6px;font:700 10px/16px Sora,system-ui,sans-serif;margin-left:6px;vertical-align:middle}' +
    '.kgc-ty{align-self:flex-start;background:#fff;border:1px solid #E4E9F0;border-radius:16px;padding:12px 14px;display:flex;gap:4px}' +
    '.kgc-ty i{width:7px;height:7px;border-radius:50%;background:#9AA8B8;animation:kgcB 1s infinite}.kgc-ty i:nth-child(2){animation-delay:.15s}.kgc-ty i:nth-child(3){animation-delay:.3s}' +
    '@keyframes kgcB{0%,60%,100%{opacity:.3}30%{opacity:1}}' +
    '.kgc-f{display:flex;gap:8px;padding:8px 12px 10px;background:#fff}' +
    '.kgc-f textarea{flex:1;resize:none;border:1.5px solid #E4E9F0;border-radius:14px;padding:10px 12px;font:500 14px "Noto Sans Georgian",Sora,system-ui,sans-serif;max-height:110px;min-height:44px;color:#0F1E33;outline:none}' +
    '.kgc-f textarea:focus{border-color:#0D2847}' +
    '.kgc-f button{border:0;background:#F45D48;color:#fff;border-radius:14px;width:48px;cursor:pointer;display:grid;place-items:center}.kgc-f button svg{width:20px;height:20px}' +
    '.kgc-w{font-size:12px;text-align:center;padding:0 0 8px;background:#fff;color:#5E6E82}.kgc-w a{color:#0E9F9A;font-weight:700;text-decoration:none}' +
    '@media (max-width:520px){.kgc-p{right:0!important;bottom:0!important;width:100vw;max-width:100vw;height:100%;max-height:100%;border-radius:0}}';
  var st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);

  var ICON_CHAT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/><path d="M8 11h.01M12 11h.01M16 11h.01"/></svg>';
  var ICON_SEND = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4z"/></svg>';
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]; }); };

  var hasWa = !!document.querySelector('.wa-float');
  var base = hasWa ? 92 : 20;
  var btn = document.createElement('button');
  btn.className = 'kgc-l'; btn.type = 'button'; btn.setAttribute('aria-label', TX.open); btn.style.bottom = base + 'px';
  btn.innerHTML = ICON_CHAT;
  document.body.appendChild(btn);

  var S = {id: +store.get('kg_chat_id', 0) || 0, token: store.get('kg_chat_tok', ''), last: 0, status: 'bot', open: false, timer: null, unread: 0, started: false};
  var panel, body, ta, sub;

  function setBadge(n) {
    S.unread = n;
    var d = btn.querySelector('.kgc-dot');
    if (n && !S.open) { if (!d) { d = document.createElement('span'); d.className = 'kgc-dot'; btn.appendChild(d); } d.textContent = n; }
    else if (d) d.remove();
  }
  function statusText() {
    if (!sub) return;
    sub.innerHTML = '<i' + (S.status === 'waiting' ? ' style="background:#F59E0B"' : '') + '></i>' + esc(S.status === 'agent' ? TX.agent : S.status === 'waiting' ? TX.wait : TX.bot);
  }
  function build() {
    panel = document.createElement('div');
    panel.className = 'kgc-p'; panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-label', TX.title);
    panel.style.bottom = (base + 74) + 'px';
    panel.innerHTML = '<div class="kgc-h"><div class="kgc-av">KG</div><div><b>' + esc(TX.title) + '</b><small></small></div>' +
      '<button class="kgc-x" type="button" aria-label="' + esc(TX.close) + '">×</button></div>' +
      '<div class="kgc-b" aria-live="polite"></div>' +
      '<div class="kgc-s" role="group">' + STRIP.map(function (k) { var c = chip(k); return '<button type="button" data-q="' + esc(c.v) + '">' + esc(c.l) + '</button>'; }).join('') + '</div>' +
      '<form class="kgc-f"><textarea rows="1" maxlength="1000" placeholder="' + esc(TX.ph) + '" aria-label="' + esc(TX.ph) + '"></textarea><button type="submit" aria-label="' + esc(TX.send) + '">' + ICON_SEND + '</button></form>' +
      '<div class="kgc-w">' + esc(TX.wa) + ' <a href="https://wa.me/995577114118" target="_blank" rel="noopener">WhatsApp</a></div>';
    document.body.appendChild(panel);
    body = panel.querySelector('.kgc-b'); ta = panel.querySelector('textarea'); sub = panel.querySelector('small');
    panel.querySelector('.kgc-x').onclick = toggle;
    panel.querySelector('form').onsubmit = function (e) { e.preventDefault(); var t = ta.value.trim(); if (t) { ta.value = ''; send(t, t); } };
    ta.addEventListener('keydown', function (e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); panel.querySelector('form').requestSubmit ? panel.querySelector('form').requestSubmit() : panel.querySelector('form').onsubmit(e); } });
    ta.addEventListener('input', function () { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 110) + 'px'; });
    panel.querySelector('.kgc-s').addEventListener('click', function (e) {
      var b = e.target.closest('button[data-q]'); if (b) send(b.dataset.q, b.textContent);
    });
    body.addEventListener('click', function (e) {
      var b = e.target.closest('button[data-v]');
      if (!b) return;
      var wrap = b.parentNode; if (wrap) wrap.remove();
      send(b.dataset.v, b.textContent);
    });
    statusText();
  }
  function render(m) {
    if (m.id <= S.last) return;
    S.last = m.id;
    var html = '';
    if (m.text) html += '<div class="kgc-m ' + esc(m.who) + '">' + (m.who === 'agent' ? '<em>' + esc(TX.agentL) + '</em>' : '') + esc(m.text) + '</div>';
    if (m.cards && m.cards.length) html += '<div class="kgc-cs">' + m.cards.map(function (c) {
      var ext = /^https?:/.test(c.url) && c.url.indexOf(location.host) < 0;
      return '<a class="kgc-c" href="' + esc(c.url) + '"' + (ext ? ' target="_blank" rel="noopener"' : '') + '><div class="im"' + (c.photo ? ' style="background-image:url(' + esc(c.photo) + ')"' : '') + '></div>' +
        '<div class="tx"><b>' + esc(c.price) + (c.badge ? '<span class="vip">' + esc(c.badge) + '</span>' : '') + '</b><span>' + esc(c.title) + '</span><small>' + esc(c.specs) + '</small></div></a>';
    }).join('') + '</div>';
    if (m.buttons && m.buttons.length) html += '<div class="kgc-bt">' + m.buttons.map(function (b) {
      return b.url ? '<a href="' + esc(b.url) + '"' + (b.url.indexOf(location.host) < 0 ? ' target="_blank" rel="noopener"' : '') + '>' + esc(b.label) + '</a>' : '<button type="button" data-v="' + esc(b.value) + '">' + esc(b.label) + '</button>';
    }).join('') + '</div>';
    var tmp = document.createElement('div'); tmp.innerHTML = html;
    var first = tmp.firstChild;
    while (tmp.firstChild) body.appendChild(tmp.firstChild);
    return first;
  }
  function scroll() { body.scrollTop = body.scrollHeight; }
  function apply(j) {
    if (!j || !j.ok) return false;
    if (j.token) { S.id = j.chat_id; S.token = j.token; store.set('kg_chat_id', S.id); store.set('kg_chat_tok', S.token); }
    var prev = S.status; S.status = j.status || S.status;
    var fresh = 0, firstEl = null;
    (j.messages || []).forEach(function (m) { if (m.id > S.last) { if (m.who === 'agent') fresh++; if (body) { var el = render(m); firstEl = firstEl || el; } else S.last = Math.max(S.last, m.id); } });
    if (body) {
      if (j.fromSend && firstEl && firstEl.offsetTop) body.scrollTop = Math.max(0, firstEl.offsetTop - 70);
      else scroll();
      statusText();
    }
    if (!S.open && fresh) setBadge(S.unread + fresh);
    if (prev !== S.status) schedule();
    return true;
  }
  function post(path, data) {
    return fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data), credentials: 'same-origin'})
      .then(function (r) { return r.json(); });
  }
  var startP = null;
  function start() {
    S.started = true;
    return startP = post('/api/chat/start', {chat_id: S.id, token: S.token, lang: L, page: location.pathname}).then(function (j) {
      if (j.ok) { S.last = 0; if (body) body.innerHTML = ''; }
      apply(j);
    }).catch(function () {});
  }
  function typing(on) {
    var t = body.querySelector('.kgc-ty');
    if (on && !t) { t = document.createElement('div'); t.className = 'kgc-ty'; t.innerHTML = '<i></i><i></i><i></i>'; body.appendChild(t); scroll(); }
    if (!on && t) t.remove();
  }
  function send(text, label) {
    window.kgTrack('chat_question', {q: text.indexOf('__') === 0 ? text : 'text'});
    if (label) render({id: S.last + 0.001, who: 'visitor', text: label});
    scroll();
    var botMode = S.status === 'bot';
    if (botMode) typing(true);
    var last = Math.floor(S.last);
    var go = function () {
      return post('/api/chat/send', {chat_id: S.id, token: S.token, text: text, label: label, after: last}).then(function (j) {
        typing(false);
        if (!j.ok && j.error === 'Chat not found') { store.set('kg_chat_id', 0); S.id = 0; S.token = ''; return start().then(go); }
        if (!j.ok) { render({id: S.last + 0.001, who: 'system', text: j.error || TX.err}); scroll(); return; }
        // server echoes the visitor message: skip it, it is already on screen
        j.messages = (j.messages || []).filter(function (m) { if (m.who === 'visitor') { S.last = Math.max(S.last, m.id); return false; } return true; });
        j.fromSend = true;
        setTimeout(function () { apply(j); }, botMode ? 350 : 0);
      }).catch(function () { typing(false); render({id: S.last + 0.001, who: 'system', text: TX.err}); scroll(); });
    };
    go();
  }
  function poll() {
    if (!S.id || !S.token) return;
    fetch('/api/chat/poll?chat_id=' + S.id + '&token=' + encodeURIComponent(S.token) + '&after=' + Math.floor(S.last), {credentials: 'same-origin'})
      .then(function (r) { return r.json(); }).then(function (j) {
        if (!j.ok) return;
        j.messages = (j.messages || []).filter(function (m) { if (m.who === 'visitor') { S.last = Math.max(S.last, m.id); return false; } return true; });
        apply(j);
      }).catch(function () {});
  }
  function schedule() {
    clearInterval(S.timer);
    var human = S.status === 'waiting' || S.status === 'agent';
    if (!S.id) return;
    if (human) S.timer = setInterval(poll, S.open ? 4000 : 15000);
  }
  function toggle() {
    S.open = !S.open;
    hideTeaser();
    if (S.open) {
      window.kgTrack('chat_opened');
      if (!panel) build();
      panel.style.display = 'flex';
      btn.style.display = window.innerWidth <= 520 ? 'none' : '';
      setBadge(0);
      if (!S.started) start().then(function () { scroll(); }); else scroll();
      setTimeout(function () { ta.focus(); }, 50);
    } else {
      panel.style.display = 'none'; btn.style.display = '';
    }
    schedule();
  }
  btn.onclick = toggle;
  function askFromOutside(v, label) {
    if (!S.open) toggle();
    var go = function () { send(v, label); };
    if (startP) startP.then(function () { setTimeout(go, 250); }); else go();
  }

  // resume an open agent conversation in the background (shows a badge when the agent answers)
  if (S.id && S.token) {
    fetch('/api/chat/poll?chat_id=' + S.id + '&token=' + encodeURIComponent(S.token) + '&after=0', {credentials: 'same-origin'})
      .then(function (r) { return r.json(); }).then(function (j) {
        if (!j.ok || j.status === 'closed') { if (j && !j.ok) { store.set('kg_chat_id', 0); S.id = 0; } return; }
        S.status = j.status; S.last = Math.max.apply(null, [0].concat((j.messages || []).map(function (m) { return m.id; })));
        schedule();
      }).catch(function () {});
  }

  // friendly teaser once per visit
  var teaser;
  function hideTeaser() { if (teaser) { teaser.remove(); teaser = null; } }
  try {
    if (!sessionStorage.getItem('kgc_t')) setTimeout(function () {
      if (S.open) return;
      sessionStorage.setItem('kgc_t', '1');
      teaser = document.createElement('div'); teaser.className = 'kgc-t'; teaser.style.bottom = (base + 74) + 'px';
      var tc = STRIP.slice(0, 3).map(chip);
      teaser.innerHTML = esc(TEASE) + '<button type="button" class="kgc-tx" aria-label="×">×</button><div class="kgc-tc">' +
        tc.map(function (c) { return '<button type="button" data-q="' + esc(c.v) + '">' + esc(c.l) + '</button>'; }).join('') + '</div>';
      teaser.onclick = function (e) {
        var q = e.target.closest('button[data-q]');
        if (q) { hideTeaser(); askFromOutside(q.dataset.q, q.textContent); return; }
        if (e.target.closest('.kgc-tx')) { hideTeaser(); return; }
        toggle();
      };
      document.body.appendChild(teaser);
    }, PAGE === 'owner' ? 5000 : 9000);
  } catch (e) {}
})();
