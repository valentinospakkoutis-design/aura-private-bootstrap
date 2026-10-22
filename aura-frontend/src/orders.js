// orders.js — Order entry wiring
export function wireOrderEntry(refreshPositions) {
  const form = document.getElementById('order-form');
  const errEl = document.getElementById('order-error');
  if (!form) return;
  async function submitOrder(side) {
    errEl.textContent = '';
    const lots = parseFloat(document.getElementById('order-lots').value);
    const sl = parseFloat(document.getElementById('order-sl').value) || null;
    const tp = parseFloat(document.getElementById('order-tp').value) || null;
    if (!isFinite(lots) || lots <= 0) { errEl.textContent = 'Invalid lot size'; return; }
    try {
      await fetch('/api/xag/order', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ symbol: 'XAGUSD-STD', side, volume: lots, sl, tp }) });
      await refreshPositions();
    } catch (err) { errEl.textContent = err.message || 'Order failed'; }
  }
  document.getElementById('btn-buy')?.addEventListener('click', () => submitOrder('buy'));
  document.getElementById('btn-sell')?.addEventListener('click', () => submitOrder('sell'));
}
