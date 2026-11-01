"use client";
import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";
type Notice = { message: string; kind?: "error" | "success" | "info" };
export default function GlobalNotice() {
  const [notice, setNotice] = useState<Notice | null>(null);
  useEffect(() => {
    const onNotice = (event: Event) => { const detail = (event as CustomEvent<Notice>).detail; if (detail?.message) setNotice(detail); };
    window.addEventListener("libraai-notice", onNotice);
    return () => window.removeEventListener("libraai-notice", onNotice);
  }, []);
  useEffect(() => { if (!notice) return; const timer = window.setTimeout(() => setNotice(null), 5200); return () => window.clearTimeout(timer); }, [notice]);
  if (!notice) return null;
  const Icon = notice.kind === "error" ? AlertCircle : notice.kind === "success" ? CheckCircle2 : Info;
  return <div className={`libra-global-toast ${notice.kind || "info"}`} role="status" aria-live="polite"><Icon size={18}/><span>{notice.message}</span><button onClick={() => setNotice(null)} aria-label="Dismiss notification"><X size={16}/></button></div>;
}
