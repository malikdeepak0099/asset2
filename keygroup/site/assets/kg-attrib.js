/* KEY GROUP landing-page attribution (no cookies, no personal data).
   Remembers the page a visitor landed on from another site (e.g. Google) for 30 days,
   tags WhatsApp messages with it, and records enquiry-form submissions via the existing kgTrack(). */
(function () {
  if (window.__kgAttrib) return; window.__kgAttrib = 1;
  var K = 'kg_land', DAY = 864e5;
  function get() { try { return JSON.parse(localStorage.getItem(K) || '{}') || {}; } catch (e) { return {}; } }
  try {
    var ref = document.referrer || '', ext = ref && ref.indexOf(location.host) < 0, cur = get();
    if (ext || !cur.p || Date.now() - (cur.t || 0) > 30 * DAY) {
      var host = ''; try { host = ext ? new URL(ref).hostname.replace(/^www\./, '') : ''; } catch (e) {}
      var q = new URLSearchParams(location.search), src = q.get('utm_source') || '';
      if (ext || !cur.p) localStorage.setItem(K, JSON.stringify({p: location.pathname, r: src || host || 'direct', t: Date.now()}));
    }
  } catch (e) {}
  function tag() { var L = get(); return L.p ? ' [ref ' + L.p + ' · ' + (L.r || 'direct') + ']' : ''; }
  document.addEventListener('click', function (e) {
    var a = e.target && e.target.closest && e.target.closest('a[href*="wa.me/"]');
    if (!a) return;
    try {
      var u = new URL(a.href), t = u.searchParams.get('text') || '';
      if (t.indexOf('[ref ') < 0) { u.searchParams.set('text', (t ? t + ' ' : '') + tag()); a.href = u.toString(); }
    } catch (err) {}
  }, true);
  document.addEventListener('submit', function (e) {
    var f = e.target;
    if (!f || !f.querySelector || !f.querySelector('[name=phone],[type=tel]')) return;
    if (location.pathname === '/') return; // homepage already reports lead_submitted itself
    var L = get();
    if (window.kgTrack) window.kgTrack('lead_submitted', {form: f.id || 'form', land: L.p || '', lsrc: L.r || ''});
  }, true);
})();
