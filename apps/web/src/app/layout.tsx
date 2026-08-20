import './globals.css';
import type { Metadata } from 'next';
import Link from 'next/link';
import Image from 'next/image';
import AuthButton from './auth-button';

export const metadata: Metadata = {
  title: 'AgentMason.ai — AI Agents That Deliver',
  description: 'AI agents that design, build, and orchestrate delivery',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body suppressHydrationWarning>
        {/* Header */}
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
            <Link href="/" className="flex items-center gap-3">
              <Image src="/logo.svg" alt="AgentMason" width={40} height={40} className="h-10 w-10" />
              <div>
                <span className="text-xl font-bold text-slate-900">Agent<span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-500 to-purple-600">Mason</span>.ai</span>
                <p className="text-[10px] font-medium uppercase tracking-[0.15em] text-slate-400">Design. Build. Orchestrate.</p>
              </div>
            </Link>
            <nav className="flex items-center gap-8">
              <Link href="/dashboard" className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors">Dashboard</Link>
              <Link href="/inbox" className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors">Inbox</Link>
              <Link href="/approvals" className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors">Approvals</Link>
              <Link href="/activity" className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors">Activity</Link>
              <Link href="/scenarios" className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors">Scenarios</Link>
              <Link href="/orchestration" className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors">Orchestration</Link>
              <Link href="/workflows" className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors">Workflows</Link>
              <Link href="/memory" className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors">Memory</Link>
              <Link href="/graph" className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors">Graph</Link>
              <AuthButton />
            </nav>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
