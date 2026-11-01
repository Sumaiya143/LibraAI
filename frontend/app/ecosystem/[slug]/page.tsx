import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, ArrowUpRight, CheckCircle2, ShieldCheck, Sparkles, BookOpen } from "lucide-react";
import modules from "../ecosystem-data.json";

export function generateStaticParams() {
  return modules.map((m: any) => ({ slug: m.slug }));
}
export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const item = modules.find((m: any) => m.slug === slug);
  return { title: item ? `${item.title} | LibraAI` : "Ecosystem | LibraAI", description: item?.description || "Explore LibraAI modules." };
}
export default async function EcosystemModulePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const item = modules.find((m: any) => m.slug === slug);
  if (!item) notFound();
  return <><main className="eco-detail-page">
    <nav className="eco-breadcrumb"><Link href="/">Home</Link><span>/</span><Link href="/ecosystem">Ecosystem</Link><span>/</span><b>{item.title}</b></nav>
    <section className="eco-detail-hero"><div><span className="eco-eyebrow"><Sparkles size={14}/> {item.tag.toUpperCase()} WORKSPACE</span><h1>{item.title}</h1><p>{item.description}</p><div className="eco-hero-actions"><Link href="/login" className="eco-primary">Sign in to continue <ArrowUpRight size={16}/></Link><Link href="/ecosystem" className="eco-secondary"><ArrowLeft size={15}/> All modules</Link></div></div><div className="eco-detail-art"><div className="eco-detail-art-glow"><BookOpen size={62}/><span>LibraAI</span></div><div className="eco-detail-orb"></div></div></section>
    <div className="eco-detail-columns"><section className="eco-detail-panel"><span className="eco-kicker">CAPABILITIES</span><h2>What this workspace covers</h2><p className="eco-detail-intro">A clear overview of the workflows associated with this module.</p><div className="eco-capability-list">{item.features.map((feature: string, i: number)=>{const featureSlug = feature.toLowerCase().replace(/&/g, " and ").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); return <Link key={feature} href={`/feature/${item.slug}--${featureSlug}`} className="eco-capability-link"><span><CheckCircle2 size={17}/></span><p>{feature}</p><small>{String(i+1).padStart(2,"0")}</small><ArrowUpRight className="eco-capability-arrow" size={15}/></Link>})}</div></section><aside className="eco-detail-aside"><div className="eco-status-card"><span className="eco-aside-icon"><ShieldCheck size={21}/></span><h3>Designed for responsible use</h3><p>Access to data-changing actions should be permission-checked and confirmed. Live behavior depends on the connected backend and configured services.</p><div className="eco-status-note"><i/> Module overview</div></div><div className="eco-next-card"><span className="eco-kicker">KEEP EXPLORING</span><h3>Connected by design.</h3><p>Discover other parts of the LibraAI ecosystem and see how they work together.</p><Link href="/ecosystem">Explore all modules <ArrowUpRight size={15}/></Link></div></aside></div>
    <footer className="eco-footer"><Link href="/" className="eco-brand"><span className="eco-brand-mark"><BookOpen size={17}/></span>LibraAI</Link><span>One connected ecosystem for reading, learning and library operations.</span><nav><Link href="/library">Library</Link><Link href="/about">About</Link><Link href="/login">Sign in</Link><Link href="/signup">Create account</Link></nav><small>© LibraAI · Designed for accessible knowledge</small></footer>
  </main></>;
}