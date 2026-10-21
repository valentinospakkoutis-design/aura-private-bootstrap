import { normalizeQuote } from './quotes.js';

// Dependencies are injectable so reconnect and shutdown can be tested without a server.
export function openTickStream({ url, onTick, onStatusChange = () => {},
  onBarClose = () => {}, onError = () => {},
  WebSocketImpl = globalThis.WebSocket, schedule = setTimeout,
  cancel = clearTimeout, random = Math.random }) {
  let ws, stopped = false, retryDelay = 1000, retryTimer = null;

  function connect() {
    if (stopped) return;
    retryTimer = null;
    onStatusChange('reconnecting');
    let socket;
    try {
      socket = new WebSocketImpl(url());
    } catch {
      onError({ type: 'error', message: 'WebSocket connection failed' });
      reconnect();
      return;
    }
    ws = socket;
    const active = () => !stopped && ws === socket;
    socket.onopen = () => {
      if (!active()) return;
      retryDelay = 1000;
      onStatusChange('connected');
    };
    socket.onmessage = (event) => {
      if (!active()) return;
      let message;
      try { message = JSON.parse(event.data); } catch { return; }
      if (!message || typeof message !== 'object' || Array.isArray(message)) return;
      switch (message.type) {
        case 'tick': {
          const quote = normalizeQuote(message.data);
          if (quote) onTick(quote);
          break;
        }
        case 'ping':
        case 'pong':
          // Server keepalives require no response; no quote mutation.
          break;
        case 'bar_close':
          onBarClose(message);
          break;
        case 'error':
          onError(message);
          break;
        default:
          break;
      }
    };
    socket.onerror = () => {
      if (active()) onError({ type: 'error', message: 'WebSocket transport error' });
      // The browser follows a transport failure with close; only close schedules retry.
    };
    socket.onclose = () => {
      if (!active()) return;
      ws = null;
      reconnect();
    };
  }
  function reconnect() {
    if (stopped || retryTimer !== null) return;
    onStatusChange('reconnecting');
    retryTimer = schedule(connect, retryDelay);
    retryDelay = Math.min(retryDelay * 2 + random() * 500, 30000);
  }
  connect();
  return { close() {
    if (stopped) return;
    stopped = true;
    cancel(retryTimer);
    retryTimer = null;
    const socket = ws;
    ws = null;
    socket?.close();
    onStatusChange('disconnected');
  } };
}
