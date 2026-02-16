/**
 * MultiSelect - Railbookers
 * Clean chip selector: click to select, auto-populates input.
 * Max 4 selections. No confirm button - natural chat flow.
 */
export class MultiSelect {
  static render(options, config = {}) {
    const max = config.maxSelect || 4;
    const chips = options.slice(0, 20).map((opt, i) => {
      const val = opt.value || opt.label || opt;
      const lbl = opt.label || opt;
      return `<button class="ms-chip" data-value="${val}">${lbl}</button>`;
    }).join('');

    return `
      <div class="multi-select" data-max="${max}">
        <div class="ms-header">
          <span class="ms-hint">Select up to ${max} destinations</span>
          <span class="ms-count">0/${max}</span>
        </div>
        <div class="ms-chips">${chips}</div>
      </div>`;
  }

  static attachHandlers(container, onUpdate) {
    const widget = container.querySelector('.multi-select');
    if (!widget) return;
    
    const max = parseInt(widget.dataset.max) || 4;
    const chips = widget.querySelectorAll('.ms-chip');
    const countEl = widget.querySelector('.ms-count');
    const selected = new Set();

    chips.forEach(chip => {
      chip.addEventListener('click', () => {
        const val = chip.dataset.value;
        
        if (selected.has(val)) {
          selected.delete(val);
          chip.classList.remove('selected');
        } else if (selected.size < max) {
          selected.add(val);
          chip.classList.add('selected');
        }
        
        countEl.textContent = `${selected.size}/${max}`;
        
        const text = Array.from(selected).join(', ');
        if (onUpdate) onUpdate(text);
      });
    });
  }
}
