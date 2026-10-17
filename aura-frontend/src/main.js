// ─── Entry Point ──────────────────────────────────────────────────────────────
// Bootstraps the app: chart, positions, tick stream, refresh loop.

import { state } from './state.js';
import { fetchSnapshot, createTickWS } from './api.js';
import { initChart, loadHistory, switchTimeframe, processTick } from './chart.js';
import { updatePriceUI, updateRSICards, updateRSICard, updateWSDot, setPriceBadge } from './indicators.js';
import { refreshPositions, wirePositionEvents, renderPositions } from './positions.js';

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
      const mid = (tick.bid + tick.ask) / 2;
      state.price = mid;
      state.bid   = tick.bid;
      state.ask   = tick.ask;
      updatePriceUI();
      processTick(mid, false);
      // Re-render position P/L on each tick (XAGUSD-STD live P/L)
      renderPositions();
    },
    onStatusChange(status) {
      state.wsStatus = status;
      updateWSDot(status);
    },
  });

  // 4. Initial snapshot
  await doRefresh();

  // 5. Wire UI controls
  wireControls(ws);
}

// ── Refresh (snapshot) ────────────────────────────────────────────────────────
async function doRefresh() {
  if (state.isRefreshing) return;
  state.isRefreshing = true;
  setPriceBadge('fetching', 'gray');

  try {
    const data = await fetchSnapshot();
    state.anchor   = data.price;
    state.price    = data.price;
    state.bid      = data.bid;
    state.ask      = data.ask;
    state.priceAsof = data.asof;

    for (const tf of ['1m', '15m', '1h']) {
      state.rsi[tf] = { val: data[`rsi_${tf}`], ts: Date.now(), source: data._stub ? 'sim' : 'real' };
    }

    updatePriceUI();
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
function wireControls(ws) {
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
