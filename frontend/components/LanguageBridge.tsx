"use client";

import { useEffect } from "react";

/** Lightweight client-side UI translation layer. Keeps the existing routes and layout intact. */
const EN_BN: Record<string, string> = {
  "Skip to main content": "মূল কনটেন্টে যান", "Main navigation": "প্রধান নেভিগেশন", "Search books, authors, genres, ISBN": "বই, লেখক, ধরন ও ISBN খুঁজুন",
  "Search books, authors, genres, ISBN...": "বই, লেখক, ধরন ও ISBN খুঁজুন...", "Your AI-Powered Library & Learning Platform": "আপনার এআই-চালিত লাইব্রেরি ও শেখার প্ল্যাটফর্ম",
  "Read · Learn · Grow": "পড়ুন · শিখুন · এগিয়ে যান", "Get Started": "শুরু করুন", "Sign In": "সাইন ইন", "Sign in": "সাইন ইন", "Sign up": "নিবন্ধন করুন",
  "Home": "হোম", "Books": "বই", "AI Tools": "এআই টুলস", "My Library": "আমার লাইব্রেরি", "Ecosystem": "ইকোসিস্টেম", "Community": "কমিউনিটি", "Dashboard": "ড্যাশবোর্ড", "Pricing": "মূল্য", "About": "পরিচিতি", "Contact": "যোগাযোগ",
  "Library": "লাইব্রেরি", "Trending Books": "জনপ্রিয় বই", "Browse catalog": "ক্যাটালগ দেখুন", "Browse library": "লাইব্রেরি দেখুন", "Explore ecosystem": "ইকোসিস্টেম ঘুরে দেখুন", "Ecosystem overview": "ইকোসিস্টেম পরিচিতি", "Feature overview": "ফিচার পরিচিতি",
  "AI Study Tools": "এআই স্টাডি টুলস", "AI study tools and creator spaces": "এআই স্টাডি টুলস ও ক্রিয়েটর স্পেস", "Generate study set": "স্টাডি সেট তৈরি করুন", "Generating…": "তৈরি হচ্ছে…", "Ask AI": "এআই-কে জিজ্ঞাসা করুন", "Ask questions": "প্রশ্ন করুন", "Assistant": "সহকারী",
  "Add to Cart": "কার্টে যোগ করুন", "Upload New Book": "নতুন বই আপলোড করুন", "Import Catalog": "ক্যাটালগ ইমপোর্ট করুন", "All formats": "সব ফরম্যাট", "All items": "সব আইটেম", "All modules": "সব মডিউল", "Refresh": "রিফ্রেশ", "Refresh data": "ডেটা রিফ্রেশ করুন",
  "Back to home": "হোমে ফিরুন", "Back to dashboard": "ড্যাশবোর্ডে ফিরুন", "Back to Sign In": "সাইন ইন-এ ফিরুন", "Sign in to continue": "চালিয়ে যেতে সাইন ইন করুন", "Try again": "আবার চেষ্টা করুন", "Listen": "শুনুন", "Watch Video": "ভিডিও দেখুন",
  "Save note": "নোট সংরক্ষণ করুন", "Save highlights for later": "হাইলাইট পরে দেখার জন্য সংরক্ষণ করুন", "Access help": "সহায়তা নিন", "Module overview": "মডিউল পরিচিতি", "Library operations": "লাইব্রেরি কার্যক্রম", "Available audiobooks": "উপলভ্য অডিওবুক", "Audiobooks": "অডিওবুক", "Audiobook": "অডিওবুক",
  "CHAPTER SUMMARY": "অধ্যায়ের সারসংক্ষেপ", "KNOWLEDGE CHECK": "জ্ঞান যাচাই", "REVISION CARDS": "রিভিশন কার্ড", "LEARNING WORKSPACE": "শেখার কর্মক্ষেত্র", "LIBRAAI ECOSYSTEM": "LIBRAAI ইকোসিস্টেম", "THE LIBRAAI EXPERIENCE": "LIBRAAI অভিজ্ঞতা", "WELCOME BACK": "ফিরে আসায় স্বাগতম", "ACCOUNT RECOVERY": "অ্যাকাউন্ট পুনরুদ্ধার",
  "Reader-first design": "পাঠককে অগ্রাধিকার দেওয়া ডিজাইন", "Reading & learning support": "পড়া ও শেখার সহায়তা", "Rights-aware access": "স্বত্ব-সচেতন অ্যাক্সেস", "Seekable audio playback": "নির্দিষ্ট অংশে অডিও চালানো", "Curated catalog": "বাছাইকৃত ক্যাটালগ", "Backend-validated cart": "ব্যাকএন্ড-যাচাইকৃত কার্ট",
  "Your data is safe with us": "আপনার তথ্য আমাদের কাছে নিরাপদ", "No credentials are collected here.": "এখানে কোনো লগইন তথ্য সংগ্রহ করা হয় না।", "Credentials are never displayed here.": "এখানে কখনো লগইন তথ্য দেখানো হয় না।", "Avoid sharing passwords or payment details.": "পাসওয়ার্ড বা পেমেন্টের তথ্য শেয়ার করবেন না।", "Admin accounts are by invitation only.": "অ্যাডমিন অ্যাকাউন্ট শুধু আমন্ত্রণের মাধ্যমে তৈরি হয়।",
  "A new day, a new chapter. What will you read today?": "নতুন দিন, নতুন অধ্যায়। আজ কী পড়বেন?", "Discover fresh perspectives": "নতুন দৃষ্টিভঙ্গি আবিষ্কার করুন", "Access a Massive Library": "বিশাল লাইব্রেরিতে প্রবেশ করুন", "Access a World of Knowledge": "জ্ঞানের বিশাল জগতে প্রবেশ করুন", "Be Part of a Global Community": "বিশ্বব্যাপী কমিউনিটির অংশ হোন",
  "Already have an account?": "আগেই অ্যাকাউন্ট আছে?", "Answer:": "উত্তর:", "Active": "সক্রিয়", "All in one place": "সবকিছু এক জায়গায়", "Help": "সহায়তা", "Privacy": "গোপনীয়তা", "Terms": "শর্তাবলি"
};
const BN_EN = Object.fromEntries(Object.entries(EN_BN).map(([en, bn]) => [bn, en]));
const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const EN_KEYS = Object.keys(EN_BN).sort((a, b) => b.length - a.length);
const BN_KEYS = Object.keys(BN_EN).sort((a, b) => b.length - a.length);

