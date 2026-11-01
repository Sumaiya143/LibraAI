import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import assert from "node:assert/strict";

const header = readFileSync(resolve("components/Header.tsx"), "utf8");
const chat = readFileSync(resolve("components/FloatingAIChat.tsx"), "utf8");
const studyPage = readFileSync(resolve("app/study-tools/page.tsx"), "utf8");
const backend = readFileSync(resolve("../app.py"), "utf8");

for (const token of [
  'localStorage.getItem("libraai-language")',
  'localStorage.setItem("libraai-language", next)',
  'document.documentElement.lang = next',
  'হোম', 'আমার লাইব্রেরি', 'labels.search'
]) assert.ok(header.includes(token), `Missing language/navigation contract: ${token}`);
assert.ok(!header.includes('href="/study-tools"'), 'AI Tools must not appear as a primary navigation item.');
assert.ok(!header.includes('href="/workspace/my-library"'), 'My Library must not appear as a primary navigation item.');
assert.ok(!header.includes('href="/pricing"'), 'Pricing must not appear as a primary navigation item.');

for (const token of [
  'libraai-ai-chat-history-v1', 'localStorage.setItem("libraai-ai-chat-history-v1"',
  'localStorage.getItem("libraai-ai-chat-history-v1")', 'localStorage.removeItem("libraai-ai-chat-history-v1")',
  '.slice(-100)', 'Clear conversation history', '/backend/api/ai/history', 'historyReady'
]) assert.ok(chat.includes(token), `Missing chat-history contract: ${token}`);

for (const token of ['api_ai_history', "@app.route('/api/ai/history'", 'ai_conversation_messages', "@app.post('/api/study-tools')", "from study_tools import generate_study_set"])
  assert.ok(backend.includes(token), `Missing backend feature contract: ${token}`);
for (const token of ['/backend/api/study-tools', 'CHAPTER SUMMARY', 'KNOWLEDGE CHECK', 'REVISION CARDS'])
  assert.ok(studyPage.includes(token), `Missing study tools UI contract: ${token}`);

console.log("Client enhancement contracts passed: bilingual header without removed primary links, account-scoped chat history API, and study tools UI/API.");
