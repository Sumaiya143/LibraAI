import fs from "node:fs";
import assert from "node:assert/strict";
const dashboard=fs.readFileSync("app/dashboard/page.tsx","utf8");
const seller=fs.readFileSync("components/SellerWorkspace.tsx","utf8");
const admin=fs.readFileSync("components/AdminWorkspace.tsx","utf8");
const deep=fs.readFileSync("app/workspace/[slug]/page.tsx","utf8");
const readerLabels=["My Library","Reading Community","Knowledge Vault","Reading Goals","Analytics","Cart & Orders","Wallet & Payments"];
const sellerLabels=["Upload & Edit Products","My Products & Inventory","Orders & Sales","Earnings & Payouts","Sales Analytics","Author Profile","Settings"];
const adminLabels=["Catalog & Import","Members","Issue & Return","Reservations","Multi-Branch Network","Reports & Analytics","Settings"];
for(const label of readerLabels){assert.ok(dashboard.includes(`active==='${label}'`)||dashboard.includes(`active===\"${label}\"`),`Reader page missing: ${label}`);console.log(`PASS Reader page: ${label}`);}
for(const label of sellerLabels){assert.ok(seller.includes(`section==='${label}'`),`Seller page missing: ${label}`);console.log(`PASS Seller page: ${label}`);}
for(const label of adminLabels){assert.ok(admin.includes(`\"${label}\":{eyebrow`),`Admin page missing: ${label}`);console.log(`PASS Admin page: ${label}`);}
assert.ok(dashboard.includes('isAdmin?<AdminWorkspace section="Dashboard"'),"Admin dashboard must not render the reader dashboard.");
assert.ok(admin.includes('onNavigate(item.title)'),"Admin dashboard section cards must navigate to their dedicated page.");
assert.ok(deep.includes('redirect(`/dashboard?section=${encodeURIComponent(slug)}`)'),"Workspace deep links must open the signed-in role workspace instead of a sign-in placeholder.");
assert.ok(dashboard.includes('const aliases:Record<string,string>'),"Dashboard must map workspace deep links to the correct role page.");
console.log("Role-aware page coverage passed: reader, seller, admin and workspace deep links.");
