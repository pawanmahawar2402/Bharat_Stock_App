import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'BharatStock Analyzer - Institutional Indian Stock Market Intelligence',
  description: 'Full-stack institutional stock market analytics platform for NSE/BSE equities with Macro Regime Modeling, Corporate Actions Tracker, Swing Profit-Booking Scanner, and intrinsic value suite.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen antialiased bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors duration-200">
        {children}
      </body>
    </html>
  );
}
