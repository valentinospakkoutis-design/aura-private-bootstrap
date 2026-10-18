// --- API Layer ---
// Phase 2: fetchSnapshot + fetchOHLC call real backend.
// Phase 4: createTickWS uses real WebSocket.
// Phase 5: fetchPositions / closePosition / closeBulk still stubbed.

const BASE = import.meta.env.VITE_AURA_API_URL || "";

// -- Auth --
let _token = localStorage.getItem("aura_jwt") || null;

export function setToken(token) {
  _token = token;
  if (token) localStorage.setItem("aura_jwt", token);
  else        localStorage.removeItem("aura_jwt");
}

function authHeaders() {
  return _token ? { Authorization: `Bearer ${_token}` } : {};
}

// -- Core fetch helper --
async function apiFetch(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", ...authHeaders(), ...opts.headers },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw Object.assign(new Error(err.detail || res.statusText), { status: res.status });
  }
  return res.json();
}

// -- XAG endpoints --

export async function fetchSnapshot() {
  return apiFetch("/api/xag/snapshot");
}

export async function fetchOHLC(tf = "1m", n = 200) {
  return apiFetch(`/api/xag/ohlc?tf=${tf}&n=${n}`);
}

// Phase 5 stubs
export async function fetchPositions() {
  await delay(150);
  return SAMPLE_POSITIONS;
}

export async function closePosition(ticket) {
  await delay(400);
  return { success: true, ticket };
}

export async function closeBulk(tickets) {
  await delay(600);
  return tickets.map(t => ({ success: true, ticket: t }));
}

// -- WebSocket factory --
export function createTickWS({ onTick, onStatusChange }) {
  const WS_BASE = import.meta.env.VITE_AURA_WS_URL || BASE.replace(/^http/, "ws");
  let ws, retryDelay = 1000, retryTimer = null;

  function connect() {
    onStatusChange("reconnecting");
    const token = _token ? `?token=${encodeURIComponent(_token)}` : "";
    ws = new WebSocket(`${WS_BASE}/api/xag/ws/tick${token}`);
    ws.onopen = () => { retryDelay = 1000; onStatusChange("connected"); };
    ws.onmessage = (e) => onTick(JSON.parse(e.data));
    ws.onclose = () => {
      onStatusChange("reconnecting");
      retryTimer = setTimeout(connect, Math.min(retryDelay, 30000));
      retryDelay = Math.min(retryDelay * 2 + Math.random() * 500, 30000);
    };
  }
  connect();
  return { close: () => { clearTimeout(retryTimer); ws?.close(); } };
}

// -- Internal helpers --
function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

const SAMPLE_POSITIONS = [
  {
    ticket: 100001, symbol: "XAGUSD-STD", side: "BUY",
    volume: 0.5, open_price: 31.50, current_price: 31.85,
    profit: 17.50, swap: -0.12, commission: -0.50,
    opened_at: new Date(Date.now() - 3600000).toISOString(),
  },
];
