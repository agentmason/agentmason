import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'AgentMason AI Platform',
  description: 'Enterprise-grade AI agent platform foundation',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
