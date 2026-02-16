/**
 * Railbookers - Package Finder Controller (Production Match v4)
 * ================================================================
 * Matches production Railbookers booking site exactly:
 *   - Mode dropdown (Includes / Starts in / Ends in)
 *   - Multi-row destination search with AND logic, OR within row
 *   - Filter pills: Region, Trip Duration, Trains, Vacation Type
 *   - TRAINS panel shows actual train NAMES from route column
 *   - Duration range slider (not chips)
 *   - Close button on panels
 *   - Trash icon for row delete
 *   - Production-style result cards
 *   - Sort: Most Popular, A to Z, Newest, etc.
 *
 * Database: 23 columns, 2000 packages, 448 cities, 54 countries,
 *   6 regions, 67 unique train names, 39 trip types, 43 states
 *
 * Developed by Rajan Mishra
 */

const API_BASE = (() => {
  const origin = window.location.origin;
  if (origin.includes('localhost') || origin.includes('127.0.0.1')) {
    return 'http://localhost:8890/api/v1';
  }
  return '/api/v1';
})();

// ============================================================================
// STATE
// ============================================================================
const state = {
  // Search rows: each row has {id, destinations: string[], mode: 'includes'|'starts_in'|'ends_in'}
  searchRows: [{ id: 1, destinations: [], mode: 'includes' }],
  nextRowId: 2,

  // Filter selections
  selectedRegions: [],        // country names from Region panel
  selectedDuration: null,     // { min, max } or null
  selectedTrains: [],         // actual train names from route column
  selectedVacTypes: [],       // vacation type names (trip types)

  // Sort
  sortBy: 'popularity',

  // Cached filter options from API
  filterOptions: null,
  allCountries: [],           // 54 countries
  allVacationTypes: [],       // all trip types for Vacation Type panel
  allTrainNames: [],          // 67 unique train names from route column
  durationRange: { min: 2, max: 34 },

  // Chip pagination
  chipPages: { region: 1, trains: 1, vactype: 1 },

  // UI state
  activePanel: null,
  searching: false,
  totalPackages: 0,
  resultCount: 0,
  expandedCards: new Set(),
  openModeRowId: null,        // Track which row has mode dropdown open

  // Region = regions + countries combined
  allRegions: [],              // e.g. ["Europe", "Africa", ...]
  allRegionItems: [],          // regions + countries combined for Region panel
};

// Mode labels for the dropdown
const MODE_OPTIONS = [
  { value: 'includes',  label: 'Includes...' },
  { value: 'starts_in', label: 'Starts in...' },
  { value: 'ends_in',   label: 'Ends in...' },
];

// Chip pagination
const CHIPS_PER_PAGE = 15;

// ============================================================================
// API LAYER
// ============================================================================
async function apiFetch(path, options = {}, retries = 2) {
  const controller = new AbortController();
  const timeout = options.timeout || 15000;
  const timer = setTimeout(() => controller.abort(), timeout);

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(`${API_BASE}${path}`, {
        ...options,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          ...(options.headers || {}),
        },
      });
      clearTimeout(timer);
      if (!res.ok) {
        const errBody = await res.text().catch(() => '');
        throw new Error(`HTTP ${res.status}: ${errBody || res.statusText}`);
      }
      return await res.json();
    } catch (e) {
      clearTimeout(timer);
      if (e.name === 'AbortError') throw new Error('Request timed out.');
      if (attempt < retries && !e.message.includes('HTTP 4')) {
        await new Promise(r => setTimeout(r, 300 * Math.pow(2, attempt)));
        continue;
      }
      throw e;
    }
  }
}

