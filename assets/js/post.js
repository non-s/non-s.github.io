/* GlobalBR News — post.js
 * Loaded only on post pages via post.html
 * Covers: TOC, code copy, save-for-later, reader mode, font toggle,
 *         reading position restore, image lightbox, font-size controls,
 *         article feedback, selection share, reading progress bar.
 */

/* ── Table of Contents (sidebar + active section highlight) ─ */
(function(){
  var article   = document.getElementById('post-article');
  var nav       = document.getElementById('toc-nav');
  var container = document.getElementById('toc-container');
  if (!article) return;

  var headings = article.querySelectorAll('h2, h3');
  if (headings.length < 2) return;

  headings.forEach(function(h, i){
    if (!h.id) h.id = 'h-' + i;
  });

  /* Sidebar TOC */
  if (nav && container) {
    var fragment = document.createDocumentFragment();
    headings.forEach(function(h){
      var a = document.createElement('a');
      a.href = '#' + h.id;
      a.textContent = h.textContent;
      a.className = 'toc-link toc-' + h.tagName.toLowerCase();
      a.addEventListener('click', function(e){
        e.preventDefault();
        var target = document.getElementById(h.id);
        if (target) target.scrollIntoView({behavior:'smooth', block:'start'});
      });
      fragment.appendChild(a);
    });
    nav.appendChild(fragment);
    container.style.display = 'block';

    if (window.IntersectionObserver) {
      var tocLinks = nav.querySelectorAll('a');
      var observer = new IntersectionObserver(function(entries){
        entries.forEach(function(e){
          if (e.isIntersecting) {
            tocLinks.forEach(function(l){ l.classList.remove('active'); });
            var active = nav.querySelector('a[href="#' + e.target.id + '"]');
            if (active) active.classList.add('active');
          }
        });
      }, { rootMargin: '-20% 0px -60% 0px' });
      headings.forEach(function(h){ if (h.id) observer.observe(h); });
    }
  }

  /* Inline fallback (used by smaller viewports / no sidebar) */
  var fallback = document.getElementById('toc');
  if (fallback && headings.length >= 3) {
    var titleEl = document.createElement('p');
    titleEl.className = 'toc-title';
    titleEl.textContent = 'Contents';
    var ul = document.createElement('ul');
    headings.forEach(function(h){
      var li = document.createElement('li');
      if (h.tagName !== 'H2') li.className = 'toc-sub';
      var a = document.createElement('a');
      a.href = '#' + h.id;
      a.textContent = h.textContent;
      li.appendChild(a);
      ul.appendChild(li);
    });
    fallback.innerHTML = '';
    fallback.appendChild(titleEl);
    fallback.appendChild(ul);
    fallback.style.display = 'block';
  }
})();

/* ── Code copy button ─────────────────────────────────────── */
(function(){
  document.querySelectorAll('#post-article pre').forEach(function(pre) {
    var btn = document.createElement('button');
    btn.className = 'code-copy-btn';
    btn.textContent = 'Copy';
    btn.addEventListener('click', function() {
      var code = pre.querySelector('code');
      navigator.clipboard.writeText(code ? code.textContent : pre.textContent).then(function() {
        btn.textContent = '✓ Copied';
        setTimeout(function() { btn.textContent = 'Copy'; }, 2000);
      });
    });
    pre.style.position = 'relative';
    pre.appendChild(btn);
  });
})();

/* gbToast is defined in main.js (loaded globally) */

/* ── Save for later (global functions used by HTML onclick) ─ */
function getSaved() { try { return JSON.parse(localStorage.getItem('gb-saved') || '[]'); } catch(e) { return []; } }
function setSaved(arr) { localStorage.setItem('gb-saved', JSON.stringify(arr)); }
function toggleSave(btn) {
  var url = btn.dataset.url;
  var saved = getSaved();
  var idx = saved.findIndex(function(x){ return x.url === url; });
  if (idx >= 0) {
    saved.splice(idx, 1);
    document.getElementById('save-icon').className = 'bi bi-bookmark';
    document.getElementById('save-label').textContent = 'Save';
    if (window.gbToast) gbToast('Removed from Reading List', { icon: 'bi-bookmark-x' });
  } else {
    saved.unshift({ url: url, title: btn.dataset.title, image: btn.dataset.image, date: btn.dataset.date, savedAt: new Date().toISOString() });
    if (saved.length > 50) saved = saved.slice(0, 50);
    document.getElementById('save-icon').className = 'bi bi-bookmark-fill';
    document.getElementById('save-label').textContent = 'Saved';
    if (window.gbToast) gbToast('Saved to Reading List', { icon: 'bi-bookmark-check-fill' });
  }
  setSaved(saved);
}
(function(){
  var btn = document.getElementById('save-article-btn');
  if (!btn) return;
  if (getSaved().some(function(x){ return x.url === btn.dataset.url; })) {
    document.getElementById('save-icon').className = 'bi bi-bookmark-fill';
    document.getElementById('save-label').textContent = 'Saved';
  }
})();

