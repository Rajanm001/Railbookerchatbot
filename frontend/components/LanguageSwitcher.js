/**
 * LanguageSwitcher - Railbookers
 * LANGUAGE-ONLY selector in header. Changes chatbot display language.
 * Currency is separate — determined by destination country in chat flow.
 * Globe icon + language name. Clean, compact.
 */

const LANGUAGES = [
  { code: 'en', name: 'English',    native: 'English' },
  { code: 'hi', name: 'Hindi',      native: 'हिन्दी' },
  { code: 'fr', name: 'French',     native: 'Français' },
  { code: 'es', name: 'Spanish',    native: 'Español' },
  { code: 'de', name: 'German',     native: 'Deutsch' },
  { code: 'ja', name: 'Japanese',   native: '日本語' },
  { code: 'zh', name: 'Chinese',    native: '中文' },
  { code: 'pt', name: 'Portuguese', native: 'Português' },
  { code: 'it', name: 'Italian',    native: 'Italiano' },
  { code: 'ar', name: 'Arabic',     native: 'العربية' },
];

const GLOBE_SVG = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>`;

export class LanguageSwitcher {
  constructor(container, onLanguageChange) {
    this.container = container;
    this.onLanguageChange = onLanguageChange;
    const saved = localStorage.getItem('rb-lang') || 'en';
    this.current = LANGUAGES.find(l => l.code === saved) || LANGUAGES[0];
    this.isOpen = false;
    this._onDocClick = this._onDocClick.bind(this);
  }

  async init() {
    this._applyLanguage();
    this.render();
    this.attachEvents();
  }

  _applyLanguage() {
    window.__rb_lang = this.current;
    document.documentElement.lang = this.current.code;
  }

  render() {
    const items = LANGUAGES.map(l => `
      <button class="lang-opt${l.code === this.current.code ? ' lang-active' : ''}"
              data-code="${l.code}" role="menuitem">
        <span class="lang-code-badge">${l.code.toUpperCase()}</span>
        <span class="lang-name">${l.name}</span>
        <span class="lang-native">${l.native}</span>
      </button>`).join('');

    this.container.innerHTML = `
      <div class="language-switcher">
        <button class="language-btn" aria-label="Change language" aria-expanded="false">
          ${GLOBE_SVG}
          <span class="current-lang-code">${this.current.name}</span>
          <svg class="lang-chevron" width="10" height="10" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="3"><polyline points="6 9 12 15 18 9"/></svg>
        </button>
        <div class="language-dropdown" role="menu">${items}</div>
      </div>`;
  }

  attachEvents() {
    const btn = this.container.querySelector('.language-btn');
    const drop = this.container.querySelector('.language-dropdown');
    if (!btn || !drop) return;

    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      this.isOpen = !this.isOpen;
      drop.classList.toggle('active', this.isOpen);
      btn.setAttribute('aria-expanded', String(this.isOpen));
    });

    this.container.querySelectorAll('.lang-opt').forEach(opt => {
      opt.addEventListener('click', () => {
        const lang = LANGUAGES.find(l => l.code === opt.dataset.code);
        if (!lang || lang.code === this.current.code) {
          this.isOpen = false;
          drop.classList.remove('active');
          btn.setAttribute('aria-expanded', 'false');
          return;
        }
        this.current = lang;
        localStorage.setItem('rb-lang', lang.code);
        this._applyLanguage();
        this.isOpen = false;
        this.render();
        this.attachEvents();
        if (this.onLanguageChange) this.onLanguageChange(lang);
      });
    });

    document.removeEventListener('click', this._onDocClick);
    document.addEventListener('click', this._onDocClick);
  }

  _onDocClick(e) {
    const sw = this.container.querySelector('.language-switcher');
    if (sw && !sw.contains(e.target) && this.isOpen) {
      this.isOpen = false;
      const d = this.container.querySelector('.language-dropdown');
      const b = this.container.querySelector('.language-btn');
      if (d) d.classList.remove('active');
      if (b) b.setAttribute('aria-expanded', 'false');
    }
  }

  /** Currency is now set by destination, not language switcher */
  static getCurrency() {
    return window.__rb_currency || '\u00a3';
  }

  static getCurrencyCode() {
    return window.__rb_currency_code || 'GBP';
  }

  destroy() {
    document.removeEventListener('click', this._onDocClick);
  }
}