// ============================================================================
// DEBOUNCE
// ============================================================================
function debounce(fn, delay = 300) {
  let timer = null;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

// ============================================================================
// INIT
// ============================================================================
async function init() {
  // Render search rows immediately so UI is interactive from the start
  renderSearchRows();
  bindEvents();

  try {
    const data = await apiFetch('/recommendations/filters');
    state.filterOptions = data;
    state.totalPackages = data.total_packages || 0;

    // Countries for Region panel (54 unique)
    state.allCountries = (data.countries || []).filter(c => c && c.trim());

    // Regions (continents)
    state.allRegions = (data.regions || []).filter(r => r && r.trim());

    // Combine regions + countries for the Region panel
    state.allRegionItems = [...state.allRegions, ...state.allCountries];

    // All vacation types for the Vacation Type panel
    state.allVacationTypes = (data.vacation_types || []).filter(t => t && t.trim());

    // Actual train names from route column
    state.allTrainNames = (data.train_names || []).filter(t => t && t.trim());

    // Duration range
    if (data.duration_range) {
      state.durationRange = {
        min: data.duration_range.min || 2,
        max: data.duration_range.max || 34,
      };
    }

    // Update displays
    updateTotalDisplay(state.totalPackages);
    const emptyCount = document.getElementById('total-count-empty');
    if (emptyCount) emptyCount.textContent = state.totalPackages.toLocaleString();

    // Populate filter panel chips
    populateRegionChips();
    populateTrainChips();
    populateVacTypeChips();
    initDurationSlider();

    // Update pill counts (available options count)
    updatePillCounts();

    // Auto-load ALL packages on page load sorted by popularity
    await doSearch();

  } catch (e) {
    console.error('Failed to load filter options:', e);
    const rc = document.getElementById('results-count');
    if (rc) rc.innerHTML =
      '<span style="color:#c0392b;font-weight:500;">Unable to connect to backend (port 8890)</span>';
  }
}

function updateTotalDisplay(count) {
  const el = document.getElementById('total-display');
  if (el) el.textContent = typeof count === 'number' ? count.toLocaleString() : count;
}

function updatePillCounts() {
  // Show available option counts in parentheses when no selection;
  // show selection count when something is selected
  const regionCount = state.selectedRegions.length || state.allRegionItems.length;
  const trainCount = state.selectedTrains.length || state.allTrainNames.length;
  const vacCount = state.selectedVacTypes.length || state.allVacationTypes.length;

  setText('pill-count-region', `(${regionCount})`);
  setText('pill-count-trains', `(${trainCount})`);
  setText('pill-count-vactype', `(${vacCount})`);

  // Duration - show "(1)" if a selection is active, else empty
  if (state.selectedDuration) {
    setText('pill-count-duration', '(1)');
  } else {
    setText('pill-count-duration', '');
  }
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val || '';
}

/**
 * Update filter panel options from search-result-dependent available_filters.
 * This ensures filters only show options present in the current results.
 */
function updateFiltersFromResults(af) {
  const regions = (af.regions || []).filter(r => r && r.trim());
  const countries = (af.countries || []).filter(c => c && c.trim());
  state.allRegions = regions;
  state.allCountries = countries;
  state.allRegionItems = [...regions, ...countries];

  state.allTrainNames = (af.train_names || []).filter(t => t && t.trim());
  state.allVacationTypes = (af.vacation_types || []).filter(t => t && t.trim());

  if (af.duration_range) {
    state.durationRange = {
      min: af.duration_range.min || 2,
      max: af.duration_range.max || 34,
    };
  }

  // Remove selected values that are no longer in the result set
  state.selectedRegions = state.selectedRegions.filter(r => state.allRegionItems.includes(r));
  state.selectedTrains = state.selectedTrains.filter(t => state.allTrainNames.includes(t));
  state.selectedVacTypes = state.selectedVacTypes.filter(v => state.allVacationTypes.includes(v));

  // Reset chip pages and repopulate panels
  state.chipPages = { region: 1, trains: 1, vactype: 1 };
  populateRegionChips();
  populateTrainChips();
  populateVacTypeChips();
  initDurationSlider();
  updatePillCounts();
}

// ============================================================================
// FILTER PANEL CHIPS: Populate
// ============================================================================
/**
 * Unified paginated chip renderer.
 * Shows CHIPS_PER_PAGE items at a time with Prev/Next navigation.
 * When panel search is active, shows all matching items (no pagination).
 */
function populateChips(panelName, allItems, selectedItems, searchInputId) {
  const container = document.getElementById(`${panelName}-chips`);
  if (!container) return;

  const searchInput = document.getElementById(searchInputId);
  const searchQuery = (searchInput?.value || '').toLowerCase().trim();

  let visibleItems = allItems;
  if (searchQuery) {
    visibleItems = allItems.filter(item => item.toLowerCase().includes(searchQuery));
  }

  // Clamp page
  const totalPages = Math.ceil(visibleItems.length / CHIPS_PER_PAGE) || 1;
  if ((state.chipPages[panelName] || 1) > totalPages) {
    state.chipPages[panelName] = totalPages;
  }
  const currentPage = searchQuery ? 1 : (state.chipPages[panelName] || 1);
  const startIdx = (currentPage - 1) * CHIPS_PER_PAGE;
  const endIdx = startIdx + CHIPS_PER_PAGE;
  const pageItems = searchQuery ? visibleItems : visibleItems.slice(startIdx, endIdx);

  container.innerHTML = '';
  pageItems.forEach(item => {
    const chip = createChip(item, selectedItems.includes(item));
    chip.addEventListener('click', () => toggleChipSelection(chip, item, selectedItems));
    container.appendChild(chip);
  });

  // Selected count indicator
  const selCount = selectedItems.length;
  let selBadge = container.parentElement?.querySelector('.rb-selected-badge');
  if (selCount > 0) {
    if (!selBadge) {
      selBadge = document.createElement('div');
      selBadge.className = 'rb-selected-badge';
      container.before(selBadge);
    }
    selBadge.textContent = `${selCount} selected`;
  } else if (selBadge) {
    selBadge.remove();
  }

  // Render pagination (only when not searching and >1 page)
  renderChipPagination(panelName, currentPage, totalPages, visibleItems.length, !searchQuery);
}

function renderChipPagination(panelName, currentPage, totalPages, totalItems, showPagination) {
  const existing = document.getElementById(`${panelName}-pagination`);
  if (existing) existing.remove();

  if (!showPagination || totalPages <= 1) return;

  const chipsContainer = document.getElementById(`${panelName}-chips`);
  if (!chipsContainer) return;

  const pag = document.createElement('div');
  pag.className = 'rb-chips-pagination';
  pag.id = `${panelName}-pagination`;

  const prevBtn = document.createElement('button');
  prevBtn.className = 'rb-page-btn';
  prevBtn.type = 'button';
  prevBtn.disabled = currentPage <= 1;
  prevBtn.innerHTML = '&#8249; Prev';
  prevBtn.addEventListener('click', (e) => {
    e.preventDefault();
    if (state.chipPages[panelName] > 1) {
      state.chipPages[panelName]--;
      repopulateChips(panelName);
    }
  });

  const info = document.createElement('span');
  info.className = 'rb-page-info';
  info.textContent = `Page ${currentPage} of ${totalPages}`;

  const nextBtn = document.createElement('button');
  nextBtn.className = 'rb-page-btn';
  nextBtn.type = 'button';
  nextBtn.disabled = currentPage >= totalPages;
  nextBtn.innerHTML = 'Next &#8250;';
  nextBtn.addEventListener('click', (e) => {
    e.preventDefault();
    if (state.chipPages[panelName] < totalPages) {
      state.chipPages[panelName]++;
      repopulateChips(panelName);
    }
  });

  pag.appendChild(prevBtn);
  pag.appendChild(info);
  pag.appendChild(nextBtn);

  chipsContainer.after(pag);
}

function repopulateChips(panelName) {
  if (panelName === 'region') populateRegionChips();
  else if (panelName === 'trains') populateTrainChips();
  else if (panelName === 'vactype') populateVacTypeChips();
}

function populateRegionChips() {
  populateChips('region', state.allRegionItems, state.selectedRegions, 'region-search');
}

function populateTrainChips() {
  populateChips('trains', state.allTrainNames, state.selectedTrains, 'trains-search');
}

function populateVacTypeChips() {
  populateChips('vactype', state.allVacationTypes, state.selectedVacTypes, 'vactype-search');
}

function createChip(label, selected = false) {
  const btn = document.createElement('button');
  btn.className = 'rb-chip-opt' + (selected ? ' selected' : '');
  btn.textContent = label;
  btn.type = 'button';
  return btn;
}

function toggleChipSelection(chipEl, value, stateArray) {
  const idx = stateArray.indexOf(value);
  if (idx >= 0) {
    stateArray.splice(idx, 1);
    chipEl.classList.remove('selected');
  } else {
    stateArray.push(value);
    chipEl.classList.add('selected');
  }
}

// ============================================================================
// DURATION RANGE SLIDER
// ============================================================================
let _sliderListenersBound = false;
function initDurationSlider() {
  const minSlider = document.getElementById('dur-slider-min');
  const maxSlider = document.getElementById('dur-slider-max');
  if (!minSlider || !maxSlider) return;

  const min = state.durationRange.min;
  const max = state.durationRange.max;
  minSlider.min = min;
  minSlider.max = max;
  minSlider.value = min;
  maxSlider.min = min;
  maxSlider.max = max;
  maxSlider.value = max;

  updateSliderLabels();
  updateSliderFill();

  if (!_sliderListenersBound) {
    _sliderListenersBound = true;
    minSlider.addEventListener('input', () => {
      const minVal = parseInt(minSlider.value);
      const maxVal = parseInt(maxSlider.value);
      if (minVal > maxVal - 1) {
        minSlider.value = maxVal - 1;
      }
      updateSliderLabels();
      updateSliderFill();
    });

    maxSlider.addEventListener('input', () => {
      const minVal = parseInt(minSlider.value);
      const maxVal = parseInt(maxSlider.value);
      if (maxVal < minVal + 1) {
        maxSlider.value = minVal + 1;
      }
      updateSliderLabels();
      updateSliderFill();
    });
  }
}

function updateSliderLabels() {
  const minSlider = document.getElementById('dur-slider-min');
  const maxSlider = document.getElementById('dur-slider-max');
  const minLabel = document.getElementById('dur-min-label');
  const maxLabel = document.getElementById('dur-max-label');
  if (minSlider && minLabel) minLabel.textContent = `${minSlider.value} days`;
  if (maxSlider && maxLabel) maxLabel.textContent = `${maxSlider.value} days`;
}

function updateSliderFill() {
  const minSlider = document.getElementById('dur-slider-min');
  const maxSlider = document.getElementById('dur-slider-max');
  const fill = document.getElementById('slider-fill');
  if (!minSlider || !maxSlider || !fill) return;

  const min = parseInt(minSlider.min);
  const max = parseInt(minSlider.max);
  const minVal = parseInt(minSlider.value);
  const maxVal = parseInt(maxSlider.value);
  const range = max - min;

  const leftPct = ((minVal - min) / range) * 100;
  const rightPct = ((max - maxVal) / range) * 100;
  fill.style.left = `${leftPct}%`;
  fill.style.right = `${rightPct}%`;
}

function getDurationSelection() {
  const minSlider = document.getElementById('dur-slider-min');
  const maxSlider = document.getElementById('dur-slider-max');
  if (!minSlider || !maxSlider) return null;

  const minVal = parseInt(minSlider.value);
  const maxVal = parseInt(maxSlider.value);
  const dMin = state.durationRange.min;
  const dMax = state.durationRange.max;

  // If slider is at full range, no duration filter
  if (minVal === dMin && maxVal === dMax) return null;

  return { min: minVal, max: maxVal };
}

function resetDurationSlider() {
  const minSlider = document.getElementById('dur-slider-min');
  const maxSlider = document.getElementById('dur-slider-max');
  if (minSlider) minSlider.value = state.durationRange.min;
  if (maxSlider) maxSlider.value = state.durationRange.max;
  updateSliderLabels();
  updateSliderFill();
  state.selectedDuration = null;
}

// ============================================================================
// AUTOSUGGEST ENGINE
// ============================================================================
async function fetchSuggestions(query, field = 'all', limit = 12, mode = 'includes') {
  if (!query || query.length < 1) return [];
  try {
    // Map search mode to autosuggest field for better relevance
    let autoField = field;
    if (field === 'all') {
      if (mode === 'starts_in') autoField = 'start_locations';
      else if (mode === 'ends_in') autoField = 'end_locations';
    }
    // Request extra results so we can re-rank on the client side
    const fetchLimit = Math.min(limit * 3, 50);
    const params = new URLSearchParams({ q: query, field: autoField, limit: String(fetchLimit) });
    const data = await apiFetch(`/recommendations/autosuggest?${params}`, { timeout: 5000 }, 1);
    let items = (data.suggestions || []).map(s => typeof s === 'string' ? s : s.value);

    // Client-side re-ranking: starts-with first, then shorter names, then alphabetical
    const ql = query.toLowerCase();
    items.sort((a, b) => {
      const aStarts = a.toLowerCase().startsWith(ql) ? 0 : 1;
      const bStarts = b.toLowerCase().startsWith(ql) ? 0 : 1;
      if (aStarts !== bStarts) return aStarts - bStarts;
      // Prefer shorter names (more likely to be the direct match)
      if (a.length !== b.length) return a.length - b.length;
      return a.localeCompare(b);
    });

    return items.slice(0, limit);
  } catch (e) {
    console.warn('Autosuggest error:', e);
    return [];
  }
}

function showSuggestions(dropdownEl, items, onSelect) {
  if (!dropdownEl) return;
  dropdownEl.innerHTML = '';
  if (items.length === 0) {
    dropdownEl.classList.remove('visible');
    return;
  }
  items.forEach((item, idx) => {
    const div = document.createElement('div');
    div.className = 'rb-suggest-item';
    div.setAttribute('role', 'option');
    div.setAttribute('data-index', idx);
    div.textContent = item;
    div.addEventListener('mousedown', (e) => {
      e.preventDefault();
      e.stopPropagation();
      onSelect(item);
    });
    dropdownEl.appendChild(div);
  });
  dropdownEl.classList.add('visible');
}

function hideSuggestions(dropdownEl) {
  if (dropdownEl) dropdownEl.classList.remove('visible');
}

function hideAllSuggestions() {
  document.querySelectorAll('.rb-suggest-dropdown').forEach(dd => dd.classList.remove('visible'));
}

// ============================================================================
// MODE DROPDOWN
// ============================================================================
function openModeDropdown(rowId, triggerEl) {
  // If same row already open, just close (toggle behavior)
  if (state.openModeRowId === rowId) {
    closeModeDropdown();
    return;
  }

  // Close any existing dropdown first
  closeModeDropdown();

  const row = state.searchRows.find(r => r.id === rowId);
  if (!row) return;

  // Find the row-inner container (position context)
  const rowInner = triggerEl.closest('.rb-search-row-inner');
  if (!rowInner) return;

  const dd = document.createElement('div');
  dd.className = 'rb-mode-dropdown';
  dd.id = 'mode-dropdown-active';

  MODE_OPTIONS.forEach(opt => {
    const item = document.createElement('div');
    item.className = 'rb-mode-option' + (row.mode === opt.value ? ' active' : '');
    item.textContent = opt.label;
    item.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      row.mode = opt.value;
      closeModeDropdown();
      renderSearchRows();
      autoSearch();
    });
    dd.appendChild(item);
  });

  // Position below the trigger button using getBoundingClientRect
  const triggerRect = triggerEl.getBoundingClientRect();
  const rowRect = rowInner.getBoundingClientRect();
  dd.style.top = `${triggerRect.bottom - rowRect.top + 2}px`;
  dd.style.left = `${triggerRect.left - rowRect.left}px`;

  rowInner.appendChild(dd);
  state.openModeRowId = rowId;
}

