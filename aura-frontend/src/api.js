// ─── API Layer ────────────────────────────────────────────────────────────────
const BASE = import.meta.env.VITE_AURA_API_URL || '';

// ── Token ──────────────────────────────────────────────────────────────────────
let _token = sessionStorage.getItem('aura_jwt') || null;
let _refreshToken = sessionStorage.getItem('aura_refresh') || null;
let _tokenExpiry = Number(sessionStorage.getItem('aura_jwt_exp') || 0);
let _refreshing = null; // in-flight refresh promise (dedupe)

export function setToken(t, refresh = null, expiresIn = 3600) {
  _token = t;
  _refreshToken = refresh ?? _refreshToken;
  _tokenExpiry = t ? Date.now() + expiresIn * 1000 : 0;
  if (t) {
    sessionStorage.setItem('aura_jwt', t);
    sessionStorage.setItem('aura_jwt_exp', String(_tokenExpiry));
  } else {
    sessionStorage.removeItem('aura_jwt');
    sessionStorage.removeItem('aura_jwt_exp');
  }
  if (refresh) sessionStorage.setItem('aura_refresh', refresh);
  else if (!t) sessionStorage.removeItem('aura_refresh');
}
export function getToken() { return _token; }

// ── Silent refresh ─────────────────────────────────────────────────────────────
async function _doRefresh() {
  if (!_refreshToken) throw new Error('No refresh token');
  const res = await fetch(`${BASE}/api/v1/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: _refreshToken }),
  });
  if (!res.ok) {
    setToken(null, null);
    window.dispatchEvent(new CustomEvent('aura:logout'));
    throw Object.assign(new Error('Session expired'), { status: 401 });
  }
  const data = await res.json();
  setToken(data.access_token, data.refresh_token ?? _refreshToken, data.expires_in ?? 3600);
  return data.access_token;
}

async function ensureFreshToken() {
  if (!_token) return;
  // proactive refresh: if token expires in < 5 min, refresh now
  if (_tokenExpiry && Date.now() < _tokenExpiry - 5 * 60 * 1000) return;
  if (!_refreshing) _refreshing = _doRefresh().finally(() => { _refreshing = null; });
  await _refreshing;
}

// ── Core fetch ────────────────────────────────────────────────────────────────
async function apiFetch(path, opts = {}, _retry = true) {
  await ensureFreshToken();
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      ...(_token ? { Authorization: `Bearer ${_token}` } : {}),
      ...(opts.headers || {}),
    },
  });
  if (res.status === 401 && _retry && _refreshToken) {
    try {
      if (!_refreshing) _refreshing = _doRefresh().finally(() => { _refreshing = null; });
      await _refreshing;
      return apiFetch(path, opts, false);
    } catch (_) {
      throw Object.assign(new Error('Session expired'), { status: 401 });
    }
  }
  if (res.status === 401) {
    setToken(null, null);
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
  setToken(data.access_token, data.refresh_token ?? null, data.expires_in ?? 3600);
  return data;
}

export async function logout() {
  try { await apiFetch('/api/v1/auth/logout', { method: 'POST' }); } catch(_) {}
  setToken(null, null);
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
  let ws, retryDelay = 1000, retryTimer = null, closed = false;

  function connect() {
    onStatusChange('reconnecting');
    const url = `${wsBase}/api/xag/ws/tick${_token ? `?token=${_token}` : ''}`;
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
