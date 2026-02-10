/**
 * MultiSelect - Railbookers
 * Smart chip selector with search filter and counter.
 * Users click chips to populate the chat input, then press Enter to send.
 * No confirm button -- chatbot paradigm: type your answer.
 */

export class MultiSelect {
  static render(options, config = {}) {
    const max = config.maxSelect || 5;
    const searchable = config.searchable !== false;

    const chips = options.map((opt, i) => {
      const val = opt.value || opt.label || opt;
      const lbl = opt.label || opt;
      return `<button class="ms-chip" data-value="${val}" data-idx="${i}" aria-label="${lbl}">${lbl}</button>`;
    }).join('');

    const searchHtml = searchable
      ? `<input type="text" class="ms-search" placeholder="Search or type a destination..." aria-label="Filter destinations">`
      : '';

    return `
      <div class="multi-select-widget" data-max="${max}" role="group" aria-label="Select options">
        <div class="ms-bar">
          ${searchHtml}
          <span class="ms-counter">0 / ${max}</span>
        </div>
        <div class="ms-chips">${chips}</div>
      </div>`;
  }

  static attachHandlers(container, onSelectionChange) {
    const w = container.querySelector('.multi-select-widget');
    if (!w) return;
    const max = parseInt(w.dataset.max) || 5;
    const chips = w.querySelectorAll('.ms-chip');
    const counter = w.querySelector('.ms-counter');
    const search = w.querySelector('.ms-search');
    const sel = new Set();

    if (search) {
      search.addEventListener('input', () => {
        const q = search.value.toLowerCase();
        chips.forEach(c => {
          const match = c.textContent.toLowerCase().includes(q);
          c.style.display = match ? '' : 'none';
        });
      });
      // Enter in search: combine selected chips + typed text -> populate input
      search.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && search.value.trim()) {
          e.preventDefault();
          const val = search.value.trim();
          const selected = Array.from(sel);
          const combined = selected.length > 0 ? [...selected, val].join(', ') : val;
          search.value = '';
          chips.forEach(c => c.style.display = '');
          if (onSelectionChange) onSelectionChange(combined);
        }
      });
    }

    chips.forEach(chip => {
      chip.addEventListener('click', () => {
        const v = chip.dataset.value;
        if (sel.has(v)) { sel.delete(v); chip.classList.remove('ms-on'); }
        else if (sel.size < max) { sel.add(v); chip.classList.add('ms-on'); }
        counter.textContent = `${sel.size} / ${max}`;
        // Update chat input with current selection
        if (onSelectionChange) onSelectionChange(Array.from(sel).join(', '));
      });
    });
  }
}
