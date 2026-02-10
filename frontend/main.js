/**
 * Railbookers Rail Vacation Planner
 * Professional chatbot: fast, compact, smart UX.
 * PRD-strict. No emojis. No progress bar. No step indicators.
 * Blue/yellow/white brand palette. All options from backend database.
 * Text-first input with autocomplete from real DB data.
 */

import { api } from './services/api.js';
import { ChatMessage } from './components/ChatMessage.js';
import { ChatInput } from './components/ChatInput.js';
import { DatePicker } from './components/DatePicker.js';
import { LanguageSwitcher } from './components/LanguageSwitcher.js';

class RailbookersApp {
  constructor() {
    this.messages = [];
    this.sessionId = null;
    this.messagesContainer = null;
    this.input = null;
    this.currentStep = 0;
    this.messageCount = 0;
    this._sending = false; // Debounce flag to prevent duplicate sends
    this._online = true;
    this.init();
  }

  async init() {
    try {
      this.setupErrorHandler();
      this.messagesContainer = document.getElementById('chat-messages');

      // Restore session from localStorage
      this._restoreSession();

      // Expose API base URL for autocomplete component
      window.__rb_api_base = api.baseURL || 'http://localhost:8890/api/v1';

      // Input component
      this.input = new ChatInput(
        document.getElementById('chat-input'),
        (msg) => this.handleUserMessage(msg)
      );

      // Language switcher (always works — no backend needed)
      try {
        const langContainer = document.getElementById('language-switcher');
        if (langContainer) {
          this.langSwitcher = new LanguageSwitcher(langContainer, (lang) => {
            // Show language change notification
            this.addMessage({
              role: 'assistant',
              content: `Language changed to **${lang.name}** (${lang.native}). The next responses will be in ${lang.name}.`,
              timestamp: new Date(),
            });
          });
          await this.langSwitcher.init();
        } else {
          console.warn('[LanguageSwitcher] Container #language-switcher not found');
        }
      } catch (langErr) {
        console.error('[LanguageSwitcher] Init failed:', langErr);
      }

      // Online status indicator in header
      this._addOnlineStatus();

      // Connection health monitor (check every 30s)
      this._startHealthMonitor();

      // Keyboard shortcuts
      document.addEventListener('keydown', (e) => {
        // Ctrl+Shift+R: restart conversation
        if (e.ctrlKey && e.shiftKey && e.key === 'R') {
          e.preventDefault();
          this.handleUserMessage('Plan another trip');
        }
        // Escape: clear input
        if (e.key === 'Escape') {
          const textarea = document.querySelector('#chat-textarea');
          if (textarea && textarea.value) {
            textarea.value = '';
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
          }
        }
      });

      // Welcome
      await this.showWelcome();
    } catch (error) {
      console.error('Init error:', error);
      this.showErrorInChat('Failed to initialize. Please refresh the page.');
    }
  }

  _addOnlineStatus() {
    const tagline = document.querySelector('.brand-tagline');
    if (tagline) {
      tagline.innerHTML = '<span class="online-dot"></span>Your Rail Vacation Planner';
    }
  }

  _setTypingStatus(typing) {
    const tagline = document.querySelector('.brand-tagline');
    if (!tagline) return;
    if (typing) {
      tagline.innerHTML = '<span class="online-dot typing-pulse"></span><span class="typing-text">Searching packages</span>';
    } else {
      tagline.innerHTML = `<span class="online-dot${this._online ? '' : ' offline-dot'}"></span>Your Rail Vacation Planner`;
    }
  }

  _startHealthMonitor() {
    setInterval(async () => {
      try {
        const resp = await fetch(
          (api.baseURL || 'http://localhost:8890/api/v1') + '/planner/health',
          { signal: AbortSignal.timeout(5000) }
        );
        if (resp.ok) {
          if (!this._online) {
            this._online = true;
            this._setTypingStatus(false);
          }
        } else {
          this._online = false;
          this._setTypingStatus(false);
        }
      } catch {
        this._online = false;
        this._setTypingStatus(false);
      }
    }, 30000);
  }

  // Session persistence: save/restore to localStorage
  _saveSession() {
    try {
      localStorage.setItem('rb_session_id', this.sessionId || '');
      localStorage.setItem('rb_step', String(this.currentStep));
    } catch { /* localStorage unavailable */ }
  }

  _restoreSession() {
    try {
      const sid = localStorage.getItem('rb_session_id');
      const step = localStorage.getItem('rb_step');
      if (sid) {
        this.sessionId = sid;
        this.currentStep = parseInt(step || '0', 10);
      }
    } catch { /* localStorage unavailable */ }
  }

  _clearSession() {
    try {
      localStorage.removeItem('rb_session_id');
      localStorage.removeItem('rb_step');
    } catch { /* localStorage unavailable */ }
  }

