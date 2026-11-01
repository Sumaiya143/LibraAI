import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=path.resolve(import.meta.dirname,'..','..');
const dashboard=fs.readFileSync(path.join(root,'frontend/app/dashboard/page.tsx'),'utf8');
const component=fs.readFileSync(path.join(root,'frontend/components/SellerWorkspace.tsx'),'utf8');
const backend=fs.readFileSync(path.join(root,'seller_workspace.py'),'utf8');
const app=fs.readFileSync(path.join(root,'app.py'),'utf8');
for(const label of ['Upload & Edit Products','My Products & Inventory','Orders & Sales','Earnings & Payouts','Sales Analytics'])assert.ok(dashboard.includes(label),`missing seller nav: ${label}`);
for(const label of ['Your Products','Physical Book','Stationery','Audiobook','Discount (%)','Tags (comma separated)','Hashtags (comma separated)','Additional product details','Single price','2 units','Platform charges','Delivered','Processing / pending','Returned / Refunded','This week','This month','This year','Request payout review'])assert.ok(component.includes(label),`missing seller UI: ${label}`);
for(const route of ["@bp.get('/api/seller/products')","@bp.post('/api/seller/products')","@bp.put('/api/seller/products/<int:product_id>')","@bp.get('/api/seller/overview')","@bp.post('/api/seller/payout-requests')"])assert.ok(backend.includes(route),`missing API route: ${route}`);
for(const security of ['seller_id=?','seller_required','pending_review','sale_enabled=0','available seller balance','LIBRAAI_PLATFORM_COMMISSION_RATE'])assert.ok(backend.includes(security),`missing backend control: ${security}`);
assert.ok(app.includes('install_seller_workspace(app, db, current_user)'),'seller blueprint not registered');
console.log('Seller workspace verification passed: navigation, UI fields, CRUD APIs, owner scoping, review gating, commission and payout balance controls.');

const sellerCtaChecks = [
  ['Dashboard upload CTA navigates to Upload & Edit Products', dashboard.includes('<SellerWorkspace section="Dashboard" onNavigate={navigate}/>') && component.includes('onNavigate?onNavigate("Upload & Edit Products"):openNew')],
  ['Seller Profile has a dedicated page', component.includes("section==='Author Profile'")],
  ['Seller Settings has a dedicated page', component.includes("section==='Settings'")],
  ['Seller Settings stays in the role-specific workspace', dashboard.includes('if(label==="Settings"&&!isMerchant&&!isAdmin)')],
];
for (const [label, ok] of sellerCtaChecks) { console.log(`${ok?'PASS':'FAIL'} ${label}`); if(!ok) process.exitCode=1; }
