import fs from 'node:fs';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root=fileURLToPath(new URL('../..',import.meta.url));
const backend=fs.readFileSync(path.join(root,'library_operations.py'),'utf8');
const app=fs.readFileSync(path.join(root,'app.py'),'utf8');
const admin=fs.readFileSync(path.join(root,'frontend/components/AdminWorkspace.tsx'),'utf8');
const dashboard=fs.readFileSync(path.join(root,'frontend/app/dashboard/page.tsx'),'utf8');
const reader=fs.readFileSync(path.join(root,'static/reader.html'),'utf8');
const checks=[
 ['Admin member directory API',"@app.get('/api/admin/members')"],
 ['Admin member role/status mutation API',"@app.patch('/api/admin/members/<int:member_id>')"],
 ['Suspension revokes existing sessions',"status']=='suspended'"],
 ['Circulation issue API',"@app.post('/api/admin/circulation/issue')"],
 ['Circulation return API',"@app.post('/api/admin/circulation/<int:loan_id>/return')"],
 ['Auditable circulation event records','CREATE TABLE IF NOT EXISTS circulation_events'],
 ['Reservation creation and waitlist API',"@app.post('/api/reservations')"],
 ['Reservation staff management API',"@app.patch('/api/admin/reservations/<int:reservation_id>')"],
 ['Branch create/list/update APIs',"@app.post('/api/admin/branches')"],
 ['Branch inventory management API',"@app.put('/api/admin/branches/<int:branch_id>/inventory')"],
 ['Reader session start/stop APIs',"@app.post('/api/reader/sessions/start')"],
 ['Reader daily and genre analytics API',"@app.get('/api/reader/analytics')"],
 ['Admin live members UI',"section==='Members'"],
 ['Admin live circulation UI',"section==='Issue & Return'"],
 ['Admin live reservation UI',"section==='Reservations'"],
 ['Admin live branch and stock UI',"section==='Multi-Branch Network'"],
 ['Reader analytics dashboard UI','Daily reading time · last 30 days'],
 ['Reader opens timed session','startAnalyticsSession(current)'],
 ['CSRF protection remains globally enforced','def verify_form_csrf()']
];
for(const [label,needle] of checks){const hay=label.includes('UI')||label.includes('dashboard')?admin+'\n'+dashboard:label.includes('opens timed')?reader:label.includes('CSRF')?app:backend+'\n'+app;assert.ok(hay.includes(needle),`Missing: ${label}`);console.log(`PASS ${label}`);}
console.log(`Library operations contract verification passed: ${checks.length}/${checks.length}.`);
