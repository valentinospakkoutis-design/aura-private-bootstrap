// ─── API Layer ────────────────────────────────────────────────────────────────
const BASE = import.meta.env.VITE_AURA_API_URL || '';

// ── Token ──────────────────────────────────────────────────────────────────────
let _token = sessionStorage.getItem('aura_jwt') || null;

export function setToken(t) {
  _token = t;
  if (t) sessionStorage.setItem('aura_jwt', t);
  else   sessionStorage.removeItem('aura_jwt');
}
export function getToken() { return _token; }

// ── Core fetch ────────────────────────────────────────────────────────────────
async function apiFetch(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      ...(_token ? { Authorization: `Bearer ${_token}` } : {}),
      ...(opts.headers || {}),
    },
  });
  if (res.status === 401) {
    setToken(null);
    window.dispatchEvent(new CustomEvent('aura:logout'));
    throw Object.assign(new Error('Session expired'), { status: 401 });
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw Object.assign(new Error(err.detail || res.statusText), { status: res.status });
  }
  return res.json();
}

// ── Auth ──────────────────────────────────────────────────────────────────────
export async function login(email, password) {
  const data = await apiFetch('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  setToken(data.access_token);
  return data;
}

export async function logout() {
  try { await apiFetch('/api/v1/auth/logout', { method: 'POST' }); } catch(_) {}
  setToken(null);
}

// ── XAG endpoints ─────────────────────────────────────────────────────────────
export async function fetchSnapshot() {
  return apiFetch('/api/xag/snapshot');
}

export async function fetchOHLC(tf = '1m', n = 200) {
  return apiFetch(`/api/xag/ohlc?tf=${tf}&n=${n}`);
}

export async function fetchPositions() {
  return apiFetch('/api/xag/positions');
}

export async function fetchSmartScore() {
  return apiFetch('/api/xag/smart-score');
}

export async function fetchSignal() {
  return apiFetch('/api/xag/signal');
}

export async function closePosition(ticket) {
  return apiFetch(`/api/xag/positions/${ticket}/close`, { method: 'POST' });
}

export async function closeBulk(tickets) {
  return apiFetch('/api/xag/positions/close_bulk', {
    method: 'POST',
    body: JSON.stringify({ tickets }),
  });
}

// ── WebSocket ─────────────────────────────────────────────────────────────────
export function createTickWS({ onTick, onStatusChange }) {
  const wsBase = (BASE || location.origin).replace(/^http/, 'ws');
  const url = `${wsBase}/api/xag/ws/tick${_token ? `?token=${_token}` : ''}`;
  let ws, retryDelay = 1000, retryTimer = null, closed = false;

  function connect() {
    onStatusChange('reconnecting');
    ws = new WebSocket(url);
    ws.onopen    = () => { retryDelay = 1000; onStatusChange('connected'); };
    ws.onmessage = (e) => { try { onTick(JSON.parse(e.data)); } catch(_) {} };
    ws.onclose   = () => {
      if (closed) return;
      onStatusChange('reconnecting');
      retryTimer = setTimeout(connect, Math.min(retryDelay, 30000));
      retryDelay = Math.min(retryDelay * 2 + Math.random() * 500, 30000);
    };
  }
  connect();
  return { close: () => { closed = true; clearTimeout(retryTimer); ws?.close(); onStatusChange('disconnected'); } };
}