"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { BookOpen, ChevronDown, Search, Globe, Sun, Moon, Menu, X, Bot, Sparkles, LibraryBig, UsersRound, Headphones, Brain } from "lucide-react";

export default function Header() {
  const [mobile, setMobile] = useState(false);
  const [resourcesOpen, setResourcesOpen] = useState(false);
  const [dark, setDark] = useState(false);
  const [query, setQuery] = useState("");
  const [language, setLanguage] = useState<"en" | "bn">("en");
  const pathname = usePathname();
  const router = useRouter();
  const active = (path: string) => pathname === path || (path !== "/" && pathname.startsWith(`${path}/`));

  useEffect(() => {
    const savedLanguage = window.localStorage.getItem("libraai-language");
    const initialLanguage = savedLanguage === "bn" ? "bn" : "en";
    setLanguage(initialLanguage);
    document.documentElement.lang = initialLanguage;
    const savedTheme = window.localStorage.getItem("libraai-theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const initialDark = savedTheme ? savedTheme === "dark" : prefersDark;
    document.documentElement.classList.toggle("dark-mode", initialDark);
    setDark(initialDark);
    const onSearchQuery = (event: Event) => { const value = (event as CustomEvent<string>).detail; if (typeof value === "string") setQuery(value); };
    window.addEventListener("libraai-search-query", onSearchQuery);
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        document.querySelector<HTMLInputElement>(".home-topbar .searchbar input")?.focus();
      }
      if (event.key === "Escape") setMobile(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => { window.removeEventListener("keydown", onKeyDown); window.removeEventListener("libraai-search-query", onSearchQuery); };
  }, []);

  const search = (event: React.FormEvent) => {
    event.preventDefault();
    if (query.trim()) { window.dispatchEvent(new CustomEvent("libraai-search", { detail: query.trim() })); router.push(`/library?search=${encodeURIComponent(query.trim())}`); }
  };
  const toggleTheme = () => {
    const next = !document.documentElement.classList.contains("dark-mode");
    document.documentElement.classList.toggle("dark-mode", next);
    window.localStorage.setItem("libraai-theme", next ? "dark" : "light");
    setDark(next);
  };
  const closeMobile = () => setMobile(false);
  const toggleLanguage = () => {
    const next = language === "en" ? "bn" : "en";
    setLanguage(next);
    document.documentElement.lang = next;
    window.localStorage.setItem("libraai-language", next);
    window.dispatchEvent(new CustomEvent("libraai-language", { detail: next }));
  };
  if (pathname === "/dashboard" || pathname.startsWith("/dashboard/")) return null;

  const labels = language === "bn"
    ? { home: "হোম", books: "বই", ai: "এআই টুলস", library: "আমার লাইব্রেরি", ecosystem: "ইকোসিস্টেম", community: "কমিউনিটি", dashboard: "ড্যাশবোর্ড", pricing: "মূল্য", about: "পরিচিতি", search: "বই, লেখক, ধরন বা ISBN খুঁজুন", ask: "এআই-কে জিজ্ঞাসা", signIn: "সাইন ইন", getStarted: "শুরু করুন" }
    : { home: "Home", books: "Books", ai: "AI Tools", library: "My Library", ecosystem: "Ecosystem", community: "Community", dashboard: "Dashboard", pricing: "Pricing", about: "About", search: "Search books, authors, genres, ISBN...", ask: "Ask AI", signIn: "Sign In", getStarted: "Get Started" };

  return (
    <header className="topbar home-topbar">
      <Link href="/" className="brand" onClick={closeMobile}>
        <span className="brand-icon"><BookOpen size={30} /></span>
        <span><b>LibraAI</b><small>Read · Learn · Grow</small></span>
      </Link>
      <button className="mobile-toggle" onClick={() => setMobile(value => !value)} aria-label={mobile ? "Close navigation" : "Open navigation"} aria-expanded={mobile} aria-controls="primary-navigation">
        {mobile ? <X /> : <Menu />}
      </button>
      <nav id="primary-navigation" className={mobile ? "nav-links nav-open" : "nav-links"} aria-label="Main navigation">
        <Link className={active("/") ? "active" : ""} aria-current={active("/") ? "page" : undefined} href="/" onClick={closeMobile}>{labels.home}</Link>
        <Link className={active("/library") ? "active" : ""} aria-current={active("/library") ? "page" : undefined} href="/library" onClick={closeMobile}>Browse</Link>
        <Link className={active("/about") ? "active" : ""} href="/about" onClick={closeMobile}>About</Link>
        <div className={`nav-dropdown ${resourcesOpen ? "nav-dropdown-open" : ""}`}>
          <button type="button" className={active("/workspace") || active("/community") || active("/study-tools") ? "active" : ""} aria-expanded={resourcesOpen} onClick={() => setResourcesOpen(v => !v)}>Resources <ChevronDown size={13}/></button>
          <div className="nav-dropdown-menu">
            <Link href="/ecosystem/manga" onClick={() => {closeMobile();setResourcesOpen(false)}}><LibraryBig size={16}/> Manga</Link>
            <Link href="/community" onClick={() => {closeMobile();setResourcesOpen(false)}}><UsersRound size={16}/> Community</Link>
            <Link href="/workspace/audiobooks" onClick={() => {closeMobile();setResourcesOpen(false)}}><Headphones size={16}/> Audio Books</Link>
            <Link href="/help" onClick={() => {closeMobile();setResourcesOpen(false)}}><Brain size={16}/> AI Help</Link>
          </div>
        </div>
      </nav>
      <form className="searchbar" role="search" onSubmit={search}>
        <Search size={15} aria-hidden="true" />
        <input aria-label="Search books, authors, genres, ISBN" placeholder={labels.search} value={query} onChange={event => setQuery(event.target.value)} />
        <kbd aria-hidden="true">Ctrl + K</kbd>
      </form>
      <div className="header-actions">
        <button className="header-ask-ai" onClick={() => window.dispatchEvent(new CustomEvent("libraai-open-assistant"))} aria-label="Open LibraAI AI chatbot"><Bot size={16}/><span>{labels.ask}</span><Sparkles size={11}/></button>
        <button className="language" onClick={toggleLanguage} aria-label="Switch language, English or Bangla" aria-pressed={language === "bn"}><Globe size={14} /> {language === "en" ? "EN" : "বাংলা"}</button>
        <button className="icon-button" aria-label={dark ? "Switch to light theme" : "Switch to dark theme"} aria-pressed={dark} onClick={toggleTheme}>{dark ? <Sun size={17} /> : <Moon size={17} />}</button>
        <Link className="btn btn-ghost btn-small" href="/login">{labels.signIn}</Link>
        <Link className="btn btn-primary btn-small" href="/signup">{labels.getStarted}</Link>
      </div>
    </header>
  );
}
