// ─── App State ────────────────────────────────────────────────────────────────
// Single source of truth. All modules import from here.

export const state = {
  // Price
  anchor: null,       // last real price from backend
  price:  null,       // current displayed price (may be drifted)
  bid:    null,
  ask:    null,
  priceAsof: null,    // ISO string

  // RSI — { val: number|null, ts: number|null, source: 'real'|'stale'|'none' }
  rsi: {
    '1m':  { val: null, ts: null, source: 'none' },
    '15m': { val: null, ts: null, source: 'none' },
    '1h':  { val: null, ts: null, source: 'none' },
  },

  // Chart
  currentTf: '1m',         // active timeframe key
  barCount: 0,
  realTickCount: 0,
  currentCandle: null,     // { time, open, high, low, close }

  // Positions — array of position objects from backend
  positions: [],
  selectedTickets: new Set(),

  // UI flags
  isRefreshing: false,
  wsStatus: 'disconnected',  // 'connected' | 'reconnecting' | 'disconnected'
  autoRefreshSec: 0,
  autoRefreshTimer: null,
};

// Timeframe → seconds mapping (for drift loop cadence)
export const TF_SECONDS = {
  '1m':  60,
  '5m':  300,
  '15m': 900,
  '1h':  3600,
};

// RSI stale threshold: 5 minutes
export const RSI_STALE_MS = 5 * 60 * 1000;
