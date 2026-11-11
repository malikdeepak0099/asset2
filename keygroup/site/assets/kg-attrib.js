/* KEY GROUP landing-page attribution (no cookies, no personal data).
   Remembers the page a visitor landed on from another site (e.g. Google) for 30 days and
   the visitor's market from the browser time zone (GE / IN / AE / other). Tags WhatsApp messages
   with them and records WhatsApp, call and enquiry-form actions via the existing kgTrack(). */
(function () {
  if (window.__kgAttrib) return; window.__kgAttrib = 1;
  var K = 'kg_land', DAY = 864e5;
  function get() { try { return JSON.parse(localStorage.getItem(K) || '{}') || {}; } catch (e) { return {}; } }
  function market() {
    var tz = ''; try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || ''; } catch (e) {}
    if (tz === 'Asia/Tbilisi') return 'GE';
    if (tz === 'Asia/Kolkata' || tz === 'Asia/Calcutta') return 'IN';
    if (tz === 'Asia/Dubai') return 'AE';
    return tz ? 'other:' + tz.split('/')[0] : 'unknown';
  }
  try {
    var ref = document.referrer || '', ext = ref && ref.indexOf(location.host) < 0, cur = get();
    if (ext || !cur.p || Date.now() - (cur.t || 0) > 30 * DAY) {
      var host = ''; try { host = ext ? new URL(ref).hostname.replace(/^www\./, '') : ''; } catch (e) {}
      var q = new URLSearchParams(location.search), src = q.get('utm_source') || '';
      if (ext || !cur.p) localStorage.setItem(K, JSON.stringify({p: location.pathname, r: src || host || 'direct', t: Date.now(), m: market()}));
    }
  } catch (e) {}
  function props(extra) {
    var L = get(), o = {via: 'attrib', land: L.p || location.pathname, lsrc: L.r || 'direct', mkt: L.m || market()};
    for (var k in extra) o[k] = extra[k];
    return o;
  }
  document.addEventListener('click', function (e) {
    var a = e.target && e.target.closest && e.target.closest('a[href]');
    if (!a) return;
    var h = a.getAttribute('href') || '';
    if (h.indexOf('wa.me/') >= 0) {
      try {
        var L = get(), u = new URL(a.href), t = u.searchParams.get('text') || '';
        if (t.indexOf('[ref ') < 0) {
          u.searchParams.set('text', (t ? t + ' ' : '') + '[ref ' + (L.p || location.pathname) + ' · ' + (L.r || 'direct') + ' · ' + (L.m || market()) + ']');
          a.href = u.toString();
        }
      } catch (err) {}
      if (window.kgTrack) window.kgTrack('whatsapp_click', props({}));
    } else if (h.indexOf('tel:') === 0) {
      if (window.kgTrack) window.kgTrack('call_click', props({}));
    }
  }, true);
  document.addEventListener('submit', function (e) {
    var f = e.target;
    if (!f || !f.querySelector || !f.querySelector('[name=phone],[type=tel]')) return;
    if (location.pathname === '/') return; // homepage already reports lead_submitted itself
    if (window.kgTrack) window.kgTrack('lead_submitted', props({form: f.id || 'form'}));
  }, true);
})();
