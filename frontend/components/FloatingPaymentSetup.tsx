"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, ChevronDown, CreditCard, ExternalLink, ShieldCheck, X } from "lucide-react";

type Provider = { configured: boolean; sandbox: boolean };
type Readiness = { ready: boolean; providers: { sslcommerz: Provider; bkash: Provider }; missing_providers: string[]; live_transactions_verified: boolean; message: string };

export default function FloatingPaymentSetup() {
  const [status, setStatus] = useState<Readiness | null>(null);
  const [open, setOpen] = useState(false);
  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/backend/api/payments/readiness", { cache: "no-store", credentials: "same-origin" });
      if (!response.ok) return;
      const data = await response.json();
      if (data && typeof data.ready === "boolean" && data.providers) setStatus(data as Readiness);
    } catch { /* Backend may be offline in local preview; the notice stays non-blocking. */ }
  }, []);

  useEffect(() => {
    void refresh();
    const onCredentialsNeeded = () => { setOpen(true); void refresh(); };
    const onShow = () => setOpen(true);
    window.addEventListener("libraai-payment-credentials-needed", onCredentialsNeeded);
    window.addEventListener("libraai-open-payment-setup", onShow);
    const path = window.location.pathname.toLowerCase();
    if (/checkout|cart-orders|wallet-payments|payment|orders/.test(path)) setOpen(true);
    return () => {
      window.removeEventListener("libraai-payment-credentials-needed", onCredentialsNeeded);
      window.removeEventListener("libraai-open-payment-setup", onShow);
    };
  }, [refresh]);

  if (!status) return <button className="payment-setup-launcher" onClick={() => { setOpen(value => !value); void refresh(); }} aria-expanded={open} aria-label="Open payment setup status"><CreditCard size={17}/><span>Payment setup</span></button>;
  const ready = status.ready && status.live_transactions_verified && !status.providers.sslcommerz.sandbox && !status.providers.bkash.sandbox;
  const pending = !ready;
  return <>
    <button className={`payment-setup-launcher ${pending ? "pending" : "ready"}`} onClick={() => setOpen(value => !value)} aria-expanded={open} aria-controls="payment-setup-panel">
      {pending ? <AlertTriangle size={17}/> : <CheckCircle2 size={17}/>}<span>{ready ? "Payments ready" : "Payment setup"}</span>{pending && <i aria-hidden="true"/>}
    </button>
    {open && <aside id="payment-setup-panel" className="payment-setup-panel" role="dialog" aria-modal="false" aria-labelledby="payment-setup-title">
      <header><span className="payment-setup-icon"><CreditCard size={19}/></span><div><strong id="payment-setup-title">Payment launch checklist</strong><small>LibraAI secure checkout</small></div><button onClick={() => setOpen(false)} aria-label="Close payment setup"><X size={18}/></button></header>
      <div className={`payment-setup-status ${ready ? "ok" : "waiting"}`}>{ready ? <CheckCircle2 size={16}/> : <AlertTriangle size={16}/>}<span>{ready ? "Configuration looks ready" : "Live payments are not enabled yet"}</span></div>
      <p>Checkout must remain in setup mode until merchant credentials are added securely and real sandbox/live transactions are verified. No payment credentials are requested in this window.</p>
      <div className="payment-setup-providers">
        <div><span><b>SSLCommerz</b><small>{status.providers.sslcommerz.configured ? (status.providers.sslcommerz.sandbox ? "Credentials set · Sandbox mode" : "Credentials set · Live mode") : "Merchant credentials required"}</small></span>{status.providers.sslcommerz.configured ? <CheckCircle2 size={17}/> : <AlertTriangle size={17}/>}</div>
        <div><span><b>bKash</b><small>{status.providers.bkash.configured ? (status.providers.bkash.sandbox ? "Credentials set · Sandbox mode" : "Credentials set · Live mode") : "Merchant credentials required"}</small></span>{status.providers.bkash.configured ? <CheckCircle2 size={17}/> : <AlertTriangle size={17}/>}</div>
      </div>
      <div className="payment-setup-next"><ShieldCheck size={17}/><div><b>When you're ready</b><ol><li>Get approved merchant credentials from your chosen provider.</li><li>Add them to the server environment or secret manager—not the frontend.</li><li>Set the HTTPS callback URL and verify successful, failed, cancelled and refund flows.</li><li>Only then mark live payment E2E as verified.</li></ol></div></div>
      <footer><span><ShieldCheck size={13}/> Credentials are never displayed here.</span><a href="/help">Payment setup help <ExternalLink size={13}/></a></footer>
    </aside>}
  </>;
}
