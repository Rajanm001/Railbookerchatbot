/**
 * ChatMessage Component - Railbookers
 * Message rendering component.
 * Clean, professional, accessible. No emojis.
 */

export class ChatMessage {
  /**
   * Create a message element
   */
  static create(messageData) {
    const { role, content, timestamp, recommendations, actions } = messageData;

    const el = document.createElement('div');
    el.className = `message ${role}`;

    const timeStr = this.formatTime(timestamp || new Date());
    const avatarText = role === 'assistant' ? 'R' : 'You';

    el.innerHTML = `
      <div class="message-avatar ${role}" aria-label="${role === 'assistant' ? 'Railbookers' : 'You'}">${avatarText}</div>
      <div class="message-content">
        <div class="message-bubble ${role}">
          <div class="message-text">${this.formatContent(content)}</div>
          <div class="loading-indicator" style="display: none;">
            <div class="loading-dots">
              <span class="loading-text">Searching packages</span>
              <div class="loading-dot"></div>
              <div class="loading-dot"></div>
              <div class="loading-dot"></div>
            </div>
          </div>
        </div>
        <div class="message-time">${timeStr}</div>
        ${recommendations ? this.renderRecommendations(recommendations) : ''}
        ${actions ? this.renderActions(actions) : ''}
      </div>
    `;

    return el;
  }

  /**
   * Format message content (markdown-like) with XSS protection
   */
  static formatContent(content) {
    if (!content) return '';
    // Escape HTML entities first (XSS protection)
    let safe = content
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
    // Then apply markdown-like formatting on safe text
    return safe
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/  - (.*?)(?=\n|$)/g, '<div class="summary-line">$1</div>')
      .replace(/\n\n/g, '<br><br>')
      .replace(/\n/g, '<br>');
  }

  /**
   * Format timestamp
   */
  static formatTime(date) {
    return date.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  /**
   * Render recommendation cards
   */
  static renderRecommendations(recommendations) {
    if (!recommendations || recommendations.length === 0) return '';

    const cur = (typeof window !== 'undefined' && window.__rb_currency) || '\u00a3';

    const cards = recommendations.slice(0, 5).map((rec, i) => {
      const score = rec.match_score ? Math.min(Math.round(rec.match_score), 100) : 0;
      const desc = rec.description
        ? rec.description.replace(/<[^>]*>/g, '').substring(0, 140)
        : '';
      const highlights = rec.highlights
        ? rec.highlights.replace(/<[^>]*>/g, '').substring(0, 100)
        : '';
      const urlBtn = rec.package_url
        ? `<a href="${rec.package_url}" target="_blank" rel="noopener noreferrer" class="rec-view-btn" onclick="event.stopPropagation()">View Details</a>`
        : '';

      const scoreClass = score >= 70 ? 'score-high' : score >= 40 ? 'score-mid' : 'score-low';

      const durBadge = rec.duration
        ? `<span class="rec-badge rec-badge-duration">${rec.duration}</span>` : '';
      const routeBadge = rec.route
        ? `<span class="rec-badge rec-badge-route">${rec.route}</span>` : '';
      const countriesClean = rec.countries ? rec.countries.replace(/\|/g, ', ').trim() : '';
      const countriesBadge = countriesClean
        ? `<span class="rec-badge rec-badge-country">${countriesClean}</span>` : '';
      const tripBadge = rec.trip_type
        ? `<span class="rec-badge rec-badge-trip">${rec.trip_type.split(',')[0].trim()}</span>` : '';

      // Cities badge
      const citiesClean = rec.cities ? rec.cities.replace(/\|/g, ', ').trim() : '';
      const citiesBadge = citiesClean
        ? `<span class="rec-badge rec-badge-cities">${citiesClean.length > 40 ? citiesClean.substring(0, 40) + '...' : citiesClean}</span>` : '';

      // Hotel tier badge
      let tierBadge = '';
      if (rec.hotel_tier) {
        const tierMap = { Luxury: 'rec-price-tier-luxury', Premium: 'rec-price-tier-premium', Value: 'rec-price-tier-value' };
        const tierCls = tierMap[rec.hotel_tier] || 'rec-price-tier-premium';
        tierBadge = `<span class="rec-price-tier ${tierCls}">${rec.hotel_tier}</span>`;
      }

      // Departure type badge
      let depBadge = '';
      if (rec.departure_type) {
        const depLabel = rec.departure_type === 'Anyday' ? 'Depart any day' : rec.departure_type;
        depBadge = `<span class="rec-badge rec-badge-dep">${depLabel}</span>`;
      }

      // Match reasons
      const reasonsList = (rec.match_reasons && rec.match_reasons.length > 0)
        ? `<div class="rec-reasons">
            <span class="rec-reasons-label">Why this matches:</span>
            ${rec.match_reasons.slice(0, 4).map(r => `<span class="rec-reason-tag">${r}</span>`).join('')}
          </div>` : '';

      const highlightsHtml = highlights
        ? `<p class="rec-highlights">${highlights}...</p>` : '';

      const medal = i === 0 ? 'rec-rank-gold' : i === 1 ? 'rec-rank-silver' : i === 2 ? 'rec-rank-bronze' : '';

      // Sanitize URL to prevent XSS: only allow http/https URLs
      const rawUrl = rec.package_url || '';
      const safeUrl = /^https?:\/\//i.test(rawUrl) ? rawUrl.replace(/"/g, '&quot;') : '';

      return `
        <div class="recommendation-card" data-package-url="${safeUrl}" role="article" aria-label="Package: ${rec.name || 'Rail Vacation'}">
          <div class="rec-rank ${medal}">${i + 1}</div>
          <div class="rec-body">
            <div class="rec-header">
              <div class="rec-title-area">
                <div class="rec-title">${rec.name || 'Rail Vacation Package'}</div>
                <div class="rec-badges">
                  ${durBadge}${tripBadge}${tierBadge}${depBadge}${routeBadge}${countriesBadge}${citiesBadge}
                </div>
              </div>
              <div class="rec-match-score ${scoreClass}">${score}%<span class="score-label">match</span></div>
            </div>
            ${desc ? `<p class="rec-description">${desc}${desc.length >= 138 ? '...' : ''}</p>` : ''}
            ${highlightsHtml}
            ${reasonsList}
            ${urlBtn ? `<div class="rec-actions">${urlBtn}</div>` : ''}
          </div>
        </div>`;
    }).join('');

    return `
      <div class="recommendation-section">
        <div class="rec-section-header">Your Top Matches</div>
        <div class="recommendation-cards">${cards}</div>
        <div class="rec-footer-note">Every journey is fully customisable. Select a package for details or speak with our travel advisors.</div>
      </div>`;
  }

  /**
   * Render action/suggestion buttons
   */
  static renderActions(actions) {
    if (!actions || actions.length === 0) return '';

    const buttons = actions
      .map(
        (a) =>
          `<button class="action-btn" data-action="${a.value || a}" aria-label="Select: ${a.label || a}">${a.label || a}</button>`
      )
      .join('');

    return `<div class="action-buttons">${buttons}</div>`;
  }

  /**
   * Show loading indicator
   */
  static showLoading(el) {
    const text = el.querySelector('.message-text');
    const loading = el.querySelector('.loading-indicator');
    if (text && loading) {
      text.style.display = 'none';
      loading.style.display = 'flex';
    }
  }

  /**
   * Hide loading indicator
   */
  static hideLoading(el) {
    const text = el.querySelector('.message-text');
    const loading = el.querySelector('.loading-indicator');
    if (text && loading) {
      text.style.display = 'block';
      loading.style.display = 'none';
    }
  }
}
