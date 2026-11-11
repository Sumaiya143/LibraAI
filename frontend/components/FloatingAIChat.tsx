"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import Link from "next/link";
import { Bot, Sparkles, X, Send, BookOpen, ShieldCheck, LoaderCircle, MessageCircle, ArrowUpRight, Trash2 } from "lucide-react";

type Message = { role: "assistant" | "user"; text: string };
const welcome: Message = { role: "assistant", text: "Hello! I’m LibraAI, your reading and learning assistant. Ask about reading strategies, study planning, or your library." };

export default function FloatingAIChat() {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState<Message[]>([welcome]);
  const [historyReady, setHistoryReady] = useState(false);
  const syncQueue = useRef<Promise<void>>(Promise.resolve());
  const [notice, setNotice] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Restore account history when authenticated; retain device-local fallback for guests/offline use.
  useEffect(() => {
    let cancelled = false;
    const restore = async () => {
      let local: Message[] = [];
      try {
        const raw = window.localStorage.getItem("libraai-ai-chat-history-v1");
        const parsed: unknown = raw ? JSON.parse(raw) : [];
        if (Array.isArray(parsed)) local = parsed.filter((item): item is Message =>
          !!item && typeof item === "object" &&
          ((item as Message).role === "assistant" || (item as Message).role === "user") &&
          typeof (item as Message).text === "string" && (item as Message).text.length <= 4000
        ).slice(-100);
      } catch { /* Ignore malformed or disabled browser storage. */ }
      try {
        const response = await fetch("/backend/api/ai/history", { credentials: "same-origin", cache: "no-store" });
        if (response.ok) {
          const data = await response.json();
          if (Array.isArray(data.messages) && data.messages.length && !cancelled) {
            const serverMessages = data.messages.filter((item: unknown): item is Message =>
              !!item && typeof item === "object" &&
              ((item as Message).role === "assistant" || (item as Message).role === "user") &&
              typeof (item as Message).text === "string" && (item as Message).text.length <= 4000
            ).slice(-100);
            if (serverMessages.length) setMessages(serverMessages);
          } else if (!cancelled) setMessages([welcome]);
        } else if (local.length && !cancelled) setMessages(local);
      } catch { if (local.length && !cancelled) setMessages(local); }
      if (!cancelled) setHistoryReady(true);
    };
    void restore();
    return () => { cancelled = true; };
  }, []);

  // Keep a local backup and sync signed-in conversations to the server database.
  useEffect(() => {
    if (!historyReady) return;
    const safeMessages = messages.slice(-100).filter(message =>
      (message.role === "assistant" || message.role === "user") && typeof message.text === "string" && message.text.length <= 4000
    );
    try { window.localStorage.setItem("libraai-ai-chat-history-v1", JSON.stringify(safeMessages)); }
    catch { /* Chat remains usable if storage is unavailable. */ }
    syncQueue.current = syncQueue.current.then(async () => {
      try {
        const csrfResponse = await fetch("/backend/api/csrf", { credentials: "same-origin", cache: "no-store" });
        if (!csrfResponse.ok) return;
        const csrfData = await csrfResponse.json().catch(() => ({}));
        if (typeof csrfData.csrfToken !== "string" || !csrfData.csrfToken) return;
        await fetch("/backend/api/ai/history", {
          method: "POST", credentials: "same-origin", headers: {
            "Content-Type": "application/json", "X-CSRF-Token": csrfData.csrfToken,
            "X-Requested-With": "XMLHttpRequest", "Accept": "application/json"
          }, body: JSON.stringify({ messages: safeMessages })
        });
      } catch { /* Local backup remains available when the backend is offline. */ }
    }).catch(() => undefined);
  }, [messages, historyReady]);

  const clearHistory = () => {
    setMessages([welcome]);
    setNotice("Conversation history cleared on this device.");
    try { window.localStorage.removeItem("libraai-ai-chat-history-v1"); } catch { /* best effort */ }
  };

  useEffect(() => {
    const openChat = () => { setOpen(true); setNotice(""); };
    const onEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false);
      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "a") { event.preventDefault(); setOpen(true); } };
    window.addEventListener("libraai-open-assistant", openChat);
    window.addEventListener("keydown", onEscape);
    return () => { window.removeEventListener("libraai-open-assistant", openChat); window.removeEventListener("keydown", onEscape); };
  }, []);
  useEffect(() => { if (open) inputRef.current?.focus(); }, [open]);
  useEffect(() => { if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight; }, [messages, busy, open]);

  const send = async (event?: FormEvent, suggestion?: string) => {
    event?.preventDefault();
    const question = (suggestion ?? draft).trim();
    if (!question || busy) return;
    setDraft(""); setNotice(""); setMessages(old => [...old, { role: "user", text: question }]); setBusy(true);
    try {
      const csrfResponse = await fetch("/backend/api/csrf", { method: "GET", credentials: "same-origin", cache: "no-store" });
      if (!csrfResponse.ok) throw new Error("csrf");
      const csrfData = await csrfResponse.json().catch(() => ({}));
      if (typeof csrfData.csrfToken !== "string" || !csrfData.csrfToken) throw new Error("csrf");
      const response = await fetch("/backend/api/ai", {
        method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfData.csrfToken, "X-Requested-With": "XMLHttpRequest", "Accept": "application/json" },
        body: JSON.stringify({ question })
      });
      const contentType = response.headers.get("content-type") || "";
      const data = contentType.includes("application/json") ? await response.json().catch(() => ({})) : {};
      const redirectedToLogin = response.redirected && /\/login(?:[/?#]|$)/i.test(response.url);
      if (response.status === 401 || response.status === 403 || redirectedToLogin) {
        setMessages(old => [...old, { role: "assistant", text: response.status === 403 ? "Your current account does not have permission for that action. You can review access help or contact support." : "Please sign in first so I can securely access account-specific library information." }]);
        setNotice(response.status === 403 ? "Access is restricted for this account. No action was taken." : "Sign in is required for account-specific AI features.");
      } else if (typeof data.answer === "string" && data.answer.trim()) {
        setMessages(old => [...old, { role: "assistant", text: data.answer }]);
        if (!response.ok || ["provider_unavailable", "evidence_only"].includes(String(data.status))) setNotice("AI provider is not fully available. This response may contain only authorized source passages.");
      } else {
        setMessages(old => [...old, { role: "assistant", text: data.error || "The AI service is not available right now. Your message has not been lost—please try again later." }]);
        setNotice("AI service unavailable. Check provider setup or try again later.");
      }
    } catch {
      setMessages(old => [...old, { role: "assistant", text: "I couldn’t reach the LibraAI service or verify your secure session. Please refresh the page, sign in again if needed, and retry." }]);
      setNotice("Could not connect or verify the secure session. Refresh and try again.");
    } finally { setBusy(false); }
  };

  return <>
    {open && <section id="libraai-assistant-window" className="libra-ai-window" role="dialog" aria-modal="false" aria-label="LibraAI AI assistant">
      <header className="libra-ai-window-head"><span className="libra-ai-avatar"><Bot size={21}/></span><span className="libra-ai-head-copy"><b>LibraAI Assistant</b><small><span className="libra-ai-online-dot"/> Reading & learning support</small></span><button className="libra-ai-close" onClick={clearHistory} aria-label="Clear conversation history" title="Clear conversation history"><Trash2 size={16}/></button><button className="libra-ai-close" onClick={() => setOpen(false)} aria-label="Close AI assistant"><X size={19}/></button></header>
      <div className="libra-ai-trust"><ShieldCheck size={13}/> Avoid sharing passwords or payment details.</div>
      <div className="libra-ai-messages" ref={listRef} aria-live="polite">{messages.map((message, index) => <div className={`libra-ai-message ${message.role}`} key={`${index}-${message.role}`}><span className="libra-ai-message-icon">{message.role === "assistant" ? <Sparkles size={13}/> : <MessageCircle size={13}/>}</span><p>{message.text}</p></div>)}{busy && <div className="libra-ai-typing"><LoaderCircle size={15}/> LibraAI is thinking…</div>}</div>
      {messages.length === 1 && <div className="libra-ai-prompts"><span>Try asking</span>{["Help me build a reading plan", "How can I study more effectively?", "Summarize a topic I provide"].map(prompt => <button key={prompt} onClick={() => void send(undefined, prompt)} disabled={busy}>{prompt}<ArrowUpRight size={13}/></button>)}</div>}
      {notice && <div className="libra-ai-notice" role="status">{notice} {notice.includes("Sign in") && <Link href="/login" onClick={() => setOpen(false)}>Sign in</Link>}{notice.includes("Access is restricted") && <Link href="/help" onClick={() => setOpen(false)}>Get help</Link>}</div>}
      <form className="libra-ai-compose" onSubmit={send}><input ref={inputRef} value={draft} onChange={event => setDraft(event.target.value)} maxLength={2000} placeholder="Ask LibraAI anything…" aria-label="Message LibraAI"/><button type="submit" disabled={!draft.trim() || busy} aria-label="Send message"><Send size={17}/></button></form>
      <footer className="libra-ai-foot"><BookOpen size={12}/> History syncs to your account when signed in; this browser keeps a local backup. Answers depend on available sources and AI provider setup.</footer>
    </section>}
    <button className={`libra-ai-launcher ${open ? "is-open" : ""}`} onClick={() => setOpen(value => !value)} aria-label={open ? "Close LibraAI chatbot" : "Open LibraAI AI chatbot"} aria-expanded={open} aria-controls="libraai-assistant-window"><span className="libra-ai-launcher-icon">{open ? <X size={23}/> : <><Bot size={25}/><Sparkles size={11} className="libra-ai-sparkle"/></>}</span><span className="libra-ai-launcher-label">Ask AI</span></button>
  </>;
}
