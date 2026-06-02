'use strict';

const state = {
  data: null,
  activeTags: new Set(),
  activeCategories: new Set(),
  searchQuery: '',
};

// ── Utilities ──────────────────────────────────────────────────────────────
function formatDate(iso) {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffH = Math.round((now - d) / 36e5);
    if (diffH < 1) return 'Just now';
    if (diffH < 24) return `${diffH}h ago`;
    if (diffH < 48) return 'Yesterday';
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch { return ''; }
}

function escHtml(str) {
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function categoryClass(cat) {
  const map = { 'Vendor':'cat-vendor','Security News':'cat-security','Government':'cat-government','Industry':'cat-industry','Research':'cat-research' };
  return map[cat] || 'cat-industry';
}

function tagsHtml(tags) {
  return tags.map(t => `<span class="tag" data-tag="${escHtml(t)}">${escHtml(t)}</span>`).join('');
}

// ── Section helpers ────────────────────────────────────────────────────────
function isWhitepaper(item) { return item.section === 'whitepaper'; }
function isBreach(item)     { return item.section === 'breach'; }
function isVendor(item)     { return item.section === 'vendor' || item.category === 'Vendor'; }

// ── Filtering (applies only to the main news feed) ─────────────────────────
function getFilteredNews() {
  if (!state.data) return [];
  let items = state.data.items.filter(i => !isBreach(i) && !isWhitepaper(i));

  if (state.activeTags.size > 0)
    items = items.filter(i => i.tags.some(t => state.activeTags.has(t)));
  if (state.activeCategories.size > 0)
    items = items.filter(i => state.activeCategories.has(i.category));
  if (state.searchQuery) {
    const q = state.searchQuery.toLowerCase();
    items = items.filter(i =>
      i.title.toLowerCase().includes(q) ||
      i.summary.toLowerCase().includes(q) ||
      i.source.toLowerCase().includes(q) ||
      i.tags.some(t => t.toLowerCase().includes(q))
    );
  }
  return items;
}

// ── Render: Priority Headlines ─────────────────────────────────────────────
function renderHeadlines() {
  const items = state.data.items
    .filter(i => !isBreach(i) && !isWhitepaper(i))
    .slice(0, 5);

  document.getElementById('headlines-list').innerHTML = items.map((item, idx) => `
    <div class="headline-item" data-id="${item.id}">
      <div class="headline-rank">${idx + 1}</div>
      <div class="headline-body">
        <div class="headline-title">${escHtml(item.title)}</div>
        <div class="headline-meta">
          <span class="headline-source">${escHtml(item.source)}</span>
          <span class="headline-date">· ${formatDate(item.published)}</span>
          <span class="cat-badge ${categoryClass(item.category)}">${escHtml(item.category)}</span>
        </div>
        <div class="headline-summary">${escHtml(item.summary)}</div>
        <div class="headline-tags">${tagsHtml(item.tags)}</div>
      </div>
    </div>`).join('');

  document.getElementById('headlines-list').querySelectorAll('.headline-item').forEach(el => {
    el.addEventListener('click', e => {
      if (e.target.classList.contains('tag')) { toggleTag(e.target.dataset.tag); return; }
      const item = state.data.items.find(i => i.id === el.dataset.id);
      if (item) openModal(item);
    });
  });
}

// ── Render: Whitepapers ────────────────────────────────────────────────────
function renderWhitepapers() {
  const items = state.data.items.filter(isWhitepaper).slice(0, 6);
  const icons = ['📄','📊','🔬','📋','📑','🗂️'];
  document.getElementById('whitepaper-list').innerHTML = items.length
    ? items.map((item, i) => `
        <div class="whitepaper-card" data-id="${item.id}">
          <div class="wp-icon">${icons[i % icons.length]}</div>
          <div class="wp-body">
            <div class="wp-title">${escHtml(item.title)}</div>
            <div class="wp-meta">${escHtml(item.source)} · ${formatDate(item.published)}</div>
          </div>
        </div>`).join('')
    : '<p style="font-size:12px;color:var(--text-dim);padding:8px 0">No whitepapers found yet.</p>';

  document.getElementById('whitepaper-list').querySelectorAll('.whitepaper-card').forEach(el => {
    el.addEventListener('click', () => {
      const item = state.data.items.find(i => i.id === el.dataset.id);
      if (item) openModal(item);
    });
  });
}

// ── Render: Vendor News ────────────────────────────────────────────────────
function renderVendorNews() {
  const items = state.data.items.filter(i => isVendor(i) && !isWhitepaper(i) && !isBreach(i)).slice(0, 6);
  document.getElementById('vendor-grid').innerHTML = items.length
    ? items.map(item => `
        <div class="mini-card" data-id="${item.id}">
          <div class="mini-title">${escHtml(item.title)}</div>
          <div class="mini-meta">
            <span>${escHtml(item.source)}</span>
            <span>·</span>
            <span>${formatDate(item.published)}</span>
          </div>
        </div>`).join('')
    : '<p style="font-size:12px;color:var(--text-dim);padding:8px 0">No vendor news found yet.</p>';

  document.getElementById('vendor-grid').querySelectorAll('.mini-card').forEach(el => {
    el.addEventListener('click', () => {
      const item = state.data.items.find(i => i.id === el.dataset.id);
      if (item) openModal(item);
    });
  });
}

// ── Render: News Feed ──────────────────────────────────────────────────────
function renderNewsFeed() {
  const grid = document.getElementById('news-grid');
  const noResults = document.getElementById('no-results');
  const items = getFilteredNews();

  if (!items.length) {
    grid.innerHTML = '';
    noResults.style.display = 'block';
    return;
  }
  noResults.style.display = 'none';
  grid.innerHTML = items.map(item => `
    <article class="card" data-id="${item.id}">
      <div class="card-meta">
        <span class="card-source">${escHtml(item.source)}</span>
        <span class="card-date">${formatDate(item.published)}</span>
      </div>
      <h2 class="card-title">${escHtml(item.title)}</h2>
      <p class="card-summary">${escHtml(item.summary)}</p>
      <div class="card-tags">${tagsHtml(item.tags)}</div>
    </article>`).join('');

  grid.querySelectorAll('.card').forEach(card => {
    card.addEventListener('click', e => {
      if (e.target.classList.contains('tag')) { toggleTag(e.target.dataset.tag); return; }
      const item = state.data.items.find(i => i.id === card.dataset.id);
      if (item) openModal(item);
    });
  });
}

// ── Render: Breach Band ────────────────────────────────────────────────────
function renderBreachBand() {
  const items = state.data.items.filter(isBreach);
  const list = document.getElementById('breach-list');

  if (!items.length) {
    list.innerHTML = '<div class="breach-empty">No breach reports in the last 7 days.</div>';
    return;
  }

  const sevClass = s => ({ critical:'sev-critical', high:'sev-high', medium:'sev-medium' }[s] || 'sev-medium');

  list.innerHTML = items.map(item => `
    <div class="breach-card" data-id="${item.id}">
      <div class="breach-card-header">
        <div class="breach-card-title">${escHtml(item.title)}</div>
        <div class="breach-card-date">${formatDate(item.published)}</div>
      </div>
      <div class="breach-card-source">${escHtml(item.source)}</div>
      <div class="breach-card-summary">${escHtml(item.summary)}</div>
      <div style="margin-top:7px;display:flex;gap:5px;flex-wrap:wrap">
        ${item.vector ? `<span class="breach-vector">⚡ ${escHtml(item.vector)}</span>` : ''}
        ${item.severity ? `<span class="breach-vector"><span class="breach-severity ${sevClass(item.severity)}"></span>${item.severity.toUpperCase()}</span>` : ''}
      </div>
    </div>`).join('');

  list.querySelectorAll('.breach-card').forEach(card => {
    card.addEventListener('click', () => {
      const item = state.data.items.find(i => i.id === card.dataset.id);
      if (item) openModal(item);
    });
  });
}

// ── Render: Sidebar ────────────────────────────────────────────────────────
function renderSidebar() {
  const { tag_index, category_index } = state.data;

  const tagEl = document.getElementById('tag-filters');
  tagEl.innerHTML = Object.entries(tag_index)
    .filter(([,ids]) => ids.length > 0)
    .sort((a,b) => b[1].length - a[1].length)
    .map(([tag, ids]) => `
      <button class="filter-chip ${state.activeTags.has(tag)?'active':''}" data-tag="${escHtml(tag)}">
        <span>${escHtml(tag)}</span>
        <span class="chip-count">${ids.length}</span>
      </button>`).join('');
  tagEl.querySelectorAll('.filter-chip').forEach(b => b.addEventListener('click', () => toggleTag(b.dataset.tag)));

  const catEl = document.getElementById('category-filters');
  catEl.innerHTML = Object.entries(category_index)
    .map(([cat, ids]) => `
      <button class="filter-chip ${state.activeCategories.has(cat)?'active':''}" data-cat="${escHtml(cat)}">
        <span>${escHtml(cat)}</span>
        <span class="chip-count">${ids.length}</span>
      </button>`).join('');
  catEl.querySelectorAll('.filter-chip').forEach(b => b.addEventListener('click', () => toggleCategory(b.dataset.cat)));
}

// ── Render: Active filter pills ────────────────────────────────────────────
function renderPills() {
  const container = document.getElementById('active-filters');
  const pills = [];
  state.activeTags.forEach(t => pills.push(
    `<span class="active-filter-pill">${escHtml(t)}<button class="pill-remove" data-tag="${escHtml(t)}">✕</button></span>`));
  state.activeCategories.forEach(c => pills.push(
    `<span class="active-filter-pill">${escHtml(c)}<button class="pill-remove" data-cat="${escHtml(c)}">✕</button></span>`));
  container.innerHTML = pills.join('');
  container.querySelectorAll('.pill-remove').forEach(b => {
    b.addEventListener('click', () => {
      if (b.dataset.tag) toggleTag(b.dataset.tag);
      if (b.dataset.cat) toggleCategory(b.dataset.cat);
    });
  });
}

function renderAll() {
  renderSidebar();
  renderPills();
  renderHeadlines();
  renderWhitepapers();
  renderVendorNews();
  renderNewsFeed();
  renderBreachBand();
}

// ── Filter actions ─────────────────────────────────────────────────────────
function toggleTag(tag) {
  state.activeTags.has(tag) ? state.activeTags.delete(tag) : state.activeTags.add(tag);
  renderSidebar(); renderPills(); renderNewsFeed();
}
function toggleCategory(cat) {
  state.activeCategories.has(cat) ? state.activeCategories.delete(cat) : state.activeCategories.add(cat);
  renderSidebar(); renderPills(); renderNewsFeed();
}
function clearFilters() {
  state.activeTags.clear(); state.activeCategories.clear();
  state.searchQuery = '';
  document.getElementById('search').value = '';
  renderAll();
}

// ── Modal ──────────────────────────────────────────────────────────────────
function openModal(item) {
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-source">${escHtml(item.source)} · ${escHtml(item.category)}</div>
    <h2 class="modal-title">${escHtml(item.title)}</h2>
    <div class="modal-date">${new Date(item.published).toLocaleString('en-US',{weekday:'long',year:'numeric',month:'long',day:'numeric',hour:'2-digit',minute:'2-digit',timeZoneName:'short'})}</div>
    <p class="modal-summary">${escHtml(item.summary)}</p>
    <div class="modal-tags">${tagsHtml(item.tags)}</div>
    <a class="modal-link" href="${escHtml(item.url)}" target="_blank" rel="noopener">Read full article ↗</a>`;
  document.getElementById('modal-overlay').style.display = 'flex';
  document.body.style.overflow = 'hidden';
}
function closeModal() {
  document.getElementById('modal-overlay').style.display = 'none';
  document.body.style.overflow = '';
}

// ── Load data ──────────────────────────────────────────────────────────────
async function loadNews() {
  try {
    const res = await fetch('news.json?t=' + Date.now());
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.data = await res.json();

    document.getElementById('article-count').textContent = `${state.data.total} articles`;
    const gen = new Date(state.data.generated);
    document.getElementById('last-updated').textContent =
      `Updated ${gen.toLocaleDateString('en-US',{month:'short',day:'numeric'})} ${gen.toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit'})}`;

    renderAll();
  } catch (err) {
    document.getElementById('news-grid').innerHTML = `
      <div class="loading-state" style="grid-column:1/-1">
        <p style="color:#f87171">Could not load news.json — run the fetch script first.</p>
        <code style="font-size:11px;color:#5a6478;margin-top:6px">python scripts/fetch_news.py</code>
      </div>`;
    document.getElementById('breach-list').innerHTML = '';
    console.error(err);
  }
}

// ── Init ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadNews();
  document.getElementById('search').addEventListener('input', e => {
    state.searchQuery = e.target.value.trim();
    renderNewsFeed();
  });
  document.getElementById('clear-filters').addEventListener('click', clearFilters);
  document.getElementById('reset-link').addEventListener('click', e => { e.preventDefault(); clearFilters(); });
  document.getElementById('modal-close').addEventListener('click', closeModal);
  document.getElementById('modal-overlay').addEventListener('click', e => { if (e.target === e.currentTarget) closeModal(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
});
