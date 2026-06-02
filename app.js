'use strict';

const state = {
  data: null,
  activeTags: new Set(),
  activeSection: 'all',
  searchQuery: '',
};

// ── Utils ──────────────────────────────────────────────────────────────────
function formatDate(iso) {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffH = Math.round((now - d) / 36e5);
    if (diffH < 1) return 'Just now';
    if (diffH < 24) return `${diffH}h ago`;
    if (diffH < 48) return 'Yesterday';
    return d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
  } catch { return ''; }
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function tagsHtml(tags) {
  return tags.map(t => `<span class="tag" data-tag="${esc(t)}">${esc(t)}</span>`).join('');
}

// ── Section helpers ────────────────────────────────────────────────────────
const isWhitepaper = i => i.section === 'whitepaper';
const isBreach     = i => i.section === 'breach';
const isVendor     = i => i.section === 'vendor' || i.category === 'Vendor';
const isNews       = i => !isWhitepaper(i) && !isBreach(i);

// Section emoji icons for whitepapers
const wpIcons = ['📄','📊','🔬','📋','📑','🗂️'];

// ── Date in masthead ───────────────────────────────────────────────────────
function setMastheadDate() {
  const el = document.getElementById('masthead-date');
  if (el) el.textContent = new Date().toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric'
  });
}

// ── Render: Priority Headlines ─────────────────────────────────────────────
function renderHeadlines() {
  const items = state.data.items.filter(isNews).slice(0, 5);
  if (!items.length) return;

  const [lead, ...secondary] = items;

  // Lead story
  const leadCat = (lead.tags[0] || lead.category).toUpperCase();
  document.getElementById('lead-story').innerHTML = `
    <div class="lead-image-block">
      <div class="lead-image-inner">${getCategoryEmoji(lead)}</div>
    </div>
    <div class="lead-body">
      <div class="lead-category">${esc(leadCat)}</div>
      <div class="lead-title" data-id="${lead.id}">${esc(lead.title)}</div>
      <div class="lead-summary">${esc(lead.summary)}</div>
      <div class="lead-byline">${esc(lead.source)} &nbsp;·&nbsp; ${formatDate(lead.published)}</div>
    </div>`;

  document.querySelector('.lead-title')?.addEventListener('click', () => openModal(lead));

  // Secondary stories
  const secHtml = secondary.slice(0, 4).map(item => `
    <div class="sec-story" data-id="${item.id}">
      <div class="sec-category">${esc((item.tags[0] || item.category).toUpperCase())}</div>
      <div class="sec-title">${esc(item.title)}</div>
      <div class="sec-summary">${esc(item.summary)}</div>
      <div class="sec-meta">${esc(item.source)} · ${formatDate(item.published)}</div>
    </div>`).join('');
  document.getElementById('secondary-stories').innerHTML = secHtml;

  document.querySelectorAll('.sec-story').forEach(el => {
    el.addEventListener('click', () => {
      const item = state.data.items.find(i => i.id === el.dataset.id);
      if (item) openModal(item);
    });
  });
}

function getCategoryEmoji(item) {
  const tags = (item.tags || []).join(' ').toLowerCase();
  if (tags.includes('threat') || tags.includes('breach')) return '🚨';
  if (tags.includes('zero trust')) return '🛡️';
  if (tags.includes('passwordless') || tags.includes('authentication')) return '🔐';
  if (tags.includes('pam')) return '🔒';
  if (tags.includes('compliance')) return '⚖️';
  if (tags.includes('vendor')) return '🏢';
  return '🔑';
}