  async showWelcome() {
    let packageCount = 0;
    let countries = [];
    try {
      const resp = await api._fetch(
        (api.baseURL || 'http://localhost:8890/api/v1') + '/planner/flow/welcome'
      );
      if (resp.ok) {
        const data = await resp.json();
        packageCount = data.packages_available || 0;
        countries = data.suggestions || [];
      }
    } catch (_) { /* fallback */ }

    const countText = packageCount > 0
      ? packageCount.toLocaleString()
      : 'thousands of';

    const welcomeMsg = {
      role: 'assistant',
      content:
        `Welcome to **Railbookers**. I will find your perfect rail vacation from **${countText} curated packages** across 50+ countries.\n\n` +
        `**Where would you like to go?**\n` +
        `Type a country, city, or region below.`,
      timestamp: new Date(),
      actions: null,
    };
    this.addMessage(welcomeMsg);

    // Set autocomplete step context
    this.input.setStep('destination');
    this.updatePlaceholder('e.g. Italy, Swiss Alps, Tokyo...');
  }

  updatePlaceholder(text) {
    const input = document.querySelector('#chat-input .chat-input') || document.querySelector('#chat-textarea');
    if (input) input.placeholder = text;
  }

  async handleUserMessage(message) {
    // Debounce guard: prevent duplicate sends
    if (this._sending) return;
    this._sending = true;

    // Disable any active widgets (MultiSelect, DatePicker, suggestion buttons)
    this._disableActiveWidgets();

    // User message
    this.addMessage({
      role: 'user',
      content: message,
      timestamp: new Date(),
    });

    this.input.disable();
    this._setTypingStatus(true);

    // Loading bubble
    const loadingMsg = {
      role: 'assistant',
      content: '',
      timestamp: new Date(),
    };
    const loadingEl = this.addMessage(loadingMsg);
    ChatMessage.showLoading(loadingEl);

    try {
      const lang = window.__rb_lang?.code || 'en';
      const response = await api.sendMessage(message, {}, this.sessionId, lang);

      if (response.session_id) this.sessionId = response.session_id;
      if (response.step_number != null) {
        this.currentStep = response.step_number;
        // Save session after every step update
        this._saveSession();
        // Update autocomplete context based on step
        const stepMap = {
          1: 'destination', 2: 'destination', 3: 'duration',
          4: 'trip_type', 5: 'destination', 6: 'hotel_tier',
          7: 'destination', 8: 'destination', 9: 'destination',
        };
        this.input.setStep(stepMap[this.currentStep] || 'destination');
      }

      // Auto-detect currency from destination country (sent by backend after step 1)
      if (response.currency_sym) {
        window.__rb_currency = response.currency_sym;
        window.__rb_currency_code = response.currency_code || 'GBP';
      }

      if (response.placeholder) {
        this.updatePlaceholder(response.placeholder);
      } else {
        this.updatePlaceholder('Type your response...');
      }

      // Hide loading, show content
      ChatMessage.hideLoading(loadingEl);
      const textEl = loadingEl.querySelector('.message-text');
      if (textEl) {
        textEl.innerHTML = ChatMessage.formatContent(response.message || '');
      }

      // Recommendation cards
      if (response.recommendations && response.recommendations.length > 0) {
        const recsHtml = ChatMessage.renderRecommendations(response.recommendations);
        loadingEl.querySelector('.message-content').insertAdjacentHTML('beforeend', recsHtml);
        this.attachRecCardHandlers(loadingEl);
        // Delayed scroll to ensure cards are rendered before scrolling
        setTimeout(() => this.scrollToBottom(), 350);
      }

      // Date picker for step 3 (travel dates/duration)
      if (this.currentStep === 3 && !response.recommendations) {
        const dpHtml = DatePicker.render();
        loadingEl.querySelector('.message-content').insertAdjacentHTML('beforeend', dpHtml);
        DatePicker.attachHandlers(loadingEl, (dateStr) => {
          this._populateInput(dateStr);
        });
      }

      // Suggestion buttons for all steps (quick-pick helpers, user can also type)
      if (response.suggestions && response.suggestions.length > 0) {
        const actions = response.suggestions.map(s => ({ label: s, value: s }));
        const actionsHtml = ChatMessage.renderActions(actions);
        loadingEl.querySelector('.message-content').insertAdjacentHTML('beforeend', actionsHtml);
        this.attachActionHandlers(loadingEl);
      }
    } catch (error) {
      console.error('Error:', error);
      ChatMessage.hideLoading(loadingEl);
      const textEl = loadingEl.querySelector('.message-text');
      if (textEl) {
        const isTimeout = error.message && error.message.includes('timed out');
        const msg = isTimeout
          ? 'The request took too long. Please try again.'
          : 'Unable to connect to the server. Please check your connection and try again.';
        textEl.innerHTML =
          `<span style="color:#c53030;">${msg}</span>` +
          '<div class="action-buttons" style="margin-top:0.5rem">' +
          '<button class="action-btn" data-action="__retry__">Try again</button></div>';
        // Attach retry handler
        const retryBtn = textEl.querySelector('[data-action="__retry__"]');
        if (retryBtn) {
          retryBtn.addEventListener('click', () => {
            loadingEl.remove();
            this.messages.pop(); // remove error message
            this.messages.pop(); // remove user message
            this.input.enable();
            this.input.focus();
          });
        }
      }
    } finally {
      this._setTypingStatus(false);
      this._sending = false;
      this.input.enable();
      this.input.focus();
    }
  }

