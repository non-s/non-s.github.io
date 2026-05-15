/* GlobalBR News — main.js
 * Loaded on every page via default.html
 * Covers: back-to-top, infinite scroll, keyboard shortcuts,
 *         reading progress, new-posts polling, freshness labels,
 *         lazy-image fade-in, navbar search autocomplete, toasts.
 */

/* ── Global toast notification (used across the site) ────── */
window.gbToast = function gbToast(msg, opts) {
  opts = opts || {};
  var icon = opts.icon || 'bi-check-circle-fill';
  var cls  = opts.success === false ? '' : 'gb-toast--success';
  var existing = document.querySelector('.gb-toast');
  if (existing) existing.remove();
  var el = document.createElement('div');
  el.className = 'gb-toast ' + cls;
  el.setAttribute('role', 'status');
  el.setAttribute('aria-live', 'polite');
  el.innerHTML = '<i class="bi ' + icon + '"></i><span>' + msg + '</span>';
  document.body.appendChild(el);
  requestAnimationFrame(function(){ el.classList.add('show'); });
  setTimeout(function(){
    el.classList.remove('show');
    setTimeout(function(){ el.remove(); }, 350);
  }, 2400);
};

/* ── Back-to-top with circular progress ──────────────────── */
(function(){
  var btn  = document.getElementById('back-top');
  var ring = document.getElementById('ring-progress');
  if (!btn || !ring) return;
  var circ = 2 * Math.PI * 15;
  ring.style.strokeDasharray  = circ;
  ring.style.strokeDashoffset = circ;
  window.addEventListener('scroll', function(){
    var doc     = document.documentElement;
    var scrolled = doc.scrollTop || document.body.scrollTop;
    var total    = doc.scrollHeight - doc.clientHeight;
    var pct      = total > 0 ? scrolled / total : 0;
    ring.style.strokeDashoffset = circ * (1 - pct);
    btn.classList.toggle('visible', scrolled > 300);
  }, {passive: true});
  btn.addEventListener('click', function(){
    window.scrollTo({top: 0, behavior: 'smooth'});
  });
})();

/* ── Infinite scroll ──────────────────────────────────────── */
(function(){
  var nextLink = document.querySelector('a[rel="next"], .pagination-wrap .page-chip[href*="page"]');
  var paginationWrap = document.querySelector('.pagination-wrap');
  if (paginationWrap) {
    paginationWrap.querySelectorAll('a.page-chip').forEach(function(chip){
      if (chip.querySelector('.bi-chevron-right')) nextLink = chip;
    });
  }
  if (!nextLink) return;
  var loading = false;
  var grid = document.querySelector('.row.g-3');
  if (!grid) return;
  window.addEventListener('scroll', function(){
    if (loading || !nextLink) return;
    if (window.scrollY + window.innerHeight > document.body.offsetHeight - 600) {
      loading = true;
      var href = nextLink.href;
      fetch(href)
        .then(function(r){ return r.text(); })
        .then(function(html){
          var doc = new DOMParser().parseFromString(html, 'text/html');
          doc.querySelectorAll('.row.g-3 > [class*="col-"]').forEach(function(c){
            grid.appendChild(c.cloneNode(true));
          });
          nextLink = null;
          var newPag = doc.querySelector('.pagination-wrap');
          if (newPag) {
            newPag.querySelectorAll('a.page-chip').forEach(function(chip){
              if (chip.querySelector('.bi-chevron-right')) nextLink = {href: chip.href};
            });
          }
          loading = false;
        })
        .catch(function(){ loading = false; nextLink = null; });
    }
  }, {passive:true});
})();

/* ── Keyboard shortcuts (vi-style: j=next, k=prev) ────────── */
(function(){
  document.addEventListener('keydown', function(e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    var key = e.key;
    if (key === '/') {
      e.preventDefault();
      var search = document.querySelector('.search-input');
      if (search) { search.focus(); search.select(); }
    }
    if (key === 'j') {
      var next = document.querySelector('a[rel="next"], .post-nav-item.next a, .prevnext-next');
      if (next && next.href) window.location.href = next.href;
    }
    if (key === 'k') {
      var prev = document.querySelector('a[rel="prev"], .post-nav-item.prev a, .prevnext-prev');
      if (prev && prev.href) window.location.href = prev.href;
    }
    if (key === 'h') { window.location.href = '/'; }
    if (key === '?') {
      var modal = document.getElementById('kb-shortcuts-modal');
      if (modal) modal.classList.toggle('active');
    }
  });
})();

