/* GlobalBR News — main.js
 * Loaded on every page via default.html
 * Covers: back-to-top, infinite scroll, keyboard shortcuts,
 *         reading progress, new-posts polling, freshness labels,
 *         lazy-image fade-in, navbar search autocomplete.
 */

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

/* ── Keyboard shortcuts ───────────────────────────────────── */
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
      var next = document.querySelector('.post-nav-item.prev a, a[rel="prev"]');
      if (next) window.location.href = next.href;
    }
    if (key === 'k') {
      var prev = document.querySelector('.post-nav-item.next a, a[rel="next"]');
      if (prev) window.location.href = prev.href;
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

  function checkForNewPosts() {
    if (notified) return;
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
    var banner = document.createElement('div');
    banner.className = 'new-posts-banner';
    banner.innerHTML = '<i class="bi bi-arrow-up-circle"></i> New article: <strong>' +
      (post.title || '').substring(0, 50) + '</strong> <a href="' + (post.url || '/') +
      '">Read &rarr;</a> <button onclick="this.parentElement.remove()">&#x2715;</button>';
    document.body.appendChild(banner);
    setTimeout(function(){ if (banner.parentElement) banner.style.opacity = '0'; }, 10000);
    setTimeout(function(){ if (banner.parentElement) banner.remove(); }, 10500);
  }

  if (!document.body.classList.contains('layout-post')) {
    setTimeout(function poll(){
      checkForNewPosts();
      setTimeout(poll, POLL_INTERVAL);
    }, POLL_INTERVAL);
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
  fetch('/search-index.json').then(function(r){ return r.json(); }).then(function(data){ searchData = data; });

  var input = document.querySelector('form[action*="search"] .search-input');
  if (!input) return;
  var wrapper = input.closest('form');
  if (!wrapper) return;
  wrapper.style.position = 'relative';

  var dropdown = document.createElement('div');
  dropdown.id = 'nav-autocomplete-dropdown';
  dropdown.style.cssText = 'position:absolute;top:100%;left:0;right:0;background:var(--c-surface);border:1px solid var(--c-border2);border-radius:0 0 var(--r-sm) var(--r-sm);z-index:9999;max-height:300px;overflow-y:auto;display:none;min-width:280px;';
  wrapper.appendChild(dropdown);

  input.addEventListener('input', function() {
    var q = this.value.trim().toLowerCase();
    if (q.length < 3) { dropdown.style.display = 'none'; return; }
    var matches = searchData.filter(function(p){
      return p.title.toLowerCase().includes(q);
    }).slice(0, 8);
    if (!matches.length) { dropdown.style.display = 'none'; return; }
    dropdown.innerHTML = matches.map(function(p){
      return '<a href="' + p.url + '" style="display:flex;align-items:center;gap:.75rem;padding:.6rem 1rem;color:var(--c-text);text-decoration:none;border-bottom:1px solid var(--c-border);font-size:.85rem;" onmouseover="this.style.background=\'var(--c-surface2)\'" onmouseout="this.style.background=\'\'">' +
        '<span style="flex:1;">' + p.title + '</span>' +
        '<span style="color:var(--c-muted);font-size:.75rem;">' + (p.category || '') + '</span>' +
        '</a>';
    }).join('');
    dropdown.style.display = 'block';
  });

  document.addEventListener('click', function(e) {
    if (!wrapper.contains(e.target)) dropdown.style.display = 'none';
  });
})();
