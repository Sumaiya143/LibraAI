'use strict';
(() => {
  const message = document.getElementById('payout-provider-message');
  if (!message) return;
  async function action(button, action) {
    const id = button.getAttribute(action === 'submit-transfer' ? 'data-payout-submit' : 'data-payout-reconcile');
    if (!id || !/^\d+$/.test(id)) return;
    const promptText = action === 'submit-transfer'
      ? `Submit payout #${id} to the configured provider? This may initiate a real money transfer.`
      : `Query the provider and reconcile payout #${id}?`;
    if (!window.confirm(promptText)) return;
    button.disabled = true;
    message.textContent = action === 'submit-transfer' ? 'Submitting transfer securely…' : 'Checking provider status…';
    try {
      const csrfResponse = await fetch('/api/csrf', { credentials: 'same-origin', cache: 'no-store' });
      if (!csrfResponse.ok) throw new Error('Could not obtain a security token. Refresh and sign in again.');
      const { csrfToken } = await csrfResponse.json();
      const response = await fetch(`/api/admin/royalty-payouts/${encodeURIComponent(id)}/${action}`, {
        method: 'POST', credentials: 'same-origin', cache: 'no-store',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken, 'Accept': 'application/json' },
        body: '{}'
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || `Request failed (HTTP ${response.status}).`);
      message.textContent = data.message || `Payout #${id} updated. Refreshing…`;
      window.setTimeout(() => window.location.reload(), 900);
    } catch (error) {
      message.textContent = error instanceof Error ? error.message : 'Payout action failed. Reconcile the provider before retrying.';
      button.disabled = false;
    }
  }
  document.addEventListener('click', event => {
    const target = event.target instanceof Element ? event.target.closest('[data-payout-submit],[data-payout-reconcile]') : null;
    if (!target) return;
    action(target, target.hasAttribute('data-payout-submit') ? 'submit-transfer' : 'reconcile');
  });
})();
