// ─── UI Utilities ─────────────────────────────────────────────────────────────
// Toast notifications + confirm modal.

// ── Toast ─────────────────────────────────────────────────────────────────────
export function showToast(msg, kind = 'info', durationMs = 3500) {
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast toast-${kind}`;
  el.textContent = msg;
  container.appendChild(el);
  requestAnimationFrame(() => el.classList.add('toast-visible'));
  setTimeout(() => {
    el.classList.remove('toast-visible');
    el.addEventListener('transitionend', () => el.remove());
  }, durationMs);
}

// ── Confirm modal ─────────────────────────────────────────────────────────────
export function showConfirm(text) {
  return new Promise((resolve) => {
    const modal = document.getElementById('confirm-modal');
    document.getElementById('confirm-text').textContent = text;
    modal.classList.remove('hidden');

    function cleanup(result) {
      modal.classList.add('hidden');
      document.getElementById('confirm-yes').removeEventListener('click', onYes);
      document.getElementById('confirm-no').removeEventListener('click', onNo);
      resolve(result);
    }
    const onYes = () => cleanup(true);
    const onNo  = () => cleanup(false);

    document.getElementById('confirm-yes').addEventListener('click', onYes);
    document.getElementById('confirm-no').addEventListener('click', onNo);
  });
}
