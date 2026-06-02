'use strict';

// ── State ──────────────────────────────────────────────────────────────────
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

function categoryClass(cat) {
  const map = {
    'Vendor': 'cat-vendor',
    'Security News': 'cat-security',
    'Government': 'cat-government',
    'Industry': 'cat-industry',
  };
  return map[cat] || 'cat-industry';
}

function escHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Filtering ──────────────────────────────────────────────────────────────
function getFilteredItems() {
  if (!state.data) return [];
  let items = state.data.items;

  if (state.activeTags.size > 0) {
    items = items.filter(item =>
      item.tags.some(t => state.activeTags.has(t))
    );
  }
  if (state.activeCategories.size > 0) {
    items = items.filter(item => state.activeCategories.has(item.category));
  }
  if (state.searchQuery) {
    const q = state.searchQuery.toLowerCase();
    items = items.filter(item =>
      item.title.toLowerCase().includes(q) ||
      item.summary.toLowerCase().includes(q) ||
      item.source.toLowerCase().includes(q) ||
      item.tags.some(t => t.toLowerCase().includes(q))
    );
  }
  return items;
}

// ── Rendering ──────────────────────────────────────────────────────────────
function renderCard(item) {
  const tagsHtml = item.tags.map(t =>
    `<span class="tag" data-tag="${escHtml(t)}">${escHtml(t)}</span>`
  ).join('');

  return `
    <article class="card" data-id="${item.id}">
      <div class="card-meta">
        <span class="card-source">${escHtml(item.source)}</span>
        <span class="card-date">${formatDate(item.published)}</span>
      </div>
      <h2 class="card-title">${escHtml(item.title)}</h2>
      <p class="card-summary">${escHtml(item.summary)}</p>
      <div class="card-tags">${tagsHtml}</div>
      <div class="card-footer">
        <span class="cat-badge ${categoryClass(item.category)}">${escHtml(item.category)}</span>
        <span class="read-more">Read more →</span>
      </div>
    </article>`;
}

function renderGrid() {
  const grid = document.getElementById('news-grid');
  const noResults = document.getElementById('no-results');
  const items = getFilteredItems();

  if (items.length === 0) {
    grid.innerHTML = '';
    noResults.style.display = 'block';
  } else {
    noResults.style.display = 'none';
    grid.innerHTML = items.map(renderCard).join('');
    // Attach card click listeners
    grid.querySelectorAll('.card').forEach(card => {
      card.addEventListener('click', (e) => {
        // If clicking a tag, filter rather than open modal
        if (e.target.classList.contains('tag')) {
          toggleTag(e.target.dataset.tag);
          return;
        }
        const id = card.dataset.id;
        const item = state.data.items.find(i => i.id === id);
        if (item) openModal(item);
      });
    });
  }
}

function renderSidebar() {
  const { tag_index, category_index, items } = state.data;

  // Tags sorted by count
  const tagEl = document.getElementById('tag-filters');
  const sortedTags = Object.entries(tag_index)
    .sort((a, b) => b[1].length - a[1].length);

  tagEl.innerHTML = sortedTags.map(([tag, ids]) => `
    <button class="filter-chip ${state.activeTags.has(tag) ? 'active' : ''}" data-tag="${escHtml(tag)}">
      <span>${escHtml(tag)}</span>
      <span class="chip-count">${ids.length}</span>
    </button>`).join('');

  tagEl.querySelectorAll('.filter-chip').forEach(btn => {
    btn.addEventListener('click', () => toggleTag(btn.dataset.tag));
  });

  // Categories
  const catEl = document.getElementById('category-filters');
  catEl.innerHTML = Object.entries(category_index).map(([cat, ids]) => `
    <button class="filter-chip ${state.activeCategories.has(cat) ? 'active' : ''}" data-cat="${escHtml(cat)}">
      <span>${escHtml(cat)}</span>
      <span class="chip-count">${ids.length}</span>
    </button>`).join('');

  catEl.querySelectorAll('.filter-chip').forEach(btn => {
    btn.addEventListener('click', () => toggleCategory(btn.dataset.cat));
  });
}

