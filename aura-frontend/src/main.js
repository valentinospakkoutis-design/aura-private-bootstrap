// ─── Entry Point ──────────────────────────────────────────────────────────────
import { state } from './state.js';
import { login, logout, getToken, fetchSnapshot, fetchSmartScore, fetchSignal, createTickWS } from './api.js';
import { initChart, loadHistory, switchTimeframe, processTick } from './chart.js';
import { updatePriceUI, updateRSICards, updateRSICard, updateWSDot, setPriceBadge, updateSmartScore, updateSignal } from './indicators.js';
import { refreshPositions, wirePositionEvents, renderPositions } from './positions.js';
import { showLoginOverlay, hideLoginOverlay, showToast } from './ui.js';
import { wireOrderEntry } from './orders.js';

async function init() {
  if (getToken()) {
    await boot();
  } else {
    showLoginOverlay(async (email, password) => {
      await login(email, password);
      hideLoginOverlay();
      await boot();
    });
  }

  window.addEventListener('aura:logout', () => {
    showToast('Session expired — please sign in again.', 'warn');
    showLoginOverlay(async (email, password) => {
      await login(email, password);
      hideLoginOverlay();
    });
  });
}

async function boot() {
  const container = document.getElementById('chart-container');
  initChart(container);
  await loadHistory(state.currentTf);

  wirePositionEvents();
  await refreshPositions();

  await doRefresh();

  const ws = createTickWS({
    onTick(tick) {
      const bid = Number(tick.bid);
      const ask = Number(tick.ask);
      if (!isFinite(bid) || !isFinite(ask)) return;
      const mid = (bid + ask) / 2;
      state.price = mid;
      state.bid   = bid;
      state.ask   = ask;
      updatePriceUI();
      processTick(mid, false);
      renderPositions();
    },
    onStatusChange(status) {
      state.wsStatus = status;
      updateWSDot(status);
    },
  });

  state.autoRefreshSec = 30;
  state.autoRefreshTimer = setInterval(doRefresh, 30000);

  wireControls(ws);
  wireOrderEntry(refreshPositions);
}

async function doRefresh() {
  if (state.isRefreshing) return;
  state.isRefreshing = true;
  setPriceBadge('fetching', 'gray');

  try {
    const data = await fetchSnapshot();
    if (state.anchor == null) state.anchor = data.daily_open ?? data.price;
    state.price     = data.price;
    state.bid       = data.bid;
    state.ask       = data.ask;
    state.priceAsof = data.asof;

    for (const tf of ['1m', '15m', '1h']) {
      state.rsi[tf] = { val: data[`rsi_${tf}`], ts: Date.now(), source: 'real' };
    }

    updatePriceUI();
    updateRSICards();
    try { updateSmartScore(await fetchSmartScore()); } catch(_) {}
    try { updateSignal(await fetchSignal()); } catch(_) {}
    setPriceBadge(data.source === 'mt5_bridge' ? 'real' : 'yfinance', 'green');
  } catch (err) {
    console.error('Snapshot fetch failed', err);
    setPriceBadge('fetch failed', 'red');
  } finally {
    state.isRefreshing = false;
  }
}

function wireControls(ws) {
  document.getElementById('btn-logout')?.addEventListener('click', async () => {
    await logout();
    location.reload();
  });

  document.getElementById('btn-refresh').addEventListener('click', doRefresh);

  document.getElementById('auto-refresh').addEventListener('change', (e) => {
    clearInterval(state.autoRefreshTimer);
    state.autoRefreshSec = +e.target.value;
    if (state.autoRefreshSec > 0) {
      state.autoRefreshTimer = setInterval(doRefresh, state.autoRefreshSec * 1000);
    }
  });

  document.querySelectorAll('.tf-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      await switchTimeframe(btn.dataset.tf);
    });
  });
}

setInterval(() => {
  for (const tf of ['1m', '15m', '1h']) updateRSICard(tf);
}, 30_000);

init().catch(err => console.error('Init failed', err));