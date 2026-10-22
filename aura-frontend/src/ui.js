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

// ── Login overlay ─────────────────────────────────────────────────────────────
export function showLoginOverlay(onLogin) {
  let overlay = document.getElementById('login-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'login-overlay';
    overlay.innerHTML = `
      <div class="login-card">
        <div class="login-logo"><span>Aura XAG</span></div>
        <h2>Sign in</h2>
        <div id="login-error" class="login-error" style="display:none"></div>
        <form id="login-form">
          <label>Email<input type="email" id="login-email" autocomplete="email" placeholder="you@example.com" required /></label>
          <label>Password<input type="password" id="login-password" autocomplete="current-password" placeholder="••••••••" required /></label>
          <button type="submit" id="login-btn">Sign in</button>
        </form>
      </div>`;
    document.body.appendChild(overlay);
  }
  overlay.style.display = 'flex';
  const form  = document.getElementById('login-form');
  const errEl = document.getElementById('login-error');
  const btn   = document.getElementById('login-btn');
  form.onsubmit = async (e) => {
    e.preventDefault();
    errEl.style.display = 'none';
    btn.disabled = true;
    btn.textContent = 'Signing in…';
    try {
      await onLogin(
        document.getElementById('login-email').value.trim(),
        document.getElementById('login-password').value
      );
    } catch (err) {
      errEl.textContent = err.message;
      errEl.style.display = 'block';
    } finally {
      btn.disabled = false;
      btn.textContent = 'Sign in';
    }
  };
}

export function hideLoginOverlay() {
  const overlay = document.getElementById('login-overlay');
  if (overlay) overlay.style.display = 'none';
}