  addMessage(messageData) {
    const el = ChatMessage.create(messageData);
    // Staggered animation delay for visual polish
    this.messageCount++;
    el.style.animationDelay = `${Math.min(this.messageCount * 50, 200)}ms`;
    this.messagesContainer.appendChild(el);
    this.attachActionHandlers(el);
    this.attachRecCardHandlers(el);
    this.messages.push(messageData);
    this.scrollToBottom();
    return el;
  }

  attachActionHandlers(container) {
    const buttons = container.querySelectorAll('.action-btn');
    // Actions that should auto-send (not populate input)
    const autoSendLabels = new Set([
      'plan another trip', 'modify preferences', 'speak with an advisor',
      'find my perfect trips', 'search now', 'continue',
      // Translated equivalents
      'planifier un autre voyage', 'modifier les préférences', 'parler à un conseiller',
      'trouver mes voyages parfaits', 'rechercher maintenant', 'continuer',
      'planificar otro viaje', 'modificar preferencias', 'hablar con un asesor',
      'encontrar mis viajes perfectos', 'buscar ahora', 'continuar',
      'weitere reise planen', 'einstellungen ändern', 'mit einem berater sprechen',
      'meine perfekten reisen finden', 'jetzt suchen', 'weiter',
      'pianifica un altro viaggio', 'modifica preferenze', 'parla con un consulente',
      'trova i miei viaggi perfetti', 'cerca ora', 'continua',
    ]);
    buttons.forEach((btn) => {
      if (btn.dataset.attached) return;
      btn.dataset.attached = '1';
      btn.addEventListener('click', () => {
        const action = btn.getAttribute('data-action');
        if (action === '__retry__') return; // handled separately
        if (autoSendLabels.has(action.toLowerCase())) {
          // Auto-send command: disable all buttons and send immediately
          container.querySelectorAll('.action-btn').forEach((b) => {
            b.disabled = true;
            b.classList.add('action-btn-used');
          });
          this.handleUserMessage(action);
        } else {
          // Populate input: highlight active button, let user edit and press Enter
          container.querySelectorAll('.action-btn').forEach(b => b.classList.remove('action-btn-active'));
          btn.classList.add('action-btn-active');
          this._populateInput(action);
        }
      });
    });
  }

  /**
   * Populate the chat input textarea with text (from chip/button clicks).
   * User can edit the text and press Enter to send.
   */
  _populateInput(text) {
    const textarea = document.querySelector('#chat-textarea') ||
                     document.querySelector('.chat-input');
    if (textarea) {
      textarea.value = text;
      textarea.focus();
      // Trigger input event for auto-resize / state sync
      textarea.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }

  /**
   * Disable all active interactive widgets (MultiSelect, DatePicker, suggestion buttons)
   * when a message is sent, so old widgets become inert.
   */
  _disableActiveWidgets() {
    // Disable DatePicker widgets
    document.querySelectorAll('.cal-widget:not(.cal-done)').forEach(w => {
      w.classList.add('cal-done');
      w.querySelectorAll('button, input').forEach(el => el.disabled = true);
    });
    // Disable active suggestion buttons
    document.querySelectorAll('.action-btn:not(.action-btn-used)').forEach(b => {
      b.disabled = true;
      b.classList.add('action-btn-used');
    });
  }

  attachRecCardHandlers(container) {
    const cards = container.querySelectorAll('.recommendation-card');
    cards.forEach((card) => {
      if (card.dataset.attached) return;
      card.dataset.attached = '1';
      card.addEventListener('click', (e) => {
        if (e.target.closest('.rec-view-btn')) return;
        const url = card.getAttribute('data-package-url');
        if (url && url !== '' && url !== '#') {
          window.open(url, '_blank', 'noopener,noreferrer');
        }
      });
    });
  }

  scrollToBottom() {
    requestAnimationFrame(() => {
      this.messagesContainer.scrollTo({
        top: this.messagesContainer.scrollHeight,
        behavior: 'smooth',
      });
    });
  }

  showErrorInChat(message) {
    this.addMessage({
      role: 'assistant',
      content: message,
      timestamp: new Date(),
    });
  }

  setupErrorHandler() {
    window.addEventListener('unhandledrejection', (e) => {
      console.error('Unhandled rejection:', e.reason);
    });
  }
}

document.addEventListener('DOMContentLoaded', () => {
  new RailbookersApp();
});
