 "use client";
import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, X } from "lucide-react";

export type NoticeData = { message: string; kind?: "error" | "success" | "info" } | null;
export default function Notice({ notice, clear }: { notice: NoticeData; clear: () => void }) {
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(clear, 5200);
    return () => clearTimeout(timer);
  }, [notice, clear]);
  if (!notice) return null;
  const error = notice.kind === "error";
  return <div role="status" aria-live="polite" className={`notice ${error ? "notice-error" : "notice-success"}`}>
    {error ? <AlertCircle size={19}/> : <CheckCircle2 size={19}/>}
    <span>{notice.message}</span><button aria-label="Dismiss notification" onClick={clear}><X size={17}/></button>
  </div>;
}
