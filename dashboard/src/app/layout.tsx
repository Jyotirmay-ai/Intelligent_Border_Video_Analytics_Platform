import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const ibmSans = IBM_Plex_Sans({
  weight: ['400', '500', '600', '700'],
  subsets: ["latin"],
  variable: "--font-sans",
});

const ibmMono = IBM_Plex_Mono({
  weight: ['400', '500'],
  subsets: ["latin"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "IBVAP Command Console",
  description: "Intelligent Border Video Analytics Platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${ibmSans.variable} ${ibmMono.variable} h-full antialiased`}>
      <body className="h-full bg-[var(--color-void)] text-[var(--color-primary)] font-sans overflow-hidden flex flex-col">
        {/* Top System Health Strip */}
        <header className="h-10 shrink-0 border-b border-[var(--color-hair)] flex items-center px-4 text-xs text-[var(--color-muted)] font-mono">
          <span className="mr-6">SYSTEM_STATUS: NOMINAL</span>
          <span className="mr-6">EDGE_NODES: 3/3 ONLINE</span>
          <span className="mr-6 text-[var(--color-active)]">SYNC: ESTABLISHED</span>
        </header>
        
        {/* Main Application Area */}
        <main className="flex-1 flex overflow-hidden">
          {children}
        </main>
      </body>
    </html>
  );
}