function closeModeDropdown() {
  const dd = document.getElementById('mode-dropdown-active');
  if (dd) dd.remove();
  state.openModeRowId = null;
}

function getModeLabel(mode) {
  const found = MODE_OPTIONS.find(o => o.value === mode);
  return found ? found.label : 'Includes...';
}

// ============================================================================
// SEARCH ROW MANAGEMENT
// ============================================================================
function addSearchRow() {
  const rowId = state.nextRowId++;
  state.searchRows.push({ id: rowId, destinations: [], mode: 'includes' });
  renderSearchRows();
}

function removeSearchRow(rowId) {
  if (state.searchRows.length <= 1) return;
  state.searchRows = state.searchRows.filter(r => r.id !== rowId);
  renderSearchRows();
  autoSearch();
}

function addDestToRow(rowId, dest) {
  const row = state.searchRows.find(r => r.id === rowId);
  if (!row) return;
  const v = dest.trim();
  if (!v || v.length > 100) return;
  if (row.destinations.some(d => d.toLowerCase() === v.toLowerCase())) return;
  if (row.destinations.length >= 10) return;
  row.destinations.push(v);
  renderSearchRows();
  autoSearch();
}

function removeDestFromRow(rowId, dest) {
  const row = state.searchRows.find(r => r.id === rowId);
  if (!row) return;
  row.destinations = row.destinations.filter(d => d !== dest);
  renderSearchRows();
  autoSearch();
}

