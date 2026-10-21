// ─── Entry Point ──────────────────────────────────────────────────────────────
// Bootstraps the app: chart, positions, tick stream, refresh loop.

import { applyQuote } from './quotes.js';
import { state } from './state.js';
import { fetchSnapshot, createTickWS } from './api.js';
import { initChart, loadHistory, switchTimeframe, processTick } from './chart.js';
import { updatePriceUI, updateRSICards, updateRSICard, updateWSDot, setPriceBadge } from './indicators.js';
import { refreshPositions, wirePositionEvents, renderPositions } from './positions.js';

const quoteEffects = { updatePriceUI, processTick, renderPositions };
let liveQuoteRevision = 0;

// ── Bootstrap ─────────────────────────────────────────────────────────────────
async function boot() {
  // 1. Chart
  const container = document.getElementById('chart-container');
  initChart(container);
  await loadHistory(state.currentTf);

  // 2. Positions
  wirePositionEvents();
  await refreshPositions();

  // 3. Tick stream
  const ws = createTickWS({
    onTick(tick) {
      if (applyQuote(state, tick, quoteEffects)) {
        liveQuoteRevision++;
        setPriceBadge(tick.stale ? 'stale' : 'real', tick.stale ? 'gray' : 'green');
      }
    },
    onBarClose() {
      // Existing positions API is still a stub; do not trigger trade actions.
      refreshPositions().catch(err => console.error('Position refresh failed', err));
    },
    onError() {
      setPriceBadge('stream error', 'red');
    },
    onStatusChange(status) {
      state.wsStatus = status;
      updateWSDot(status);
    },
  });

  window.addEventListener('pagehide', () => ws.close(), { once: true });

  // 4. Initial snapshot
  await doRefresh();

  // 5. Wire UI controls
  wireControls();
}

// ── Refresh (snapshot) ────────────────────────────────────────────────────────
async function doRefresh() {
  if (state.isRefreshing) return;
  state.isRefreshing = true;
  setPriceBadge('fetching', 'gray');

  try {
    const revision = liveQuoteRevision;
    const data = await fetchSnapshot();
    // An HTTP response started before a live tick must not roll it back.
    if (revision !== liveQuoteRevision) return;
    if (!applyQuote(state, data, quoteEffects, false)) throw new Error('Invalid or older snapshot');

    for (const tf of ['1m', '15m', '1h']) {
      state.rsi[tf] = { val: data[`rsi_${tf}`], ts: Date.now(), source: data._stub ? 'sim' : 'real' };
    }

    updateRSICards();
    setPriceBadge(data._stub ? 'simulated' : 'real', data._stub ? 'gray' : 'green');
  } catch (err) {
    console.error('Snapshot fetch failed', err);
    setPriceBadge('fetch failed', 'red');
  } finally {
    state.isRefreshing = false;
  }
}

// ── UI Controls ───────────────────────────────────────────────────────────────
function wireControls() {
  // Refresh button
  document.getElementById('btn-refresh').addEventListener('click', doRefresh);

  // Auto-refresh
  document.getElementById('auto-refresh').addEventListener('change', (e) => {
    clearInterval(state.autoRefreshTimer);
    state.autoRefreshSec = +e.target.value;
    if (state.autoRefreshSec > 0) {
      state.autoRefreshTimer = setInterval(doRefresh, state.autoRefreshSec * 1000);
    }
  });

  // Timeframe buttons
  document.querySelectorAll('.tf-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      await switchTimeframe(btn.dataset.tf);
    });
  });
}

// ── RSI staleness checker ─────────────────────────────────────────────────────
setInterval(() => {
  for (const tf of ['1m', '15m', '1h']) updateRSICard(tf);
}, 30_000);

// ── Run ───────────────────────────────────────────────────────────────────────
boot().catch(err => console.error('Boot failed', err));
