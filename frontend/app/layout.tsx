import type { Metadata } from "next";
import "./globals.css";
import "./premium-system.css";
import FloatingAIChat from "@/components/FloatingAIChat";
import Header from "@/components/Header";
import LanguageBridge from "@/components/LanguageBridge";
import GlobalNotice from "@/components/GlobalNotice";
import FloatingLaunchReadiness from "@/components/FloatingLaunchReadiness";

export const metadata: Metadata = {
  title: "LibraAI — Your AI-Powered Library & Learning Platform",
  description: "Discover books, explore knowledge, and grow your skills with LibraAI — your AI-powered library and learning platform.",
  applicationName: "LibraAI",
  metadataBase: process.env.LIBRAAI_PUBLIC_URL ? new URL(process.env.LIBRAAI_PUBLIC_URL) : undefined,
  robots: { index: process.env.NODE_ENV === "production", follow: process.env.NODE_ENV === "production" },
  themeColor: "#f8f9ff"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en">
    <head>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      <link href="https://fonts.googleapis.com/css2?family=Lora:wght@400;500;600;700&display=swap" rel="stylesheet" />
    </head>
    <body>
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <Header />
      <LanguageBridge />
      <div id="main-content" tabIndex={-1}>{children}</div>
      <GlobalNotice />
      <FloatingLaunchReadiness />
      <FloatingAIChat />
    </body>
  </html>;
}
