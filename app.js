'use strict';

// ── State ──────────────────────────────────────────────────────────────────
const state = {
  data: null,
  spSearch: '',   // section-page search
};

// IDs already displayed in homepage sections (excluded from news feed)
let shownOnHome = new Set();

// ── Utils ──────────────────────────────────────────────────────────────────
function formatDate(iso) {
  try {
    const d = new Date(iso), now = new Date();
    const diffH = Math.round((now - d) / 36e5);
    if (diffH < 1)  return 'Just now';
    if (diffH < 24) return `${diffH}h ago`;
    if (diffH < 48) return 'Yesterday';
    return d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
  } catch { return ''; }
}
function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function tagsHtml(tags, clickable = true) {
  return tags.map(t =>
    `<span class="tag${clickable ? '' : ''}" data-tag="${esc(t)}">${esc(t)}</span>`
  ).join('');
}
function categoryEmoji(item) {
  const t = (item.tags || []).join(' ').toLowerCase();
  if (t.includes('threat') || t.includes('breach'))     return '🚨';
  if (t.includes('zero trust'))                          return '🛡️';
  if (t.includes('passwordless') || t.includes('auth')) return '🔐';
  if (t.includes('pam'))                                 return '🔒';
  if (t.includes('compliance'))                          return '⚖️';
  if (t.includes('machine identity') || t.includes('ai identity')) return '🤖';
  if (t.includes('vendor'))                              return '🏢';
  return '🔑';
}

// ── Section helpers ────────────────────────────────────────────────────────
const isWhitepaper = i => i.section === 'whitepaper';
const isBreach     = i => i.section === 'breach';
const isVendor     = i => i.section === 'vendor';
const isNews       = i => !isWhitepaper(i) && !isBreach(i);
const wpIcons = ['📄','📊','🔬','📋','📑','🗂️'];

// ── Routing ────────────────────────────────────────────────────────────────
function getRoute() {
  const hash = window.location.hash.replace(/^#\/?/, '');
  if (!hash) return { view: 'home' };
  if (hash.startsWith('section/')) return { view: 'section', value: hash.replace('section/', '') };
  if (hash.startsWith('tag/'))     return { view: 'tag',     value: decodeURIComponent(hash.replace('tag/', '')) };
  return { view: 'home' };
}

function navigate(path) {
  window.location.hash = path;
}

// ── Master render (called on hash change) ──────────────────────────────────
function route() {
  const r = getRoute();
  if (!state.data) return;
  const homePage = document.getElementById('home-page');
  const sectionPage = document.getElementById('section-page');

  if (r.view === 'home') {
    homePage.style.display = '';
    sectionPage.style.display = 'none';
    window.scrollTo(0, 0);
  } else {
    homePage.style.display = 'none';
    sectionPage.style.display = 'block';
    state.spSearch = '';
    document.getElementById('sp-search').value = '';
    renderSectionPage(r);
    window.scrollTo(0, 0);
  }
  // Keep nav active state in sync
  document.querySelectorAll('.nav-link').forEach(b => {
    const matches = r.view === 'section' && b.dataset.section === r.value;
    b.classList.toggle('active', matches || (r.view === 'home' && b.dataset.section === 'all'));
  });
}

// ── Home page rendering ────────────────────────────────────────────────────
function renderHome() {
  shownOnHome = new Set();
  setMastheadDate();
  renderTopicChips();
  renderHeadlines();
  renderWhitepapers();
  renderVendorNews();
  renderNewsFeed();
  renderBreachBand();
}

function setMastheadDate() {
  const el = document.getElementById('masthead-date');
  if (el) el.textContent = new Date().toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric'
  });
}