/* ── Reading progress bar ─────────────────────────────────── */
(function() {
  var bar = document.getElementById('reading-progress');
  if (!bar) return;
  window.addEventListener('scroll', function() {
    var doc = document.documentElement;
    var scrolled = doc.scrollTop || document.body.scrollTop;
    var total = doc.scrollHeight - doc.clientHeight;
    bar.style.width = total > 0 ? (scrolled / total * 100) + '%' : '0%';
  }, { passive: true });
})();

/* ── New posts polling notification ──────────────────────── */
(function(){
  var POLL_INTERVAL = 5 * 60 * 1000;
  var lastCheck = Date.now();
  var notified = false;

  function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, function(c) {
      return { '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c];
    });
  }

  function checkForNewPosts() {
    if (notified || document.hidden) return;
    fetch('/search-index.json?t=' + Date.now(), {cache: 'no-store'})
      .then(function(r){ return r.json(); })
      .then(function(data){
        if (!data || !data.length) return;
        var latest = new Date(data[0].date);
        if (latest.getTime() > lastCheck) {
          showNewPostsBanner(data[0]);
          notified = true;
        }
      }).catch(function(){});
  }

  function showNewPostsBanner(post) {
    var title = escapeHtml((post.title || '').substring(0, 60));
    var url = post.url || '/';
    var safeUrl = url.charAt(0) === '/' ? url : '/';
    var banner = document.createElement('div');
    banner.className = 'new-posts-banner';
    var anchor = document.createElement('a');
    anchor.href = safeUrl;
    anchor.textContent = 'Read →';
    var closeBtn = document.createElement('button');
    closeBtn.setAttribute('aria-label', 'Dismiss notification');
    closeBtn.textContent = '✕';
    closeBtn.addEventListener('click', function(){ banner.remove(); });
    banner.innerHTML = '<i class="bi bi-arrow-up-circle"></i> New article: <strong>' + title + '</strong> ';
    banner.appendChild(anchor);
    banner.appendChild(document.createTextNode(' '));
    banner.appendChild(closeBtn);
    document.body.appendChild(banner);
    setTimeout(function(){ if (banner.parentElement) banner.style.opacity = '0'; }, 10000);
    setTimeout(function(){ if (banner.parentElement) banner.remove(); }, 10500);
  }

  if (!document.body.classList.contains('layout-post')) {
    setInterval(checkForNewPosts, POLL_INTERVAL);
  }
})();

/* ── Freshness indicators ("2h ago") ─────────────────────── */
(function() {
  function timeAgo(iso) {
    var d = new Date(iso), now = new Date();
    var s = Math.floor((now - d) / 1000);
    if (s < 60)  return 'Just now';
    var m = Math.floor(s / 60);
    if (m < 60)  return m + 'm ago';
    var h = Math.floor(m / 60);
    if (h < 24)  return h + 'h ago';
    var day = Math.floor(h / 24);
    if (day < 7) return day + 'd ago';
    return d.toLocaleDateString('en', {month:'short', day:'numeric'});
  }
  document.querySelectorAll('.post-date[data-pubdate]').forEach(function(el) {
    el.textContent = timeAgo(el.dataset.pubdate);
  });
})();

/* ── Lazy image fade-in ───────────────────────────────────── */
document.querySelectorAll('img[loading="lazy"]').forEach(function(img) {
  if (img.complete) img.classList.add('loaded');
  else img.addEventListener('load', function() { img.classList.add('loaded'); });
});

