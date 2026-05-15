/* GlobalBR News — index.js
 * Loaded only on the homepage via index.html
 * Covers: card link copy, skeleton fade-in, NEW badge,
 *         category/sentiment/period filters, next-update countdown.
 */

/* ── Copy card link (global — called from HTML onclick) ───── */
function copyCardLink(btn) {
  var url = btn.dataset.url;
  navigator.clipboard.writeText(url).then(function(){
    btn.innerHTML = '<i class="bi bi-check2"></i>';
    setTimeout(function(){ btn.innerHTML = '<i class="bi bi-link-45deg"></i>'; }, 2000);
    if (typeof gbToast === 'function') gbToast('Link copied to clipboard', { icon: 'bi-link-45deg' });
  });
}

(function(){

  /* ── Skeleton → posts fade-in ───────────────────────────── */
  var skeleton  = document.getElementById('skeleton-grid');
  var postsGrid = document.getElementById('posts-grid');
  if (skeleton && postsGrid) {
    setTimeout(function(){
      skeleton.style.display  = 'none';
      postsGrid.style.display = '';
      initObserver();
      addBadges();
    }, 400);
  } else {
    initObserver();
    addBadges();
  }

  /* ── IntersectionObserver fade-in ──────────────────────── */
  function initObserver() {
    if (!window.IntersectionObserver) {
      document.querySelectorAll('.news-card').forEach(function(c){ c.classList.add('visible'); });
      return;
    }
    var obs = new IntersectionObserver(function(entries){
      entries.forEach(function(e){
        if (e.isIntersecting) { e.target.classList.add('visible'); obs.unobserve(e.target); }
      });
    }, { threshold: 0.1 });
    document.querySelectorAll('.news-card').forEach(function(c){ obs.observe(c); });
  }

  /* ── NEW badge (posts published in the last 2 hours) ────── */
  function addBadges() {
    document.querySelectorAll('.news-card[data-pubdate]').forEach(function(card){
      var pub = new Date(card.dataset.pubdate);
      if (Date.now() - pub.getTime() < 7200000) {
        var badge = document.createElement('span');
        badge.className = 'badge-new';
        badge.textContent = 'NEW';
        var headline = card.querySelector('.card-headline');
        if (headline) headline.prepend(badge);
      }
    });
  }

  /* ── Category / Sentiment / Period filters ──────────────── */
  var cards      = document.querySelectorAll('#posts-grid > [data-category]');
  var activeCat  = 'all';
  var activeSent = 'all';
  var activePer  = 'all';

  function applyFilters() {
    var now = Date.now();
    var todayStart = new Date(); todayStart.setHours(0, 0, 0, 0);
    var weekStart  = new Date(now - 7 * 24 * 3600 * 1000);
    cards.forEach(function(card){
      var cat  = (card.getAttribute('data-category') || '').toLowerCase();
      var sent = (card.getAttribute('data-sentiment') || '').toLowerCase();
      var pub  = card.getAttribute('data-pubdate') ? new Date(card.getAttribute('data-pubdate')) : null;
      var catOk  = activeCat  === 'all' || cat  === activeCat;
      var sentOk = activeSent === 'all' || sent === activeSent;
      var perOk  = true;
      if (pub && activePer === 'today') perOk = pub >= todayStart;
      if (pub && activePer === 'week')  perOk = pub >= weekStart;
      card.style.display = (catOk && sentOk && perOk) ? '' : 'none';
    });
  }

  function bindFilterBar(selector, attrName, setter) {
    document.querySelectorAll(selector + ' .filter-btn').forEach(function(btn){
      btn.addEventListener('click', function(){
        document.querySelectorAll(selector + ' .filter-btn').forEach(function(b){ b.classList.remove('active'); });
        btn.classList.add('active');
        setter(btn.getAttribute(attrName));
        applyFilters();
      });
    });
  }
  bindFilterBar('#cat-filter-bar',    'data-cat',    function(v){ activeCat  = v; });
  bindFilterBar('#sent-filter-bar',   'data-sent',   function(v){ activeSent = v; });
  bindFilterBar('#period-filter-bar', 'data-period', function(v){ activePer  = v; });

  /* ── Next-update countdown (schedule: 6,10,14,18,22 UTC) ── */
  function updateCountdown() {
    var HOURS_UTC = [6, 10, 14, 18, 22];
    var now = new Date();
    var nowUtcH = now.getUTCHours();
    var nowUtcM = now.getUTCMinutes();
    var nowUtcS = now.getUTCSeconds();
    var nextH = HOURS_UTC.find(function(h){
      return h > nowUtcH || (h === nowUtcH && (nowUtcM > 0 || nowUtcS > 0));
    });
    if (nextH == null) nextH = HOURS_UTC[0];
    var next = new Date(now);
    next.setUTCHours(nextH, 0, 0, 0);
    if (next <= now) next.setUTCDate(next.getUTCDate() + 1);
    var diff = Math.max(0, Math.floor((next - now) / 1000));
    var h = Math.floor(diff / 3600);
    var m = Math.floor((diff % 3600) / 60);
    var s = diff % 60;
    var el = document.getElementById('update-countdown');
    if (el) el.textContent = (h > 0 ? h + 'h ' : '') + m + ':' + (s < 10 ? '0' : '') + s;
  }
  setInterval(updateCountdown, 1000);
  updateCountdown();

})();
