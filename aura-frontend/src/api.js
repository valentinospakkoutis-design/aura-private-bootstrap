// ─── API Layer ────────────────────────────────────────────────────────────────
// All backend calls go through here.
// Phase 1: stubs returning simulated data (no backend yet).
// Phase 2+: replace each function body with a real fetch().

const BASE = import.meta.env.VITE_AURA_API_URL || 'http://localhost:8080';

// ── Auth ──────────────────────────────────────────────────────────────────────
// JWT token storage — set after login
let _token = localStorage.getItem('aura_jwt') || null;

export function setToken(token) {
  _token = token;
  if (token) localStorage.setItem('aura_jwt', token);
  else        localStorage.removeItem('aura_jwt');
}

function authHeaders() {
  return _token ? { Authorization: `Bearer ${_token}` } : {};
}

// ── Core fetch helper ─────────────────────────────────────────────────────────
async function apiFetch(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...opts.headers },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw Object.assign(new Error(err.detail || res.statusText), { status: res.status });
  }
  return res.json();
}

// ── XAG endpoints ─────────────────────────────────────────────────────────────

/**
 * GET /api/xag/snapshot
 * Returns: { symbol, price, bid, ask, rsi_1m, rsi_15m, rsi_1h, asof }
 *
 * Phase 1 stub — returns simulated data.
 * Phase 2: uncomment the fetch, remove the stub block.
 */
export async function fetchSnapshot() {
  // ── Phase 2: real backend ─────────────────────────────
  // return apiFetch('/api/xag/snapshot');
  // ─────────────────────────────────────────────────────

  // ── Phase 1 stub ──────────────────────────────────────
  await delay(300);
  const base = 31.85 + (Math.random() - 0.5) * 0.4;
  const spread = 0.025;
  return {
    symbol: 'XAGUSD-STD',
    price:   base,
    bid:     base - spread / 2,
    ask:     base + spread / 2,
    rsi_1m:  simRSI(),
    rsi_15m: simRSI(),
    rsi_1h:  simRSI(),
    asof:    new Date().toISOString(),
    _stub:   true,
  };
  // ─────────────────────────────────────────────────────
}

/**
 * GET /api/xag/ohlc?tf=1m&n=200
 * Returns: [{ time, open, high, low, close, volume }, ...]
 *
 * Phase 1 stub — generates random-walk bars.
 * Phase 3: replace with real fetch.
 */
export async function fetchOHLC(tf = '1m', n = 200) {
  // ── Phase 3: real backend ─────────────────────────────
  // return apiFetch(`/api/xag/ohlc?tf=${tf}&n=${n}`);
  // ─────────────────────────────────────────────────────

  // ── Phase 1 stub ──────────────────────────────────────
  await delay(200);
  return generateDemoBars(tf, n);
  // ─────────────────────────────────────────────────────
}

/**
 * GET /api/xag/positions
 * Returns: [{ ticket, symbol, side, volume, open_price, current_price,
 *             profit, swap, commission, opened_at }, ...]
 *
 * Phase 1 stub — returns sample positions.
 * Phase 5: replace with real fetch.
 */
export async function fetchPositions() {
  // ── Phase 5: real backend ─────────────────────────────
  // return apiFetch('/api/xag/positions');
  // ─────────────────────────────────────────────────────

  // ── Phase 1 stub ──────────────────────────────────────
  await delay(150);
  return SAMPLE_POSITIONS;
  // ─────────────────────────────────────────────────────
}

/**
 * POST /api/xag/positions/{ticket}/close
 * Phase 5: real backend.
 */
export async function closePosition(ticket) {
  // ── Phase 5: real backend ─────────────────────────────
  // return apiFetch(`/api/xag/positions/${ticket}/close`, { method: 'POST' });
  // ─────────────────────────────────────────────────────

  // ── Phase 1 stub ──────────────────────────────────────
  await delay(400);
  return { success: true, ticket };
  // ─────────────────────────────────────────────────────
}

/**
 * POST /api/xag/positions/close_bulk
 * Body: { tickets: [int, ...] }
 * Phase 5: real backend.
 */
export async function closeBulk(tickets) {
  // ── Phase 5: real backend ─────────────────────────────
  // return apiFetch('/api/xag/positions/close_bulk', {
  //   method: 'POST',
  //   body: JSON.stringify({ tickets }),
  // });
  // ─────────────────────────────────────────────────────

  // ── Phase 1 stub ──────────────────────────────────────
  await delay(600);
  return tickets.map(t => ({ success: true, ticket: t }));
  // ─────────────────────────────────────────────────────
}