function renderSearchRows() {
  const container = document.getElementById('search-rows');
  if (!container) return;
  container.innerHTML = '';

  state.searchRows.forEach((row, idx) => {
    // AND separator between rows
    if (idx > 0) {
      const sep = document.createElement('div');
      sep.className = 'rb-and-separator';
      sep.innerHTML = '<span class="rb-and-label">And...</span><div class="rb-and-line"></div>';
      container.appendChild(sep);
    }

    const rowEl = document.createElement('div');
    rowEl.className = 'rb-search-row';
    rowEl.dataset.rowId = row.id;

    const inner = document.createElement('div');
    inner.className = 'rb-search-row-inner';

    // Mode selector — using a <div> with role="button" to avoid button overflow clipping
    const modeBtn = document.createElement('div');
    modeBtn.className = 'rb-mode-selector';
    modeBtn.setAttribute('role', 'button');
    modeBtn.setAttribute('tabindex', '0');
    modeBtn.innerHTML = `<span class="rb-mode-label">${getModeLabel(row.mode)}</span>
      <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor"><path d="M2 3.5L5 7l3-3.5H2z"/></svg>`;
    modeBtn.title = 'Click to change search mode';
    modeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      openModeDropdown(row.id, modeBtn);
    });
    modeBtn.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        e.stopPropagation();
        openModeDropdown(row.id, modeBtn);
      }
    });
    inner.appendChild(modeBtn);

    // Input area
    const inputArea = document.createElement('div');
    inputArea.className = 'rb-search-input-area';

    // Inline tags
    row.destinations.forEach((dest, dIdx) => {
      if (dIdx > 0) {
        const orSep = document.createElement('span');
        orSep.className = 'rb-or-sep';
        orSep.textContent = 'or';
        inputArea.appendChild(orSep);
      }
      const tag = document.createElement('span');
      tag.className = 'rb-inline-tag';
      tag.innerHTML = `<span>${escapeHtml(dest)}</span>`;
      const removeBtn = document.createElement('button');
      removeBtn.className = 'rb-inline-tag-remove';
      removeBtn.innerHTML = '&times;';
      removeBtn.title = `Remove ${dest}`;
      removeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        removeDestFromRow(row.id, dest);
      });
      tag.appendChild(removeBtn);
      inputArea.appendChild(tag);
    });

    // Text input
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'rb-dest-input';
    input.placeholder = 'Add a destination';
    input.autocomplete = 'off';
    input.spellcheck = false;
    input.setAttribute('aria-label', 'Search destinations');
    inputArea.appendChild(input);

    // Suggest dropdown
    const dropdown = document.createElement('div');
    dropdown.className = 'rb-suggest-dropdown';
    dropdown.setAttribute('role', 'listbox');
    inputArea.appendChild(dropdown);

    inner.appendChild(inputArea);
    rowEl.appendChild(inner);

    // Row action buttons
    const actions = document.createElement('div');
    actions.className = 'rb-row-actions';

    // Add (+) button (green circle)
    const addBtn = document.createElement('button');
    addBtn.className = 'rb-row-btn rb-row-add';
    addBtn.title = 'Add another filter row';
    addBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M8 3v10M3 8h10"/></svg>';
    addBtn.addEventListener('click', addSearchRow);
    actions.appendChild(addBtn);

    // Delete (trash) button - only if more than 1 row
    if (state.searchRows.length > 1) {
      const delBtn = document.createElement('button');
      delBtn.className = 'rb-row-btn rb-row-delete';
      delBtn.title = 'Remove this row';
      // Trash can icon
      delBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M2 4h12"/><path d="M5 4V3a1 1 0 011-1h4a1 1 0 011 1v1"/>
        <path d="M13 4v9a1 1 0 01-1 1H4a1 1 0 01-1-1V4"/>
        <path d="M6.5 7v4"/><path d="M9.5 7v4"/>
      </svg>`;
      delBtn.addEventListener('click', () => removeSearchRow(row.id));
      actions.appendChild(delBtn);
    }

    rowEl.appendChild(actions);
    container.appendChild(rowEl);

    setupRowAutosuggest(input, dropdown, row.id);
  });
}

function setupRowAutosuggest(inputEl, dropdownEl, rowId) {
  const debouncedFetch = debounce(async () => {
    const query = inputEl.value.trim();
    if (query.length < 1) {
      hideSuggestions(dropdownEl);
      return;
    }
    // Get the row's mode for mode-aware autosuggest
    const row = state.searchRows.find(r => r.id === rowId);
    const mode = row ? row.mode : 'includes';
    const suggestions = await fetchSuggestions(query, 'all', 12, mode);
    // Only show if input still has focus and value matches
    if (document.activeElement === inputEl && inputEl.value.trim().length >= 1) {
      showSuggestions(dropdownEl, suggestions, (item) => {
        addDestToRow(rowId, item);
        inputEl.value = '';
        hideSuggestions(dropdownEl);
      });
    }
  }, 250);

  inputEl.addEventListener('input', debouncedFetch);

  inputEl.addEventListener('keydown', (e) => {
    if (!dropdownEl.classList.contains('visible')) {
      if (e.key === 'Enter' && inputEl.value.trim()) {
        e.preventDefault();
        addDestToRow(rowId, inputEl.value.trim());
        inputEl.value = '';
      }
      return;
    }
    const items = dropdownEl.querySelectorAll('.rb-suggest-item');
    const active = dropdownEl.querySelector('.rb-suggest-item.active');
    let activeIndex = active ? parseInt(active.dataset.index) : -1;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        activeIndex = Math.min(activeIndex + 1, items.length - 1);
        items.forEach(i => i.classList.remove('active'));
        items[activeIndex]?.classList.add('active');
        items[activeIndex]?.scrollIntoView({ block: 'nearest' });
        break;
      case 'ArrowUp':
        e.preventDefault();
        activeIndex = Math.max(activeIndex - 1, 0);
        items.forEach(i => i.classList.remove('active'));
        items[activeIndex]?.classList.add('active');
        items[activeIndex]?.scrollIntoView({ block: 'nearest' });
        break;
      case 'Enter':
        e.preventDefault();
        if (active) {
          addDestToRow(rowId, active.textContent);
          inputEl.value = '';
        } else if (inputEl.value.trim()) {
          addDestToRow(rowId, inputEl.value.trim());
          inputEl.value = '';
        }
        hideSuggestions(dropdownEl);
        break;
      case 'Escape':
        e.preventDefault();
        hideSuggestions(dropdownEl);
        break;
      case 'Backspace':
        if (inputEl.value === '') {
          const row = state.searchRows.find(r => r.id === rowId);
          if (row && row.destinations.length > 0) {
            removeDestFromRow(rowId, row.destinations[row.destinations.length - 1]);
          }
        }
        break;
    }
  });

  inputEl.addEventListener('focus', () => {
    if (inputEl.value.trim().length >= 1) debouncedFetch();
  });

  inputEl.addEventListener('blur', () => {
    // Delay hide to allow mousedown on suggestion items to fire first
    setTimeout(() => hideSuggestions(dropdownEl), 250);
  });
}

// ============================================================================
// FILTER PANEL TOGGLE
// ============================================================================
function togglePanel(filterName) {
  const panelId = `panel-${filterName}`;
  const panel = document.getElementById(panelId);
  if (!panel) return;

  if (state.activePanel === filterName) {
    closeAllPanels();
    return;
  }

  closeAllPanels();
  panel.style.display = 'flex';
  state.activePanel = filterName;

  // Reset chip page and refresh when opening
  if (filterName !== 'duration' && state.chipPages[filterName] !== undefined) {
    state.chipPages[filterName] = 1;
    const panelSearch = document.getElementById(`${filterName}-search`);
    if (panelSearch) panelSearch.value = '';
    repopulateChips(filterName);
  }

  // Mark pill as active
  document.querySelectorAll('.rb-filter-pill').forEach(p => p.classList.remove('active'));
  const pill = document.getElementById(`pill-${filterName}`);
  if (pill) pill.classList.add('active');

  // Add overlay
  const overlay = document.createElement('div');
  overlay.className = 'rb-overlay';
  overlay.id = 'panel-overlay';
  overlay.addEventListener('click', closeAllPanels);
  document.body.appendChild(overlay);
}

function closeAllPanels() {
  document.querySelectorAll('.rb-filter-panel').forEach(p => p.style.display = 'none');
  document.querySelectorAll('.rb-filter-pill').forEach(p => p.classList.remove('active'));
  const overlay = document.getElementById('panel-overlay');
  if (overlay) overlay.remove();
  state.activePanel = null;
  updatePillSelectionState();
}

function updatePillSelectionState() {
  const pills = {
    region: state.selectedRegions.length > 0,
    duration: state.selectedDuration !== null,
    trains: state.selectedTrains.length > 0,
    vactype: state.selectedVacTypes.length > 0,
  };
  Object.entries(pills).forEach(([key, hasSelection]) => {
    const pill = document.getElementById(`pill-${key}`);
    if (pill) pill.classList.toggle('has-selection', hasSelection);

    const countEl = document.getElementById(`pill-count-${key}`);
    if (countEl) {
      if (hasSelection) {
        let count = 0;
        if (key === 'region') count = state.selectedRegions.length;
        else if (key === 'duration') count = 1;
        else if (key === 'trains') count = state.selectedTrains.length;
        else if (key === 'vactype') count = state.selectedVacTypes.length;
        countEl.textContent = `(${count})`;
      } else {
        if (key === 'region') countEl.textContent = `(${state.allRegionItems.length})`;
        else if (key === 'trains') countEl.textContent = `(${state.allTrainNames.length})`;
        else if (key === 'vactype') countEl.textContent = `(${state.allVacationTypes.length})`;
        else countEl.textContent = '';
      }
    }
  });
}

// ============================================================================
// SEARCH
// ============================================================================
const autoSearch = debounce(() => doSearch(), 500);

async function doSearch() {
  if (state.searching) return;
  state.searching = true;
  hideAllSuggestions();
  closeModeDropdown();

  const filters = buildFilters();

  // Show loading
  document.getElementById('loading').style.display = 'block';
  document.getElementById('results-list').innerHTML = '';
  document.getElementById('empty-state').style.display = 'none';

  try {
    const result = await apiFetch('/recommendations/search', {
      method: 'POST',
      body: JSON.stringify(filters),
      timeout: 20000,
    }, 1);

    document.getElementById('loading').style.display = 'none';

    // Update filter panels from result-dependent available_filters
    if (result.available_filters) {
      updateFiltersFromResults(result.available_filters);
    }

    if (result.packages && result.packages.length > 0) {
      renderResults(result);
    } else {
      renderNoResults();
    }
  } catch (e) {
    document.getElementById('loading').style.display = 'none';
    console.error('Search error:', e);
    document.getElementById('results-list').innerHTML = `
      <div class="rb-error-card">
        <div class="rb-error-icon">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/><path d="M12 8v4"/><circle cx="12" cy="16" r="0.5" fill="currentColor"/>
          </svg>
        </div>
        <h3>Search failed</h3>
        <p>${escapeHtml(e.message)}</p>
        <button class="rb-btn-retry" onclick="doSearch()">Try Again</button>
      </div>`;
  } finally {
    state.searching = false;
  }
}

function buildFilters() {
  const f = {};

  // Build search_rows (multi-mode format: each row carries its own mode)
  const searchRows = [];
  state.searchRows.forEach(row => {
    if (row.destinations.length === 0) return;
    searchRows.push({
      mode: row.mode,
      destinations: [...row.destinations]
    });
  });

  if (searchRows.length > 0) {
    f.search_rows = searchRows;
  }

  // Countries (from Region panel — separate regions vs countries for API)
  if (state.selectedRegions.length > 0) {
    // Separate regions from countries
    const regionSet = new Set(state.allRegions.map(r => r.toLowerCase()));
    const selectedRegionNames = state.selectedRegions.filter(r => regionSet.has(r.toLowerCase()));
    const selectedCountryNames = state.selectedRegions.filter(r => !regionSet.has(r.toLowerCase()));
    
    if (selectedCountryNames.length > 0) {
      f.countries = [...selectedCountryNames];
    }
    if (selectedRegionNames.length > 0) {
      // Use the first region for the region filter (API supports single region)
      f.region = selectedRegionNames[0];
    }
  }

  // Duration (from range slider)
  if (state.selectedDuration) {
    f.duration_min = state.selectedDuration.min;
    f.duration_max = state.selectedDuration.max;
  }

  // Train names (actual train names from route column)
  if (state.selectedTrains.length > 0) {
    f.train_names = [...state.selectedTrains];
  }

  // Vacation Types (trip types)
  if (state.selectedVacTypes.length > 0) {
    f.vacation_types = [...state.selectedVacTypes];
  }

  f.sort_by = state.sortBy || 'popularity';
  return f;
}

// ============================================================================
// RENDER RESULTS (production-match card layout)
// ============================================================================
function renderResults(result) {
  const { packages, total_matched, total_returned, elapsed_ms } = result;
  state.resultCount = total_returned;
  state.expandedCards.clear();

  updateTotalDisplay(total_returned);

  const container = document.getElementById('results-list');
  container.innerHTML = '';

  packages.forEach((pkg, index) => {
    const card = document.createElement('article');
    card.className = 'rb-result-card';
    card.style.animationDelay = `${index * 50}ms`;
    card.dataset.pkgId = pkg.id || index;

    // Build route display with arrows
    const routeHtml = buildRouteHtml(pkg);

    // Duration
    const duration = pkg.duration_display || '';
    const durationNum = (duration.match(/\d+/) || [''])[0];

    // Description (truncated)
    const desc = (pkg.description || '').substring(0, 250);

    // Train/route names
    const trainNames = pkg.trains_display || '';

    // Highlights list
    const highlights = pkg.highlights_list || [];

    // Inclusions list
    const inclusions = pkg.inclusions_list || [];

    // Departure dates
    const depDates = pkg.departure_dates_display || '';

    // Access rule
    const accessRule = pkg.access_rule_display || '';

    // Countries
    const countries = pkg.countries_display || '';

    // Departure type
    const depType = pkg.departure_type || '';

    // Trip types for sub-label
    const tripTypes = (pkg.trip_type_display || '').split(',').map(t => t.trim()).filter(t => t);

    const url = pkg.package_url || '#';
    const pkgId = pkg.id || index;

    // Hotel tier
    const hotelTier = pkg.hotel_tier || '';

    // Use estimated_price from backend or fall back to tier-based proxy
    const estimatedPrice = pkg.estimated_price;
    const promoSavings = pkg.promo_savings || 0;
    let priceDisplay = '';
    if (estimatedPrice) {
      priceDisplay = '£' + Number(estimatedPrice).toLocaleString();
    } else {
      const tierPriceMap = { 'Luxury': '£2,500', 'Premium': '£1,000', 'Value': '£409' };
      priceDisplay = tierPriceMap[hotelTier] || '';
    }

    // SAVE badge HTML
    const saveBadge = promoSavings > 0
      ? `<span class="rb-save-badge">SAVE £${promoSavings}</span>`
      : '';

    // Train names badge
    const trainBadge = trainNames
      ? `<div class="rb-train-names"><span class="rb-train-icon">&#128642;</span> ${escapeHtml(trainNames)}</div>`
      : '';

    // Highlights HTML (first 4)
    const hlHtml = highlights.length > 0
      ? `<ul class="rb-hl-list">${highlights.slice(0, 4).map(h => `<li>${escapeHtml(h)}</li>`).join('')}</ul>`
      : '';

    // Inclusions HTML (first 4)
    const incHtml = inclusions.length > 0
      ? `<ul class="rb-inc-list">${inclusions.slice(0, 4).map(i => `<li>${escapeHtml(i)}</li>`).join('')}</ul>`
      : '';

    // Departure dates HTML
    const depHtml = depDates ? `<div class="rb-dep-dates"><span class="rb-dep-icon">&#128197;</span> ${escapeHtml(depDates)}</div>` : '';

    // Access rule badge (smaller, inline)
    const accessHtml = accessRule && accessRule !== 'Standard'
      ? `<span class="rb-access-badge">${escapeHtml(accessRule)}</span>` : '';

    // Country + departure type tags
    const metaTags = [];
    if (countries) metaTags.push(countries);
    if (depType) metaTags.push(depType);
    const metaHtml = metaTags.map(t => `<span class="rb-meta-tag">${escapeHtml(t)}</span>`).join('');

    // Trip type tags
    const tripHtml = tripTypes.slice(0, 3).map(t =>
      `<span class="rb-meta-tag highlight">${escapeHtml(t)}</span>`
    ).join('');

    card.innerHTML = `
      <div class="rb-card-content">
        <h3 class="rb-card-title" onclick="window.open('detail.html?id=${pkgId}','_blank')">${escapeHtml(pkg.name || 'Rail Vacation')}</h3>
        ${desc || saveBadge ? `<p class="rb-card-desc">${saveBadge}${desc ? escapeHtml(desc) : ''}</p>` : ''}
        ${routeHtml}
      </div>
      <div class="rb-card-aside">
        <span class="rb-card-duration-price">${durationNum ? durationNum + ' days' : duration}${priceDisplay ? ' from ' + priceDisplay : ''}</span>
        <a href="detail.html?id=${pkgId}" target="_blank" rel="noopener" class="rb-dates-link">Dates and Prices &rarr;</a>
        <a href="detail.html?id=${pkgId}" target="_blank" rel="noopener noreferrer" class="rb-btn-itinerary">
          <span class="rb-btn-itinerary-text">View Itinerary</span><span class="rb-itinerary-icon"><span class="rb-arrow-diag">&rarr;</span></span>
        </a>
      </div>
      <div class="rb-card-gold-line"></div>`;

    container.appendChild(card);
  });

  document.getElementById('empty-state').style.display = 'none';
}

