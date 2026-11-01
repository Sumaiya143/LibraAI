"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import Link from "next/link";
import { ArrowLeft, BookOpen, BrainCircuit, CheckCircle2, LoaderCircle, Sparkles } from "lucide-react";

type StudyResult = {
  summary: string;
  keywords: string[];
  quiz: { question: string; answer: string; type: string }[];
  flashcards: { front: string; back: string }[];
  notice?: string;
  mode?: string;
  saved_set?: { id: number; title: string };
};
type SavedStudySet = { id: number; title: string; created_at: string };

export default function StudyToolsPage() {
  const [source, setSource] = useState("");
  const [result, setResult] = useState<StudyResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [revealed, setRevealed] = useState<number[]>([]);
  const [savedSets, setSavedSets] = useState<SavedStudySet[]>([]);
  const [setTitle, setSetTitle] = useState("My study set");
  const [saveBusy, setSaveBusy] = useState(false);
  const [savedNotice, setSavedNotice] = useState("");

  async function refreshSavedSets() {
    try {
      const response = await fetch("/backend/api/study-tools/saved", { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) return;
      const data = await response.json();
      setSavedSets(Array.isArray(data.study_sets) ? data.study_sets : []);
    } catch { /* Saved sets are optional when the service is offline. */ }
  }

  useEffect(() => { void refreshSavedSets(); }, []);

  async function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(""); setResult(null); setRevealed([]); setBusy(true);
    try {
      const csrfResponse = await fetch("/backend/api/csrf", { credentials: "same-origin", cache: "no-store" });
      const csrf = await csrfResponse.json().catch(() => ({}));
      if (!csrfResponse.ok || typeof csrf.csrfToken !== "string") throw new Error("Please sign in and refresh your session before generating study materials.");
      const response = await fetch("/backend/api/study-tools", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf.csrfToken, "X-Requested-With": "XMLHttpRequest", Accept: "application/json" },
        body: JSON.stringify({ text: source, mode: "auto" })
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || (response.status === 401 ? "Sign in to use Study Tools." : "Could not generate study materials."));
      setResult(data as StudyResult);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Study tools are temporarily unavailable."); }
    finally { setBusy(false); }
  }

  async function saveCurrentSet() {
    if (!result || source.trim().length < 100) return;
    setSaveBusy(true); setSavedNotice(""); setError("");
    try {
      const csrfResponse = await fetch("/backend/api/csrf", { credentials: "same-origin", cache: "no-store" });
      const csrf = await csrfResponse.json().catch(() => ({}));
      if (!csrfResponse.ok || typeof csrf.csrfToken !== "string") throw new Error("Sign in again to save this study set.");
      const response = await fetch("/backend/api/study-tools", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf.csrfToken, "X-Requested-With": "XMLHttpRequest", Accept: "application/json" },
        body: JSON.stringify({ text: source, mode: "auto", save: true, title: setTitle })
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || "Could not save this study set.");
      setResult(data as StudyResult); setSavedNotice("Study set saved to your account."); await refreshSavedSets();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not save this study set."); }
    finally { setSaveBusy(false); }
  }

  async function openSavedSet(id: number) {
    setError(""); setSavedNotice("");
    try {
      const response = await fetch(`/backend/api/study-tools/saved/${id}`, { credentials: "same-origin", cache: "no-store" });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || "Could not open this saved set.");
      setResult(data.result as StudyResult); setSetTitle(data.title || "My study set"); setRevealed([]);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not open this saved set."); }
  }

  async function deleteSavedSet(id: number) {
    setError(""); setSavedNotice("");
    try {
      const csrfResponse = await fetch("/backend/api/csrf", { credentials: "same-origin", cache: "no-store" });
      const csrf = await csrfResponse.json().catch(() => ({}));
      if (!csrfResponse.ok || typeof csrf.csrfToken !== "string") throw new Error("Refresh your session before deleting a saved set.");
      const response = await fetch(`/backend/api/study-tools/saved/${id}`, { method: "DELETE", credentials: "same-origin", headers: { "X-CSRF-Token": csrf.csrfToken, "X-Requested-With": "XMLHttpRequest", Accept: "application/json" } });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || "Could not delete this study set.");
      setSavedSets(items => items.filter(item => item.id !== id)); setSavedNotice("Saved study set deleted.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not delete this study set."); }
  }

  return <main className="eco-detail-page" style={{ maxWidth: 1120 }}>
    <nav className="eco-breadcrumb"><Link href="/">Home</Link><span>/</span><b>AI Study Tools</b></nav>
    <section className="eco-detail-hero"><div><span className="eco-eyebrow"><Sparkles size={14}/> LEARNING WORKSPACE</span><h1>Turn reading into <span>understanding.</span></h1><p>Build a chapter summary, quick knowledge check, and revision flashcards from text you are authorized to use.</p><div className="eco-hero-actions"><Link href="/ecosystem" className="eco-secondary"><ArrowLeft size={15}/> All modules</Link></div></div><div className="eco-detail-art"><div className="eco-detail-art-glow"><BrainCircuit size={62}/><span>Study smarter</span></div><div className="eco-detail-orb"/></div></section>
    <section className="eco-detail-panel" style={{ marginTop: 28 }}><span className="eco-kicker">CHAPTER WORKBENCH</span><h2>Paste your chapter or notes</h2><p className="eco-detail-intro">LibraAI uses a configured AI provider when available, with a transparent local-analysis fallback. Use your own text or content you have permission to process.</p>
      <form onSubmit={generate} style={{ display: "grid", gap: 14 }}><label htmlFor="study-title">Study set name</label><input id="study-title" value={setTitle} onChange={event => setSetTitle(event.target.value)} maxLength={120} placeholder="e.g. Chapter 1 revision" style={{ width: "100%", borderRadius: 12, padding: 12, border: "1px solid var(--line, #d9d9e7)", background: "var(--surface, #fff)", color: "inherit", font: "inherit" }} /><label htmlFor="study-source">Chapter text</label><textarea id="study-source" value={source} onChange={event => setSource(event.target.value)} minLength={100} maxLength={20000} required rows={9} placeholder="Paste at least 100 characters of chapter text or study notes…" style={{ width: "100%", resize: "vertical", borderRadius: 16, padding: 16, border: "1px solid var(--line, #d9d9e7)", background: "var(--surface, #fff)", color: "inherit", font: "inherit", lineHeight: 1.7 }} /><div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}><small>{source.length.toLocaleString()} / 20,000 characters · Minimum 100</small><button className="eco-primary" type="submit" disabled={busy || source.trim().length < 100}>{busy ? <><LoaderCircle size={16} className="spin"/> Generating…</> : <><Sparkles size={16}/> Generate study set</>}</button>{result && source.trim().length >= 100 && <button className="eco-secondary" type="button" onClick={() => void saveCurrentSet()} disabled={saveBusy || busy}>{saveBusy ? <><LoaderCircle size={16} className="spin"/> Saving…</> : "Save to my library"}</button>}</div></form>
      {savedNotice && <p role="status" style={{ color: "#17684e", marginTop: 12 }}>{savedNotice}</p>}
      <section className="eco-detail-panel" style={{ marginTop: 18 }}><span className="eco-kicker">YOUR STUDY LIBRARY</span><h2>Saved study sets</h2><p className="eco-detail-intro">Saved sets are private to your account and can be reopened or deleted later.</p>{savedSets.length ? <div style={{ display: "grid", gap: 10 }}>{savedSets.map(item => <div key={item.id} style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap", borderBottom: "1px solid var(--line, #e5e7eb)", padding: "10px 0" }}><div><strong>{item.title}</strong><small style={{ display: "block", opacity: .7 }}>{item.created_at}</small></div><div style={{ display: "flex", gap: 8 }}><button type="button" className="eco-secondary" onClick={() => void openSavedSet(item.id)}>Open</button><button type="button" className="eco-secondary" onClick={() => void deleteSavedSet(item.id)} aria-label={`Delete ${item.title}`}>Delete</button></div></div>)}</div> : <p className="eco-detail-intro">No saved study sets yet. Generate a set and choose Save to your library.</p>}</section>
      {error && <p role="alert" style={{ color: "#b42318", marginTop: 16 }}>{error} {error.toLowerCase().includes("sign in") && <Link href="/login">Sign in</Link>}</p>}
    </section>
    {result && <div style={{ display: "grid", gap: 20, marginTop: 24 }}>
      <section className="eco-detail-panel"><span className="eco-kicker"><BookOpen size={14}/> CHAPTER SUMMARY · {result.mode === "ai-assisted" ? "AI-ASSISTED" : "LOCAL ANALYSIS"}</span><h2>Key ideas at a glance</h2><p style={{ lineHeight: 1.85, whiteSpace: "pre-wrap" }}>{result.summary}</p><div className="eco-capability-list">{result.keywords.map(word => <span key={word} className="eco-secondary" style={{ display: "inline-flex", margin: 4 }}>{word}</span>)}</div></section>
      <section className="eco-detail-panel"><span className="eco-kicker"><CheckCircle2 size={14}/> KNOWLEDGE CHECK</span><h2>Quick quiz</h2>{result.quiz.length ? result.quiz.map((item, index) => <details key={`${index}-${item.question}`} style={{ padding: "14px 0", borderBottom: "1px solid var(--line, #e5e7eb)" }}><summary style={{ cursor: "pointer", fontWeight: 650 }}>{index + 1}. {item.question}</summary><p style={{ marginTop: 10 }}>Answer: <strong>{item.answer}</strong></p></details>) : <p>Could not identify clear keywords for fill-in-the-blank questions. Review the summary and flashcards below.</p>}</section>
      <section className="eco-detail-panel"><span className="eco-kicker"><BrainCircuit size={14}/> REVISION CARDS</span><h2>Flashcards</h2><div className="eco-capability-list">{result.flashcards.map((card, index) => <button key={`${index}-${card.front}`} type="button" className="eco-capability-link" onClick={() => setRevealed(old => old.includes(index) ? old.filter(n => n !== index) : [...old, index])} style={{ width: "100%", textAlign: "left", cursor: "pointer", color: "inherit", background: "transparent" }}><span><Sparkles size={17}/></span><p>{revealed.includes(index) ? card.back : card.front}</p><small>{revealed.includes(index) ? "ANSWER" : "REVEAL"}</small></button>)}</div><p className="eco-detail-intro" style={{ marginTop: 16 }}>{result.notice}</p></section>
    </div>}
    <footer className="eco-footer"><Link href="/" className="eco-brand"><span className="eco-brand-mark"><BookOpen size={17}/></span>LibraAI</Link><span>One connected ecosystem for reading, learning and library operations.</span><nav><Link href="/library">Library</Link><Link href="/help">Help</Link><Link href="/login">Sign in</Link></nav><small>© LibraAI · Designed for accessible knowledge</small></footer>
  </main>;
}
