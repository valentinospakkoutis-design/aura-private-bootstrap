// Backend wire protocol. Reject the whole quote rather than mix different ticks.
export function validQuote(data) {
  return data !== null && typeof data === 'object' && !Array.isArray(data)
    && ['price', 'bid', 'ask'].every(k => typeof data[k] === 'number'
      && Number.isFinite(data[k]) && data[k] > 0) && data.bid <= data.ask;
}

export function applyQuote(state, data) {
  if (!validQuote(data)) return false;
  const asof = data.market_asof ?? data.asof;
  const time = typeof asof === 'string' ? Date.parse(asof) : NaN;
  const previous = Date.parse(state.priceAsof);
  if (Number.isFinite(time) && Number.isFinite(previous) && time < previous) return false;
  Object.assign(state, { price: data.price, bid: data.bid, ask: data.ask });
  if (state.anchor == null) state.anchor = data.price;
  if (Number.isFinite(time)) state.priceAsof = asof;
  return true;
}

export function openTickStream({ url, getToken, onTick, onStatusChange = () => {},
  onBarClose = () => {}, onError = () => {},
  WebSocketImpl = globalThis.WebSocket, schedule = setTimeout, cancel = clearTimeout }) {
  let ws, stopped = false, retryTimer = null, retryDelay = 1000;
  function reconnect() {
    if (stopped || retryTimer !== null) return;
    onStatusChange('reconnecting');
    retryTimer = schedule(() => { retryTimer = null; connect(); }, retryDelay);
    retryDelay = Math.min(retryDelay * 2, 30000);
  }
  function connect() {
    if (stopped) return;
    onStatusChange('reconnecting');
    const token = getToken();
    let socket;
    try { socket = new WebSocketImpl(`${url}${token ? `?token=${encodeURIComponent(token)}` : ''}`); }
    catch { onError({ message: 'WebSocket connection failed' }); reconnect(); return; }
    ws = socket;
    const active = () => !stopped && ws === socket;
    socket.onopen = () => { if (active()) { retryDelay = 1000; onStatusChange('connected'); } };
    socket.onmessage = e => {
      if (!active()) return;
      let msg;
      try { msg = JSON.parse(e.data); } catch { return; }
      if (!msg || typeof msg !== 'object' || Array.isArray(msg)) return;
      switch (msg.type) {
        case 'tick': if (validQuote(msg.data)) onTick(msg.data); break;
        case 'ping': case 'pong': break; // Server heartbeat; no quote data.
        case 'bar_close':
          if (msg.timeframe === '1m' && typeof msg.market_asof === 'string'
              && Number.isFinite(Date.parse(msg.market_asof))) onBarClose(msg);
          break;
        case 'error': onError({ message: typeof msg.message === 'string' ? msg.message : 'Upstream error' }); break;
        default: break;
      }
    };
    socket.onerror = () => { if (active()) onError({ message: 'WebSocket transport error' }); };
    socket.onclose = e => {
      if (!active()) return;
      ws = null;
      if (e.code === 4001) { stopped = true; onStatusChange('disconnected'); return; }
      reconnect();
    };
  }
  connect();
  return { close() {
    if (stopped) return;
    stopped = true;
    cancel(retryTimer); retryTimer = null;
    ws?.close();
    onStatusChange('disconnected');
  } };
}