// Toggle expand/collapse
function toggleCardExpand(pkgId) {
  const expandEl = document.getElementById(`expand-${pkgId}`);
  const toggleBtn = document.querySelector(`[data-pkg-id="${pkgId}"]`);
  if (!expandEl) return;

  const isExpanded = state.expandedCards.has(String(pkgId));
  if (isExpanded) {
    expandEl.style.display = 'none';
    state.expandedCards.delete(String(pkgId));
    if (toggleBtn) {
      const textEl = toggleBtn.querySelector('.rb-expand-text');
      if (textEl) textEl.textContent = 'Show details';
      toggleBtn.classList.remove('expanded');
    }
  } else {
    expandEl.style.display = 'block';
    state.expandedCards.add(String(pkgId));
    if (toggleBtn) {
      const textEl = toggleBtn.querySelector('.rb-expand-text');
      if (textEl) textEl.textContent = 'Hide details';
      toggleBtn.classList.add('expanded');
    }
  }
}
window.toggleCardExpand = toggleCardExpand;

function buildRouteHtml(pkg) {
  const start = pkg.start_location || '';
  const end = pkg.end_location || '';
  const cities = (pkg.cities_display || '').split(/[,|]/).map(c => c.trim()).filter(c => c);

  let routeCities = [];
  if (start) routeCities.push(start);
  if (cities.length > 0) {
    cities.forEach(c => {
      if (c !== start && c !== end && !routeCities.includes(c)) {
        routeCities.push(c);
      }
    });
  }
  if (end && end !== start && !routeCities.includes(end)) routeCities.push(end);

  if (routeCities.length > 6) {
    routeCities = [routeCities[0], routeCities[1], routeCities[2], '...', routeCities[routeCities.length - 2], routeCities[routeCities.length - 1]];
  }

  if (routeCities.length === 0) return '';

  const parts = routeCities.map((city, i) => {
    const html = `<span class="rb-route-city">${escapeHtml(city)}</span>`;
    if (i < routeCities.length - 1) {
      return html + '<span class="rb-route-arrow">&#10230;</span>';
    }
    return html;
  }).join(' ');

  return `<div class="rb-card-route">${parts}</div>`;
}