/* ── Navbar search autocomplete ──────────────────────────── */
(function(){
  var searchData = [];
  fetch('/search-index.json')
    .then(function(r){ return r.json(); })
    .then(function(data){ searchData = Array.isArray(data) ? data : []; })
    .catch(function(){});

  var input = document.querySelector('form[action*="search"] .search-input');
  if (!input) return;
  var wrapper = input.closest('form');
  if (!wrapper) return;
  wrapper.style.position = 'relative';

  var dropdown = document.createElement('div');
  dropdown.id = 'nav-autocomplete-dropdown';
  dropdown.setAttribute('role', 'listbox');
  dropdown.style.cssText = 'position:absolute;top:100%;left:0;right:0;background:var(--c-surface);border:1px solid var(--c-border2);border-radius:0 0 var(--r-sm) var(--r-sm);z-index:9999;max-height:300px;overflow-y:auto;display:none;min-width:280px;';
  wrapper.appendChild(dropdown);

  function buildRow(p) {
    var a = document.createElement('a');
    a.href = (typeof p.url === 'string' && p.url.charAt(0) === '/') ? p.url : '/';
    a.setAttribute('role', 'option');
    a.style.cssText = 'display:flex;align-items:center;gap:.75rem;padding:.6rem 1rem;color:var(--c-text);text-decoration:none;border-bottom:1px solid var(--c-border);font-size:.85rem;';
    a.addEventListener('mouseover', function(){ a.style.background = 'var(--c-surface2)'; });
    a.addEventListener('mouseout',  function(){ a.style.background = ''; });
    var titleEl = document.createElement('span');
    titleEl.style.flex = '1';
    titleEl.textContent = p.title || '';
    var catEl = document.createElement('span');
    catEl.style.cssText = 'color:var(--c-muted);font-size:.75rem;';
    catEl.textContent = p.category || '';
    a.appendChild(titleEl);
    a.appendChild(catEl);
    return a;
  }

  input.addEventListener('input', function() {
    var q = this.value.trim().toLowerCase();
    if (q.length < 3) { dropdown.style.display = 'none'; return; }
    var matches = searchData.filter(function(p){
      return p && typeof p.title === 'string' && p.title.toLowerCase().includes(q);
    }).slice(0, 8);
    dropdown.innerHTML = '';
    if (!matches.length) { dropdown.style.display = 'none'; return; }
    matches.forEach(function(p){ dropdown.appendChild(buildRow(p)); });
    dropdown.style.display = 'block';
  });

  document.addEventListener('click', function(e) {
    if (!wrapper.contains(e.target)) dropdown.style.display = 'none';
  });
})();

/* ── Local view tracker + trending widget ─────────────────────
   Maintains a per-device count of which posts the user opens.
   Used to:
     • Populate the "Trending" sidebar widget with the user's own
       most-visited posts (purely client-side, no analytics service).
     • Show a "viewed N times" badge on bookmarked / recent items.
   Stored under `gb-views` as { "/url/": {count, last} }. Capped at 200
   entries via LRU eviction on `last`.
*/
(function(){
  var KEY = 'gb-views';
  var MAX = 200;
  function read() {
    try { return JSON.parse(localStorage.getItem(KEY) || '{}'); }
    catch(_) { return {}; }
  }
  function write(v) {
    try {
      var entries = Object.entries(v);
      if (entries.length > MAX) {
        entries.sort(function(a,b){ return (b[1].last||0) - (a[1].last||0); });
        v = Object.fromEntries(entries.slice(0, MAX));
      }
      localStorage.setItem(KEY, JSON.stringify(v));
    } catch(_) {}
  }
  // Record current page view if it's an article URL.
  if (/\/\w[\w-]*\/\d{4}\/\d{2}\/\d{2}\//.test(window.location.pathname)) {
    var v = read();
    var key = window.location.pathname;
    var e = v[key] || { count: 0 };
    e.count = (e.count || 0) + 1;
    e.last = Date.now();
    v[key] = e;
    write(v);
  }
  // Render "your trending" widget into #gb-trending-mine if present.
  window.gbRenderUserTrending = function(targetEl, limit) {
    targetEl = targetEl || document.getElementById('gb-trending-mine');
    if (!targetEl) return;
    var v = read();
    var entries = Object.entries(v);
    if (!entries.length) { targetEl.style.display = 'none'; return; }
    entries.sort(function(a,b){ return (b[1].count||0) - (a[1].count||0); });
    var top = entries.slice(0, limit || 5);
    targetEl.style.display = '';
    targetEl.innerHTML = '';
    top.forEach(function(pair, i){
      var url = pair[0];
      var meta = pair[1] || {};
      var row = document.createElement('a');
      row.href = url;
      row.className = 'wpl-item';
      row.style.textDecoration = 'none';
      // Reconstruct a readable title from the slug.
      var slug = url.replace(/\/$/, '').split('/').pop() || '';
      var title = slug.replace(/-/g, ' ').replace(/\b\w/g, function(c){ return c.toUpperCase(); });
      var num = document.createElement('div');
      num.className = 'wpl-num';
      num.textContent = String(i + 1);
      var info = document.createElement('div');
      info.className = 'wpl-title';
      info.textContent = title;
      var badge = document.createElement('div');
      badge.className = 'wpl-date';
      badge.textContent = (meta.count || 1) + ' view' + ((meta.count || 1) === 1 ? '' : 's');
      info.appendChild(document.createElement('br'));
      info.appendChild(badge);
      row.appendChild(num);
      row.appendChild(info);
      targetEl.appendChild(row);
    });
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function(){ window.gbRenderUserTrending(); });
  } else {
    window.gbRenderUserTrending();
  }
})();
