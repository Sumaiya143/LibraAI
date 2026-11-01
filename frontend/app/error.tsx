"use client";
import { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";
export default function ErrorPage({error,reset}:{error:Error & {digest?:string};reset:()=>void}){useEffect(()=>{console.error(error)},[error]);return <main className="system-state-page"><div className="system-state-card"><div className="system-state-icon"><AlertTriangle size={30}/></div><span className="system-state-code">TEMPORARY ISSUE</span><h1>We couldn’t load this page.</h1><p>Your account and data have not been changed by this screen. You can try again or return to a safe page.</p><div className="system-state-actions"><button className="btn btn-primary" onClick={()=>reset()}><RefreshCw size={16}/> Try again</button><Link className="btn btn-ghost" href="/"><Home size={16}/> Home</Link></div><small>If the problem continues, contact LibraAI support and include the time it occurred.</small></div></main>}
