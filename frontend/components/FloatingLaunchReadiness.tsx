"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, ChevronRight, CircleHelp, ClipboardCheck, ExternalLink, RefreshCw, X } from "lucide-react";

type Item = { id: string; title: string; status: "ready" | "blocked" | "manual" | "optional"; summary: string; action: string; href: string; routes: string[] };
type Report = { items: Item[]; open_count: number; launch_ready: boolean; scope: string };
const statusLabel: Record<Item["status"], string> = { ready: "Ready", blocked: "Needs action", manual: "Manual process", optional: "Optional setup" };

export default function FloatingLaunchReadiness() {
  const [report, setReport] = useState<Report | null>(null);
  const [visible, setVisible] = useState(true);
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState<"all" | "action">("action");
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  const [lastChecked, setLastChecked] = useState<number | null>(null);
  const autoOpened = useRef(false);
  const requestId = useRef(0);

  const refresh = useCallback(async () => {
    const currentRequest = ++requestId.current;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 10000);
    setChecking(true);
    setError("");
    try {
      let response = await fetch("/backend/api/setup/readiness", { cache: "no-store", credentials: "same-origin", signal: controller.signal, headers: { Accept: "application/json" } });
      // Non-admin users receive only generic public-safe setup notices. Never
      // hide the launcher merely because the detailed operator report is denied.
      if (response.status === 401 || response.status === 403) {
        response = await fetch("/backend/api/setup/notices", { cache: "no-store", credentials: "same-origin", signal: controller.signal, headers: { Accept: "application/json" } });
      }
      if (!response.ok) throw new Error(`Readiness service returned ${response.status}`);
      const data = await response.json();
      if (!Array.isArray(data?.items) || typeof data?.open_count !== "number") throw new Error("Readiness response was incomplete");
      if (currentRequest === requestId.current) {
        setVisible(data.scope === "generic operator actions only; no secret or provider configuration details exposed" ? data.items.length > 0 : true);
        setReport(data as Report);
        setLastChecked(Date.now());
      }
    } catch (err) {
      if (currentRequest === requestId.current) {
        setVisible(true);
        setOpen(true);
        setError(err instanceof Error && err.name === "AbortError" ? "Status check timed out. Try again." : "Could not check launch status. The backend may be unavailable.");
      }
    } finally {
      window.clearTimeout(timeout);
      if (currentRequest === requestId.current) setChecking(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const onShow = () => { setOpen(true); void refresh(); };
    const blockerEvents = ["libraai-open-launch-readiness", "libraai-launch-blocker", "libraai-payment-credentials-needed", "libraai-license-required", "libraai-ai-provider-needed", "libraai-payout-provider-needed"];
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    blockerEvents.forEach(name => window.addEventListener(name, onShow));
    window.addEventListener("keydown", onKeyDown);
    return () => {
      blockerEvents.forEach(name => window.removeEventListener(name, onShow));
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [refresh]);

  useEffect(() => {
    if (!open) return;
    const interval = window.setInterval(() => { if (document.visibilityState === "visible") void refresh(); }, 60000);
    return () => window.clearInterval(interval);
  }, [open, refresh]);

  useEffect(() => {
    if (!report || autoOpened.current) return;
    const path = window.location.pathname.toLowerCase().replace(/^\//, "");
    const related = report.items.filter(item => item.status !== "ready" && item.routes.some(route => path.includes(route)));
    const routeKey = related.length ? `libraai-readiness-route-${related[0].id}` : "libraai-readiness-intro-dismissed";
    let alreadyShown = false;
    try { alreadyShown = Boolean(window.sessionStorage.getItem(routeKey)); } catch { /* Storage can be disabled. */ }
    autoOpened.current = true;
    if (!alreadyShown) {
      const timer = window.setTimeout(() => setOpen(true), 650);
      try { window.sessionStorage.setItem(routeKey, "1"); if (related.length) window.sessionStorage.setItem("libraai-readiness-intro-dismissed", "1"); } catch { /* The card remains available through the launcher. */ }
      return () => window.clearTimeout(timer);
    }
  }, [report]);

  const pending = useMemo(() => (report?.items || []).filter(item => filter === "all" || item.status !== "ready"), [report, filter]);
  const dismiss = () => { setOpen(false); try { window.sessionStorage.setItem("libraai-readiness-intro-dismissed", "1"); } catch { /* Optional convenience only. */ } };
  const checkedLabel = lastChecked ? `Updated ${new Date(lastChecked).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : "Not checked yet";

  if (!visible) return null;

  return <>
    <button className={`launch-readiness-launcher ${report?.open_count ? "has-open-items" : "is-ready"}`} onClick={() => { setOpen(v => !v); void refresh(); }} aria-expanded={open} aria-controls="launch-readiness-panel" aria-label="Open LibraAI launch readiness checklist">
      {report?.open_count ? <AlertTriangle size={17}/> : <CheckCircle2 size={17}/>}<span>{report?.open_count ? `Setup checklist · ${report.open_count}` : "Launch readiness"}</span>{Boolean(report?.open_count) && <i aria-hidden="true"/>}
    </button>
    {open && <aside id="launch-readiness-panel" className="launch-readiness-panel" role="dialog" aria-modal="false" aria-labelledby="launch-readiness-title">
      <header className="launch-readiness-head"><span className="launch-readiness-icon"><ClipboardCheck size={20}/></span><div><strong id="launch-readiness-title">LibraAI launch checklist</strong><small>{report?.open_count ? `${report.open_count} items need attention or manual completion` : "Readiness overview"}</small></div><button onClick={() => void refresh()} aria-label="Refresh launch status" title="Refresh launch status" disabled={checking}><RefreshCw size={16} className={checking ? "launch-readiness-spinning" : ""}/></button><button onClick={dismiss} aria-label="Close launch checklist"><X size={18}/></button></header>
      <div className={`launch-readiness-summary ${report?.open_count ? "waiting" : "ok"}`}>{report?.open_count ? <AlertTriangle size={16}/> : <CheckCircle2 size={16}/>}<span>{error ? "Status could not be verified" : checking && !report ? "Checking launch dependencies…" : report?.open_count ? "Some launch dependencies remain" : report ? "No configured blockers detected" : "Waiting for status check"}</span></div>
      <div className="launch-readiness-last-checked" aria-live="polite">{checkedLabel}{checking ? " · Refreshing…" : ""}</div>
      {error && <div className="launch-readiness-error" role="alert"><span>{error}</span><button onClick={() => void refresh()} disabled={checking}>Try again</button></div>}
      <p className="launch-readiness-disclaimer">This checklist never asks for passwords or API keys. Public users see generic external-action notices; only admins can view detailed configuration checks. It cannot independently verify legal rights, live transfers or security reviews.</p>
      <div className="launch-readiness-filter"><button className={filter === "action" ? "active" : ""} onClick={() => setFilter("action")}>Needs attention</button><button className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>All items</button></div>
      <div className="launch-readiness-items" aria-live="polite">
        {!report && !error && <div className="launch-readiness-empty">Checking setup status…</div>}
        {report && pending.length === 0 && <div className="launch-readiness-empty"><CheckCircle2 size={18}/> No remaining items in this view.</div>}
        {pending.map(item => <article key={item.id} className={`launch-readiness-item ${item.status}`}>
          <div className="launch-readiness-item-top"><b>{item.title}</b><span className={`launch-status ${item.status}`}>{statusLabel[item.status]}</span></div>
          <p>{item.summary}</p>
          <a href={item.href} onClick={dismiss}>{item.action}<ChevronRight size={14}/></a>
        </article>)}
      </div>
      <footer className="launch-readiness-foot"><span><CircleHelp size={13}/> No credentials are collected here.</span><a href="/help" onClick={dismiss}>Help centre <ExternalLink size={12}/></a></footer>
    </aside>}
  </>;
}