function renderActivePills() {
  const container = document.getElementById('active-filters');
  const pills = [];

  state.activeTags.forEach(tag => {
    pills.push(`<span class="active-filter-pill">
      <span>${escHtml(tag)}</span>
      <button class="pill-remove" data-tag="${escHtml(tag)}">✕</button>
    </span>`);
  });
  state.activeCategories.forEach(cat => {
    pills.push(`<span class="active-filter-pill">
      <span>${escHtml(cat)}</span>
      <button class="pill-remove" data-cat="${escHtml(cat)}">✕</button>
    </span>`);
  });

  container.innerHTML = pills.join('');
  container.querySelectorAll('.pill-remove').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.dataset.tag) toggleTag(btn.dataset.tag);
      if (btn.dataset.cat) toggleCategory(btn.dataset.cat);
    });
  });
}

function renderAll() {
  renderSidebar();
  renderActivePills();
  renderGrid();
}

// ── Filter toggles ─────────────────────────────────────────────────────────
function toggleTag(tag) {
  if (state.activeTags.has(tag)) state.activeTags.delete(tag);
  else state.activeTags.add(tag);
  renderAll();
}

function toggleCategory(cat) {
  if (state.activeCategories.has(cat)) state.activeCategories.delete(cat);
  else state.activeCategories.add(cat);
  renderAll();
}

function clearFilters() {
  state.activeTags.clear();
  state.activeCategories.clear();
  state.searchQuery = '';
  document.getElementById('search').value = '';
  renderAll();
}

// ── Modal ──────────────────────────────────────────────────────────────────
function openModal(item) {
  const tagsHtml = item.tags.map(t =>
    `<span class="tag" data-tag="${escHtml(t)}">${escHtml(t)}</span>`
  ).join('');

  document.getElementById('modal-content').innerHTML = `
    <div class="modal-source">${escHtml(item.source)} · ${escHtml(item.category)}</div>
    <h2 class="modal-title">${escHtml(item.title)}</h2>
    <div class="modal-date">${new Date(item.published).toLocaleString('en-US', {
      weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
      hour: '2-digit', minute: '2-digit', timeZoneName: 'short'
    })}</div>
    <p class="modal-summary">${escHtml(item.summary)}</p>
    <div class="modal-tags">${tagsHtml}</div>
    <a class="modal-link" href="${escHtml(item.url)}" target="_blank" rel="noopener noreferrer">
      Read full article ↗
    </a>`;

  const overlay = document.getElementById('modal-overlay');
  overlay.style.display = 'flex';
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  document.getElementById('modal-overlay').style.display = 'none';
  document.body.style.overflow = '';
}

// ── Data loading ───────────────────────────────────────────────────────────
async function loadNews() {
  try {
    const res = await fetch('news.json?t=' + Date.now());
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.data = await res.json();

    document.getElementById('article-count').textContent =
      `${state.data.total} articles`;

    const gen = new Date(state.data.generated);
    document.getElementById('last-updated').textContent =
      `Updated ${gen.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`;

    renderAll();
  } catch (err) {
    document.getElementById('news-grid').innerHTML = `
      <div class="loading-state" style="grid-column:1/-1">
        <p style="color:#f87171">Failed to load news.json. Run the fetch script first.</p>
        <p style="font-size:12px;color:#5a6478;margin-top:8px">python scripts/fetch_news.py</p>
      </div>`;
    console.error(err);
  }
}

// ── Init ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadNews();

  document.getElementById('search').addEventListener('input', e => {
    state.searchQuery = e.target.value.trim();
    renderGrid();
  });

  document.getElementById('clear-filters').addEventListener('click', clearFilters);
  document.getElementById('reset-link').addEventListener('click', e => {
    e.preventDefault(); clearFilters();
  });

  document.getElementById('modal-close').addEventListener('click', closeModal);
  document.getElementById('modal-overlay').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeModal();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModal();
  });
});
