// ─── Indicators Module ────────────────────────────────────────────────────────
// Renders RSI cards and price card.

import { state, RSI_STALE_MS } from './state.js';

// ── Price card ────────────────────────────────────────────────────────────────
export function updatePriceUI() {
  const { price, bid, ask, anchor, priceAsof } = state;
  if (price == null) return;

  const dig = price > 100 ? 2 : 4;

  document.getElementById('price-value').textContent = price.toFixed(dig);

  if (bid != null && ask != null) {
    document.getElementById('price-bid-ask').textContent =
      `Bid ${bid.toFixed(dig)} / Ask ${ask.toFixed(dig)}`;
  }

  if (anchor != null) {
    const delta  = price - anchor;
    const pct    = (delta / anchor) * 100;
    const sign   = delta >= 0 ? '+' : '';
    const el     = document.getElementById('price-change');
    el.textContent  = `${sign}${delta.toFixed(dig)} (${sign}${pct.toFixed(2)}%)`;
    el.className    = delta >= 0 ? 'price-change-up' : 'price-change-down';
  }

  if (priceAsof) {
    const t = new Date(priceAsof);
    document.getElementById('price-status').textContent =
      `Last update: ${t.toLocaleTimeString()}`;
  }
}

export function setPriceBadge(text, kind = 'gray') {
  const el = document.getElementById('price-source-badge');
  el.textContent = text;
  el.className   = `badge badge-${kind}`;
}

// ── RSI cards ─────────────────────────────────────────────────────────────────
const TF_KEYS = ['1m', '15m', '1h'];

export function updateRSICards() {
  for (const tf of TF_KEYS) {
    updateRSICard(tf);
  }
}

export function updateRSICard(tf) {
  const { val, ts, source } = state.rsi[tf];
  const card  = document.getElementById(`rsi-${tf}`);
  const valEl = document.getElementById(`rsi-${tf}-val`);
  const bdgEl = document.getElementById(`rsi-${tf}-badge`);

  if (val == null) {
    valEl.textContent = '—';
    bdgEl.textContent = '—';
    card.className    = 'rsi-card rsi-neutral';
    return;
  }

  valEl.textContent = val.toFixed(1);

  const isStale = ts != null && (Date.now() - ts) > RSI_STALE_MS;
  const freshSource = isStale ? 'stale' : (source || 'real');

  bdgEl.textContent = freshSource;
  bdgEl.className   = `rsi-badge rsi-badge-${freshSource}`;

  if (val >= 70) {
    card.className = 'rsi-card rsi-overbought';
  } else if (val <= 30) {
    card.className = 'rsi-card rsi-oversold';
  } else {
    card.className = 'rsi-card rsi-neutral';
  }
}

// ── WebSocket dot ─────────────────────────────────────────────────────────────
export function updateWSDot(status) {
  const el = document.getElementById('ws-indicator');
  el.className = `ws-dot ws-${status}`;
  el.title = { connected: 'WebSocket connected', reconnecting: 'Reconnecting…', disconnected: 'Disconnected' }[status] ?? status;
}


// -- Smart Score card ---------------------------------------------------------
export function updateSmartScore(data) {
  const valEl = document.getElementById('smart-score-val');
  const bdgEl = document.getElementById('smart-score-badge');
  const card  = document.getElementById('smart-score-card');
  if (!valEl) return;
  if (!data || data.smart_score == null) {
    valEl.textContent = '—';
    bdgEl.textContent = '—';
    card.className = 'rsi-card rsi-neutral';
    return;
  }
  const score = data.smart_score;
  const rec   = data.recommendation || '';
  valEl.textContent = score.toFixed(1);
  bdgEl.textContent = rec;
  card.className = 'rsi-card ' + (score >= 75 ? 'rsi-ob' : score >= 50 ? 'rsi-neutral' : 'rsi-os');
}


// -- Signal card --------------------------------------------------------------
export function updateSignal(data) {
  const valEl = document.getElementById('signal-val');
  const bdgEl = document.getElementById('signal-badge');
  const card  = document.getElementById('signal-card');
  if (!valEl) return;
  if (!data || !data.signal) {
    valEl.textContent = '—';
    bdgEl.textContent = '—';
    card.className = 'rsi-card rsi-neutral';
    return;
  }
  valEl.textContent = data.signal;
  bdgEl.textContent = data.confidence != null ? data.confidence.toFixed(1) + '%' : '—';
  const sig = data.signal.toUpperCase();
  card.className = 'rsi-card ' + (sig === 'BUY' ? 'rsi-os' : sig === 'SELL' ? 'rsi-ob' : 'rsi-neutral');
}
