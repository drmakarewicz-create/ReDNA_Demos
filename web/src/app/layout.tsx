import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Northstar',
  description: 'React/Next.js Northstar - AI orchestrator and user experience'
};

export default function RootLayout({
  children
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full bg-hc-background text-slate-100">
        {children}
      </body>
    </html>
  );
}
