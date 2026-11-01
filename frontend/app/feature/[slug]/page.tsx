import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, ArrowUpRight, BookOpen, CheckCircle2, ShieldCheck, Sparkles } from "lucide-react";
import modules from "../../ecosystem/ecosystem-data.json";

function slugify(value: string) {
  return value.toLowerCase().replace(/&/g, " and ").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}
function getFeatureSlug(moduleSlug: string, feature: string) {
  return `${moduleSlug}--${slugify(feature)}`;
}
const allFeatures = modules.flatMap((module: any) => module.features.map((feature: string, index: number) => ({
  module, feature, index, slug: getFeatureSlug(module.slug, feature)
})));
export function generateStaticParams() {
  return allFeatures.map((feature: any) => ({ slug: feature.slug }));
}
export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const item = allFeatures.find((feature: any) => feature.slug === slug);
  return {
    title: item ? `${item.feature} | LibraAI` : "Feature | LibraAI",
    description: item ? `${item.feature} within ${item.module.title}. Explore the purpose, workflow and related LibraAI capabilities.` : "Explore LibraAI features."
  };
}
export default async function FeatureDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const item = allFeatures.find((feature: any) => feature.slug === slug);
  if (!item) notFound();
  const related = item.module.features.filter((feature: string) => feature !== item.feature).slice(0, 4);
  return <><main className="eco-detail-page feature-detail-page">
    <nav className="eco-breadcrumb"><Link href="/">Home</Link><span>/</span><Link href="/ecosystem">Ecosystem</Link><span>/</span><Link href={`/ecosystem/${item.module.slug}`}>{item.module.title}</Link><span>/</span><b>{item.feature}</b></nav>
    <section className="eco-detail-hero feature-detail-hero"><div><span className="eco-eyebrow"><Sparkles size={14}/> {item.module.tag.toUpperCase()} FEATURE</span><h1>{item.feature}</h1><p>{item.module.description} This page describes how this capability fits into the {item.module.title} workspace.</p><div className="eco-hero-actions"><Link href="/login" className="eco-primary">Sign in to continue <ArrowUpRight size={16}/></Link><Link href={`/ecosystem/${item.module.slug}`} className="eco-secondary"><ArrowLeft size={15}/> Back to module</Link></div></div><div className="eco-detail-art"><div className="eco-detail-art-glow"><BookOpen size={62}/><span>LibraAI</span></div><div className="eco-detail-orb"></div></div></section>
    <div className="eco-detail-columns"><section className="eco-detail-panel"><span className="eco-kicker">FEATURE OVERVIEW</span><h2>What you can do</h2><p className="eco-detail-intro">This capability is part of {item.module.title}. Its availability and live behavior depend on account permissions, backend support, licensed content and any required integrations.</p><div className="feature-overview-card"><span><CheckCircle2 size={20}/></span><div><h3>{item.feature}</h3><p>{item.module.description}</p></div></div><h2 className="feature-workflow-heading">Related capabilities</h2><div className="eco-capability-list">{related.map((feature: string, i: number) => <Link key={feature} href={`/feature/${getFeatureSlug(item.module.slug, feature)}`} className="eco-capability-link"><span><CheckCircle2 size={17}/></span><p>{feature}</p><small>{String(i+1).padStart(2,"0")}</small><ArrowUpRight className="eco-capability-arrow" size={15}/></Link>)}</div></section><aside className="eco-detail-aside"><div className="eco-status-card"><span className="eco-aside-icon"><ShieldCheck size={21}/></span><h3>Responsible access</h3><p>Features that read private data or change records should require sign-in, role-based permissions and server-side validation.</p><div className="eco-status-note"><i/> Feature overview</div></div><div className="eco-next-card"><span className="eco-kicker">PARENT WORKSPACE</span><h3>{item.module.title}</h3><p>{item.module.description}</p><Link href={`/ecosystem/${item.module.slug}`}>Explore module <ArrowUpRight size={15}/></Link></div></aside></div>
    <footer className="eco-footer"><Link href="/" className="eco-brand"><span className="eco-brand-mark"><BookOpen size={17}/></span>LibraAI</Link><span>One connected ecosystem for reading, learning and library operations.</span><nav><Link href="/ecosystem">All modules</Link><Link href="/library">Library</Link><Link href="/login">Sign in</Link><Link href="/signup">Create account</Link></nav><small>© LibraAI · Designed for accessible knowledge</small></footer>
  </main></>;
}