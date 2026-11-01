import fs from 'node:fs';

const config = fs.readFileSync(new URL('../next.config.mjs', import.meta.url), 'utf8');
const required = [
  ['X-Content-Type-Options', 'nosniff'],
  ['X-Frame-Options', 'DENY'],
  ['Content-Security-Policy', "frame-ancestors 'none'; object-src 'none'; base-uri 'self'"],
  ['Referrer-Policy', 'strict-origin-when-cross-origin'],
  ['Permissions-Policy', 'camera=()'],
];
const errors = required.filter(([name, value]) => !config.includes(name) || !config.includes(value));
if (!config.includes('async headers()')) errors.push(['global headers()', 'missing']);
if (errors.length) {
  console.error('Frontend security-header contract failed:');
  for (const [name, value] of errors) console.error(`- ${name}: expected ${value}`);
  process.exit(1);
}
console.log(`Frontend security-header contract passed (${required.length} required header policies).`);
