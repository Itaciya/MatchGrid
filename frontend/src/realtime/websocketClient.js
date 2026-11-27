const DEFAULTS = {
  url: import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws',
  getToken: () => localStorage.getItem('access_token'),
  baseDelay: 1000,
  maxDelay: 30000,
  heartbeatMs: 25000,
};

export class WebSocketClient {
  constructor(options = {}) {
    this.opts = { ...DEFAULTS, ...options };
    this.ws = null;
    this.status = 'idle';
    this.attempts = 0;
    this.manualClose = false;
    this.listeners = new Map();
    this.statusListeners = new Set();
    this.reconnectTimer = null;
    this.heartbeatTimer = null;
    this.rejectedToken = null;
  }

  connect() {
    if (this.ws && (this.status === 'connecting' || this.status === 'open')) return;

    if (location.protocol === 'https:' && this.opts.url.startsWith('ws://')) {
      this._setStatus('closed');
      console.error('[ws] Refusing insecure ws:// URL on https page. Use wss://');
      return;
    }

    // Signed-in users authenticate with their token and also receive their
    // personal notifications. Everyone else (or a token the server already
    // rejected) joins as a guest, which can still follow public live scores.
    const storedToken = this.opts.getToken?.();
    const token = storedToken && storedToken !== this.rejectedToken ? storedToken : null;

    this.manualClose = false;
    this._setStatus('connecting');
    const ws = new WebSocket(this.opts.url);
    this.ws = ws;

    ws.onopen = () => {
      if (this.ws !== ws) return;
      this.attempts = 0;
      this._send(token ? { type: 'auth', token } : { type: 'auth', anonymous: true });
      this._setStatus('open');
      this._startHeartbeat();
    };

    ws.onmessage = (e) => {
      if (this.ws !== ws) return;
      let msg;
      try { msg = JSON.parse(e.data); } catch { return; }
      if (!msg || !msg.type || msg.type === 'pong') return;
      this.listeners.get(msg.type)?.forEach((fn) => fn(msg.payload, msg));
      this.listeners.get('*')?.forEach((fn) => fn(msg.payload, msg));
    };

    ws.onerror = () => {};

    ws.onclose = (event) => {
      if (this.ws !== ws) return;
      this._stopHeartbeat();
      this.ws = null;
      this._setStatus('closed');
      if (this.manualClose) return;
      // 1008 = the server refused our token: reconnect as a guest now.
      if (event.code === 1008 && token) {
        this.rejectedToken = token;
        this.connect();
        return;
      }
      this._scheduleReconnect();
    };
  }

  // Reconnect with the current credentials, e.g. right after sign-in or out.
  reconnect() {
    this.rejectedToken = null;
    this.disconnect();
    this.connect();
  }

  disconnect() {
    this.manualClose = true;
    clearTimeout(this.reconnectTimer);
    this._stopHeartbeat();
    this.ws?.close(1000, 'client disconnect');
    this.ws = null;
    this._setStatus('closed');
  }

  on(type, fn) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type).add(fn);
    return () => this.listeners.get(type)?.delete(fn);
  }

  onStatus(fn) {
    this.statusListeners.add(fn);
    fn(this.status);
    return () => this.statusListeners.delete(fn);
  }

  send(type, payload) { return this._send({ type, payload }); }

  _send(obj) {
    if (this.ws?.readyState !== WebSocket.OPEN) return false;
    this.ws.send(JSON.stringify(obj));
    return true;
  }

  _setStatus(s) {
    this.status = s;
    this.statusListeners.forEach((fn) => fn(s));
  }

  _scheduleReconnect() {
    clearTimeout(this.reconnectTimer);
    const delay = Math.min(this.opts.baseDelay * 2 ** this.attempts, this.opts.maxDelay);
    const jitter = Math.random() * 300;
    this.attempts += 1;
    this.reconnectTimer = setTimeout(() => this.connect(), delay + jitter);
  }

  _startHeartbeat() {
    this._stopHeartbeat();
    this.heartbeatTimer = setInterval(() => this._send({ type: 'ping' }), this.opts.heartbeatMs);
  }

  _stopHeartbeat() { clearInterval(this.heartbeatTimer); }
}

export const wsClient = new WebSocketClient();