function renderHeadlines() {
  // Top 5 news items (non-breach, non-whitepaper)
  const items = state.data.items.filter(isNews).slice(0, 5);
  items.forEach(i => shownOnHome.add(i.id));

  if (!items.length) { document.getElementById('lead-story').innerHTML = ''; return; }
  const [lead, ...secondary] = items;
  const leadCat = (lead.tags[0] || lead.category).toUpperCase();

  document.getElementById('lead-story').innerHTML = `
    <div class="lead-image-block"><div class="lead-image-inner">${categoryEmoji(lead)}</div></div>
    <div class="lead-body">
      <div class="lead-category">${esc(leadCat)}</div>
      <div class="lead-title" data-id="${lead.id}">${esc(lead.title)}</div>
      <div class="lead-summary">${esc(lead.summary)}</div>
      <div class="lead-byline">${esc(lead.source)} &nbsp;·&nbsp; ${formatDate(lead.published)}</div>
    </div>`;
  document.querySelector('.lead-title')?.addEventListener('click', () => openModal(lead));

  document.getElementById('secondary-stories').innerHTML = secondary.slice(0,4).map(item => `
    <div class="sec-story" data-id="${item.id}">
      <div class="sec-category">${esc((item.tags[0] || item.category).toUpperCase())}</div>
      <div class="sec-title">${esc(item.title)}</div>
      <div class="sec-summary">${esc(item.summary)}</div>
      <div class="sec-meta">${esc(item.source)} · ${formatDate(item.published)}</div>
    </div>`).join('');

  document.querySelectorAll('.sec-story').forEach(el => {
    el.addEventListener('click', () => {
      const item = state.data.items.find(i => i.id === el.dataset.id);
      if (item) openModal(item);
    });
  });
}

function renderWhitepapers() {
  const items = state.data.items.filter(isWhitepaper).slice(0, 5);
  items.forEach(i => shownOnHome.add(i.id));
  document.getElementById('whitepaper-list').innerHTML = items.length
    ? items.map((item, idx) => `
        <div class="wp-item" data-id="${item.id}">
          <div class="wp-icon-block">${wpIcons[idx % wpIcons.length]}</div>
          <div class="wp-body">
            <div class="wp-source">${esc(item.source)}</div>
            <div class="wp-title">${esc(item.title)}</div>
            <div class="wp-date">${formatDate(item.published)}</div>
          </div>
        </div>`).join('')
    : '<p style="font-size:13px;color:#888;padding:8px 0">No whitepapers found yet.</p>';
  document.querySelectorAll('.wp-item').forEach(el => {
    el.addEventListener('click', () => openModalById(el.dataset.id));
  });
}

function renderVendorNews() {
  const items = state.data.items.filter(i => isVendor(i) && !isWhitepaper(i) && !isBreach(i)).slice(0, 5);
  items.forEach(i => shownOnHome.add(i.id));
  document.getElementById('vendor-list').innerHTML = items.length
    ? items.map(item => `
        <div class="vendor-item" data-id="${item.id}">
          <div class="vendor-source">${esc(item.source)}</div>
          <div class="vendor-title">${esc(item.title)}</div>
          <div class="vendor-summary">${esc(item.summary)}</div>
          <div class="vendor-meta">${formatDate(item.published)}</div>
        </div>`).join('')
    : '<p style="font-size:13px;color:#888;padding:8px 0">No vendor news yet.</p>';
  document.querySelectorAll('.vendor-item').forEach(el => {
    el.addEventListener('click', () => openModalById(el.dataset.id));
  });
}

function renderNewsFeed() {
  const grid = document.getElementById('news-grid');
  // Exclude anything already shown in headlines / whitepapers / vendor sections
  const items = state.data.items.filter(isNews).filter(i => !shownOnHome.has(i.id));
  grid.innerHTML = items.length
    ? items.map(item => newsCardHtml(item)).join('')
    : '<div class="loading-state" style="grid-column:1/-1">No more articles.</div>';
  attachCardClicks(grid);
}

function renderBreachBand() {
  const items = state.data.items.filter(isBreach);
  const list = document.getElementById('breach-list');
  if (!items.length) {
    list.innerHTML = '<div style="padding:24px 16px;font-size:12px;color:#5a3030;text-align:center">No breach reports in the last 7 days.</div>';
    return;
  }
  const sevClass = s => ({ critical:'sev-critical', high:'sev-high', medium:'sev-medium' }[s] || 'sev-medium');
  list.innerHTML = items.map(item => `
    <div class="breach-item" data-id="${item.id}">
      <div class="breach-item-top">
        <div class="breach-title">${esc(item.title)}</div>
        ${item.severity ? `<div class="breach-sev ${sevClass(item.severity)}"><span class="sev-dot"></span>${item.severity.toUpperCase()}</div>` : ''}
      </div>
      <div class="breach-source">${esc(item.source)} · ${formatDate(item.published)}</div>
      <div class="breach-summary">${esc(item.summary)}</div>
      ${item.vector ? `<div class="breach-vector">⚡ ${esc(item.vector)}</div>` : ''}
    </div>`).join('');
  list.querySelectorAll('.breach-item').forEach(el => {
    el.addEventListener('click', () => openModalById(el.dataset.id));
  });
}

