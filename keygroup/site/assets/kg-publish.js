/* KEY GROUP publisher — fills the MyHome.ge / SS.ge "add listing" form in the user's own logged-in browser.
   It never presses Publish: the user checks the form and publishes. Loaded by the "KEY GROUP ⇢ fill" bookmark. */
(function () {
  if (window.__kgpubRunning) return;
  window.__kgpubRunning = true;
  var API = 'https://keygroup.ge';
  var host = location.hostname;
  var SITE = /myhome\.ge$/.test(host) ? 'myhome' : /ss\.ge$/.test(host) ? 'ss' : '';
  var sleep = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  var tsetter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
  var log = [];
  function note(ok, what) { log.push([ok, what]); draw(); }

  // ---------- small floating panel
  var panel = document.createElement('div');
  panel.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:2147483647;width:340px;max-height:70vh;overflow:auto;background:#0D2847;color:#fff;border-radius:16px;padding:14px 16px;font:14px/1.45 system-ui,sans-serif;box-shadow:0 12px 40px rgba(0,0,0,.35)';
  document.body.appendChild(panel);
  var head = 'KEY GROUP ⇢ ' + (SITE === 'myhome' ? 'MyHome.ge' : SITE === 'ss' ? 'SS.ge' : '?');
  function draw(extra) {
    panel.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px"><b>' + head + '</b><button id="kgx" style="background:none;border:0;color:#fff;font-size:18px;cursor:pointer">×</button></div>' +
      log.map(function (l) { return '<div style="margin-top:4px">' + (l[0] === true ? '✅' : l[0] === false ? '⚠️' : '⏳') + ' ' + l[1] + '</div>'; }).join('') + (extra || '');
    panel.querySelector('#kgx').onclick = function () { panel.remove(); window.__kgpubRunning = false; };
  }
  draw();

  // ---------- helpers
  function val(el, v) {
    (el.tagName === 'TEXTAREA' ? tsetter : setter).call(el, v == null ? '' : String(v));
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
    el.dispatchEvent(new Event('blur', {bubbles: true}));
  }
  async function typeInto(el, text) {
    el.focus(); el.click();
    setter.call(el, ''); el.dispatchEvent(new Event('input', {bubbles: true}));
    for (var i = 0; i < text.length; i++) {
      var ch = text[i];
      el.dispatchEvent(new KeyboardEvent('keydown', {key: ch, bubbles: true}));
      setter.call(el, el.value + ch);
      el.dispatchEvent(new InputEvent('input', {bubbles: true, data: ch, inputType: 'insertText'}));
      el.dispatchEvent(new KeyboardEvent('keyup', {key: ch, bubbles: true}));
      await sleep(35);
    }
  }
  function leaves(root) { return Array.prototype.filter.call((root || document.body).querySelectorAll('*'), function (e) { return e.childElementCount === 0 && !/^(SCRIPT|STYLE|NOSCRIPT)$/.test(e.tagName) && (e.innerText || '').trim(); }); }
  // an option whose visible text is exactly `text` — also cards like "icon\nბინა" (icon name + label)
  function optionEl(root, text) {
    var c = Array.prototype.filter.call((root || document.body).querySelectorAll('button,label,a,div,span,p,li'), function (e) {
      if (/^(SCRIPT|STYLE)$/.test(e.tagName)) return false;
      var t = (e.innerText || '').trim();
      if (!t || t.length > 40) return false;
      var lines = t.split('\n').map(function (x) { return x.trim(); }).filter(Boolean);
      return t === text || lines[lines.length - 1] === text;
    });
    c.sort(function (a, b) { return (a.innerText || '').length - (b.innerText || '').length || b.querySelectorAll('*').length - a.querySelectorAll('*').length; });
    var el = c[0];
    if (!el) return null;
    // climb to the clickable card (the element whose text is still just this option)
    while (el.parentElement && (el.parentElement.innerText || '').trim().split('\n').filter(Boolean).length <= 2 && (el.parentElement.innerText || '').trim().length <= 40) el = el.parentElement;
    return el;
  }
  function realClick(el) {
    var r = el.getBoundingClientRect(), o = {bubbles: true, cancelable: true, view: window, clientX: r.left + r.width / 2, clientY: r.top + r.height / 2, button: 0};
    try { el.dispatchEvent(new PointerEvent('pointerdown', o)); } catch (e) {}
    el.dispatchEvent(new MouseEvent('mousedown', o));
    try { el.dispatchEvent(new PointerEvent('pointerup', o)); } catch (e) {}
    el.dispatchEvent(new MouseEvent('mouseup', o));
    el.dispatchEvent(new MouseEvent('click', o));
  }
  // MyHome only saves the address after its geocode call — watch for it
  (function () {
    if (window.__kgGeoHook) return; window.__kgGeoHook = true; window.__kgGeo = 0;
    var oo = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (m, u) { if (/geocode/.test(String(u))) window.__kgGeo++; return oo.apply(this, arguments); };
  })();
  function txt(e) { return (e.innerText || e.textContent || '').trim(); }
  function press(el) { ['mousedown', 'mouseup', 'click'].forEach(function (t) { el.dispatchEvent(new MouseEvent(t, {bubbles: true, cancelable: true})); }); }
  async function photosToFiles(urls) {
    var files = [];
    for (var i = 0; i < urls.length; i++) {
      try {
        var r = await fetch(urls[i], {mode: 'cors'});
        var b = await r.blob();
        files.push(new File([b], 'keygroup-' + (i + 1) + '.jpg', {type: b.type || 'image/jpeg'}));
      } catch (e) { /* skip one photo */ }
    }
    return files;
  }
  function putFiles(input, files) {
    var dt = new DataTransfer();
    files.forEach(function (f) { dt.items.add(f); });
    input.files = dt.files;
    input.dispatchEvent(new Event('change', {bubbles: true}));
  }

  var TYPE_KA = {flat: 'ბინა', house: 'კერძო სახლი', land: 'მიწის ნაკვეთი', commercial: 'კომერციული ფართი', hotel: 'სასტუმრო'};
  var DEAL_KA = {sale: 'იყიდება', rent: 'ქირავდება', daily: 'ქირავდება დღიურად'};

  // ---------- MyHome.ge
  async function fillMyHome(d) {
    var T = function (id) { return document.querySelector('[data-test-id="' + id + '"]'); };
    var chip = function (sec, text) {
      var s = T(sec); if (!s) return false;
      var l = Array.prototype.find.call(s.querySelectorAll('label'), function (x) { return txt(x) === text; });
      if (l) l.click();
      return !!l;
    };
    for (var w = 0; w < 30 && !T('add-statement-real-estate-type'); w++) await sleep(300);
    if (!T('add-statement-real-estate-type')) { note(false, 'Open the MyHome “add listing” page first'); return; }
    note(chip('add-statement-real-estate-type', TYPE_KA[d.type] || 'ბინა'), 'Property type: ' + (TYPE_KA[d.type] || 'ბინა'));
    note(chip('add-statement-deal-type', DEAL_KA[d.deal] || 'იყიდება'), 'Deal: ' + (DEAL_KA[d.deal] || 'იყიდება'));
    await sleep(500);
    if (d.auto && d.auto.building) note(chip('add-statement-status', d.auto.building), 'Status: ' + d.auto.building);
    else note(chip('add-statement-status', 'ძველი აშენებული') ? null : false, 'Status: “old building” chosen — change it if the building is new');
    if (d.auto && d.auto.condition_myhome) note(chip('add-statement-condition', d.auto.condition_myhome), 'Condition: ' + d.auto.condition_myhome);
    else note(false, 'Condition: choose it yourself (renovated, white frame…)');
    // location
    var loc = T('add-statement-location-id'), li;
    if (loc && d.district_ka) {
      await typeInto(loc.querySelector('input'), d.district_ka);
      await sleep(1500);
      li = Array.prototype.find.call(loc.querySelectorAll('li'), function (x) { return txt(x).indexOf(d.city_ka || 'თბილისი') >= 0; }) || loc.querySelector('li');
      if (li) { li.scrollIntoView({block: 'center'}); realClick(li); }
      note(!!li, 'Location: ' + (li ? txt(li).replace(/\n/g, ', ') : d.district_ka + ' — choose it yourself'));
      await sleep(800);
    }
    var st = T('add-statement-street-id');
    if (st && d.street && li) {
      var sti = st.querySelector('input');
      await typeInto(sti, d.street.split(' ')[0]);
      await sleep(1500);
      var key = d.street.split(' ').slice(0, 2).join(' ');
      var sli = Array.prototype.find.call(st.querySelectorAll('li'), function (x) { return txt(x).indexOf(key) === 0; }) || st.querySelector('li');
      var geo0 = window.__kgGeo;
      if (sli) { sli.scrollIntoView({block: 'center'}); realClick(sli); }
      await sleep(1500);
    }
    var num = T('add-statement-street-number');
    if (num && d.number) {
      var ni = num.querySelector('input'); await typeInto(ni, String(d.number));
      ni.dispatchEvent(new Event('change', {bubbles: true})); ni.blur(); ni.dispatchEvent(new FocusEvent('focusout', {bubbles: true}));
      await sleep(1500); note(true, 'Number: ' + d.number);
    }
    if (st && d.street && li) {
      var geoOk = window.__kgGeo > geo0;
      note(sli && geoOk ? true : false, 'Street: ' + (sli ? txt(sli).split('\n')[0] + (geoOk ? '' : ' — address not saved: pick the street again by hand from the list') : d.street + ' — choose it yourself'));
    }
    // price
    var ct = T('add-statement-currency-toggle');
    if (ct) {
      var sign = d.currency === 'GEL' ? '₾' : '$';
      var c = leaves(ct).find(function (e) { return txt(e) === sign; });
      if (c) press(c.closest('button,label,div') || c);
      await sleep(400);
    }
    val(T('add-statement-total-price'), Math.round(d.price));
    note(true, 'Price: ' + Math.round(d.price) + ' ' + (d.currency === 'GEL' ? '₾' : '$'));
    var area = T('add-statement-area'); if (area && d.area) { val(area.querySelector('input'), d.area); note(true, 'Area: ' + d.area + ' m²'); }
    if (d.rooms) note(chip('add-statement-room-type', d.rooms >= 10 ? '10+' : String(d.rooms)), 'Rooms: ' + d.rooms);
    var fl = T('add-statement-floor-and-total-floors');
    if (fl) { var fi = fl.querySelectorAll('input'); if (d.floor) val(fi[0], d.floor); if (d.total_floors && fi[1]) val(fi[1], d.total_floors); note(!!d.floor, 'Floor: ' + (d.floor || '—') + ' / ' + (d.total_floors || '—')); }
    var pt = T('add-statement-project-type');
    if (pt) {
      var trig = pt.querySelector('.luk-custom-select > div');
      if (trig) { press(trig); await sleep(600); var opt = leaves(pt).find(function (e) { return txt(e) === 'არასტანდარტული'; }); if (opt) press(opt); }
      note(null, 'Project type: “non-standard” — change it if needed');
    }
    // descriptions
    [['ka', d.desc_ka], ['en', d.desc_en], ['ru', d.desc_ru]].forEach(function (x) { var t = T('add-statement-description-' + x[0]); if (t && x[1]) val(t, x[1].slice(0, 3000)); });
    note(!!(d.desc_ka || d.desc_en), 'Description: ' + [d.desc_ka ? 'GE' : '', d.desc_en ? 'EN' : '', d.desc_ru ? 'RU' : ''].filter(Boolean).join(' / '));
    if (d.video_url) { var yt = T('add-statement-url-youtube'); if (yt) val(yt, d.video_url); }
    // photos
    var pu = T('add-statement-photo-upload'), finput = pu && pu.querySelector('input[type=file]');
    if (finput && d.photos.length) {
      note(null, 'Uploading ' + d.photos.length + ' photos…');
      var files = await photosToFiles(d.photos.slice(0, 16));
      putFiles(finput, files);
      log.pop(); note(files.length > 0, 'Photos: ' + files.length);
    } else note(false, 'Photos: none on keygroup.ge — add at least one');
    var cn = T('add-statement-contact-name'); if (cn) { var ci = cn.querySelector('input'); if (ci && !ci.value) val(ci, d.contact_name); }
    if (d.promo) await promoMyHome(d.promo);
  }

  var TIER = {vip: 'VIP', vipplus: 'VIP+', supervip: 'Super VIP'};
  // MyHome paid option: pick the package card + days. Never pays — the person presses Publish (balance is charged there).
  async function promoMyHome(p) {
    var T = function (id) { return document.querySelector('[data-test-id="' + id + '"]'); };
    var site = T('add-statement-services-website-2');                    // 2 = Myhome (1 = Livo)
    var card = site && Array.prototype.find.call(site.querySelectorAll('[data-test-id^="add-statement-service-card-2-"]'), function (c) {
      var h = (c.innerText || '').split('\n').map(function (x) { return x.trim(); });
      return h.indexOf(TIER[p.tier]) >= 0;
    });
    if (!card) { note(false, 'Paid: ' + TIER[p.tier] + ' — not found, choose it yourself'); return; }
    card.scrollIntoView({block: 'center'}); realClick(card); await sleep(900);
    var ds = T('add-statement-vip-day-selection-2'), days = p.myhome_days || p.days, price = '';
    if (ds) {
      var trig = Array.prototype.filter.call(ds.querySelectorAll('div'), function (x) { return x.offsetParent && /^არჩევა/.test(txt(x)) && x.querySelector('img'); }).pop();
      if (trig) { realClick(trig); await sleep(600); }
      var li = Array.prototype.find.call(ds.querySelectorAll('li'), function (x) { return x.offsetParent && txt(x) === days + ' დღე'; });
      if (li) { realClick(li); await sleep(700); }
      price = (txt(ds).match(/([\d.,]+)\s*₾/) || [])[1] || '';
      note(li ? null : false, 'Paid: ' + TIER[p.tier] + ' · ' + days + ' days' + (price ? ' = ' + price + '₾' : '') + ' — check your MyHome balance; it is charged when you press Publish');
    } else note(null, 'Paid: ' + TIER[p.tier] + ' selected — choose the days yourself');
  }

  // SS paid option: the package step opens after “გაგრძელება” — watch for it, then pick the package + days
  function promoSS(p) {
    var done = false, tries = 0;
    var tm = setInterval(async function () {
      if (done || ++tries > 600) { clearInterval(tm); return; }
      var h = leaves().find(function (e) { return txt(e) === 'აირჩიე სტატუსი'; });
      if (!h) return;
      done = true; clearInterval(tm);
      var name = {vip: 'VIP', vipplus: 'VIP+', supervip: 'SUPER VIP'}[p.tier];
      var card = Array.prototype.filter.call(document.querySelectorAll('label,div'), function (e) { return e.offsetParent && (e.innerText || '').trim().split('\n')[0].trim() === name; })
        .sort(function (a, b) { return a.innerText.length - b.innerText.length; })[0];
      if (!card) { note(false, 'SS paid: ' + name + ' — choose it yourself'); draw(); return; }
      card.scrollIntoView({block: 'center'}); (card.querySelector('input[type=radio]') || card).click(); await sleep(900);
      var box = card; for (var k = 0; k < 6 && box.parentElement && !/დღე -/.test(box.innerText || ''); k++) box = box.parentElement;
      var chips = Array.prototype.filter.call(box.querySelectorAll('button,div,span,label'), function (e) { return /^\d+ დღე - [\d.]+ ₾$/.test(txt(e)); });
      var best = null;
      chips.forEach(function (c) { var n = parseInt(txt(c), 10); if (n <= p.days && (!best || n > parseInt(txt(best), 10))) best = c; });
      if (best) { realClick(best); await sleep(500); }
      note(best ? null : false, 'SS paid: ' + name + (best ? ' · ' + txt(best) : ' — choose the days yourself') + ' — check your SS balance; it is charged when you press “განაცხადის განთავსება”');
      window.__kgPromoDone = true;
      draw();
    }, 500);
  }

  // ---------- SS.ge
  async function fillSS(d) {
    var chipNear = function (heading, text) {
      var h = leaves().find(function (e) { return txt(e).replace(/\*$/, '').trim() === heading; });
      if (!h) return false;
      var box = h.parentElement;
      for (var i = 0; i < 6 && box && !optionEl(box, text); i++) box = box.parentElement;
      var el = box && optionEl(box, text);
      if (el) { press(el); }
      return !!el;
    };
    // "you have an unfinished listing" dialog: start a new one
    for (var m0 = 0; m0 < 10; m0++) {
      var nb = Array.prototype.find.call(document.querySelectorAll('button'), function (b) { return txt(b) === 'დაამატე ახალი განცხადება'; });
      if (nb) { nb.click(); await sleep(1500); break; }
      await sleep(300);
    }
    var ssType = {flat: 'ბინა', house: 'კერძო სახლი', land: 'მიწის ნაკვეთი', commercial: 'კომერციული', hotel: 'სასტუმრო'}[d.type] || 'ბინა';
    var ssDeal = {sale: 'იყიდება', rent: 'ქირავდება', daily: 'ქირავდება დღიურად'}[d.deal] || 'იყიდება';
    note(chipNear('აირჩიეთ უძრავი ქონების ტიპი', ssType), 'Property type: ' + ssType);
    await sleep(700);
    note(chipNear('აირჩიეთ გარიგების ტიპი', ssDeal), 'Deal: ' + ssDeal);
    for (var w = 0; w < 30 && !document.querySelector('input[name=totalArea]'); w++) await sleep(300);
    if (!document.querySelector('input[name=totalArea]')) { note(false, 'The SS form did not open — choose type and deal, then press the bookmark again'); return; }
    // photos first (top of the form)
    var finput = document.querySelectorAll('input[type=file]')[0];
    if (finput && d.photos.length) {
      note(null, 'Uploading ' + d.photos.length + ' photos…');
      var files = await photosToFiles(d.photos.slice(0, 16));
      putFiles(finput, files); window.__kgPhotoCount = files.length;
      log.pop(); note(files.length > 0, 'Photos: ' + files.length);
    } else note(false, 'Photos: none on keygroup.ge — add at least one');
    // street (city is preselected on SS: Tbilisi)
    var sti = document.querySelector('input[id^=react-select-3-input]') || document.querySelectorAll('input[id^=react-select]')[1];
    if (sti && d.street) {
      await typeInto(sti, d.street.split(' ')[0]);
      await sleep(1600);
      var opts = Array.prototype.slice.call(document.querySelectorAll('[id*=-option-]'));
      var o = opts.find(function (x) { return d.district_ka && txt(x).indexOf(d.district_ka) >= 0; }) || opts[0];
      if (o) { o.dispatchEvent(new MouseEvent('mousedown', {bubbles: true})); o.click(); }
      note(!!o, 'Street: ' + (o ? txt(o).replace(/\n/g, ', ') : d.street + ' — choose it yourself'));
    }
    var hn = document.querySelector('input[name=house-number]'); if (hn && d.number) { val(hn, d.number); note(true, 'Number: ' + d.number); }
    if (d.rooms) note(chipNear('ოთახები', d.rooms > 8 ? '8+' : String(d.rooms)), 'Rooms: ' + d.rooms);
    var bedN = d.bedrooms || (d.type === 'flat' || d.type === 'house' ? Math.max(1, (d.rooms || 2) - 1) : 0);   // SS requires bedrooms for flats / houses
    if (bedN) {
      // SS shows the bedroom choices only after the rooms are chosen (and only up to the room count) — wait for them
      var bedOk = false, bedTxt = String(bedN);
      for (var bw = 0; bw < 12 && !bedOk; bw++) {
        await sleep(400);
        var bh = leaves().find(function (e) { return /^საძინებ/.test(txt(e).replace(/\*$/, '')); });
        var sec = bh && bh.parentElement && bh.parentElement.parentElement;
        var opts = sec ? Array.prototype.filter.call(sec.querySelectorAll('p,span,div,button,label'), function (e) { return e.childElementCount === 0 && /^\d\+?$/.test(txt(e)); }) : [];
        if (opts.length) {
          var pick = opts.find(function (e) { return txt(e) === bedTxt; }) || opts[Math.min(opts.length, bedN) - 1];
          press(pick.parentElement || pick); bedOk = true; bedTxt = txt(pick);
        }
      }
      note(bedOk, 'Bedrooms: ' + bedTxt + (d.bedrooms ? '' : ' (from rooms — check)'));
    }
    if (d.area) { val(document.querySelector('input[name=totalArea]'), d.area); note(true, 'Area: ' + d.area + ' m²'); }
    if (d.floor) val(document.querySelector('input[name=floor]'), d.floor);
    if (d.total_floors) val(document.querySelector('input[name=floors]'), d.total_floors);
    note(!!d.floor, 'Floor: ' + (d.floor || '—') + ' / ' + (d.total_floors || '—'));
    if (d.auto && d.auto.building) note(chipNear('სტატუსი', d.auto.building), 'Status: ' + d.auto.building);
    else note(chipNear('სტატუსი', 'ძველი აშენებული') ? null : false, 'Status: “old building” — change it if the building is new');
    if (d.auto && d.auto.condition_ss) note(chipNear('მდგომარეობა', d.auto.condition_ss), 'Condition: ' + d.auto.condition_ss);
    else note(false, 'Condition: choose it yourself');
    var ta = document.querySelector('textarea');
    if (ta && (d.desc_ka || d.desc_en)) { val(ta, (d.desc_ka || d.desc_en).slice(0, 3000)); note(true, 'Description (GE)'); }
    // price: SS keeps ₾ in the input; for $ prices switch the currency first
    var pinput = document.querySelector('input[type=number]');
    if (pinput) {
      if (d.currency !== 'GEL') {
        var usd = leaves().find(function (e) { return txt(e) === '$' && e.closest('label'); });
        if (usd) usd.closest('label').click();
        await sleep(400);
        pinput = Array.prototype.slice.call(document.querySelectorAll('input[type=number]')).pop() || pinput;
      }
      val(pinput, Math.round(d.price));
      note(null, 'Price: ' + Math.round(d.price) + ' ' + (d.currency === 'GEL' ? '₾' : '$') + ' — check the currency');
    }
    if (d.promo) { promoSS(d.promo); note(null, 'Paid: ' + TIER[d.promo.tier] + ' — it will be selected on the next step (after “გაგრძელება”)'); }
  }

  // ---------- after the person presses Publish: tell keygroup.ge the MyHome / SS id (so the admin sees where each listing is live)
  var ACC = '';
  // the exact reason MyHome / SS gave when it refused the listing (any JSON shape), short and readable
  function failReason(status, text) {
    var out = [];
    function walk(v, key, depth) {
      if (out.length > 8 || depth > 4 || v == null) return;
      if (typeof v === 'string' || typeof v === 'number') { var t = String(v).trim(); if (t && !/^(error|false|true)$/i.test(t)) out.push((key && !/^\d+$/.test(key) && !/^(message|messages|msg|error|errors|userMessage|detail|title)$/i.test(key) ? key + ': ' : '') + t); return; }
      if (Array.isArray(v)) { v.forEach(function (x) { walk(x, key, depth + 1); }); return; }
      if (typeof v === 'object') Object.keys(v).forEach(function (k) { if (!/^(code|status|statusCode|result|success|trace|stack|timestamp|path)$/i.test(k)) walk(v[k], k, depth + 1); });
    }
    try { var j = JSON.parse(text); walk(j.errors || j.error || j.message || j.userMessage || j.data || j, '', 0); } catch (e) { if (text && text.length < 300 && !/</.test(text)) out.push(text.trim()); }
    var seenMsg = {}; out = out.filter(function (x) { if (seenMsg[x]) return false; seenMsg[x] = 1; return true; });
    return ('HTTP ' + status + (out.length ? ' — ' + out.join(' · ') : '')).slice(0, 300);
  }

  function watchPublish(code, d) {
    if (window.__kgWatch) return; window.__kgWatch = true;
    window.__kgOnFail = function (u, status, text) {
      var msg = failReason(status, text);
      window.__kgFailed = msg;
      note(false, '<b style="color:#ffb4a8">' + (SITE === 'myhome' ? 'MyHome' : 'SS') + ' did not publish:</b> ' + msg.replace(/</g, '&lt;') +
        '<br><span style="opacity:.75;font-size:12px">Sent to keygroup.ge — the office sees this reason too.</span>');
      draw();
      reportStatus(code, 'failed', msg);
    };
    function onPayPage() { return /checkout/i.test(location.pathname + location.search); }
    async function report(site, extId) {
      // over MyHome's monthly free limit the listing is created unpaid and MyHome opens its payment page: the agent pays there, never us
      if (site === 'myhome') { for (var w = 0; w < 10 && !onPayPage(); w++) await sleep(400); }
      if (site === 'myhome' && onPayPage()) {
        window.__kgPay = site;
        note(false, '<b>💳 MyHome free limit used.</b> Choose the payment (balance / card) here and press “გადახდა და ატვირთვა” yourself. ID ' + String(extId).replace(/</g, ''));
        reportStatus(code, 'needs_payment', 'MyHome payment page', extId);
        return;
      }
      window.__kgDone = site;
      var body = JSON.stringify({site: site, ext_id: String(extId), promo: d.promo || null, account: ACC});
      fetch(API + '/api/publish/' + code + '/done', {method: 'POST', body: body, keepalive: true})
        .then(function (r) { return r.json(); })
        .then(function (j) { note(!!j.ok, j.ok ? 'Saved on keygroup.ge: ' + (site === 'myhome' ? 'MyHome' : 'SS') + ' #' + extId : 'Could not save the ' + site + ' id on keygroup.ge'); })
        .catch(function () { note(false, 'Could not reach keygroup.ge to save the ' + site + ' id'); });
    }
    async function myhomeId(uuid) {      // the success page may show the new listing's number; otherwise keep the uuid
      for (var i = 0; i < 30; i++) {
        await sleep(500);
        var a = document.querySelector('a[href*="/pr/"]'), m = a && a.href.match(/\/pr\/(\d{5,10})/);
        if (!m) m = (document.body.innerText.match(/ID[:\s]+(\d{6,10})/) || null);
        if (m) return m[1];
      }
      return uuid;
    }
    function seen(url, text) {
      try {
        if (/statements\/create/.test(url)) {
          var j = JSON.parse(text);
          if (j && j.result && j.data && j.data.uuid) myhomeId(j.data.uuid).then(function (id) { report('myhome', id); });
        } else if (/PaidService\/create-application/i.test(url)) {
          var k = JSON.parse(text), id = k && k.application && k.application.success && k.application.realEstateApplicationId;
          if (id) report('ss', id);
        }
      } catch (e) { /* not JSON */ }
    }
    var oo = XMLHttpRequest.prototype.open, os = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function (m, u) { this.__kgu = String(u); return oo.apply(this, arguments); };
    XMLHttpRequest.prototype.send = function () {
      var x = this; this.addEventListener('load', function () {
        var u = x.__kgu || x.responseURL;
        if (x.status < 300) seen(u, String(x.responseText || ''));
        else if (/statements\/create|create-application/i.test(u) && window.__kgOnFail) window.__kgOnFail(u, x.status, String(x.responseText || ''));
      });
      return os.apply(this, arguments);
    };
    var of = window.fetch;
    window.fetch = function (i, o) {
      var u = typeof i === 'string' ? i : (i && i.url) || '';
      return of.apply(this, arguments).then(function (r) {
        if (/statements\/create|create-application/i.test(u)) r.clone().text().then(function (t) { if (r.ok) seen(u, t); else if (window.__kgOnFail) window.__kgOnFail(u, r.status, t); });
        return r;
      });
    };
  }

  // ---------- SS.ge "my listings" page: link the agent's SS listings to their keygroup.ge listings
  async function ssCollect() {
    head = 'KEY GROUP ⇢ SS.ge links';
    var code = (location.hash.match(/kgss=([A-Z0-9]{6,12})/i) || [])[1];
    try { code = code || sessionStorage.getItem('kgss'); } catch (e) { /* storage blocked */ }
    if (!code) code = (prompt('KEY GROUP code (keygroup.ge → My profile → “Link my SS.ge listings”):') || '').trim();
    if (!code) { note(false, 'No code'); return; }
    code = code.toUpperCase();
    try { sessionStorage.setItem('kgss', code); } catch (e) { /* ignore */ }
    for (var w = 0; w < 20 && !document.querySelector('a[href*="/udzravi-qoneba/"]'); w++) await sleep(300);
    var seen = {}, items = [];
    Array.prototype.forEach.call(document.querySelectorAll('a[href]'), function (a) {
      var m = (a.getAttribute('href') || '').match(/-(\d{7,9})(?:[?#]|$)/);
      if (!m || seen[m[1]]) return;
      var full = function (el) { var x = el.innerText || ''; return x.indexOf(m[1]) >= 0 && /[$₾€]/.test(x) && /იყიდება|ქირავდება|გირავდება/.test(x); };
      var card = a; for (var i = 0; i < 14 && card.parentElement && !full(card); i++) card = card.parentElement;
      var t = card.innerText || '', pm = t.replace(/ID:\s*\d+/g, '').match(/([\d][\d,. ]*)\s*([$₾€])/);
      var title = (t.split('\n').map(function (x) { return x.trim(); }).find(function (x) { return /^(იყიდება|ქირავდება|გირავდება)/.test(x); }) || '');
      seen[m[1]] = 1;
      items.push({id: m[1], title: title.slice(0, 200), price: pm ? pm[1].replace(/[ .]/g, '') : '', currency: pm ? pm[2] : '$'});
    });
    if (!items.length) { note(false, 'No listings found on this page — open “ჩემი განცხადებები” (my listings) and press the bookmark again'); return; }
    note(null, 'Found ' + items.length + ' SS listings on this page — matching…');
    var r;
    try { r = await (await fetch(API + '/api/ss-match/' + encodeURIComponent(code), {method: 'POST', body: JSON.stringify({items: items})})).json(); }
    catch (e) { r = {ok: false, error: 'Could not reach keygroup.ge'}; }
    log.pop();
    if (!r.ok) { note(false, r.error || 'Error'); return; }
    note(true, 'Linked: ' + r.matched.length + (r.already ? ' · already linked: ' + r.already : ''));
    if (r.ambiguous.length) note(false, r.ambiguous.length + ' with several possible keygroup.ge listings (not linked): ' + r.ambiguous.slice(0, 5).map(function (x) { return x.ss; }).join(', '));
    if (r.unmatched.length) note(false, r.unmatched.length + ' not on keygroup.ge yet: ' + r.unmatched.slice(0, 5).map(function (x) { return x.ss; }).join(', ') + (r.unmatched.length > 5 ? '…' : ''));
    var more = Array.prototype.some.call(document.querySelectorAll('button,a'), function (b) { return /chevron_right|შემდეგი|next/i.test(txt(b)) && !b.disabled; });
    draw('<div style="margin-top:10px;padding-top:10px;border-top:1px solid rgba(255,255,255,.2)">' + (more ? '<b>More pages?</b> Open the next page and press the bookmark again.' : '<b>Done.</b> The SS badges now show on keygroup.ge.') +
      '<br><span style="opacity:.75;font-size:12px">Unclear ones can be linked by hand: keygroup.ge → listing → “MyHome / SS ⇢” → add the link.</span></div>');
  }

  // ---------- auto mode (KEY GROUP extension): press Publish after filling, report problems to keygroup.ge
  var AUTO = /kgauto=/.test(location.hash);
  function reportStatus(code, state, message, extId) {
    try { fetch(API + '/api/publish/' + code + '/status', {method: 'POST', keepalive: true, body: JSON.stringify({site: SITE, state: state, message: String(message || '').slice(0, 200), ext_id: extId ? String(extId) : ''})}); } catch (e) { /* ignore */ }
  }
  function visibleText(re) { return leaves().filter(function (e) { return e.offsetParent && re.test(txt(e)); }).map(txt).slice(0, 6); }
  // short red texts on the page (how SS marks missing fields), with the field label above when it can find one
  function redTexts() {
    return leaves().filter(function (e) {
      if (!e.offsetParent) return false; var t = txt(e); if (!t || t.length > 80) return false;
      var c = (getComputedStyle(e).color.match(/\d+/g) || []).map(Number);
      return c.length >= 3 && c[0] > 170 && c[1] < 110 && c[2] < 110;
    }).map(function (e) {
      var box = e.parentElement && e.parentElement.parentElement, lab = box && box.querySelector('label, p, span');
      var l = lab && lab !== e ? txt(lab).slice(0, 40) : '';
      return (l && l !== txt(e) ? l + ': ' : '') + txt(e);
    }).slice(0, 6);
  }
  async function waitFor(fn, ms) { for (var t = 0; t < ms; t += 400) { var v = fn(); if (v) return v; await sleep(400); } return null; }
  async function autoSubmit(code) {
    if (SITE === 'myhome') {
      var T = function (id) { return document.querySelector('[data-test-id="' + id + '"]'); };
      var otp = T('add-statement-otp-code'), oi = otp && otp.querySelector('input');
      if (oi && !oi.disabled) {        // phone not confirmed yet on this account: MyHome sends an SMS code to the agent
        var gb = Array.prototype.find.call(document.querySelectorAll('button'), function (b) { return /კოდის მიღება/.test(txt(b)); });
        if (gb) gb.click();
        note(false, 'Enter the SMS code here and press Publish yourself'); reportStatus(code, 'needs_otp', 'SMS code');
        return;
      }
      // over the free limit MyHome shows the price on the button: “გამოქვეყნება (2₾)”
      var pb = T('add-statement-publish') || Array.prototype.find.call((T('add-statement-actions') || document).querySelectorAll('button'), function (b) { return /^გამოქვეყნება/.test(txt(b)); });
      var price = (txt(pb || {}).match(/\(([\d.,]+)\s*₾\)/) || [])[1];
      if (pb && price) note(null, '💳 MyHome charges ' + price + ' ₾ for this listing (free limit used) — you confirm the payment on the next page');
      if (!pb) { reportStatus(code, 'failed', 'Publish button not found'); return; }
      note(null, 'Publishing on MyHome…'); pb.click();
      // MyHome can take a while (8 s+ to create, then the payment page) — wait up to 2 minutes
      var r = await waitFor(function () { return window.__kgDone || window.__kgFailed || window.__kgPay || /checkout/i.test(location.pathname + location.search); }, 120000);
      if (!r) {
        var errs = visibleText(/სავალდებულო|შეცდომ|required/i).filter(function (x) { return !/^\*?\s*სავალდებულო ველი$|არასავალდებულო/.test(x); });
        reportStatus(code, 'failed', errs.join(', ') || 'no answer from MyHome in 2 minutes');
      }
      return;
    }
    // SS: wait for the photos to finish uploading, continue → package step → publish
    var nPh = (window.__kgPhotoCount || 0);
    await sleep(Math.min(30000, 3000 + nPh * 1500));
    await waitFor(function () { return !leaves().some(function (e) { return e.offsetParent && /^\d{1,3}\s?%$/.test(txt(e)); }) && !document.querySelector('[class*="spinner"],[class*="Spinner"],[class*="progress"]:not([value="100"])'); }, 30000);
    var onStep = function () { return leaves().find(function (e) { return e.offsetParent && txt(e) === 'აირჩიე სტატუსი'; }) || Array.prototype.find.call(document.querySelectorAll('button'), function (b) { return b.offsetParent && txt(b) === 'განაცხადის განთავსება'; }); };
    var ssErrors = function () { var m = visibleText(/სავალდებულოა|აუცილებელია/); return m.length ? m : redTexts(); };
    var step = null;
    for (var tryN = 0; tryN < 2 && !step; tryN++) {
      var cb = Array.prototype.find.call(document.querySelectorAll('button'), function (b) { return /^გაგრძელება/.test(txt(b)); });
      if (!cb) { if (!window.__kgDone && !onStep()) reportStatus(code, 'failed', 'Continue button not found'); break; }
      note(null, 'SS: continuing…' + (tryN ? ' (again)' : '')); cb.scrollIntoView({block: 'center'}); press(cb);
      step = await waitFor(onStep, 30000);
      if (!step && ssErrors().length) break;   // SS named missing fields — pressing again will not help
    }
    if (!step) step = onStep();
    if (window.__kgDone) return;   // SS already took it
    if (!step) {
      var miss = ssErrors();
      note(false, 'SS did not continue: ' + (miss.join(', ') || 'no message from SS'));
      reportStatus(code, 'failed', 'form: ' + (miss.join(', ') || 'SS did not open the package step (no message)')); return;
    }
    if (window.__kgPromoWanted) await waitFor(function () { return window.__kgPromoDone; }, 10000);
    await sleep(1200);
    var fb = Array.prototype.find.call(document.querySelectorAll('button'), function (b) { return txt(b) === 'განაცხადის განთავსება'; });
    if (!fb) { reportStatus(code, 'failed', 'Publish button not found'); return; }
    note(null, 'Publishing on SS…'); fb.click();
    var r2 = await waitFor(function () { return window.__kgDone || window.__kgFailed; }, 45000);
    if (!r2) reportStatus(code, 'failed', 'no answer from SS — check the SS window (balance / SMS code?)');
  }

  // ---------- photos only (KEY GROUP extension): the owner sent the original photos later → replace them in the agent's existing ad
  var PHOTOS = /kgphotos=/.test(location.hash);
  function netWatch() {   // remember every save request and its answer
    if (window.__kgNet) return; window.__kgNet = [];
    var oo = XMLHttpRequest.prototype.open, os = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function (m, u) { this.__kgm = String(m || ''); this.__kgu2 = String(u); return oo.apply(this, arguments); };
    XMLHttpRequest.prototype.send = function () {
      var x = this; this.addEventListener('load', function () { window.__kgNet.push({m: x.__kgm, u: x.__kgu2 || x.responseURL, s: x.status, t: String(x.responseText || '').slice(0, 600)}); });
      return os.apply(this, arguments);
    };
    var of = window.fetch;
    window.fetch = function (i, o) {
      var u = typeof i === 'string' ? i : (i && i.url) || '', m = (o && o.method) || (i && i.method) || 'GET';
      return of.apply(this, arguments).then(function (r) { r.clone().text().then(function (t) { window.__kgNet.push({m: m, u: u, s: r.status, t: t.slice(0, 600)}); }).catch(function () {}); return r; });
    };
  }
  function pressAll(el) { ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(function (t) { el.dispatchEvent(new MouseEvent(t, {bubbles: true, cancelable: true})); }); }
  async function photosOnly(code, d) {
    head = 'KEY GROUP ⇢ new photos · #' + d.id;
    netWatch();
    var files = await photosToFiles((d.photos || []).slice(0, 16));
    if (!files.length) { reportStatus(code, 'failed', 'no photos on keygroup.ge'); return; }
    var box, tiles, delBtn, fileInput, saveBtn, saveRe;
    if (SITE === 'myhome') {
      box = function () { return document.querySelector('[data-test-id="add-statement-photo-upload"]'); };
      tiles = function () { return box() ? Array.prototype.slice.call(box().querySelectorAll('[aria-roledescription="sortable"]')) : []; };
      delBtn = function (tile) { var x = Array.prototype.find.call(tile.querySelectorAll('svg'), function (sv) { var p = sv.querySelector('path'); return p && /^M11\.2501 0\.758431/.test(p.getAttribute('d') || ''); }); return x && x.parentElement; };
      fileInput = function () { return box() && box().querySelector('input[type=file]'); };
      saveBtn = function () { return document.querySelector('[data-test-id="add-statement-edit"]') || Array.prototype.find.call(document.querySelectorAll('button'), function (b) { return txt(b) === 'რედაქტირება'; }); };
      saveRe = /statements\/update/i;
    } else {
      box = function () { return document.getElementById('create-app-images'); };
      tiles = function () { return box() ? Array.prototype.filter.call(box().querySelectorAll('button'), function (b) { return txt(b) === 'delete'; }) : []; };
      delBtn = function (b) { return b; };
      fileInput = function () { return (box() && box().querySelector('input[type=file]')) || document.querySelector('input[type=file]'); };
      saveBtn = function () { return Array.prototype.find.call(document.querySelectorAll('button'), function (b) { return txt(b) === 'შენახვა'; }); };
      saveRe = /application|realestate|update|edit/i;
    }
    if (!(await waitFor(function () { return box() && (tiles().length || fileInput()); }, 30000))) {
      reportStatus(code, 'failed', 'edit page did not open (signed in to the agent’s own account?)'); return;
    }
    await sleep(1500);
    var before = tiles().length;
    note(null, 'Removing ' + before + ' old photos…');
    for (var i = 0; i < 60 && tiles().length; i++) {
      var b = delBtn(tiles()[0]);
      if (!b) break;
      pressAll(b);
      await sleep(500);
      var ok = Array.prototype.find.call(document.querySelectorAll('button'), function (x) { return x.offsetParent && /^(წაშლა|დიახ|კი|დადასტურება|Yes|Delete|OK)$/i.test(txt(x)); });
      if (ok) { pressAll(ok); await sleep(500); }
    }
    if (tiles().length) { reportStatus(code, 'failed', 'could not remove the old photos (' + tiles().length + ' left)'); return; }
    note(true, 'Old photos removed: ' + before);
    putFiles(fileInput(), files);
    note(null, 'Uploading ' + files.length + ' new photos…');
    await waitFor(function () { return tiles().length >= files.length; }, 90000);
    await sleep(4000);   // let the site finish its own uploads
    if (tiles().length < files.length) { reportStatus(code, 'failed', 'only ' + tiles().length + ' of ' + files.length + ' photos uploaded'); return; }
    note(true, 'New photos: ' + tiles().length);
    var sb = saveBtn();
    if (!sb) { reportStatus(code, 'failed', 'Save button not found'); return; }
    var n0 = window.__kgNet.length, startUrl = location.href;
    sb.scrollIntoView({block: 'center'}); pressAll(sb);
    note(null, 'Saving…');
    var res = await waitFor(function () {
      var hit = window.__kgNet.slice(n0).find(function (r) { return /^(POST|PUT|PATCH)$/i.test(r.m) && saveRe.test(r.u); });
      if (hit) return hit;
      if (location.href !== startUrl && !/\/edit\//.test(location.pathname)) return {s: 200, moved: true};
      return null;
    }, 60000);
    if (res && res.s < 300) { note(true, 'Saved — photos updated'); reportStatus(code, 'updated', 'photos updated'); }
    else if (res) { var msg = failReason(res.s, res.t); note(false, 'Not saved: ' + msg); reportStatus(code, 'failed', msg); }
    else { var errs = visibleText(/სავალდებულო|შეცდომ|required/i).filter(function (x) { return !/^\*?\s*სავალდებულო ველი$|არასავალდებულო/.test(x); }); reportStatus(code, 'failed', errs.join(', ') || 'no answer after Save'); }
  }

  // ---------- run
  (async function () {
    if (!SITE) { note(false, 'Open MyHome.ge or SS.ge “add listing” first'); return; }
    if (SITE === 'ss' && /\/user\/my-applications/.test(location.pathname)) { try { await ssCollect(); } catch (e) { note(false, 'Stopped: ' + e.message); } window.__kgpubRunning = false; return; }
    var code = (location.hash.match(/kg(?:pub|auto|photos)=([A-Z0-9]{6,12})/i) || [])[1];
    try { code = code || sessionStorage.getItem('kgpub'); } catch (e) { /* storage blocked */ }
    if (AUTO) head = 'KEY GROUP ⇢ auto-publish';
    if (!code) code = (prompt('KEY GROUP publish code (from the MyHome / SS button on keygroup.ge):') || '').trim();
    if (!code) { note(false, 'No code'); return; }
    try { sessionStorage.setItem('kgpub', code.toUpperCase()); } catch (e) { /* ignore */ }
    note(null, 'Loading listing ' + code.toUpperCase() + '…');
    var d;
    try { d = await (await fetch(API + '/api/publish/' + encodeURIComponent(code.toUpperCase()))).json(); } catch (e) { d = {ok: false, error: 'Could not reach keygroup.ge'}; }
    log.pop();
    if (!d.ok) { note(false, d.error || 'Code not valid'); return; }
    head += ' · #' + d.id;
    note(true, 'Listing #' + d.id + ' loaded');
    if (PHOTOS && d.photos_only) {
      try { await photosOnly(code.toUpperCase(), d); } catch (e) { reportStatus(code.toUpperCase(), 'failed', 'script: ' + e.message); }
      draw(); window.__kgpubRunning = false; return;
    }
    watchPublish(code.toUpperCase(), d);
    try { if (SITE === 'myhome') await fillMyHome(d); else await fillSS(d); } catch (e) { note(false, 'Stopped: ' + e.message); }
    // Plan B: every agent publishes from their own MyHome / SS account — warn if the wrong account is signed in
    var acc = '';
    for (var w = 0; w < 20 && !acc; w++) {
      var pi = SITE === 'myhome' ? document.querySelector('[data-test-id="add-statement-contact-phone"] input')
                                 : document.querySelector('input[placeholder="მობილურის ნომერი"]');
      acc = pi ? (pi.value || '').replace(/\D/g, '').slice(-9) : '';
      if (!acc) await sleep(300);
    }
    ACC = acc;
    var want = String(d.contact_phone || '').replace(/\D/g, '').slice(-9);
    if (acc && (d.agent_phones || []).indexOf(acc) >= 0) want = acc;   // the agent's own account (their profile phone) is fine even if the listing shows another number
    if (acc && want && acc !== want) {
      log.unshift([false, '<b style="color:#ffb4a8">Wrong account?</b> You are signed in as <b>' + acc + '</b>, but this listing belongs to <b>' +
        String(d.contact_name || '').replace(/</g, '') + ' (' + want + ')</b>. To keep it under the agent’s own name, sign in to that agent’s ' + (SITE === 'myhome' ? 'MyHome' : 'SS') + ' account and press the bookmark again.']);
      if (AUTO) { reportStatus(code.toUpperCase(), 'failed', 'signed in as ' + acc + ', not the listing agent ' + want); draw(); window.__kgpubRunning = false; return; }
    } else if (acc && want) note(true, 'Account: ' + acc + ' — matches the listing’s agent');
    if (AUTO && d.auto && d.auto.submit) {
      window.__kgPromoWanted = !!d.promo && SITE === 'ss';
      try { await autoSubmit(code.toUpperCase()); } catch (e) { reportStatus(code.toUpperCase(), 'failed', 'script: ' + e.message); }
      draw(); window.__kgpubRunning = false; return;
    }
    draw('<div style="margin-top:10px;padding-top:10px;border-top:1px solid rgba(255,255,255,.2)"><b>Check the form, fix ⚠️ items, then press Publish yourself.</b><br><span style="opacity:.75;font-size:12px">' + (d.promo ? 'Paid package pre-selected — you press Publish / Pay yourself.' : 'Paid options (VIP…) are not selected.') + '</span></div>');
    window.__kgpubRunning = false;
  })();
})();