// ── Render: Whitepapers ────────────────────────────────────────────────────
function renderWhitepapers() {
  const items = state.data.items.filter(isWhitepaper).slice(0, 5);
  document.getElementById('whitepaper-list').innerHTML = items.length
    ? items.map((item, i) => `
        <div class="wp-item" data-id="${item.id}">
          <div class="wp-icon-block">${wpIcons[i % wpIcons.length]}</div>
          <div class="wp-body">
            <div class="wp-source">${esc(item.source)}</div>
            <div class="wp-title">${esc(item.title)}</div>
            <div class="wp-date">${formatDate(item.published)}</div>
          </div>
        </div>`).join('')
    : '<p style="font-size:13px;color:#888;padding:8px 0">No whitepapers found yet.</p>';

  document.querySelectorAll('.wp-item').forEach(el => {
    el.addEventListener('click', () => {
      const item = state.data.items.find(i => i.id === el.dataset.id);
      if (item) openModal(item);
    });
  });
}

// ── Render: Vendor News ────────────────────────────────────────────────────
function renderVendorNews() {
  const items = state.data.items.filter(i => isVendor(i) && !isWhitepaper(i) && !isBreach(i)).slice(0, 5);
  document.getElementById('vendor-list').innerHTML = items.length
    ? items.map(item => `
        <div class="vendor-item" data-id="${item.id}">
          <div class="vendor-source">${esc(item.source)}</div>
          <div class="vendor-title">${esc(item.title)}</div>
          <div class="vendor-summary">${esc(item.summary)}</div>
          <div class="vendor-meta">${formatDate(item.published)}</div>
        </div>`).join('')
    : '<p style="font-size:13px;color:#888;padding:8px 0">No vendor news found yet.</p>';

  document.querySelectorAll('.vendor-item').forEach(el => {
    el.addEventListener('click', () => {
      const item = state.data.items.find(i => i.id === el.dataset.id);
      if (item) openModal(item);
    });
  });
}

