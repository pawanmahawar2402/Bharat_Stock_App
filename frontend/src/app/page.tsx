'use client';

import React, { useState, useEffect } from 'react';
import Navbar from '@/components/layout/Navbar';
import DisclaimerBanner from '@/components/layout/DisclaimerBanner';
import WatchlistDrawer from '@/components/layout/WatchlistDrawer';
import MacroTab from '@/components/macro/MacroTab';
import MarketPulseTab from '@/components/market-pulse/MarketPulseTab';
import DailyPicksTab from '@/components/daily-picks/DailyPicksTab';
import StockAnalysisTab from '@/components/stock-analysis/StockAnalysisTab';

export default function HomePage() {
  const [activeTab, setActiveTab] = useState<number>(0);
  const [selectedStock, setSelectedStock] = useState<string>('RELIANCE.NS');
  const [watchlist, setWatchlist] = useState<string[]>(['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'ZOMATO.NS']);
  const [isWatchlistOpen, setIsWatchlistOpen] = useState<boolean>(false);
  const [darkMode, setDarkMode] = useState<boolean>(true);

  // Load Watchlist & Dark Mode from LocalStorage
  useEffect(() => {
    try {
      const savedWatch = localStorage.getItem('bharatstock_watchlist');
      if (savedWatch) {
        setWatchlist(JSON.parse(savedWatch));
      }
      const savedTheme = localStorage.getItem('bharatstock_dark_mode');
      if (savedTheme !== null) {
        setDarkMode(savedTheme === 'true');
      }
    } catch (e) {
      console.error(e);
    }
  }, []);

  // Update Dark Mode Class on Root
  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('bharatstock_dark_mode', darkMode.toString());
  }, [darkMode]);

  const toggleWatchlist = (sym: string) => {
    let updated: string[];
    if (watchlist.includes(sym)) {
      updated = watchlist.filter((s) => s !== sym);
    } else {
      updated = [...watchlist, sym];
    }
    setWatchlist(updated);
    localStorage.setItem('bharatstock_watchlist', JSON.stringify(updated));
  };

  const handleSelectStock = (sym: string) => {
    setSelectedStock(sym);
    setActiveTab(3); // Switch to Tab 4: Stock Analysis
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top Navigation */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        darkMode={darkMode}
        setDarkMode={setDarkMode}
        watchlistCount={watchlist.length}
        openWatchlist={() => setIsWatchlistOpen(true)}
      />

      {/* Persistent SEBI Educational Disclaimer */}
      <DisclaimerBanner />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 pt-6">
        {activeTab === 0 && <MacroTab />}
        {activeTab === 1 && <DailyPicksTab />}
        {activeTab === 2 && <MarketPulseTab onSelectStock={handleSelectStock} />}
        {activeTab === 3 && (
          <StockAnalysisTab
            selectedSymbol={selectedStock}
            setSelectedSymbol={setSelectedStock}
            watchlist={watchlist}
            toggleWatchlist={toggleWatchlist}
            darkMode={darkMode}
          />
        )}
      </main>

      {/* Watchlist Drawer */}
      <WatchlistDrawer
        isOpen={isWatchlistOpen}
        onClose={() => setIsWatchlistOpen(false)}
        watchlist={watchlist}
        onRemove={(sym) => toggleWatchlist(sym)}
        onSelectStock={handleSelectStock}
      />

      {/* Footer */}
      <footer className="border-t border-slate-200 dark:border-slate-800 py-6 bg-white dark:bg-slate-900 text-center text-xs text-slate-500">
        <p>BharatStock Analyzer © 2024 • Institutional Indian Equity Analytics Platform • <a href="https://pawanstockrecommendations.com" className="underline hover:text-slate-700 dark:hover:text-slate-300" target="_blank" rel="noopener noreferrer">pawanstockrecommendations.com</a></p>
        <p className="mt-1 text-[11px] text-slate-400">
          Powered by FastAPI, Yahoo Finance, NSE/BSE Feeds, and Next.js. Strictly for educational & research purposes.
        </p>
      </footer>
    </div>
  );
}
