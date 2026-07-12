import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "QueryFlow AI — NL to SQL Database Operations Platform",
  description: "Create and execute database operations safely using natural language. QueryFlow AI translates text to SQL/NoSQL, sandboxes edits, runs workflows, and displays analytics.",
  keywords: ["SQL Generator", "NLP to SQL", "AI Database Agent", "Database Analytics", "Query Sandbox"],
  authors: [{ name: "QueryFlow AI Team" }],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark h-full">
      <body
        className={`${geistSans.variable} ${geistMono.variable} h-full antialiased bg-zinc-950 text-zinc-100`}
      >
        {children}
      </body>
    </html>
  );
}
