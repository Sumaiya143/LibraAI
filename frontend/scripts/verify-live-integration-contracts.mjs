import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
const root = path.resolve(process.cwd());
const read = (p) => fs.readFileSync(path.join(root, p), 'utf8');
const library = read('app/library/page.tsx');
const chat = read('components/FloatingAIChat.tsx');
const config = read('next.config.mjs');
const backendRoot = path.resolve(root, '..');
const appPy = fs.readFileSync(path.join(backendRoot, 'app.py'), 'utf8');
const aiProvider = fs.readFileSync(path.join(backendRoot, 'ai_tutor_provider.py'), 'utf8');
const paymentRoutes = fs.readFileSync(path.join(backendRoot, 'payment_routes.py'), 'utf8');
const failures = [];
function check(name, fn) { try { fn(); console.log(`PASS ${name}`); } catch (e) { failures.push(`${name}: ${e.message}`); console.error(`FAIL ${name}: ${e.message}`); } }
check('Library uses backend catalog and never renders hard-coded demo inventory on failure', () => {
  assert.match(library, /fetch\("\/backend\/api\/books/);
  assert.match(library, /setCatalog\(\[\]\)/);
  assert.match(library, /Preview books are hidden/);
  assert.doesNotMatch(library, /const books:Book\[\]=\[/);
});
check('Wishlist requires authenticated backend and CSRF-protected mutations', () => {
  assert.match(appPy, /@app\.get\('\/api\/wishlist'\)/);
  assert.match(appPy, /@app\.post\('\/api\/wishlist'\)/);
  assert.match(appPy, /Authentication required/);
  assert.match(appPy, /X-CSRF-Token|supplied/);
  assert.match(library, /X-CSRF-Token/);
});
check('AI endpoint is authenticated and provider fails closed when unconfigured', () => {
  assert.match(appPy, /@app\.post\('\/api\/ai'\)\s*@login_required/);
  assert.match(chat, /\/backend\/api\/ai/);
  assert.match(aiProvider, /LLM provider is not configured/);
  assert.match(aiProvider, /authorized source excerpts/);
});
check('Frontend backend proxy is configurable without exposing provider secrets', () => {
  assert.match(config, /LIBRAAI_BACKEND_URL/);
  assert.match(aiProvider, /LIBRAAI_LLM_API_KEY/);
  assert.doesNotMatch(chat, /LIBRAAI_LLM_API_KEY/);
});
check('Payment initiation uses provider verification and settlement checks', () => {
  assert.match(paymentRoutes, /def initiate\(/);
  assert.match(paymentRoutes, /ssl_verify\(/);
  assert.match(paymentRoutes, /bkash_execute_and_query\(/);
  assert.match(paymentRoutes, /settle_verified\(/);
});

check('Semantic search uses catalog-grounded records with external embeddings and local fallback', () => {
  const semantic = fs.readFileSync(path.resolve(backendRoot, 'semantic_search.py'), 'utf8');
  assert.match(appPy, /@app\.post\('\/api\/search\/semantic'\)/);
  assert.match(appPy, /rank_books\(query, rows, connect=db, limit=10\)/);
  assert.match(semantic, /LIBRAAI_EMBEDDINGS_API_KEY/);
  assert.match(semantic, /local_semantic_fallback/);
  assert.match(semantic, /semantic_embeddings/);
  assert.match(library, /\/backend\/api\/search\/semantic/);
  assert.match(library, /external_embeddings/);
  assert.match(library, /X-CSRF-Token.*csrfPayload\.csrfToken/);
});
if (failures.length) process.exit(1);
console.log('Live-integration contract checks passed. These are static contract checks, not live-provider acceptance tests.');
