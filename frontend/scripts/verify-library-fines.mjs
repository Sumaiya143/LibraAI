import fs from "node:fs";
import path from "node:path";
const root = process.cwd();
const app = fs.readFileSync(path.join(root, "..", "app.py"), "utf8");
const circulation = fs.readFileSync(path.join(root, "..", "circulation.py"), "utf8");
const fines = fs.readFileSync(path.join(root, "..", "library_fines.py"), "utf8");
const dashboard = fs.readFileSync(path.join(root, "app", "dashboard", "page.tsx"), "utf8");
const admin = fs.readFileSync(path.join(root, "components", "AdminWorkspace.tsx"), "utf8");
const checks = [
  ["14-day loan duration", circulation.includes("LOAN_DAYS = 14")],
  ["Default BDT 10/day fine", fines.includes('FINE_PER_DAY_PAISE = int(os.environ.get("LIBRAAI_FINE_PER_DAY_PAISE", "1000"))')],
  ["Unpaid fines block new loans", circulation.includes("CirculationError('fine_due'")],
  ["Payment requires admin approval", app.includes("def admin_approve_library_fine(payment_id)") && app.includes("current_user()['role'] != 'admin'")],
  ["Customer fine dashboard shortcut", dashboard.includes("window.location.href='/account/fines'")],
  ["Admin fine review shortcut", admin.includes('href="/admin/fines"')],
  ["Library clearance is not an academic certificate", app.includes("not an academic graduation certificate")],
];
for (const [label, ok] of checks) console.log(`${ok ? "PASS" : "FAIL"} ${label}`);
if (checks.some(([, ok]) => !ok)) process.exit(1);