function renderTopicChips() {
  const chips = Object.entries(state.data.tag_index)
    .filter(([,ids]) => ids.length > 0)
    .sort((a,b) => b[1].length - a[1].length)
    .slice(0, 14);
  document.getElementById('topic-chips').innerHTML = chips.map(([tag, ids]) => `
    <button class="topic-chip" data-tag="${esc(tag)}">
      ${esc(tag)} <span style="opacity:.6">(${ids.length})</span>
    </button>`).join('');
  document.querySelectorAll('.topic-chip').forEach(b =>
    b.addEventListener('click', () => navigate(`tag/${encodeURIComponent(b.dataset.tag)}`))
  );
  document.getElementById('clear-filters').style.display = 'none';
}

// ── Section page rendering ─────────────────────────────────────────────────
function renderSectionPage(route) {
  const { view, value } = route;
  let items = [], title = '', icon = '';

  if (view === 'section') {
    switch (value) {
      case 'news':
        items = state.data.items.filter(isNews);
        title = 'IAM News'; icon = '📰'; break;
      case 'vendor':
        items = state.data.items.filter(i => isVendor(i) && !isBreach(i));
        title = 'Vendor News'; icon = '🏢'; break;
      case 'whitepaper':
        items = state.data.items.filter(isWhitepaper);
        title = 'Research & Whitepapers'; icon = '📄'; break;
      case 'breach':
        items = state.data.items.filter(isBreach);
        title = 'Breach Tracker'; icon = '🚨'; break;
      default:
        items = state.data.items;
        title = 'All IAM News'; icon = '🔑';
    }
  } else if (view === 'tag') {
    const tagIds = new Set(state.data.tag_index[value] || []);
    items = state.data.items.filter(i => tagIds.has(i.id));
    title = value; icon = '🏷️';
  }

  // Apply section-page search
  if (state.spSearch) {
    const q = state.spSearch.toLowerCase();
    items = items.filter(i =>
      i.title.toLowerCase().includes(q) ||
      i.summary.toLowerCase().includes(q) ||
      i.source.toLowerCase().includes(q)
    );
  }

  document.getElementById('sp-title').textContent = `${icon} ${title}`;
  document.getElementById('sp-count').textContent = `${items.length} article${items.length !== 1 ? 's' : ''}`;

  const grid = document.getElementById('sp-grid');
  const empty = document.getElementById('sp-empty');

  if (!items.length) {
    grid.innerHTML = '';
    empty.style.display = 'block';
    return;
  }
  empty.style.display = 'none';

  // Breach section gets special card treatment
  if (view === 'section' && value === 'breach') {
    const sevClass = s => ({ critical:'sev-critical', high:'sev-high', medium:'sev-medium' }[s] || 'sev-medium');
    const sevColor = s => ({ critical:'#ef4444', high:'#f97316', medium:'#f59e0b' }[s] || '#f59e0b');
    grid.innerHTML = `<div class="sp-breach-bar" style="grid-column:1/-1"></div>` +
      items.map(item => `
        <div class="sp-breach-card" data-id="${item.id}">
          <div class="sp-breach-sev ${sevClass(item.severity)}" style="color:${sevColor(item.severity)}">
            <span class="sev-dot" style="background:${sevColor(item.severity)}"></span>
            ${item.severity ? item.severity.toUpperCase() : 'MEDIUM'}
          </div>
          <div class="sp-breach-title">${esc(item.title)}</div>
          <div class="sp-breach-summary">${esc(item.summary)}</div>
          ${item.vector ? `<div class="sp-breach-vector">⚡ ${esc(item.vector)}</div>` : ''}
          <div class="sp-breach-meta">${esc(item.source)} · ${formatDate(item.published)}</div>
        </div>`).join('');
    grid.querySelectorAll('.sp-breach-card').forEach(el =>
      el.addEventListener('click', () => openModalById(el.dataset.id))
    );
  } else {
    grid.innerHTML = items.map(item => newsCardHtml(item)).join('');
    attachCardClicks(grid);
  }
}

