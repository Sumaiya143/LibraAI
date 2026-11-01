import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const bridge = readFileSync(new URL('../components/LanguageBridge.tsx', import.meta.url), 'utf8');
const layout = readFileSync(new URL('../app/layout.tsx', import.meta.url), 'utf8');
const header = readFileSync(new URL('../components/Header.tsx', import.meta.url), 'utf8');
assert.match(bridge, /const EN_BN: Record<string, string>/, 'Bangla dictionary exists');
assert.match(bridge, /MutationObserver/, 'dynamically rendered content is observed');
assert.match(bridge, /localStorage\.getItem\("libraai-language"\)/, 'saved language is restored');
assert.match(bridge, /libraai-language/, 'language toggle event is handled');
assert.match(layout, /<LanguageBridge\s*\/>/, 'translation bridge is mounted globally');
assert.match(header, /window\.dispatchEvent\(new CustomEvent\("libraai-language"/, 'existing language control broadcasts changes');
for (const phrase of ['Skip to main content', 'Trending Books', 'Add to Cart', 'CHAPTER SUMMARY', 'Your data is safe with us']) {
  assert.ok(bridge.includes(`"${phrase}"`), `expected UI translation for: ${phrase}`);
}
console.log('Language bridge checks passed.');
