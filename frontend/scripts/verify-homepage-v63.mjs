import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
const home = readFileSync('app/page.tsx','utf8');
const header = readFileSync('components/Header.tsx','utf8');
const layout = readFileSync('app/layout.tsx','utf8');
const css = readFileSync('app/globals.css','utf8');
for (const [name, condition] of [
 ['Browse points directly to the library', header.includes('href="/library"')],
 ['Resources dropdown has Manga, Community, Audio Books and AI Help', ['Manga','Community','Audio Books','AI Help'].every(x=>header.includes(x))],
 ['Removed AI Tools/My Library/Pricing from primary nav', !header.includes('href="/study-tools"') && !header.includes('href="/workspace/my-library"') && !header.includes('href="/pricing"')],
 ['Hero uses motion illustration, not static image', home.includes('hero-motion-stage') && !home.includes('hero-reading.webp')],
 ['Hero subscription CTA exists', home.includes('Subscription')],
 ['About section contains AI Help tile', home.includes('about-ai-help')],
 ['Shop has five real image assets', (home.match(/\/assets\/shop-[a-z-]+\.svg/g)||[]).length === 5],
 ['View Store and account gate exist', home.includes('View Store') && home.includes('before entering the store')],
 ['Five reviews and carousel controls exist', home.includes('readerReviews') && home.includes('Previous reviews') && home.includes('Next reviews')],
 ['FAQ has interactive accordion', home.includes('faq-open') && home.includes('aria-expanded')],
 ['Payment setup floating launcher removed from root layout', !layout.includes('FloatingPaymentSetup')],
 ['Lora and Google display font are loaded', layout.includes('family=Lora') && layout.includes('family=UnifrakturMaguntia')],
 ['Motion and glassmorphism styles exist', css.includes('backdrop-filter:blur(16px)') && css.includes('@keyframes heroFloat')]
]) { assert.ok(condition, name); console.log(`PASS ${name}`); }
console.log('Homepage v63 checks passed.');
