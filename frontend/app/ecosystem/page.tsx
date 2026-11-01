"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { Search, ArrowUpRight, Sparkles, BookOpen, Brain, Headphones, ShoppingBag, LibraryBig, UsersRound, ShieldCheck, BarChart3, Settings2, Mic, MapPinned, Clock3, Database, Workflow, PlugZap, LockKeyhole, Smartphone, HeartHandshake } from "lucide-react";
import modules from "./ecosystem-data.json";

const iconNames: Record<string, any> = {
  "home-dashboard": BookOpen, "catalog-search": Search, "ebook-reader": BookOpen,
  "manga-reader": BookOpen, audiobooks: Headphones, "ai-study": Brain,
  marketplace: ShoppingBag, "my-bookshelf": LibraryBig, "library-operations": LibraryBig,
  "library-network": MapPinned, community: UsersRound, "creator-portal": Sparkles,
  analytics: BarChart3, subscriptions: HeartHandshake, "identity-security": ShieldCheck,
  "notifications-workflows": Workflow, "mobile-accessibility": Smartphone, "advanced-ai": Brain,
  "community-extras": UsersRound, "command-center": Settings2, "voice-assistant": Mic,
  "indoor-navigation": MapPinned, "planner-focus": Clock3, "smart-handover": LibraryBig,
  "building-monitor": BarChart3, "ai-trust": ShieldCheck, "data-import": Database,
  "performance-health": BarChart3, "backup-recovery": LockKeyhole, "workflow-builder": Workflow,
  "integration-hub": PlugZap, "privacy-personalization": LockKeyhole
};
const categories = ["All modules", "Home", "Discover", "Read", "Listen", "Learn", "Buy", "My Library", "Manage", "Connect", "Publish", "Analyze", "Plans", "Secure", "Automate", "Access", "Intelligence", "Productivity", "On-site", "Study", "Circulation", "Facilities", "Trust", "Operations", "Platform", "Privacy"];

export default function EcosystemPage() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All modules");
  const filtered = useMemo(() => modules.filter((m: any) => {
    const matchesQuery = `${m.title} ${m.description} ${m.features.join(" ")}`.toLowerCase().includes(query.toLowerCase());
    return matchesQuery && (category === "All modules" || m.tag === category);
  }), [query, category]);
  return <><main className="eco-page">
    <section className="eco-hero">
      <div className="eco-hero-copy">
        <span className="eco-eyebrow"><Sparkles size={14}/> LIBRAAI ECOSYSTEM</span>
        <h1>One connected home for <em>every way to learn.</em></h1>
        <p>Discover, read, listen, learn, manage and connect—through one thoughtfully designed library and knowledge platform.</p>
        <div className="eco-hero-actions"><a href="#modules" className="eco-primary">Explore all modules <ArrowUpRight size={16}/></a><Link href="/library" className="eco-secondary">Browse library</Link><Link href="/workspace/ecosystem-hub" className="eco-secondary">Open Reading & Knowledge Hub</Link></div>
        <div className="eco-trust-line"><span><i/> Reader-first design</span><span><i/> Library operations</span><span><i/> AI-assisted learning</span></div>
      </div>
      <div className="eco-hero-art" aria-hidden="true">
        <div className="eco-orbit eco-orbit-one"></div><div className="eco-orbit eco-orbit-two"></div>
        <div className="eco-book-stack"><div className="eco-book eco-book-a">READ<br/><small>Discover</small></div><div className="eco-book eco-book-b">LEARN<br/><small>Understand</small></div><div className="eco-book eco-book-c">GROW<br/><small>Connect</small></div></div>
        <div className="eco-float eco-float-top"><Brain size={17}/><span><b>AI learning</b><small>Study with context</small></span></div>
        <div className="eco-float eco-float-bottom"><LibraryBig size={17}/><span><b>Library tools</b><small>Collections in sync</small></span></div>
      </div>
    </section>
    <section className="eco-stats" aria-label="Platform areas">
      <div><b>01</b><span>Discover & read</span><small>Books, eBooks, manga and audio</small></div>
      <div><b>02</b><span>Learn & create</span><small>AI study tools and creator spaces</small></div>
      <div><b>03</b><span>Manage & measure</span><small>Library operations and analytics</small></div>
      <div><b>04</b><span>Connect & protect</span><small>Community, privacy and integrations</small></div>
    </section>
    <section className="eco-module-section" id="modules">
      <div className="eco-section-heading"><div><span className="eco-kicker">THE COMPLETE PLATFORM</span><h2>Explore the ecosystem</h2><p>Find a workspace by the job you need to get done.</p></div><span className="eco-count">{filtered.length} modules</span></div>
      <div className="eco-filters"><label className="eco-search"><Search size={18}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search features, tools or workflows…" aria-label="Search ecosystem modules"/>{query && <button onClick={()=>setQuery("")} aria-label="Clear search">×</button>}</label><div className="eco-category-scroll">{categories.map(c=><button key={c} onClick={()=>setCategory(c)} className={category===c?"active":""}>{c}</button>)}</div></div>
      <div className="eco-grid">{filtered.map((m:any, i:number)=>{const Icon=iconNames[m.slug] || BookOpen;return <Link href={`/ecosystem/${m.slug}`} key={m.slug} className="eco-card" style={{"--card-index":i} as React.CSSProperties}><div className={`eco-card-icon eco-icon-${i%6}`}><Icon size={21}/></div><div className="eco-card-meta"><span>{m.tag}</span><ArrowUpRight size={16}/></div><h3>{m.title}</h3><p>{m.description}</p><div className="eco-card-bottom"><span>{m.features.length} capabilities listed</span><b>Explore module <ArrowUpRight size={13}/></b></div></Link>})}</div>
      {filtered.length===0 && <div className="eco-empty"><Search size={24}/><h3>No modules found</h3><p>Try another keyword or choose “All modules”.</p><button onClick={()=>{setQuery("");setCategory("All modules")}}>Reset filters</button></div>}
    </section>
    <section className="eco-bottom-cta"><div className="eco-cta-icon"><Sparkles size={23}/></div><div><span className="eco-kicker">BUILT AROUND YOUR WORKFLOW</span><h2>Start with what you need today.</h2><p>Explore the catalog or open your workspace. Some advanced modules require backend services, permissions or third-party integrations.</p></div><Link href="/workspace/ecosystem-hub">Open Knowledge Hub <ArrowUpRight size={16}/></Link><Link href="/library">Open Library <ArrowUpRight size={16}/></Link></section>
    <footer className="eco-footer"><Link href="/" className="eco-brand"><span className="eco-brand-mark"><BookOpen size={17}/></span>LibraAI</Link><span>One connected ecosystem for reading, learning and library operations.</span><nav><Link href="/library">Library</Link><Link href="/about">About</Link><Link href="/login">Sign in</Link><Link href="/signup">Create account</Link></nav><small>© LibraAI · Designed for accessible knowledge</small></footer>
  </main></>;
}