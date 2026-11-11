 "use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  ArrowRight, BookOpen, Check, Eye, EyeOff, LockKeyhole, Mail,
  ShieldCheck, Sparkles, UserRound, UsersRound
} from "lucide-react";
import Notice, { NoticeData } from "@/components/Notice";

type AuthMode = "signin" | "signup";
type Role = "customer" | "merchant";

const roles = [
  {
    id: "customer" as const,
    name: "Reader / Customer",
    desc: "Discover books and build your personal library.",
    points: ["Buy books & audiobooks", "Save notes & bookmarks", "Personalized recommendations"],
    icon: BookOpen
  },
  {
    id: "merchant" as const,
    name: "Seller",
    desc: "Share your work and manage your own store.",
    points: ["List your products", "Manage your store", "Track your earnings"],
    icon: UsersRound
  }
];

function ParticleCanvas({ rootRef }: { rootRef: React.RefObject<HTMLElement | null> }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const root = rootRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !root || !ctx) return;

    type Node = { x: number; y: number; vx: number; vy: number; radius: number; phase: number };
    type Ripple = { x: number; y: number; radius: number; alpha: number };
    let width = 0, height = 0, raf = 0, visible = !document.hidden;
    let nodes: Node[] = [];
    const ripples: Ripple[] = [];
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const pointer = { x: -1000, y: -1000, active: false };
    const palette = ["rgba(86, 105, 231,", "rgba(142, 91, 226,", "rgba(91, 151, 214,"];

    const resize = () => {
      const rect = root.getBoundingClientRect();
      width = Math.max(1, rect.width);
      height = Math.max(1, rect.height);
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.max(14, Math.min(48, Math.round(width / (window.innerWidth < 700 ? 42 : 27))));
      nodes = Array.from({ length: count }, (_, i) => ({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - .5) * .28,
        vy: (Math.random() - .5) * .28,
        radius: 1 + Math.random() * 1.5,
        phase: i * .7
      }));
      draw();
    };

    const draw = () => {
      ctx.clearRect(0, 0, width, height);
      const maxLink = width < 650 ? 92 : 138;
      nodes.forEach((node, i) => {
        if (!reduceMotion) {
          node.x += node.vx;
          node.y += node.vy;
          node.phase += .008;
          node.x += Math.sin(node.phase) * .08;
          node.y += Math.cos(node.phase * .8) * .08;
          if (node.x < -8) node.x = width + 8;
          if (node.x > width + 8) node.x = -8;
          if (node.y < -8) node.y = height + 8;
          if (node.y > height + 8) node.y = -8;
          if (pointer.active) {
            const dx = node.x - pointer.x, dy = node.y - pointer.y;
            const distance = Math.hypot(dx, dy);
            if (distance < 150 && distance > 0) {
              const force = (150 - distance) / 150 * .012;
              node.x += dx * force;
              node.y += dy * force;
            }
          }
        }
        for (let j = i + 1; j < nodes.length; j++) {
          const other = nodes[j];
          const distance = Math.hypot(node.x - other.x, node.y - other.y);
          if (distance < maxLink) {
            const alpha = (1 - distance / maxLink) * .19;
            ctx.strokeStyle = `rgba(104, 111, 206, ${alpha})`;
            ctx.lineWidth = .7;
            ctx.beginPath();
            ctx.moveTo(node.x, node.y);
            ctx.lineTo(other.x, other.y);
            ctx.stroke();
          }
        }
        const color = palette[i % palette.length];
        ctx.fillStyle = `${color} 0.42)`;
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = `${color} 0.08)`;
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.radius * 4.2, 0, Math.PI * 2);
        ctx.fill();
      });

      for (let i = ripples.length - 1; i >= 0; i--) {
        const ripple = ripples[i];
        ctx.beginPath();
        ctx.arc(ripple.x, ripple.y, ripple.radius, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(105, 101, 222, ${ripple.alpha})`;
        ctx.lineWidth = 1;
        ctx.stroke();
        ripple.radius += 1.7;
        ripple.alpha -= .009;
        if (ripple.alpha <= 0) ripples.splice(i, 1);
      }
    };

    const animate = () => {
      if (!visible) return;
      draw();
      if (!reduceMotion) raf = window.requestAnimationFrame(animate);
    };
    const onMove = (event: PointerEvent) => {
      const rect = root.getBoundingClientRect();
      pointer.x = event.clientX - rect.left;
      pointer.y = event.clientY - rect.top;
      pointer.active = pointer.x >= 0 && pointer.y >= 0 && pointer.x <= width && pointer.y <= height;
    };
    const onLeave = () => { pointer.active = false; };
    const onDown = (event: PointerEvent) => {
      const rect = root.getBoundingClientRect();
      if (ripples.length < 5) ripples.push({ x: event.clientX - rect.left, y: event.clientY - rect.top, radius: 4, alpha: .34 });
    };
    const onVisibility = () => {
      visible = !document.hidden;
      if (visible) {
        if (raf) cancelAnimationFrame(raf);
        animate();
      } else if (raf) cancelAnimationFrame(raf);
    };

    resize();
    window.addEventListener("resize", resize, { passive: true });
    window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("pointerdown", onDown, { passive: true });
    window.addEventListener("pointerout", onLeave, { passive: true });
    document.addEventListener("visibilitychange", onVisibility);
    animate();

    return () => {
      if (raf) cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerdown", onDown);
      window.removeEventListener("pointerout", onLeave);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [rootRef]);

  return <canvas ref={canvasRef} className="libra-auth-particles" aria-hidden="true" />;
}

export default function AuthExperience({ initialMode }: { initialMode: AuthMode }) {
  const [mode, setMode] = useState<AuthMode>(initialMode);
  const [identifier, setIdentifier] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [signupPassword, setSignupPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [role, setRole] = useState<Role>("customer");
  const [showLoginPassword, setShowLoginPassword] = useState(false);
  const [showSignupPassword, setShowSignupPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<NoticeData>(null);
  const rootRef = useRef<HTMLElement>(null);

  useEffect(() => {
    setMode(initialMode);
  }, [initialMode]);

  useEffect(() => {
    const onPopState = () => setMode(window.location.pathname === "/signup" ? "signup" : "signin");
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  function switchMode(next: AuthMode) {
    if (next === mode) return;
    window.history.pushState({ authMode: next }, "", next === "signup" ? "/signup" : "/login");
    setNotice(null);
    setMode(next);
  }

  async function submitLogin(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!identifier.trim() || !loginPassword || loginPassword.length > 128) {
      setNotice({ kind: "error", message: "Enter a valid username/email and password." });
      return;
    }
    setBusy(true);
    try {
      const csrfRes = await fetch("/backend/api/csrf", { cache: "no-store", credentials: "same-origin" });
      if (!csrfRes.ok) throw new Error("csrf");
      const { csrfToken } = await csrfRes.json();
      const res = await fetch("/backend/api/login", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken, "Accept": "application/json" },
        body: JSON.stringify({ identifier: identifier.trim(), password: loginPassword })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        setNotice({ kind: "error", message: data.message || data.error || `We couldn't sign you in (HTTP ${res.status}). Please try again.` });
      } else {
        window.location.assign(typeof data.redirect === "string" && data.redirect.startsWith("/") ? data.redirect : "/dashboard");
      }
    } catch {
      setNotice({ kind: "error", message: "Can't reach LibraAI right now. Start the Python backend and try again." });
    } finally {
      setBusy(false);
    }
  }

  async function submitSignup(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (signupPassword !== confirm) {
      setNotice({ kind: "error", message: "Your passwords don't match. Please check both fields." });
      return;
    }
    if (signupPassword.length < 12 || signupPassword.length > 128) {
      setNotice({ kind: "error", message: "Use a password between 12 and 128 characters." });
      return;
    }
    if (!name.trim() || !email.trim()) {
      setNotice({ kind: "error", message: "Enter your name and email address." });
      return;
    }
    setBusy(true);
    try {
      const csrfRes = await fetch("/backend/api/csrf", { cache: "no-store", credentials: "same-origin" });
      if (!csrfRes.ok) throw new Error("csrf");
      const { csrfToken } = await csrfRes.json();
      const res = await fetch("/backend/api/signup", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken, "Accept": "application/json" },
        body: JSON.stringify({ name: name.trim(), username: username.trim() || undefined, email: email.trim(), password: signupPassword, role })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        setNotice({ kind: "error", message: data.message || data.error || `Registration couldn't be completed (HTTP ${res.status}). Please try again.` });
      } else {
        setNotice({ kind: "success", message: "Your account is ready. Opening your LibraAI workspace…" });
        const destination = typeof data.redirect === "string" && data.redirect.startsWith("/") ? data.redirect : "/dashboard";
        window.setTimeout(() => window.location.assign(destination), 650);
      }
    } catch {
      setNotice({ kind: "error", message: "Can't reach LibraAI right now. Start the Python backend and try again." });
    } finally {
      setBusy(false);
    }
  }

  return <>
    <main ref={rootRef} className={`libra-auth-page ${mode === "signup" ? "is-signup" : "is-signin"}`}>
      <div className="libra-auth-ambient" aria-hidden="true">
        <span className="ambient-orb ambient-orb-one" />
        <span className="ambient-orb ambient-orb-two" />
        <span className="ambient-orb ambient-orb-three" />
      </div>
      <ParticleCanvas rootRef={rootRef} />
      <div className="libra-auth-heading">
        <span className="libra-auth-kicker"><Sparkles size={14} /> THE LIBRAAI EXPERIENCE</span>
        <p>One thoughtful space for everything you want to discover.</p>
      </div>

      <section className="libra-auth-shell" aria-label="LibraAI account access">
        <div className="libra-auth-form-panel libra-auth-signin-panel" aria-hidden={mode !== "signin"}>
          <form className="libra-auth-form" onSubmit={submitLogin}>
            <fieldset disabled={mode !== "signin" || busy}>
              <div className="libra-auth-brandline">
                <Link href="/" className="libra-auth-brand"><span className="libra-auth-brandmark"><BookOpen size={22} /></span><span><b>LibraAI</b><small>READ · LEARN · GROW</small></span></Link>
                <span className="libra-auth-switch-copy">New to LibraAI? <button type="button" onClick={() => switchMode("signup")}>Create account</button></span>
              </div>
              <div className="libra-auth-form-title"><span className="libra-auth-step">01 / WELCOME BACK</span><h1>Welcome <em>back.</em></h1><p>Your next chapter is waiting. Sign in to pick up where inspiration left off.</p></div>
              <label className="libra-auth-label" htmlFor="auth-identifier">Email address or username</label>
              <div className="libra-auth-input"><Mail size={17} /><input id="auth-identifier" type="text" required maxLength={254} autoComplete="username" placeholder="you@example.com" value={identifier} onChange={e => setIdentifier(e.target.value)} /></div>
              <label className="libra-auth-label" htmlFor="auth-login-password">Password</label>
              <div className="libra-auth-input"><LockKeyhole size={17} /><input id="auth-login-password" type={showLoginPassword ? "text" : "password"} required maxLength={128} autoComplete="current-password" placeholder="Enter your password" value={loginPassword} onChange={e => setLoginPassword(e.target.value)} /><button type="button" className="libra-auth-eye" aria-label={showLoginPassword ? "Hide password" : "Show password"} onClick={() => setShowLoginPassword(v => !v)}>{showLoginPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></div>
              <div className="libra-auth-forgot"><Link href="/forgot-password">Forgot password?</Link></div>
              <button disabled={busy} className="libra-auth-submit" type="submit">{busy ? "Signing in…" : "Sign in to LibraAI"} <ArrowRight size={17} /></button>
              <div className="libra-auth-assurance"><ShieldCheck size={16} /><span>Your account is protected with secure sign-in.</span></div>
              <div className="libra-auth-mobile-switch">New to LibraAI? <button type="button" onClick={() => switchMode("signup")}>Create an account <ArrowRight size={14} /></button></div>
            </fieldset>
          </form>
        </div>

        <div className="libra-auth-form-panel libra-auth-signup-panel" aria-hidden={mode !== "signup"}>
          <form className="libra-auth-form libra-auth-form-signup" onSubmit={submitSignup}>
            <fieldset disabled={mode !== "signup" || busy}>
              <div className="libra-auth-brandline">
                <Link href="/" className="libra-auth-brand"><span className="libra-auth-brandmark"><BookOpen size={22} /></span><span><b>LibraAI</b><small>READ · LEARN · GROW</small></span></Link>
                <span className="libra-auth-switch-copy">Already a member? <button type="button" onClick={() => switchMode("signin")}>Sign in</button></span>
              </div>
              <div className="libra-auth-form-title signup-title"><span className="libra-auth-step">02 / BEGIN HERE</span><h1>Make room for <em>more.</em></h1><p>Create your account and build a library that grows with you.</p></div>
              <div className="libra-auth-role-heading"><span>Choose your experience</span><small>Your role can shape your LibraAI workspace.</small></div>
              <div className="libra-auth-role-select">
                {roles.map(({ id, name: label, desc, points, icon: Icon }) => <button type="button" key={id} className={`libra-auth-role ${role === id ? "selected" : ""}`} aria-pressed={role === id} onClick={() => setRole(id)}>
                  <span className="libra-auth-role-icon"><Icon size={19} /></span><span className="libra-auth-role-copy"><b>{label}</b><small>{desc}</small></span><span className="libra-auth-role-check">{role === id ? <Check size={13} /> : null}</span>
                  <span className="libra-auth-role-points">{points.join(" · ")}</span>
                </button>)}
              </div>
              <div className="libra-auth-fields-grid">
                <div><label className="libra-auth-label" htmlFor="auth-full-name">Full name</label><div className="libra-auth-input"><UserRound size={16} /><input id="auth-full-name" required minLength={2} autoComplete="name" placeholder="Your full name" value={name} onChange={e => setName(e.target.value)} /></div></div>
                <div><label className="libra-auth-label" htmlFor="auth-username">Username <span>(optional)</span></label><div className="libra-auth-input"><UserRound size={16} /><input id="auth-username" minLength={2} maxLength={32} pattern="[A-Za-z0-9_.-]+" autoComplete="username" placeholder="Choose a username" value={username} onChange={e => setUsername(e.target.value)} /></div></div>
                <div className="field-full"><label className="libra-auth-label" htmlFor="auth-signup-email">Email address</label><div className="libra-auth-input"><Mail size={16} /><input id="auth-signup-email" type="email" required maxLength={254} autoComplete="email" placeholder="you@example.com" value={email} onChange={e => setEmail(e.target.value)} /></div></div>
                <div><label className="libra-auth-label" htmlFor="auth-signup-password">Password</label><div className="libra-auth-input"><LockKeyhole size={16} /><input id="auth-signup-password" type={showSignupPassword ? "text" : "password"} required minLength={12} maxLength={128} autoComplete="new-password" placeholder="At least 12 characters" value={signupPassword} onChange={e => setSignupPassword(e.target.value)} /><button type="button" className="libra-auth-eye" aria-label={showSignupPassword ? "Hide password" : "Show password"} onClick={() => setShowSignupPassword(v => !v)}>{showSignupPassword ? <EyeOff size={16} /> : <Eye size={16} />}</button></div></div>
                <div><label className="libra-auth-label" htmlFor="auth-confirm-password">Confirm password</label><div className="libra-auth-input"><LockKeyhole size={16} /><input id="auth-confirm-password" type={showSignupPassword ? "text" : "password"} required maxLength={128} autoComplete="new-password" placeholder="Repeat your password" value={confirm} onChange={e => setConfirm(e.target.value)} /></div></div>
              </div>
              <label className="libra-auth-terms"><input type="checkbox" required /> <span>I agree to the <Link href="/terms">Terms of Service</Link> and <Link href="/privacy">Privacy Policy</Link>.</span></label>
              <button disabled={busy} className="libra-auth-submit" type="submit">{busy ? "Creating account…" : "Create your account"} <ArrowRight size={17} /></button>
              <div className="libra-auth-mobile-switch">Already have an account? <button type="button" onClick={() => switchMode("signin")}>Sign in <ArrowRight size={14} /></button></div>
            </fieldset>
          </form>
        </div>

        <aside className="libra-auth-promo" aria-live="polite">
          <div className="libra-auth-promo-top"><span className="promo-chip"><Sparkles size={13} /> A WORLD OF KNOWLEDGE</span><span className="promo-index">{mode === "signin" ? "01" : "02"} <i>—</i> 02</span></div>
          <div className="libra-auth-promo-art" aria-hidden="true">
            <div className="promo-orbit orbit-one" /><div className="promo-orbit orbit-two" />
            <div className="promo-book"><span>LIBRA</span><b>AI</b><small>YOUR NEXT CHAPTER</small></div>
            <span className="promo-star star-one">✦</span><span className="promo-star star-two">✧</span><span className="promo-star star-three">✳</span>
            <div className="promo-glass-note"><BookOpen size={16} /><span><b>Read with intention</b><small>Discover something meaningful.</small></span></div>
          </div>
          <div className="libra-auth-promo-copy">
            <span className="libra-auth-step">{mode === "signin" ? "YOUR STORY CONTINUES" : "YOUR STORY STARTS HERE"}</span>
            <h2>{mode === "signin" ? <>Your next chapter<br /><em>starts here.</em></> : <>Knowledge begins<br /><em>with you.</em></>}</h2>
            <p>{mode === "signin" ? "Discover knowledge, explore intelligent reading experiences, and continue your journey with LibraAI." : "Build your personal library, discover new ideas, and experience a smarter way to learn."}</p>
          </div>
          <button className="libra-auth-promo-action" type="button" onClick={() => switchMode(mode === "signin" ? "signup" : "signin")}>
            {mode === "signin" ? "Create an account" : "Already have an account?"} <ArrowRight size={17} />
          </button>
          <div className="libra-auth-promo-foot"><span>LIBRAAI · READ / LEARN / GROW</span><span>EST. FOR THE CURIOUS</span></div>
        </aside>
      </section>

      <div className="libra-auth-bottomline"><span>© 2026 LibraAI. All rights reserved.</span><nav><Link href="/privacy">Privacy</Link><Link href="/terms">Terms</Link><Link href="/help">Help & support</Link></nav><span className="bottom-secure"><ShieldCheck size={13} /> Secure account access</span></div>
    </main>
    <Notice notice={notice} clear={() => setNotice(null)} />
  </>;
}
