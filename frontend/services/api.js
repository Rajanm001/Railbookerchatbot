/**
 * Railbookers - API Service Layer
 * Production-grade with retry, timeout, and graceful error handling.
 * Developed by Rajan Mishra
 */

class APIService {
  constructor() {
    this.baseURL = window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1')
      ? 'http://localhost:8890/api/v1'
      : '/api/v1';
    this.timeout = 20000; // 20s timeout (reduced for faster feedback)
    this.maxRetries = 2;
  }

  /**
   * Fetch with timeout + retry
   */
  async _fetch(url, options = {}, retries = 0) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
      });
      clearTimeout(timer);

      if (!response.ok) {
        if (response.status >= 500 && retries < this.maxRetries) {
          await new Promise(r => setTimeout(r, Math.min(1000 * Math.pow(2, retries), 8000)));
          return this._fetch(url, options, retries + 1);
        }
        throw new Error(`${response.status} ${response.statusText}`);
      }

      return response;
    } catch (error) {
      clearTimeout(timer);
      if (error.name === 'AbortError') {
        throw new Error('Request timed out. Please try again.');
      }
      if (retries < this.maxRetries && !error.message.includes('timed out')) {
        await new Promise(r => setTimeout(r, Math.min(1000 * Math.pow(2, retries), 8000)));
        return this._fetch(url, options, retries + 1);
      }
      throw error;
    }
  }

  /**
   * Send chat message
   */
  async sendMessage(message, userData = {}, sessionId = null, lang = 'en') {
    try {
      const payload = { message, user_data: userData, lang };
      if (sessionId) payload.session_id = sessionId;

      const response = await this._fetch(`${this.baseURL}/planner/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept-Language': lang,
        },
        body: JSON.stringify(payload),
      });

      return await response.json();
    } catch (error) {
      console.error('API Error:', error);
      return {
        success: false,
        message: 'Unable to connect to the server. Please check your connection and try again.',
        error: error.message,
      };
    }
  }

  /**
   * Health check
   */
  async checkHealth() {
    try {
      const base = this.baseURL.replace(/\/api\/v1$/, '');
      const response = await this._fetch(`${base}/api/v1/health`);
      return await response.json();
    } catch (error) {
      return { status: 'unavailable' };
    }
  }
}

export const api = new APIService();