/* ── Reader mode (global — called from HTML onclick) ─────── */
function toggleReaderMode() {
  var body = document.body;
  var btn = document.getElementById('reader-mode-btn');
  var active = body.classList.toggle('reader-mode');
  btn.innerHTML = active ? '<i class="bi bi-book-fill"></i>' : '<i class="bi bi-book"></i>';
  localStorage.setItem('gb-reader', active ? '1' : '');
}
if (localStorage.getItem('gb-reader')) document.body.classList.add('reader-mode');

/* ── Font toggle serif/sans (global — called from HTML onclick) */
function toggleFont() {
  var serif = document.body.classList.toggle('font-serif');
  localStorage.setItem('gb-font', serif ? 'serif' : 'sans');
}
(function(){
  if (localStorage.getItem('gb-font') === 'serif') document.body.classList.add('font-serif');
})();

/* ── Reading position save + restore ─────────────────────── */
(function(){
  var key = 'gb-pos-' + window.location.pathname;
  var article = document.getElementById('post-article');
  if (!article) return;
  var saved = localStorage.getItem(key);
  if (saved && parseInt(saved) > 200) {
    setTimeout(function(){ window.scrollTo(0, parseInt(saved)); }, 500);
  }
  var ticking = false;
  window.addEventListener('scroll', function(){
    if (!ticking) {
      requestAnimationFrame(function(){
        localStorage.setItem(key, window.scrollY);
        ticking = false;
      });
      ticking = true;
    }
  });
  if (saved && parseInt(saved) > 500) {
    var banner = document.createElement('div');
    banner.className = 'continue-reading-banner';
    banner.innerHTML = '<i class="bi bi-bookmark-check"></i> Continue where you left off <button onclick="window.scrollTo(0,' + saved + ');this.parentElement.remove()">Jump &#8595;</button> <button onclick="this.parentElement.remove()">&#x2715;</button>';
    document.body.appendChild(banner);
    setTimeout(function(){ if (banner.parentElement) banner.remove(); }, 5000);
  }
})();

/* Image lightbox is centralised in default.html (`#gbLightbox`).
   Hero images use the .gb-zoomable class, so they participate in the
   same lightbox without needing a parallel implementation here. */

/* ── Font size toggle (global — called from HTML onclick) ─── */
(function(){
  var sizes = [14, 15, 16, 17, 18, 20];
  var article = document.getElementById('post-article');
  if (!article) return;
  var idx = parseInt(localStorage.getItem('gb-font-idx') || '2');
  function apply(i){ article.style.fontSize = sizes[i] + 'px'; localStorage.setItem('gb-font-idx', i); idx = i; }
  apply(idx);
  var up = document.getElementById('fs-up');
  var down = document.getElementById('fs-down');
  if (up) up.addEventListener('click', function(){ if (idx < sizes.length - 1) apply(idx + 1); });
  if (down) down.addEventListener('click', function(){ if (idx > 0) apply(idx - 1); });
})();

/* ── Article feedback (global — called from HTML onclick) ─── */
function gbFeedback(btn, val) {
  var key = 'gb-fb-' + window.location.pathname;
  if (localStorage.getItem(key)) return;
  localStorage.setItem(key, val);
  btn.closest('.article-feedback').querySelectorAll('.feedback-btn').forEach(function(b){ b.disabled = true; });
  btn.closest('.article-feedback').querySelector('.feedback-thanks').style.display = 'block';
}

/* ── Selection share (title read from data-title on article) ─ */
(function(){
  var article = document.getElementById('post-article');
  if (!article) return;
  var pageTitle = article.dataset.title || document.title;
  var btn = document.createElement('button');
  btn.id = 'selection-share';
  btn.innerHTML = '<i class="bi bi-quote"></i> Tweet quote';
  document.body.appendChild(btn);
  document.addEventListener('mouseup', function(){
    var sel = window.getSelection();
    var text = sel ? sel.toString().trim() : '';
    if (text.length > 10 && text.length < 200 && article.contains(sel.anchorNode)) {
      var range = sel.getRangeAt(0).getBoundingClientRect();
      btn.style.display = 'block';
      btn.style.top = (range.bottom + window.scrollY + 8) + 'px';
      btn.style.left = (range.left + range.width / 2 - 60) + 'px';
      btn.onclick = function(){
        var url = encodeURIComponent(window.location.href);
        var quote = encodeURIComponent('"' + text + '" — ' + pageTitle);
        window.open('https://twitter.com/intent/tweet?text=' + quote + '&url=' + url, '_blank');
      };
    } else {
      btn.style.display = 'none';
    }
  });
})();

/* ── Reading progress bar (post-specific) ────────────────── */
(function(){
  var bar = document.getElementById('read-progress');
  if (!bar) return;
  function update() {
    var doc = document.documentElement;
    var scrolled = doc.scrollTop || document.body.scrollTop;
    var total = doc.scrollHeight - doc.clientHeight;
    bar.style.width = total > 0 ? (scrolled / total * 100) + '%' : '0%';
  }
  window.addEventListener('scroll', update, {passive: true});
  update();
})();