function renderNoResults() {
  updateTotalDisplay(0);
  document.getElementById('results-list').innerHTML = `
    <div class="rb-no-results">
      <div class="rb-no-results-icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
          <path d="M8 11h6" stroke-linecap="round"/>
        </svg>
      </div>
      <h3>No matching packages</h3>
      <p>Try broadening your search or removing some filters.</p>
      <ul class="rb-suggestions">
        <li>Remove some destinations</li>
        <li>Clear region or country filter</li>
        <li>Widen duration range</li>
      </ul>
    </div>`;
  document.getElementById('empty-state').style.display = 'none';
}

// ============================================================================
// CLEAR ALL
// ============================================================================
function clearAll() {
  state.searchRows = [{ id: 1, destinations: [], mode: 'includes' }];
  state.nextRowId = 2;
  state.selectedRegions = [];
  state.selectedDuration = null;
  state.selectedTrains = [];
  state.selectedVacTypes = [];
  state.resultCount = 0;
  state.sortBy = 'popularity';
  state.expandedCards.clear();
  state.chipPages = { region: 1, trains: 1, vactype: 1 };

  renderSearchRows();
  closeAllPanels();

  // Reset chip selections
  document.querySelectorAll('.rb-chip-opt').forEach(c => c.classList.remove('selected'));

  // Reset duration slider
  resetDurationSlider();

  // Reset sort
  const sortEl = document.getElementById('sort-select');
  if (sortEl) sortEl.value = 'popularity';

  // Reload all packages
  updatePillCounts();
  doSearch();
}

