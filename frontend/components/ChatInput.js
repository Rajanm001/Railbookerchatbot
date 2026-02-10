/**
 * ChatInput Component
 * Professional input area with send button.
 * Clean, fast, no autocomplete dropdown.
 */

export class ChatInput {
  constructor(container, onSend) {
    this.container = container;
    this.onSend = onSend;
    this._acStep = 'destination';
    this.render();
    this.attachEvents();
  }

  render() {
    this.container.innerHTML = `
      <div class="chat-input-area">
        <div class="chat-input-wrapper">
          <textarea 
            class="chat-input" 
            id="chat-textarea"
            placeholder="Type your message..."
            rows="1"
            aria-label="Message input"
            autocomplete="off"
          ></textarea>
          <button 
            class="send-button" 
            id="send-button"
            aria-label="Send message"
            disabled
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
              <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z"/>
            </svg>
          </button>
        </div>
      </div>
    `;
  }

  setStep(step) {
    this._acStep = step;
  }

  attachEvents() {
    const input = this.container.querySelector('#chat-textarea');
    const sendBtn = this.container.querySelector('#send-button');

    // Auto-resize textarea
    input.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 120) + 'px';
      sendBtn.disabled = !input.value.trim();
    });

    // Send on button click
    sendBtn.addEventListener('click', () => {
      this.handleSend();
    });

    // Send on Enter
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (input.value.trim()) {
          this.handleSend();
        }
      }
    });
  }

  handleSend() {
    const input = this.container.querySelector('#chat-textarea');
    const message = input.value.trim();
    
    if (message && this.onSend) {
      this.onSend(message);
      input.value = '';
      input.style.height = 'auto';
      this.container.querySelector('#send-button').disabled = true;
      input.focus();
    }
  }

  disable() {
    const input = this.container.querySelector('#chat-textarea');
    const sendBtn = this.container.querySelector('#send-button');
    input.disabled = true;
    sendBtn.disabled = true;
  }

  enable() {
    const input = this.container.querySelector('#chat-textarea');
    input.disabled = false;
  }

  focus() {
    const input = this.container.querySelector('#chat-textarea');
    input.focus();
  }
}
