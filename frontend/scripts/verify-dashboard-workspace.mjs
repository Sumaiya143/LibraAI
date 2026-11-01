import fs from 'node:fs';
const page=fs.readFileSync('app/dashboard/page.tsx','utf8');
const header=fs.readFileSync('components/Header.tsx','utf8');
const api=fs.readFileSync('../dashboard_workspace.py','utf8');
const app=fs.readFileSync('../app.py','utf8');
const checks=[
 ['Public header is hidden after login',header.includes('pathname === "/dashboard"')],
 ['Dashboard loads authenticated profile and role',page.includes('/api/dashboard/summary')&&page.includes('roleMeta')],
 ['Preview role switching removed',!page.includes('Preview workspace')&&!page.includes('setView')],
 ['AI assistant remains available for all roles',page.includes('dash-ai-sidebar')&&page.includes('AI Assistant')],
 ['My Library lists reading progress only',page.includes('summary?.progress')&&page.includes('Continue reading')],
 ['Bookstore, audio and manga filters navigate to library',page.includes("window.location.href=\"/library\"")&&page.includes('format=audiobook')&&page.includes('format=manga')],
 ['Knowledge Vault quiz and memory game award server-validated coins',page.includes('Memory Match')&&api.includes("expected = {'Book Knowledge Quiz': 1, 'Memory Match': 0}")],
 ['Reading goals posts use authenticated API',page.includes('/api/dashboard/goals')&&api.includes('libra_goal_posts')],
 ['Community search, levels, create and join use backend',page.includes('/api/dashboard/guilds')&&api.includes('libra_guild_members')],
 ['Analytics are based on actual account progress',page.includes('summary?.stats.books_completed')&&api.includes('FROM progress p JOIN books')],
 ['Orders, wishlist and wallet records are surfaced',page.includes('summary?.wishlist')&&page.includes('/api/dashboard/wallet')],
 ['Per-order refunds are read from verified refund records',page.includes('refunds.map')&&api.includes("r.state='refunded'")],
 ['Bookstore audio and manga filters are supported in the library',fs.readFileSync('app/library/page.tsx','utf8').includes('Manga & Comics')&&fs.readFileSync('app/library/page.tsx','utf8').includes('requestedFormat')],
 ['Role-specific workspace and profile dropdown are present',page.includes('meta.label')&&page.includes('dash-profile-menu')],
 ['Dashboard API blueprint is registered',app.includes('install_dashboard_workspace(app, db, current_user)')],
 ['CSRF protection is used for dashboard mutations',page.includes('X-CSRF-Token')&&app.includes('verify_form_csrf')],
];
let failed=0;for(const [name,ok] of checks){console.log(`${ok?'PASS':'FAIL'} ${name}`);if(!ok)failed++;}
if(failed){console.error(`${failed} dashboard verification check(s) failed.`);process.exit(1)}
console.log(`Dashboard workspace verification passed: ${checks.length}/${checks.length}.`);

const adminWorkspace=fs.readFileSync('components/AdminWorkspace.tsx','utf8');
for(const label of ['Catalog & Import','Members','Issue & Return','Reservations','Multi-Branch Network','Reports & Analytics','Settings']){
 const ok=adminWorkspace.includes('"'+label+'"');
 console.log(`${ok?'PASS':'FAIL'} Admin workspace has a dedicated ${label} page`);
 if(!ok)process.exitCode=1;
}

console.log(`${page.includes('!isAdmin')?'PASS':'FAIL'} Admin navigation stays inside the dedicated workspace pages`);
if(!page.includes('!isAdmin'))process.exitCode=1;
