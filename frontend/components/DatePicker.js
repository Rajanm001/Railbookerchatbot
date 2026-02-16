/**
 * DatePicker - Railbookers
 * Compact date-range calendar. User selects FROM date and TO date.
 * Highlights the range between start and end.
 * Auto-calculates nights. Confirm button.
 * Google Calendar-style mini grid. Max-width 340px.
 */

export class DatePicker {
  static render() {
    const now = new Date();
    // Start from next month for travel planning
    let m = now.getMonth() + 1;
    let y = now.getFullYear();
    if (m > 11) { m = 0; y++; }

    return `
      <div class="cal-widget" data-month="${m}" data-year="${y}" role="group" aria-label="Select travel dates">
        <div class="cal-range-info">
          <span class="cal-range-label">Select your travel dates</span>
          <span class="cal-range-hint">Click start date, then end date</span>
        </div>
        ${DatePicker._buildCalendar(m, y, now)}
        <div class="cal-selected-range" id="cal-range-display" style="display:none;">
          <span class="cal-range-from" id="cal-from-text"></span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14"/><path d="M12 5l7 7-7 7"/></svg>
          <span class="cal-range-to" id="cal-to-text"></span>
          <span class="cal-range-nights" id="cal-nights-text"></span>
        </div>
        <div class="cal-options">
          <button class="cal-confirm" id="cal-confirm" disabled>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
            Confirm
          </button>
        </div>
      </div>`;
  }

  static _buildCalendar(month, year, today) {
    const MO = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const DAYS = ['S','M','T','W','T','F','S'];

    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const td = today.getDate(), tm = today.getMonth(), ty = today.getFullYear();
    const isPast = (year < ty) || (year === ty && month < tm);
    const isCurrentMonth = (year === ty && month === tm);

    const dayHeaders = DAYS.map(d => `<div class="cal-dh">${d}</div>`).join('');

    let cells = '';
    for (let i = 0; i < firstDay; i++) cells += '<div class="cal-c cal-e"></div>';
    for (let d = 1; d <= daysInMonth; d++) {
      const isToday = (d === td && month === tm && year === ty);
      const dayPast = isPast || (isCurrentMonth && d < td);
      const cls = ['cal-c'];
      if (isToday) cls.push('cal-td');
      if (dayPast) cls.push('cal-p');
      cells += `<div class="${cls.join(' ')}" data-day="${d}" data-month="${month}" data-year="${year}"${dayPast ? '' : ' tabindex="0"'}>${d}</div>`;
    }

    let prevDisabled = '';
    let pm = month - 1, py = year;
    if (pm < 0) { pm = 11; py--; }
    if (py < ty || (py === ty && pm < tm)) prevDisabled = ' disabled';

    return `
      <div class="cal-hdr">
        <button class="cal-nav cal-prev" aria-label="Previous month"${prevDisabled}>&#8249;</button>
        <span class="cal-ttl">${MO[month]} ${year}</span>
        <button class="cal-nav cal-next" aria-label="Next month">&#8250;</button>
      </div>
      <div class="cal-grid">${dayHeaders}${cells}</div>`;
  }

