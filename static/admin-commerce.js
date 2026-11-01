'use strict';
const $ = id => document.getElementById(id);
function displayFindings(data) {
  const list = $('findings');
  list.replaceChildren();
  const findings = Array.isArray(data.findings) ? data.findings : [];
  if (!findings.length) {
    const p = document.createElement('p');
    p.textContent = 'No findings were reported by the current diagnostic checks.';
    list.append(p);
    return findings.length;
  }
  for (const finding of findings) {
    const item = document.createElement('div');
    item.className = 'finding';
    const title = document.createElement('strong');
    title.textContent = typeof finding === 'object' && finding !== null
      ? String(finding.code || finding.type || finding.issue || 'Diagnostic finding')
      : 'Diagnostic finding';
    const description = document.createElement('p');
    description.textContent = typeof finding === 'object' && finding !== null
      ? String(finding.message || finding.description || JSON.stringify(finding))
      : String(finding);
    item.append(title, description);
    list.append(item);
  }
  return findings.length;
}
async function refresh() {
  $('refresh').disabled = true;
  $('message').textContent = 'Loading diagnostics…';
  $('report').hidden = true;
  try {
    const response = await fetch('/api/admin/commerce/health', {credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}});
    if (response.status === 401) throw new Error('Please sign in with an administrator account.');
    if (response.status === 403) throw new Error('Access denied. This dashboard is restricted to administrators.');
    if (!response.ok) throw new Error('Unable to retrieve commerce diagnostics.');
    const data = await response.json();
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Unexpected report format.');
    $('status').textContent = String(data.status || 'unknown');
    $('count').textContent = String(displayFindings(data));
    $('checked').textContent = new Date().toLocaleString();
    $('raw').textContent = JSON.stringify(data,null,2);
    $('report').hidden = false;
    $('message').textContent = 'Report loaded. Results are diagnostic only, not a settlement confirmation.';
  } catch(error) {
    $('message').textContent = error.message;
  } finally {
    $('refresh').disabled = false;
  }
}
$('refresh').addEventListener('click',refresh);
refresh();