// ── Render: News feed ──────────────────────────────────────────────────────
function getFilteredNews() {
  if (!state.data) return [];
  let items = state.data.items.filter(isNews);

  if (state.activeSection !== 'all') {
    items = state.data.items.filter(i => i.section === state.activeSection);
  }
  if (state.activeTags.size > 0) {
    items = items.filter(i => i.tags.some(t => state.activeTags.has(t)));
  }
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
    <article class="news-card" data-id="${item.id}">
      <div class="card-category">${esc((item.tags[0] || item.category).toUpperCase())}</div>
      <h3 class="card-title">${esc(item.title)}</h3>
      <p class="card-summary">${esc(item.summary)}</p>
      <div class="card-tags">${tagsHtml(item.tags)}</div>
      <div class="card-meta">${esc(item.source)} · ${formatDate(item.published)}</div>
    </article>`).join('');

  grid.querySelectorAll('.news-card').forEach(card => {
    card.addEventListener('click', e => {
      if (e.target.classList.contains('tag')) { toggleTag(e.target.dataset.tag); return; }
      const item = state.data.items.find(i => i.id === card.dataset.id);
      if (item) openModal(item);
    });
  });
}

// ── Render: Breach band ────────────────────────────────────────────────────
function renderBreachBand() {
  const items = state.data.items.filter(isBreach);
  const list = document.getElementById('breach-list');

  if (!items.length) {
    list.innerHTML = '<div style="padding:24px 16px;font-size:12px;color:#5a3030;text-align:center">No breach reports in the last 7 days.</div>';
    return;
  }

  const sevClass = s => ({ critical:'sev-critical', high:'sev-high', medium:'sev-medium' }[s] || 'sev-medium');
  const sevLabel = s => (s || 'medium').toUpperCase();

  list.innerHTML = items.map(item => `
    <div class="breach-item" data-id="${item.id}">
      <div class="breach-item-top">
        <div class="breach-title">${esc(item.title)}</div>
        ${item.severity ? `<div class="breach-sev ${sevClass(item.severity)}"><span class="sev-dot"></span>${sevLabel(item.severity)}</div>` : ''}
      </div>
      <div class="breach-source">${esc(item.source)} · ${formatDate(item.published)}</div>
      <div class="breach-summary">${esc(item.summary)}</div>
      ${item.vector ? `<div class="breach-vector">⚡ ${esc(item.vector)}</div>` : ''}
    </div>`).join('');

  list.querySelectorAll('.breach-item').forEach(el => {
    el.addEventListener('click', () => {
      const item = state.data.items.find(i => i.id === el.dataset.id);
      if (item) openModal(item);
    });
  });
}

// ── Render: Topic chips ────────────────────────────────────────────────────
function renderTopicChips() {
  const { tag_index } = state.data;
  const chips = Object.entries(tag_index)
    .filter(([, ids]) => ids.length > 0)
    .sort((a, b) => b[1].length - a[1].length)
    .slice(0, 14);

  document.getElementById('topic-chips').innerHTML = chips.map(([tag, ids]) => `
    <button class="topic-chip ${state.activeTags.has(tag) ? 'active' : ''}" data-tag="${esc(tag)}">
      ${esc(tag)} <span style="opacity:.6">(${ids.length})</span>
    </button>`).join('');

  document.querySelectorAll('.topic-chip').forEach(b =>
    b.addEventListener('click', () => toggleTag(b.dataset.tag))
  );

  document.getElementById('clear-filters').style.display =
    state.activeTags.size > 0 ? 'inline-flex' : 'none';
}

// ── Render: Active pills in section header ─────────────────────────────────
function renderPills() {
  const container = document.getElementById('active-filters');
  container.innerHTML = [...state.activeTags].map(t => `
    <span class="active-pill">${esc(t)}<button class="pill-remove" data-tag="${esc(t)}">✕</button></span>`
  ).join('');
  container.querySelectorAll('.pill-remove').forEach(b =>
    b.addEventListener('click', () => toggleTag(b.dataset.tag))
  );
}

function renderAll() {
  renderTopicChips();
  renderPills();
  renderHeadlines();
  renderWhitepapers();
  renderVendorNews();
  renderNewsFeed();
  renderBreachBand();
}

// ── Filters ────────────────────────────────────────────────────────────────
function toggleTag(tag) {
  state.activeTags.has(tag) ? state.activeTags.delete(tag) : state.activeTags.add(tag);
  renderTopicChips();
  renderPills();
  renderNewsFeed();
}

function clearFilters() {
  state.activeTags.clear();
  state.activeSection = 'all';
  state.searchQuery = '';
  document.getElementById('search').value = '';
  document.querySelectorAll('.nav-link').forEach(b => b.classList.toggle('active', b.dataset.section === 'all'));
  renderAll();
}

// ── Modal ──────────────────────────────────────────────────────────────────
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

// ── Load data ──────────────────────────────────────────────────────────────
async function loadNews() {
  try {
    const res = await fetch('news.json?t=' + Date.now());
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.data = await res.json();

    document.getElementById('article-count').textContent = `${state.data.total} stories`;
    const gen = new Date(state.data.generated);
    const lastUpdated = document.getElementById('last-updated');
    if (lastUpdated) lastUpdated.textContent = `Updated ${gen.toLocaleDateString('en-US',{month:'short',day:'numeric'})}`;

    renderAll();
  } catch (err) {
    document.getElementById('news-grid').innerHTML = `
      <div class="loading-state" style="grid-column:1/-1;color:#c00">
        Failed to load news.json — run: <code>python scripts/fetch_news.py</code>
      </div>`;
    document.getElementById('breach-list').innerHTML = '';
    console.error(err);
  }
}

// ── Init ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setMastheadDate();
  loadNews();

  document.getElementById('search').addEventListener('input', e => {
    state.searchQuery = e.target.value.trim();
    renderNewsFeed();
  });

  document.getElementById('clear-filters').addEventListener('click', clearFilters);
  document.getElementById('reset-link')?.addEventListener('click', e => { e.preventDefault(); clearFilters(); });

  // Nav section tabs
  document.querySelectorAll('.nav-link').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nav-link').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.activeSection = btn.dataset.section;
      renderNewsFeed();
      document.getElementById('sec-newsfeed').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });

  document.getElementById('modal-close').addEventListener('click', closeModal);
  document.getElementById('modal-overlay').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeModal();
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
});