  static attachHandlers(container, onConfirm) {
    const w = container.querySelector('.cal-widget');
    if (!w) return;
    const now = new Date();
    let curMonth = parseInt(w.dataset.month);
    let curYear = parseInt(w.dataset.year);

    // Date range state
    let startDate = null;
    let endDate = null;

    const MO_FULL = ['January','February','March','April','May','June',
      'July','August','September','October','November','December'];
    const MO_SHORT = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

    function toDateObj(d) {
      return new Date(d.year, d.month, d.day);
    }

    function daysBetween(a, b) {
      const ms = toDateObj(b) - toDateObj(a);
      return Math.round(ms / (1000 * 60 * 60 * 24));
    }

    function isInRange(day, month, year) {
      if (!startDate || !endDate) return false;
      const d = new Date(year, month, day).getTime();
      const s = toDateObj(startDate).getTime();
      const e = toDateObj(endDate).getTime();
      return d > s && d < e;
    }

    function isSameDate(day, month, year, ref) {
      if (!ref) return false;
      return day === ref.day && month === ref.month && year === ref.year;
    }

    function updateRangeDisplay() {
      const disp = w.querySelector('#cal-range-display');
      const fromEl = w.querySelector('#cal-from-text');
      const toEl = w.querySelector('#cal-to-text');
      const nightsEl = w.querySelector('#cal-nights-text');
      if (!disp) return;

      if (startDate && !endDate) {
        disp.style.display = 'flex';
        fromEl.textContent = `${startDate.day} ${MO_SHORT[startDate.month]}`;
        toEl.textContent = 'Select end date';
        nightsEl.textContent = '';
      } else if (startDate && endDate) {
        const nights = daysBetween(startDate, endDate);
        disp.style.display = 'flex';
        fromEl.textContent = `${startDate.day} ${MO_SHORT[startDate.month]} ${startDate.year}`;
        toEl.textContent = `${endDate.day} ${MO_SHORT[endDate.month]} ${endDate.year}`;
        nightsEl.textContent = `${nights} night${nights !== 1 ? 's' : ''}`;
      } else {
        disp.style.display = 'none';
      }
    }

    function updateHint() {
      const hint = w.querySelector('.cal-range-hint');
      if (!hint) return;
      if (!startDate) {
        hint.textContent = 'Click start date, then end date';
      } else if (!endDate) {
        hint.textContent = 'Now click your end date';
      } else {
        hint.textContent = 'Range selected';
      }
    }

    function refresh() {
      const hdr = w.querySelector('.cal-hdr');
      const grid = w.querySelector('.cal-grid');
      if (!hdr || !grid) return;
      const tmp = document.createElement('div');
      tmp.innerHTML = DatePicker._buildCalendar(curMonth, curYear, now);
      hdr.replaceWith(tmp.querySelector('.cal-hdr'));
      const ng = tmp.querySelector('.cal-grid');
      w.querySelector('.cal-grid').replaceWith(ng);
      applyRangeStyles();
      bind();
      updBtn();
    }

    function applyRangeStyles() {
      w.querySelectorAll('.cal-c:not(.cal-e)').forEach(c => {
        const d = parseInt(c.dataset.day);
        const m = parseInt(c.dataset.month);
        const y = parseInt(c.dataset.year);

        c.classList.remove('cal-start', 'cal-end', 'cal-in-range');

        if (isSameDate(d, m, y, startDate)) {
          c.classList.add('cal-start');
        }
        if (isSameDate(d, m, y, endDate)) {
          c.classList.add('cal-end');
        }
        if (isInRange(d, m, y)) {
          c.classList.add('cal-in-range');
        }
      });
    }

    function bind() {
      const prev = w.querySelector('.cal-prev');
      const next = w.querySelector('.cal-next');
      if (prev) prev.onclick = (e) => {
        e.preventDefault();
        curMonth--;
        if (curMonth < 0) { curMonth = 11; curYear--; }
        if (curYear < now.getFullYear() || (curYear === now.getFullYear() && curMonth < now.getMonth())) {
          curMonth = now.getMonth(); curYear = now.getFullYear();
        }
        refresh();
      };
      if (next) next.onclick = (e) => {
        e.preventDefault();
        curMonth++;
        if (curMonth > 11) { curMonth = 0; curYear++; }
        if (curYear > now.getFullYear() + 2) { curMonth = 11; curYear = now.getFullYear() + 2; }
        refresh();
      };

      w.querySelectorAll('.cal-c:not(.cal-e):not(.cal-p)').forEach(c => {
        c.onclick = () => {
          const d = parseInt(c.dataset.day);
          const m = parseInt(c.dataset.month);
          const y = parseInt(c.dataset.year);

          if (!startDate || (startDate && endDate)) {
            startDate = { day: d, month: m, year: y };
            endDate = null;
          } else {
            const clickedDate = new Date(y, m, d);
            const start = toDateObj(startDate);
            if (clickedDate <= start) {
              startDate = { day: d, month: m, year: y };
              endDate = null;
            } else {
              endDate = { day: d, month: m, year: y };
            }
          }

          applyRangeStyles();
          updateRangeDisplay();
          updateHint();
          updBtn();
        };
      });
    }

    function updBtn() {
      const btn = w.querySelector('#cal-confirm');
      if (btn) btn.disabled = !(startDate && endDate);
    }

    bind();
    updateRangeDisplay();
    updateHint();

    const confirmBtn = w.querySelector('#cal-confirm');
    if (confirmBtn) {
      confirmBtn.onclick = () => {
        if (!startDate || !endDate) return;
        const nights = daysBetween(startDate, endDate);
        const flex = false;
        const msg = `${startDate.day} ${MO_FULL[startDate.month]} ${startDate.year} to ${endDate.day} ${MO_FULL[endDate.month]} ${endDate.year}, ${nights} nights`;
        w.classList.add('cal-done');
        w.querySelectorAll('button, select, input').forEach(el => el.disabled = true);
        if (onConfirm) onConfirm(msg);
      };
    }
  }
}