// ── WebSocket factory ─────────────────────────────────────────────────────────
/**
 * Phase 4: real WS connection with exponential backoff.
 * Returns a controller object: { close() }
 */
export function createTickWS({ onTick, onStatusChange }) {
  // ── Phase 4: real WebSocket ───────────────────────────
  // const WS_BASE = import.meta.env.VITE_AURA_WS_URL || BASE.replace(/^http/, 'ws');
  // let ws, retryDelay = 1000, retryTimer = null;
  //
  // function connect() {
  //   onStatusChange('reconnecting');
  //   ws = new WebSocket(`${WS_BASE}/api/xag/ws/tick`);
  //   ws.onopen = () => { retryDelay = 1000; onStatusChange('connected'); };
  //   ws.onmessage = (e) => onTick(JSON.parse(e.data));
  //   ws.onclose = () => {
  //     onStatusChange('reconnecting');
  //     retryTimer = setTimeout(connect, Math.min(retryDelay, 30000));
  //     retryDelay = Math.min(retryDelay * 2 + Math.random() * 500, 30000);
  //   };
  // }
  // connect();
  // return { close: () => { clearTimeout(retryTimer); ws?.close(); } };
  // ─────────────────────────────────────────────────────

  // ── Phase 1 stub — drift simulation ──────────────────
  onStatusChange('connected');
  let running = true;
  let _price = 31.85;

  (async () => {
    while (running) {
      await delay(1500);
      if (!running) break;
      _price += (Math.random() - 0.5) * 0.008;
      const spread = 0.025;
      onTick({ bid: _price - spread / 2, ask: _price + spread / 2, time: Date.now() });
    }
  })();

  return { close: () => { running = false; onStatusChange('disconnected'); } };
  // ─────────────────────────────────────────────────────
}

// ── Internal helpers ──────────────────────────────────────────────────────────

function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

function simRSI() { return 30 + Math.random() * 40; }

const TF_SECONDS = { '1m': 60, '5m': 300, '15m': 900, '1h': 3600 };

function generateDemoBars(tf, n) {
  const sec = TF_SECONDS[tf] ?? 60;
  const now = Math.floor(Date.now() / 1000);
  let close = 31.85;
  const bars = [];
  for (let i = n - 1; i >= 0; i--) {
    const time = now - i * sec;
    const open  = close;
    const move  = (Math.random() - 0.48) * 0.12;
    close = Math.max(29, Math.min(35, open + move));
    const high = Math.max(open, close) + Math.random() * 0.06;
    const low  = Math.min(open, close) - Math.random() * 0.06;
    bars.push({ time, open: +open.toFixed(4), high: +high.toFixed(4),
                low:  +low.toFixed(4),  close: +close.toFixed(4), volume: Math.floor(Math.random() * 200 + 50) });
  }
  return bars;
}

// Sample positions for Phase 1
const SAMPLE_POSITIONS = [
  { ticket: 1001, symbol: 'XAGUSD-STD', side: 'BUY',  volume: 0.50, open_price: 31.620, profit:  null, swap: -1.20, commission: -0.50, opened_at: '2026-10-17T08:15:00Z' },
  { ticket: 1002, symbol: 'XAGUSD-STD', side: 'SELL', volume: 0.25, open_price: 32.150, profit:  null, swap: -0.60, commission: -0.25, opened_at: '2026-10-17T10:30:00Z' },
  { ticket: 1003, symbol: 'XAUUSD-STD', side: 'BUY',  volume: 0.10, open_price: 3281.00, profit: 142.50, swap: -3.10, commission: -1.00, opened_at: '2026-10-16T14:00:00Z' },
  { ticket: 1004, symbol: 'EURUSD',     side: 'SELL', volume: 1.00, open_price: 1.08450, profit:  -38.20, swap: 2.10, commission: -3.00, opened_at: '2026-10-15T09:00:00Z' },
  { ticket: 1005, symbol: 'BTCUSD',     side: 'BUY',  volume: 0.01, open_price: 67400.00, profit: 84.00, swap: -12.50, commission: -2.00, opened_at: '2026-10-14T16:45:00Z' },
];
