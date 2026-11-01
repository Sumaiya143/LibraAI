import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const appDir = path.join(root, "app");
const read = (file) => fs.readFileSync(file, "utf8");
const routes = [];
function walk(dir) {
  for (const item of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, item.name);
    if (item.isDirectory()) walk(full);
    else if (item.name === "page.tsx") routes.push(full);
  }
}
walk(appDir);
const layout = read(path.join(appDir, "layout.tsx"));
const header = read(path.join(root, "components", "Header.tsx"));
const chat = read(path.join(root, "components", "FloatingAIChat.tsx"));
const errors = [];
if (!layout.includes('<Header />')) errors.push("Root layout does not render the shared Header.");
if (!header.includes('pathname === "/dashboard"')) errors.push("Authenticated dashboard does not hide the public site header.");
const dashboard = read(path.join(appDir, "dashboard", "page.tsx"));
if (!dashboard.includes("dash-topbar") || !dashboard.includes("dash-user-trigger")) errors.push("Dashboard workspace is missing its own account toolbar.");
if (!layout.includes('<FloatingAIChat />')) errors.push("Root layout does not render the global AI chatbot.");
if (!layout.includes('<GlobalNotice />')) errors.push("Root layout does not render global notices.");
for (const file of routes) {
  const source = read(file);
  if (/import\s+Header\s+from/.test(source) || /<Header\s*\/>/.test(source)) {
    errors.push(`${path.relative(root, file)} still renders a page-local Header; duplicate navigation may occur.`);
  }
}
const routePaths = routes.map((file) => {
  let route = path.relative(appDir, path.dirname(file)).split(path.sep).join("/");
  if (route === ".") route = "/";
  else route = "/" + route;
  return route.replace(/\[\.\.\.[^\]]+\]/g, ".*").replace(/\[[^\]]+\]/g, "[^/]+");
});
const navPaths = [...header.matchAll(/href="(\/[^"?#]*)"/g)].map((m) => m[1]);
for (const href of navPaths) {
  const found = routePaths.some((pattern) => new RegExp(`^${pattern.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\\\[\^\/\+\]/g, "[^/]+")}$`).test(href));
  // Dynamic route matching is handled separately for known parameterized navigation paths.
  const dynamicFound = (href.startsWith("/ecosystem/") && routePaths.includes("/ecosystem/[^/]+")) || (href.startsWith("/workspace/") && routePaths.includes("/workspace/[^/]+"));
  if (!found && !dynamicFound) errors.push(`Header link ${href} has no matching Next.js page route.`);
}
if (!chat.includes('id="libraai-assistant-window"') || !chat.includes('aria-controls="libraai-assistant-window"')) errors.push("AI launcher/window accessibility relationship is missing.");
if (errors.length) {
  console.error(`Page-shell verification failed (${errors.length} issue(s)):`);
  for (const error of errors) console.error(`- ${error}`);
  process.exit(1);
}
console.log(`Page-shell verification passed: ${routes.length} routes share the global shell; authenticated dashboard has its own toolbar; ${navPaths.length} header links checked.`);
