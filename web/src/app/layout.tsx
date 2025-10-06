import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Head Coach Shell',
  description: 'React/Next.js Head Coach experience for demo bake-off'
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