function transform(value: string, language: string) {
  const dict = language === "bn" ? EN_BN : BN_EN;
  const keys = language === "bn" ? EN_KEYS : BN_KEYS;
  let result = value;
  for (const key of keys) {
    if (result.includes(key)) result = result.replace(new RegExp(escapeRegExp(key), "g"), dict[key]);
  }
  return result;
}

export default function LanguageBridge() {
  useEffect(() => {
    let language = window.localStorage.getItem("libraai-language") === "bn" ? "bn" : "en";
    const skipTags = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "TEXTAREA", "INPUT", "CODE", "PRE"]);
    const apply = () => {
      document.documentElement.lang = language;
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      const nodes: Text[] = [];
      while (walker.nextNode()) {
        const node = walker.currentNode as Text;
        if (node.parentElement && !skipTags.has(node.parentElement.tagName) && node.nodeValue?.trim()) nodes.push(node);
      }
      for (const node of nodes) {
        const oldValue = node.nodeValue || "";
        const nextValue = transform(oldValue, language);
        if (nextValue !== oldValue) node.nodeValue = nextValue;
      }
      document.querySelectorAll<HTMLElement>("input[placeholder], textarea[placeholder], [aria-label], [title]").forEach((el) => {
        for (const attr of ["placeholder", "aria-label", "title"]) {
          const oldValue = el.getAttribute(attr);
          if (oldValue) {
            const nextValue = transform(oldValue, language);
            if (nextValue !== oldValue) el.setAttribute(attr, nextValue);
          }
        }
      });
    };
    apply();
    const onLanguage = (event: Event) => {
      const detail = (event as CustomEvent<string>).detail;
      language = detail === "bn" ? "bn" : "en";
      apply();
    };
    window.addEventListener("libraai-language", onLanguage);
    const observer = new MutationObserver(() => apply());
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    return () => { observer.disconnect(); window.removeEventListener("libraai-language", onLanguage); };
  }, []);
  return null;
}
