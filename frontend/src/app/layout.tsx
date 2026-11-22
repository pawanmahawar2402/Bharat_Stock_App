import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Grow stocks with Pawan',
  description: 'Grow your portfolio with Pawan',
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
