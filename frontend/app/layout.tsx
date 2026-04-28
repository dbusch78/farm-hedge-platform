import type { Metadata } from "next";
import "./globals.css";
import MobileNav from "@/components/MobileNav";

export const metadata: Metadata = {
  title: "Farm Platform",
  description: "Hedge tracker, day trading sandbox, and portfolio monitor",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full flex flex-col bg-[#0d1117] text-[#e8edf5] antialiased">
        {/* Top navigation */}
        <header className="sticky top-0 z-50 bg-[#0d1117] border-b border-[#1e2535]">
          <nav className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
            <div className="flex items-center gap-6">
              <a href="/" className="text-sm font-bold text-[#e8edf5] hover:text-white transition-colors">
                🌽 Farm Platform
              </a>
              <div className="hidden sm:flex items-center gap-4 text-xs text-[#7b8aab]">
                <a href="/" className="hover:text-[#e8edf5] transition-colors">Dashboard</a>
                <a href="/hedge" className="hover:text-[#e8edf5] transition-colors">Hedge</a>
                <a href="/analytics" className="hover:text-[#e8edf5] transition-colors">Analytics</a>
                <a href="/agents" className="hover:text-[#e8edf5] transition-colors">Agents</a>
                <a href="/journal" className="hover:text-[#e8edf5] transition-colors">Journal</a>
                <a href="/weather" className="hover:text-[#e8edf5] transition-colors">Weather</a>
                <a href="/portfolio" className="hover:text-[#e8edf5] transition-colors">Portfolio</a>
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs text-[#7b8aab]">
              <span className="hidden sm:inline">api.farm.local</span>
              <MobileNav />
            </div>
          </nav>
        </header>

        {/* Main content */}
        <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 py-6">
          {children}
        </main>

        <footer className="border-t border-[#1e2535] py-3 px-4 sm:px-6 text-center text-[10px] text-[#4a5568]">
          Personal-use only &bull; All data delayed &bull; Not financial advice
        </footer>
      </body>
    </html>
  );
}