// ============================================================================
// PANEL-SPECIFIC SEARCH FILTERS
// ============================================================================
function setupPanelSearch(searchInputId, panelName) {
  const searchInput = document.getElementById(searchInputId);
  if (!searchInput) return;

  searchInput.addEventListener('input', () => {
    state.chipPages[panelName] = 1;
    repopulateChips(panelName);
  });
}

// ============================================================================
// EVENT BINDING
// ============================================================================
function bindEvents() {
  // Filter pill clicks
  document.querySelectorAll('.rb-filter-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      const filterName = pill.dataset.filter;
      togglePanel(filterName);
    });
  });

  // Close buttons on panels
  document.querySelectorAll('.rb-panel-close').forEach(btn => {
    btn.addEventListener('click', () => {
      closeAllPanels();
    });
  });

  // Sort change
  const sortSelect = document.getElementById('sort-select');
  if (sortSelect) {
    sortSelect.addEventListener('change', () => {
      state.sortBy = sortSelect.value;
      autoSearch();
    });
  }

  // Panel Apply/Reset/Clear buttons
  ['region', 'duration', 'trains', 'vactype'].forEach(name => {
    const applyBtn = document.getElementById(`${name}-apply`);
    if (applyBtn) {
      applyBtn.addEventListener('click', () => {
        // For duration, capture slider values
        if (name === 'duration') {
          state.selectedDuration = getDurationSelection();
        }
        closeAllPanels();
        autoSearch();
      });
    }

    const resetBtn = document.getElementById(`${name}-reset`);
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        if (name === 'region') {
          state.selectedRegions = [];
          populateRegionChips();
        } else if (name === 'duration') {
          resetDurationSlider();
        } else if (name === 'trains') {
          state.selectedTrains = [];
          populateTrainChips();
        } else if (name === 'vactype') {
          state.selectedVacTypes = [];
          populateVacTypeChips();
        }
      });
    }

    const clearBtn = document.getElementById(`${name}-clear-all`);
    if (clearBtn) {
      clearBtn.addEventListener('click', () => {
        clearAll();
        closeAllPanels();
      });
    }
  });

  // Panel search inputs
  setupPanelSearch('region-search', 'region');
  setupPanelSearch('trains-search', 'trains');
  setupPanelSearch('vactype-search', 'vactype');

  // Click outside closes suggestions
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.rb-search-input-area')) {
      hideAllSuggestions();
    }
    if (!e.target.closest('.rb-mode-selector') && !e.target.closest('.rb-mode-dropdown')) {
      closeModeDropdown();
    }
  });

  // Ctrl+Enter triggers search
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      doSearch();
    }
  });
}

// ============================================================================
// UTILS
// ============================================================================
function escapeHtml(str) {
  if (!str) return '';
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return String(str).replace(/[&<>"']/g, c => map[c]);
}

function escapeAttr(str) {
  if (!str) return '#';
  return String(str).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ============================================================================
// BOOT
// ============================================================================
document.addEventListener('DOMContentLoaded', init);
window.doSearch = doSearch;
