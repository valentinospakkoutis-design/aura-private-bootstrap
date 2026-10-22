// â”€â”€â”€ Chart Module â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Wraps lightweight-charts. Exposes init / update / switchTf / processTick.

import { createChart } from 'lightweight-charts';
import { state, TF_SECONDS } from './state.js';
import { fetchOHLC } from './api.js';

let chart = null;
let candleSeries = null;
let volumeSeries = null;

// â”€â”€ Init â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export function initChart(container) {
  const dark = window.matchMedia('(prefers-color-scheme: dark)').matches;

  chart = createChart(container, {
    layout: {
      background: { color: dark ? '#0f1117' : '#ffffff' },
      textColor:  dark ? '#c9d1d9' : '#24292f',
    },
    grid: {
      vertLines:  { color: dark ? '#1e2329' : '#f0f0f0' },
      horzLines:  { color: dark ? '#1e2329' : '#f0f0f0' },
    },
    crosshair: { mode: 1 },
    rightPriceScale: { borderColor: dark ? '#30363d' : '#d0d7de' },
    timeScale: {
      borderColor:     dark ? '#30363d' : '#d0d7de',
      timeVisible:     true,
      secondsVisible:  false,
    },
    width:  container.clientWidth,
    height: container.clientHeight,
  });

  candleSeries = chart.addCandlestickSeries({
    upColor:          '#26a641',
    downColor:        '#f85149',
    borderUpColor:    '#26a641',
    borderDownColor:  '#f85149',
    wickUpColor:      '#26a641',
    wickDownColor:    '#f85149',
  });

  volumeSeries = chart.addHistogramSeries({
    color:     '#3d444d',
    priceFormat: { type: 'volume' },
    priceScaleId: 'vol',
    scaleMargins: { top: 0.85, bottom: 0 },
  });

  // Responsive resize
  const ro = new ResizeObserver(() => {
    chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
  });
  ro.observe(container);

  return { chart, candleSeries, volumeSeries };
}

// â”€â”€ Load history â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function loadHistory(tf = state.currentTf) {
  if (!candleSeries) return;
  let bars = await fetchOHLC(tf, 200);
  if (bars.length === 0 && tf !== "1h") bars = await fetchOHLC("1h", 200);
  candleSeries.setData(bars);
  volumeSeries.setData(bars.map(b => ({ time: b.time, value: b.volume ?? 0, color: b.close >= b.open ? '#26a64140' : '#f8514940' })));
  state.barCount     = bars.length;
  state.realTickCount = 0;
  state.currentCandle = bars[bars.length - 1] ?? null;
  chart.timeScale().fitContent();
  updateChartStats();
}

// â”€â”€ Switch timeframe â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function switchTimeframe(tf) {
  state.currentTf = tf;
  await loadHistory(tf);
}

// â”€â”€ Process incoming tick â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export function processTick(mid, isReal = false) {
  if (!Number.isFinite(mid) || mid <= 0 || !candleSeries || !state.currentCandle) return;

  const tfSec  = TF_SECONDS[state.currentTf] ?? 60;
  const nowSec = Math.floor(Date.now() / 1000);
  const barTime = Math.floor(nowSec / tfSec) * tfSec;

  if (isReal) state.realTickCount++;

  if (barTime > state.currentCandle.time) {
    // New bar
    state.currentCandle = { time: barTime, open: mid, high: mid, low: mid, close: mid };
    state.barCount++;
  } else {
    // Update current bar
    state.currentCandle.high  = Math.max(state.currentCandle.high,  mid);
    state.currentCandle.low   = Math.min(state.currentCandle.low,   mid);
    state.currentCandle.close = mid;
  }

  candleSeries.update(state.currentCandle);
  updateChartStats();
}

// â”€â”€ Stats label â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function updateChartStats() {
  const el = document.getElementById('chart-stats');
  if (el) el.textContent = `${state.barCount} bars · ${state.realTickCount} real ticks`;
}

