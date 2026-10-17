// ─── Positions Module ─────────────────────────────────────────────────────────
// Table render + actions (close, bulk close).

import { state } from './state.js';
import { fetchPositions, closePosition, closeBulk } from './api.js';
import { showToast, showConfirm } from './ui.js';

// ── Render ────────────────────────────────────────────────────────────────────
export function renderPositions() {
  const tbody  = document.getElementById('positions-body');
  const tfoot  = document.getElementById('positions-footer');
  const { positions, selectedTickets, price } = state;

  if (!positions.length) {
    tbody.innerHTML = `<tr><td colspan="11" class="empty-row">No open positions</td></tr>`;
    tfoot.innerHTML = '';
    updateMasterCB();
    updateBulkButtons();
    return;
  }

  let totalPL = 0, totalSwap = 0, totalComm = 0;

  tbody.innerHTML = positions.map(p => {
    const isXAG    = p.symbol === 'XAGUSD-STD';
    const curPrice = isXAG && price != null ? price : p.current_price ?? p.open_price;
    const mult     = p.side === 'BUY' ? 1 : -1;
    const dig      = p.open_price > 100 ? 2 : 4;

    // P/L — for XAGUSD-STD compute live; for others use backend value
    let pl = p.profit;
    if (isXAG && price != null) {
      pl = mult * (curPrice - p.open_price) * p.volume * 5000; // 5000 oz/lot for XAG standard
    }
    if (pl != null) { totalPL += pl; totalSwap += p.swap ?? 0; totalComm += p.commission ?? 0; }

    const plStr  = pl != null ? `${pl >= 0 ? '+' : ''}$${pl.toFixed(2)}` : '—';
    const plCls  = pl == null ? '' : pl >= 0 ? 'pl-pos' : 'pl-neg';
    const chk    = selectedTickets.has(p.ticket) ? 'checked' : '';

    return `<tr data-ticket="${p.ticket}" class="${chk ? 'row-selected' : ''}">
      <td><input type="checkbox" class="row-cb" data-ticket="${p.ticket}" ${chk} /></td>
      <td class="tabnum">${p.ticket}</td>
      <td>${p.symbol}</td>
      <td><span class="side-badge side-${p.side.toLowerCase()}">${p.side}</span></td>
      <td class="tabnum">${p.volume.toFixed(2)}</td>
      <td class="tabnum">${p.open_price.toFixed(dig)}</td>
      <td class="tabnum">${curPrice.toFixed(dig)}</td>
      <td class="tabnum ${plCls}">${plStr}</td>
      <td class="tabnum dimmed">${p.swap != null ? p.swap.toFixed(2) : '—'}</td>
      <td class="dimmed">${fmtDate(p.opened_at)}</td>
      <td><button class="btn btn-danger btn-xs btn-close-one" data-ticket="${p.ticket}">Close</button></td>
    </tr>`;
  }).join('');

  // Footer totals
  tfoot.innerHTML = `<tr class="totals-row">
    <td colspan="7" class="totals-label">Totals (${positions.length} positions)</td>
    <td class="tabnum ${totalPL >= 0 ? 'pl-pos' : 'pl-neg'}">${totalPL >= 0 ? '+' : ''}$${totalPL.toFixed(2)}</td>
    <td class="tabnum dimmed">${totalSwap.toFixed(2)}</td>
    <td colspan="2"></td>
  </tr>`;

  updateMasterCB();
  updateBulkButtons();
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function updateMasterCB() {
  const cb  = document.getElementById('master-cb');
  const sel = state.selectedTickets.size;
  const tot = state.positions.length;
  cb.checked       = tot > 0 && sel === tot;
  cb.indeterminate = sel > 0 && sel < tot;
}

function updateBulkButtons() {
  const btn = document.getElementById('btn-close-selected');
  btn.disabled = state.selectedTickets.size === 0;
}

// ── Event wiring ──────────────────────────────────────────────────────────────
export function wirePositionEvents() {
  // Master checkbox
  document.getElementById('master-cb').addEventListener('change', (e) => {
    state.selectedTickets.clear();
    if (e.target.checked) state.positions.forEach(p => state.selectedTickets.add(p.ticket));
    renderPositions();
  });

  // Row checkboxes (delegated)
  document.getElementById('positions-body').addEventListener('change', (e) => {
    if (!e.target.classList.contains('row-cb')) return;
    const ticket = +e.target.dataset.ticket;
    if (e.target.checked) state.selectedTickets.add(ticket);
    else                   state.selectedTickets.delete(ticket);
    updateMasterCB();
    updateBulkButtons();
    e.target.closest('tr').classList.toggle('row-selected', e.target.checked);
  });

  // Per-row close (delegated)
  document.getElementById('positions-body').addEventListener('click', async (e) => {
    if (!e.target.classList.contains('btn-close-one')) return;
    const ticket = +e.target.dataset.ticket;
    const ok = await showConfirm(`Close position #${ticket}?`);
    if (!ok) return;
    await doClose([ticket]);
  });

  // Toolbar buttons
  document.getElementById('btn-select-all').addEventListener('click', () => {
    state.positions.forEach(p => state.selectedTickets.add(p.ticket));
    renderPositions();
  });

  document.getElementById('btn-clear').addEventListener('click', () => {
    state.selectedTickets.clear();
    renderPositions();
  });

  document.getElementById('btn-close-selected').addEventListener('click', async () => {
    const tickets = [...state.selectedTickets];
    const ok = await showConfirm(`Close ${tickets.length} selected position(s)?`);
    if (!ok) return;
    await doClose(tickets);
  });

  document.getElementById('btn-close-all').addEventListener('click', async () => {
    const ok = await showConfirm(`Close ALL ${state.positions.length} open positions? This cannot be undone.`);
    if (!ok) return;
    await doClose(state.positions.map(p => p.ticket));
  });
}

// ── Refresh positions ─────────────────────────────────────────────────────────
export async function refreshPositions() {
  state.positions = await fetchPositions();
  renderPositions();
}

// ── Close logic ───────────────────────────────────────────────────────────────
async function doClose(tickets) {
  // Optimistic: gray out rows
  tickets.forEach(t => {
    const row = document.querySelector(`tr[data-ticket="${t}"]`);
    if (row) row.classList.add('row-closing');
  });

  try {
    if (tickets.length === 1) {
      await closePosition(tickets[0]);
    } else {
      await closeBulk(tickets);
    }
    // Remove from local state
    state.positions = state.positions.filter(p => !tickets.includes(p.ticket));
    tickets.forEach(t => state.selectedTickets.delete(t));
    renderPositions();
    showToast(`Closed ${tickets.length} position(s)`, 'success');
  } catch (err) {
    // Restore rows on failure
    tickets.forEach(t => {
      const row = document.querySelector(`tr[data-ticket="${t}"]`);
      if (row) row.classList.remove('row-closing');
    });
    showToast(`Close failed: ${err.message}`, 'error');
  }
}
