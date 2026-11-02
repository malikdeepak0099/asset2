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
    note(chip('add-statement-status', 'ძველი აშენებული') ? null : false, 'Status: “old building” chosen — change it if the building is new');
    note(false, 'Condition: choose it yourself (renovated, white frame…)');
    // location
    var loc = T('add-statement-location-id'), li;
    if (loc && d.district_ka) {
      await typeInto(loc.querySelector('input'), d.district_ka);
      await sleep(1500);
      li = Array.prototype.find.call(loc.querySelectorAll('li'), function (x) { return txt(x).indexOf(d.city_ka || 'თბილისი') >= 0; }) || loc.querySelector('li');
      if (li) li.click();
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
      if (sli) sli.click();
      note(!!sli, 'Street: ' + (sli ? txt(sli).split('\n')[0] : d.street + ' — choose it yourself'));
    }
    var num = T('add-statement-street-number');
    if (num && d.number) { val(num.querySelector('input'), d.number); note(true, 'Number: ' + d.number); }
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
      putFiles(finput, files);
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
    if (d.area) { val(document.querySelector('input[name=totalArea]'), d.area); note(true, 'Area: ' + d.area + ' m²'); }
    if (d.floor) val(document.querySelector('input[name=floor]'), d.floor);
    if (d.total_floors) val(document.querySelector('input[name=floors]'), d.total_floors);
    note(!!d.floor, 'Floor: ' + (d.floor || '—') + ' / ' + (d.total_floors || '—'));
    note(chipNear('სტატუსი', 'ძველი აშენებული') ? null : false, 'Status: “old building” — change it if the building is new');
    note(false, 'Condition: choose it yourself');
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
  }

  // ---------- run
  (async function () {
    if (!SITE) { note(false, 'Open MyHome.ge or SS.ge “add listing” first'); return; }
    var code = (location.hash.match(/kgpub=([A-Z0-9]{6,12})/i) || [])[1];
    try { code = code || sessionStorage.getItem('kgpub'); } catch (e) { /* storage blocked */ }
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
    try { if (SITE === 'myhome') await fillMyHome(d); else await fillSS(d); } catch (e) { note(false, 'Stopped: ' + e.message); }
    draw('<div style="margin-top:10px;padding-top:10px;border-top:1px solid rgba(255,255,255,.2)"><b>Check the form, fix ⚠️ items, then press Publish yourself.</b><br><span style="opacity:.75;font-size:12px">Paid options (VIP…) are not selected.</span></div>');
    window.__kgpubRunning = false;
  })();
})();