// ── Shared card HTML ───────────────────────────────────────────────────────
function newsCardHtml(item) {
  return `
    <article class="news-card" data-id="${item.id}">
      <div class="card-category">${esc((item.tags[0] || item.category).toUpperCase())}</div>
      <h3 class="card-title">${esc(item.title)}</h3>
      <p class="card-summary">${esc(item.summary)}</p>
      <div class="card-tags">${tagsHtml(item.tags)}</div>
      <div class="card-meta">${esc(item.source)} · ${formatDate(item.published)}</div>
    </article>`;
}

function attachCardClicks(container) {
  container.querySelectorAll('.news-card').forEach(card => {
    card.addEventListener('click', e => {
      if (e.target.classList.contains('tag')) {
        navigate(`tag/${encodeURIComponent(e.target.dataset.tag)}`);
        return;
      }
      openModalById(card.dataset.id);
    });
  });
}

// ── Modal ──────────────────────────────────────────────────────────────────
function openModalById(id) {
  const item = state.data.items.find(i => i.id === id);
  if (item) openModal(item);
}

function openModal(item) {
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-source">${esc(item.source)} · ${esc(item.category)}</div>
    <h2 class="modal-title">${esc(item.title)}</h2>
    <div class="modal-date">${new Date(item.published).toLocaleDateString('en-US',{weekday:'long',year:'numeric',month:'long',day:'numeric'})}</div>
    <p class="modal-summary">${esc(item.summary)}</p>
    <div class="modal-tags">${tagsHtml(item.tags)}</div>
    <a class="modal-link" href="${esc(item.url)}" target="_blank" rel="noopener">Read Full Article ↗</a>`;
  document.getElementById('modal-overlay').style.display = 'flex';
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  document.getElementById('modal-overlay').style.display = 'none';
  document.body.style.overflow = '';
}

// ── Data load ──────────────────────────────────────────────────────────────
async function loadNews() {
  try {
    const res = await fetch('news.json?t=' + Date.now());
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.data = await res.json();
    document.getElementById('article-count').textContent = `${state.data.total} stories`;
    const gen = new Date(state.data.generated);
    const upd = document.getElementById('last-updated');
    if (upd) upd.textContent = `Updated ${gen.toLocaleDateString('en-US',{month:'short',day:'numeric'})} ${gen.toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit'})}`;
    renderHome();
    route(); // apply any hash already in URL on load
  } catch (err) {
    document.getElementById('news-grid').innerHTML =
      `<div class="loading-state" style="grid-column:1/-1;color:#c00">Failed to load news.json</div>`;
    console.error(err);
  }
}

// ── Init ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadNews();

  // Nav section tabs → navigate to section page
  document.querySelectorAll('.nav-link').forEach(btn => {
    btn.addEventListener('click', () => {
      const sec = btn.dataset.section;
      if (sec === 'all') navigate('');
      else navigate(`section/${sec}`);
    });
  });

  // Desktop search (home page only)
  document.getElementById('search').addEventListener('input', e => {
    const q = e.target.value.trim();
    if (q) navigate(`tag/${encodeURIComponent(q)}`);
  });

  // Mobile search (home page only)
  document.getElementById('search-mobile')?.addEventListener('input', e => {
    const q = e.target.value.trim();
    if (q) navigate(`tag/${encodeURIComponent(q)}`);
  });

  // Section page search
  document.getElementById('sp-search').addEventListener('input', e => {
    state.spSearch = e.target.value.trim();
    renderSectionPage(getRoute());
  });

  // Back button
  document.getElementById('back-btn').addEventListener('click', () => {
    history.back();
  });

  // Clear filters (topic bar)
  document.getElementById('clear-filters').addEventListener('click', () => navigate(''));

  // Modal
  document.getElementById('modal-close').addEventListener('click', closeModal);
  document.getElementById('modal-overlay').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeModal();
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

  // Router
  window.addEventListener('hashchange', route);
});
