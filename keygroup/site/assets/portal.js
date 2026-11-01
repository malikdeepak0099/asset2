/* KEY GROUP portal — shared helpers for /account, /admin, /search and /p pages */
(function () {
  var KG = window.KG = {};
  var LOGO = '<svg class="logo-svg" role="img" aria-label="KEY GROUP Real Estate" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 528 216"><path fill="currentColor" fill-rule="evenodd" d="M281.5 137.0 L278.2 138.2 L275.5 141.0 L274.2 144.5 L274.0 147.8 L275.0 151.5 L277.2 154.0 L281.8 155.8 L284.8 155.8 L288.2 154.8 L288.8 154.2 L288.5 153.0 L280.5 153.0 L278.0 151.0 L276.8 147.8 L277.2 147.0 L289.2 147.0 L289.8 146.5 L289.5 142.8 L288.5 140.2 L286.5 138.2 L283.5 137.0 Z M276.8 144.0 L278.0 141.5 L279.8 139.8 L281.5 139.2 L285.0 140.0 L287.0 143.2 L286.5 145.0 L277.2 145.0 Z M245.8 138.2 L245.5 139.8 L246.0 140.2 L250.0 139.2 L252.8 139.8 L254.0 141.0 L254.8 143.5 L246.2 146.0 L244.0 148.5 L244.2 153.0 L246.0 154.8 L248.5 155.8 L252.2 154.8 L254.5 153.2 L255.5 155.8 L257.5 155.8 L257.8 143.5 L256.5 139.8 L255.0 138.2 L251.8 137.0 L249.8 137.0 Z M254.8 146.8 L254.8 150.2 L253.0 152.5 L249.8 153.5 L247.2 152.2 L246.8 149.5 L248.8 147.0 L252.5 146.0 L254.0 146.0 Z M224.5 137.0 L222.5 137.0 L219.5 138.2 L218.2 139.5 L217.0 142.5 L218.5 145.2 L220.5 146.8 L224.0 148.0 L225.5 149.5 L225.8 151.2 L224.2 153.0 L222.5 153.5 L217.8 152.5 L217.0 153.2 L217.5 154.8 L222.8 155.8 L227.2 153.8 L228.8 151.0 L227.8 147.8 L226.0 146.0 L221.2 144.0 L220.0 142.2 L221.5 139.8 L226.8 140.0 L227.5 139.5 L227.2 138.0 Z M165.2 138.2 L164.8 139.5 L165.5 140.5 L166.5 139.8 L169.2 139.2 L172.2 139.8 L174.0 142.2 L174.0 143.5 L165.8 146.0 L164.0 147.8 L163.0 150.0 L164.0 153.5 L167.8 155.8 L169.2 155.8 L174.0 153.2 L174.8 155.5 L177.0 155.5 L176.8 142.0 L175.5 139.2 L174.0 138.0 L171.2 137.0 L169.2 137.0 Z M173.5 146.0 L174.0 146.8 L174.0 150.5 L172.8 152.2 L169.8 153.5 L167.5 153.0 L166.0 151.2 L166.0 149.5 L166.8 148.2 L168.8 146.8 Z M151.8 137.0 L148.2 138.5 L146.2 140.2 L145.0 142.8 L144.2 147.8 L145.2 151.0 L148.0 154.2 L152.0 155.8 L155.0 155.8 L158.5 154.8 L158.8 153.2 L158.2 152.8 L155.2 153.2 L150.2 152.8 L147.8 150.2 L147.5 147.5 L148.0 147.0 L159.5 147.0 L160.2 146.2 L159.8 142.0 L157.2 138.5 L154.0 137.0 Z M147.5 143.2 L149.5 140.2 L150.8 139.5 L153.5 139.2 L156.5 141.2 L157.2 144.2 L156.5 145.0 L148.0 145.0 Z M235.2 132.2 L233.2 133.2 L233.2 136.5 L231.2 137.0 L230.8 139.0 L233.2 140.2 L233.2 150.8 L234.0 153.5 L237.2 155.8 L239.2 155.8 L240.5 155.2 L240.8 153.5 L240.2 153.0 L237.8 153.0 L236.5 151.5 L236.2 140.5 L237.8 139.5 L240.2 139.8 L241.0 137.8 L240.5 137.0 L237.0 137.0 L236.2 136.2 L236.5 132.5 Z M266.0 132.0 L263.8 133.5 L264.0 136.2 L263.2 137.0 L261.0 137.2 L261.0 139.2 L261.5 139.8 L263.2 139.8 L264.0 140.5 L263.8 150.2 L264.2 153.5 L267.0 155.5 L269.5 155.8 L271.0 154.8 L271.0 153.5 L268.0 153.0 L266.8 151.2 L266.8 140.2 L267.5 139.5 L271.0 139.5 L271.2 137.5 L270.8 137.0 L267.2 137.0 L266.8 136.5 L266.8 132.2 Z M199.2 130.0 L199.0 155.5 L213.0 155.5 L213.2 154.0 L212.5 153.0 L202.8 153.0 L202.2 152.5 L202.0 144.8 L203.0 143.5 L211.5 143.5 L212.0 143.0 L212.0 141.2 L202.8 141.0 L202.0 140.2 L202.2 133.2 L203.2 132.5 L212.5 132.5 L212.8 130.5 L212.2 130.0 Z M125.5 130.5 L125.0 131.2 L125.0 155.5 L127.5 155.8 L128.0 155.2 L127.8 145.5 L128.5 144.8 L133.2 144.8 L136.0 147.0 L136.8 148.5 L138.2 155.0 L139.0 155.8 L141.5 155.8 L141.8 155.0 L140.8 153.8 L139.8 148.0 L136.5 143.8 L136.8 143.0 L139.8 140.8 L140.5 139.2 L140.8 135.8 L140.0 133.5 L137.8 131.2 L134.5 130.2 L129.0 130.0 Z M128.8 132.5 L134.2 132.5 L137.0 134.5 L138.0 136.5 L138.0 138.2 L135.2 141.8 L129.0 142.2 L128.0 141.5 L128.0 133.2 Z M182.8 129.0 L182.2 129.5 L182.2 155.2 L182.8 155.8 L185.2 155.8 L185.8 155.0 L185.8 129.8 L185.2 129.0 Z M10.8 102.5 L11.2 123.5 L41.2 123.5 L41.8 124.0 L14.2 168.0 L14.5 168.8 L16.2 168.2 L36.5 167.5 L63.0 123.8 L64.2 124.2 L66.0 128.0 L66.0 129.0 L71.0 139.5 L72.0 143.0 L73.0 144.2 L83.0 168.5 L84.2 169.8 L95.5 168.8 L103.2 168.8 L103.5 167.8 L84.0 124.5 L84.5 123.5 L300.5 123.5 L301.2 123.0 L301.2 102.2 L300.8 101.8 L11.2 101.8 Z M432.5 91.2 L405.5 111.8 L405.0 202.5 L405.5 203.2 L432.2 203.2 L432.8 202.8 Z M424.5 107.0 L425.2 107.5 L425.2 194.5 L424.5 195.2 L413.2 195.2 L412.5 194.2 L413.0 116.0 Z M300.8 62.2 L297.8 61.0 L277.5 60.8 L277.0 61.2 L277.2 97.8 L281.8 97.5 L281.8 84.2 L282.5 83.5 L296.2 83.5 L301.2 81.8 L302.5 80.2 L303.8 75.8 L303.8 67.5 L302.5 64.0 Z M298.0 66.2 L299.0 68.5 L299.0 75.5 L297.2 78.5 L295.5 79.0 L282.5 79.0 L281.8 78.2 L281.8 66.0 L282.2 65.5 L293.8 65.2 L296.8 65.5 Z M238.2 61.0 L238.2 88.5 L239.0 92.2 L240.2 94.5 L242.2 96.2 L245.8 97.8 L249.2 98.0 L260.2 97.8 L264.5 95.8 L266.8 92.8 L267.8 88.2 L267.8 61.2 L267.2 60.8 L263.2 61.2 L263.2 87.2 L262.8 90.2 L259.8 93.0 L252.2 93.2 L245.8 92.8 L243.8 91.0 L243.0 89.5 L242.8 61.2 L242.2 60.8 Z M165.5 60.8 L165.0 61.2 L165.0 97.5 L169.5 97.5 L169.5 84.2 L170.2 83.5 L184.2 83.5 L185.8 84.0 L187.0 85.2 L187.8 87.2 L187.8 97.2 L188.2 97.8 L192.2 97.8 L192.8 97.2 L192.8 86.8 L191.5 83.2 L189.5 81.5 L191.5 79.2 L192.8 76.0 L192.8 67.5 L191.0 63.5 L189.2 62.0 L186.5 61.0 Z M169.8 65.8 L170.5 65.2 L183.2 65.2 L186.2 66.0 L187.8 68.2 L188.0 73.5 L187.0 77.5 L184.2 79.0 L169.8 78.8 Z M47.0 97.5 L72.8 97.5 L72.8 93.2 L52.0 93.0 L51.5 92.5 L51.5 81.2 L52.0 80.8 L71.8 80.8 L72.5 80.2 L72.5 77.5 L71.8 76.5 L52.2 76.5 L51.5 75.8 L51.5 66.0 L52.0 65.5 L72.2 65.5 L72.8 65.0 L72.8 62.2 L73.5 61.8 L88.0 81.2 L88.0 97.5 L92.5 97.8 L92.8 81.2 L107.5 61.0 L102.5 61.0 L91.5 76.0 L90.2 77.0 L78.5 61.0 L47.5 60.8 L47.0 61.2 Z M13.0 61.0 L12.8 97.2 L13.2 97.8 L16.8 97.8 L17.2 97.2 L17.2 81.2 L18.2 80.5 L19.5 80.5 L36.5 97.5 L42.5 97.8 L42.8 97.2 L24.2 78.8 L24.8 77.2 L40.2 61.0 L34.5 61.0 L19.5 76.2 L18.2 76.2 L17.2 75.5 L17.2 61.2 L16.2 60.8 Z M203.5 62.0 L201.0 64.5 L199.0 71.8 L199.0 86.5 L201.0 93.8 L203.5 96.2 L207.2 97.8 L222.5 97.8 L227.0 95.8 L229.5 92.2 L230.8 87.5 L230.8 70.8 L228.8 64.2 L226.2 62.0 L220.0 60.2 L209.5 60.2 Z M206.5 65.8 L209.5 64.8 L220.5 64.8 L223.2 65.8 L225.0 67.8 L225.8 70.0 L225.8 88.2 L224.8 91.0 L223.0 92.8 L219.5 93.5 L210.2 93.5 L207.0 92.8 L204.8 90.5 L203.8 86.2 L204.0 69.8 L204.8 67.8 Z M130.5 62.0 L128.0 64.2 L126.0 70.5 L126.2 89.2 L128.0 94.0 L130.0 96.0 L134.0 97.8 L149.5 97.8 L153.8 95.8 L155.5 94.0 L156.8 91.2 L157.5 85.5 L157.5 79.2 L143.8 78.8 L142.5 79.5 L142.8 82.8 L143.5 83.2 L152.5 83.5 L152.8 88.2 L151.8 91.2 L150.5 92.5 L147.0 93.5 L137.2 93.5 L134.2 93.0 L131.8 90.8 L131.0 88.5 L131.0 69.8 L131.8 67.5 L133.5 65.8 L136.2 64.8 L147.5 64.8 L150.0 65.5 L151.5 66.8 L152.8 69.5 L153.0 71.8 L157.2 71.8 L157.5 69.8 L156.0 64.5 L153.2 62.0 L147.2 60.2 L136.5 60.2 Z M337.8 24.0 L331.2 31.5 L326.0 41.0 L324.0 46.5 L322.2 56.2 L322.2 157.8 L324.0 167.2 L328.0 177.2 L331.2 182.2 L336.0 188.0 L345.2 195.8 L352.5 199.8 L357.5 201.5 L366.8 203.5 L390.8 203.2 L391.2 122.0 L364.0 142.5 L363.8 180.2 L363.2 180.8 L360.2 180.0 L356.8 178.0 L351.0 173.0 L346.0 165.8 L343.8 159.5 L343.5 56.8 L343.8 54.2 L345.8 48.5 L349.5 42.5 L354.2 37.8 L358.5 34.8 L363.0 32.8 L370.2 31.2 L469.0 31.2 L477.0 33.0 L481.2 35.0 L486.0 38.5 L489.2 41.8 L492.5 46.5 L494.5 50.8 L496.0 56.2 L496.0 157.5 L494.0 164.5 L490.8 170.2 L488.0 173.5 L482.5 178.0 L475.5 181.2 L474.8 180.2 L475.8 60.5 L475.0 60.2 L449.0 79.5 L448.0 202.8 L448.5 203.2 L477.0 202.8 L487.2 199.5 L494.2 195.8 L499.5 191.8 L506.5 184.5 L511.8 176.2 L515.8 166.0 L517.0 155.8 L516.8 54.0 L515.8 47.8 L514.8 46.2 L514.5 44.0 L511.8 37.5 L504.8 27.2 L497.5 20.5 L489.2 15.2 L484.0 13.0 L477.8 11.2 L468.0 10.0 L368.2 10.2 L358.8 12.0 L350.8 15.0 L346.5 17.2 Z M467.2 76.0 L467.8 76.5 L467.5 194.2 L466.8 195.0 L456.2 195.2 L455.8 194.5 L456.5 83.8 L465.5 76.8 Z"/></svg>';
  var ICONS = {
    heart: '<path d="M12 20s-7-4.5-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.5-7 10-7 10z"/>',
    pin: '<path d="M12 21s7-6.2 7-12a7 7 0 0 0-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="9" r="2.5"/>',
    chat: '<path d="M4 20l1.3-3.9A8 8 0 1 1 8 19z"/>',
    phone: '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a1 1 0 0 1-1 1A16 16 0 0 1 4 5a1 1 0 0 1 1-1z"/>',
    check: '<path d="M5 12l4 4 10-10"/>', plus: '<path d="M12 5v14M5 12h14"/>', eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    star: '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/>',
    rocket: '<path d="M5 15c-1.5 1.5-2 5-2 5s3.5-.5 5-2M14 4c3 0 6 3 6 6-2 4-6 7-10 8l-4-4c1-4 4-8 8-10zM15 9h.01"/>',
    flag: '<path d="M5 21V4h11l-2 4 2 4H5"/>', share: '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/>',
    trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>', edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/>', image: '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-8 8"/>'
  };
  KG.icon = function (n, extra) { return '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"' + (extra || '') + '>' + (ICONS[n] || '') + '</svg>'; };
  KG.esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]; }); };
  KG.$ = function (s, r) { return (r || document).querySelector(s); };
  KG.$$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  // ---------- language (English / Georgian)
  KG.lang = 'ka';
  try { KG.lang = localStorage.getItem('kg_lang') === 'en' ? 'en' : (localStorage.getItem('kg_lang') === 'ru' ? 'en' : (localStorage.getItem('kg_lang') || 'ka')); } catch (e) {}
  KG.t = function (en, ka) { return KG.lang === 'ka' ? ka : en; };
  KG.setLang = function (l) { try { localStorage.setItem('kg_lang', l); } catch (e) {} location.reload(); };

  // ---------- API
  KG.api = function (path, opts) {
    opts = opts || {};
    var init = {method: opts.method || 'GET', credentials: 'same-origin', headers: {}};
    if (opts.json !== undefined) { init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(opts.json); }
    if (opts.form) init.body = opts.form;
    return fetch(path, init).then(function (r) {
      return r.json().catch(function () { return {ok: false, error: 'Server error (' + r.status + ')'}; });
    }).catch(function () { return {ok: false, error: KG.t('No connection. Check your internet.', 'კავშირი ვერ დამყარდა.')}; });
  };

  // ---------- header
  KG.header = function (active) {
    var h = document.createElement('header');
    h.className = 'top';
    h.innerHTML = '<div class="wrap"><a href="/" aria-label="KEY GROUP Real Estate">' + LOGO + '</a><nav aria-label="Main">' +
      '<a href="/"' + (active === 'home' ? ' class="on"' : '') + '>' + KG.t('Home', 'მთავარი') + '</a>' +
      '<a href="/search/"' + (active === 'search' ? ' class="on"' : '') + '>' + KG.t('Search', 'ძიება') + '</a>' +
      '<a href="/search/?fav=1"' + (active === 'fav' ? ' class="on"' : '') + '>' + KG.icon('heart') + ' ' + KG.t('Saved', 'შენახული') + '</a>' +
      '<a class="btn b-gold sm" href="/account/">' + KG.icon('plus') + KG.t('Add listing', 'განცხადების დამატება') + '</a>' +
      '<span class="lang"><button type="button" data-l="ka" aria-pressed="' + (KG.lang === 'ka') + '">ქარ</button><button type="button" data-l="en" aria-pressed="' + (KG.lang === 'en') + '">EN</button></span>' +
      '</nav></div>';
    document.body.insertBefore(h, document.body.firstChild);
    KG.$$('.lang button', h).forEach(function (b) { b.onclick = function () { KG.setLang(b.dataset.l); }; });
  };

  // ---------- favourites (saved in this browser, like MyHome's hearts)
  KG.favs = function () { try { return JSON.parse(localStorage.getItem('kg_favs') || '[]'); } catch (e) { return []; } };
  KG.isFav = function (k) { return KG.favs().indexOf(k) >= 0; };
  KG.toggleFav = function (k) {
    var f = KG.favs(), i = f.indexOf(k);
    if (i >= 0) f.splice(i, 1); else f.unshift(k);
    try { localStorage.setItem('kg_favs', JSON.stringify(f.slice(0, 300))); } catch (e) {}
    return i < 0;
  };

  // ---------- labels
  KG.VLABEL = function (lvl) { return {1: KG.t('Contact verified', 'კონტაქტი შემოწმებულია'), 2: KG.t('Verified listing', 'შემოწმებული განცხადება'), 3: KG.t('Inspected', 'ადგილზე შემოწმებული')}[lvl] || ''; };
  KG.track = function (name, props) { if (window.kgTrack) window.kgTrack(name, props); };
  KG.DEAL = function (d) { return {sale: KG.t('For sale', 'იყიდება'), rent: KG.t('For rent', 'ქირავდება'), daily: KG.t('Daily rent', 'დღიური ქირა')}[d] || d; };
  KG.TYPE = function (t) { return {flat: KG.t('Apartment', 'ბინა'), house: KG.t('House', 'სახლი'), commercial: KG.t('Commercial', 'კომერციული'), land: KG.t('Land', 'მიწა'), hotel: KG.t('Hotel', 'სასტუმრო')}[t] || t; };
  KG.money = function (n, cur) { return (cur === 'GEL' ? '₾' : cur === 'EUR' ? '€' : '$') + Math.round(Number(n) || 0).toLocaleString('en-US'); };
  KG.photo = function (name, thumb) { return name ? '/uploads/' + (thumb ? 't_' : '') + name : ''; };
  KG.COL = {rent: ['#7FD3CF', '#1F6F86'], sale: ['#FFB199', '#B5475E'], daily: ['#B9A8FF', '#3C3C8F'], commercial: ['#FFD58A', '#A86312']};

  /* normalised listing: {key, src:'owner'|'crm', id, deal, type, district, address, rooms, area, price, cur, photo, tier, verified, url, title, views} */
  KG.card = function (l) {
    var col = KG.COL[l.type === 'commercial' ? 'commercial' : l.deal] || KG.COL.rent;
    var bg = l.photo ? 'background-image:url(' + KG.esc(l.photo) + ')' : 'background-image:linear-gradient(135deg,' + col[0] + ',' + col[1] + ')';
    var badges = '';
    if (l.tier === 'super') badges += '<span class="pill t-super">' + KG.icon('star') + 'Super VIP</span>';
    else if (l.tier === 'vip') badges += '<span class="pill t-vip">' + KG.icon('star') + 'VIP</span>';
    badges += '<span class="pill" style="background:rgba(8,26,48,.75);color:#fff">' + KG.esc(KG.DEAL(l.deal)) + '</span>';
    if (l.vlevel >= 2) badges += '<span class="pill t-ver">' + KG.icon('check') + KG.VLABEL(l.vlevel) + '</span>';
    else if (l.verified) badges += '<span class="pill t-ver">' + KG.icon('check') + KG.t('Verified', 'შემოწმებული') + '</span>';
    var specs = [];
    if (l.rooms) specs.push(l.rooms + ' ' + KG.t('rooms', 'ოთახი'));
    if (l.area) specs.push(l.area + ' m²');
    if (l.floor) specs.push(KG.t('Floor ', 'სართ. ') + KG.esc(l.floor));
    var ppm = l.area && l.price && l.deal === 'sale' ? KG.money(l.price / l.area, l.cur) + ' / m²' : '';
    var ext = l.src === 'crm' ? ' target="_blank" rel="noopener"' : '';
    return '<article class="lc ' + (l.tier || '') + '"><a href="' + KG.esc(l.url) + '"' + ext + ' class="ph" style="' + bg + '" aria-label="' + KG.esc(l.title || KG.TYPE(l.type)) + '">' +
      '<span class="badges">' + badges + '</span>' + (l.photo ? '' : '<span class="dist">' + KG.esc(l.district || '') + '</span>') + '</a>' +
      '<button class="fav" type="button" data-key="' + KG.esc(l.key) + '" aria-pressed="' + KG.isFav(l.key) + '" aria-label="' + KG.t('Save', 'შენახვა') + '">' + KG.icon('heart') + '</button>' +
      '<a href="' + KG.esc(l.url) + '"' + ext + ' class="bd"><div class="pr">' + KG.money(l.price, l.cur) + (l.deal !== 'sale' ? ' <small>' + (l.deal === 'daily' ? KG.t('/ day', '/ დღე') : KG.t('/ month', '/ თვე')) + '</small>' : '') + '</div>' +
      (ppm ? '<div class="ppm">' + ppm + '</div>' : '') +
      '<div class="tt">' + KG.esc(l.title || (KG.TYPE(l.type) + (l.district ? ' · ' + l.district : ''))) + '</div>' +
      '<div class="muted" style="font-size:13px;display:flex;gap:4px;align-items:center">' + KG.icon('pin') + KG.esc([l.district, l.address].filter(Boolean).join(' · ')) + '</div>' +
      '<div class="sp">' + specs.map(function (s) { return '<span>' + s + '</span>'; }).join('') + '</div>' +
      '<div class="src">' + (l.src === 'crm' ? 'KEY GROUP · MyHome.ge ↗' : KG.t('Owner listing', 'მესაკუთრის განცხადება') + (l.views ? ' · ' + l.views + ' ' + KG.t('views', 'ნახვა') : '')) + '</div></a></article>';
  };
  KG.bindFavs = function (root, onChange) {
    (root || document).addEventListener('click', function (e) {
      var b = e.target.closest && e.target.closest('.fav');
      if (!b) return;
      e.preventDefault();
      b.setAttribute('aria-pressed', KG.toggleFav(b.dataset.key) ? 'true' : 'false');
      if (onChange) onChange();
    });
  };
  KG.fromOwner = function (r) {
    return {key: 'o' + r.id, src: 'owner', id: r.id, deal: r.deal, type: r.type, district: r.district, address: r.address, rooms: r.rooms,
      area: r.area, floor: r.floor ? r.floor + (r.total_floors ? '/' + r.total_floors : '') : '', price: r.price, cur: r.currency,
      photo: KG.photo((r.photos || [])[0], true), tier: r.tier, verified: !!r.verified, vlevel: r.verify_level || 0, lat: r.lat || 0, lon: r.lon || 0, city: r.city, url: '/p/?id=' + r.id, title: r.title, views: r.views,
      created: r.approved || r.created};
  };
  var KA_EN = {'ვაკე': 'Vake', 'საბურთალო': 'Saburtalo', 'დიდუბე': 'Didube', 'ვერა': 'Vera', 'მთაწმინდა': 'Mtatsminda', 'ისანი': 'Isani', 'სამგორი': 'Samgori',
    'გლდანი': 'Gldani', 'ნაძალადევი': 'Nadzaladevi', 'ჩუღურეთი': 'Chugureti', 'კრწანისი': 'Krtsanisi', 'დიღომი': 'Digomi', 'დიღმის მასივი': 'Digomi Massive',
    'დიდი დიღომი': 'Didi Digomi', 'ვარკეთილი': 'Varketili', 'ორთაჭალა': 'Ortachala', 'ლისი': 'Lisi', 'წყნეთი': 'Tskneti', 'ბაგები': 'Bagebi', 'ავლაბარი': 'Avlabari',
    'სოლოლაკი': 'Sololaki', 'ვაზისუბანი': 'Vazisubani', 'მუხიანი': 'Mukhiani', 'ნავთლუღი': 'Navtlughi', 'ბათუმი': 'Batumi', 'ისანი-სამგორი': 'Isani-Samgori'};
  KG.fromCrm = function (r) {
    var d = String(r.d || '').trim(); if (d.charAt(0) === '#') d = '';
    var shown = KG.lang === 'en' ? (KA_EN[d] || (d.toLowerCase() === 'vake' ? 'Vake' : d)) : d;
    var type = r.cat === 'Commercial' ? 'commercial' : r.cat === 'House' ? 'house' : r.cat === 'Land' ? 'land' : 'flat';
    return {key: 'c' + (r.k || r.link), src: 'crm', deal: r.deal === 'Rent' ? 'rent' : 'sale', type: type, district: shown, districtKa: d, address: r.a, rooms: r.rooms,
      area: r.area, floor: r.floor, price: r.price, cur: r.cur || 'USD', photo: '', tier: '', verified: true,
      url: r.link || 'https://wa.me/995577114118', title: '', views: 0, created: 0};
  };

  // ---------- maps (Leaflet + OpenStreetMap, loaded only when needed)
  var CENTERS = {'vake': [41.709, 44.759], 'saburtalo': [41.727, 44.753], 'vera': [41.706, 44.778], 'mtatsminda': [41.695, 44.786], 'sololaki': [41.690, 44.799],
    'old tbilisi': [41.691, 44.807], 'didube': [41.750, 44.780], 'didi digomi': [41.792, 44.752], 'digomi massive': [41.760, 44.770], 'digomi': [41.770, 44.765],
    'chugureti': [41.720, 44.800], 'nadzaladevi': [41.755, 44.790], 'gldani': [41.795, 44.820], 'mukhiani': [41.800, 44.810], 'isani-samgori': [41.695, 44.845],
    'isani': [41.690, 44.830], 'samgori': [41.695, 44.855], 'varketili': [41.700, 44.880], 'krtsanisi': [41.660, 44.820], 'ortachala': [41.680, 44.820],
    'avlabari': [41.693, 44.813], 'lisi': [41.740, 44.730], 'tskneti': [41.693, 44.700], 'bagebi': [41.715, 44.735], 'vazisubani': [41.714, 44.870],
    'navtlughi': [41.685, 44.845], 'batumi': [41.642, 41.633], 'kutaisi': [42.268, 42.695], 'tbilisi': [41.715, 44.827]};
  KG.center = function (district, city) {
    var d = String(district || '').toLowerCase().trim(), en = (KA_EN[String(district || '').trim()] || '').toLowerCase();
    var keys = Object.keys(CENTERS);
    for (var i = 0; i < keys.length; i++) { if ((en && en.indexOf(keys[i]) >= 0) || (d && d.indexOf(keys[i]) >= 0)) return CENTERS[keys[i]]; }
    var c = String(city || '').toLowerCase();
    return CENTERS[c] || null;
  };
  KG.coords = function (l) {   // exact (rounded) for owner listings with a pin, else district centre with a small stable offset
    if (l.lat && l.lon) return [l.lat, l.lon];
    var c = KG.center(l.districtKa || l.district, l.city); if (!c) return null;
    var h = 0, k = String(l.key || l.address || ''); for (var i = 0; i < k.length; i++) h = (h * 31 + k.charCodeAt(i)) | 0;
    return [c[0] + ((h % 100) / 100) * 0.008 - 0.004, c[1] + (((h >> 8) % 100) / 100) * 0.010 - 0.005];
  };
  var leafletP = null;
  KG.leaflet = function () {
    if (window.L && window.L.map) return Promise.resolve(window.L);
    if (leafletP) return leafletP;
    leafletP = new Promise(function (res, rej) {
      var css = document.createElement('link'); css.rel = 'stylesheet'; css.href = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css'; document.head.appendChild(css);
      var js = document.createElement('script'); js.src = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js';
      js.onload = function () { res(window.L); }; js.onerror = rej; document.head.appendChild(js);
    });
    return leafletP;
  };
  KG.baseMap = function (el, center, zoom) {
    var map = window.L.map(el, {scrollWheelZoom: false}).setView(center || CENTERS.tbilisi, zoom || 12);
    window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19, attribution: '&copy; OpenStreetMap'}).addTo(map);
    return map;
  };
  KG.loadAll = function () {
    return Promise.all([
      KG.api('/api/listings?limit=200').then(function (j) { return (j.ok ? j.listings : []).map(KG.fromOwner); }),
      fetch('/listings.json?v=' + Math.floor(Date.now() / 600000)).then(function (r) { return r.ok ? r.json() : {listings: []}; })
        .then(function (j) { return (j.listings || []).filter(function (r) { return r.price > 0; }).map(KG.fromCrm); }).catch(function () { return []; })
    ]).then(function (res) { return res[0].concat(res[1]); });
  };
})();
