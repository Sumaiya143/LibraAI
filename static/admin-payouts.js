'use strict';
const $ = id => document.getElementById(id);

function payoutText(tag, value) {
  const element = document.createElement(tag);
  element.textContent = String(value ?? '—');
  return element;
}
async function refreshPayouts() {
  $('refresh-payouts').disabled = true;
  $('payout-message').textContent = 'Loading payout ledger…';
  $('payout-list').replaceChildren();
  $('payout-history').replaceChildren();
  try {
    const response = await fetch('/api/admin/commerce/payouts?limit=50', {credentials:'same-origin',cache:'no-store'});
    if (response.status === 401 || response.status === 403) throw new Error('Administrator sign-in required.');
    if (!response.ok) throw new Error('Unable to load payouts.');
    const data = await response.json();
    for (const payout of data.payouts || []) {
      const item = document.createElement('article');
      item.className = 'payout-item';
      item.append(payoutText('strong', `#${payout.id} · Merchant ${payout.merchant_id} · ${payout.amount} ${payout.currency}`),
                  payoutText('p', `Status: ${payout.status} · Created: ${payout.created}`));
      const decisions = payout.status === 'manual_review' ? ['approved','rejected'] : payout.status === 'approved' ? ['paid','rejected'] : [];
      if (decisions.length) {
        const select = document.createElement('select');
        for (const decision of decisions) {const option=document.createElement('option');option.value=decision;option.textContent=decision;select.append(option);}
        select.setAttribute('aria-label',`Decision for payout ${payout.id}`);
        const reference = document.createElement('input');
        reference.placeholder = 'External payment reference (required for paid)';
        reference.maxLength = 120;
        reference.setAttribute('aria-label',`External reference for payout ${payout.id}`);
        const submit = payoutText('button','Record decision');
        submit.type='button';
        submit.addEventListener('click',async()=>{
          if (!confirm(`Record ${select.value} for payout #${payout.id}? This does not transfer funds.`)) return;
          submit.disabled=true;
          try {
            const res=await fetch('/api/admin/payout/review',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({payout_id:payout.id,status:select.value,reference:reference.value})});
            if (!res.ok) {const err=await res.json();throw new Error(err.error||'Review failed');}
            await refreshPayouts();
          } catch(err) {$('payout-message').textContent=err.message;} finally {submit.disabled=false;}
        });
        item.append(select,reference,submit);
      }
      $('payout-list').append(item);
    }
    if (!data.payouts?.length) $('payout-list').append(payoutText('p','No payout requests found.'));
    for (const event of data.review_events || []) $('payout-history').append(payoutText('p',`Payout #${event.payout_id}: ${event.previous_status} → ${event.new_status} · Reviewer #${event.reviewer_id} · ${event.created}`));
    $('payout-message').textContent='Ledger loaded. Paid status is not proof of settlement.';
  } catch(err) {$('payout-message').textContent=err.message;}
  finally {$('refresh-payouts').disabled=false;}
}
$('refresh-payouts').addEventListener('click',refreshPayouts);
refreshPayouts();
