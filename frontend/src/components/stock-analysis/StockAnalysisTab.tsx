import React, { useState, useEffect } from 'react';
import { Search, Bookmark, BookmarkCheck, TrendingUp, TrendingDown, Layers, ShieldCheck, Activity, Award, Sliders, ChevronDown, RefreshCw } from 'lucide-react';
import { api } from '@/lib/api';
import { formatINR, formatNumber, formatPct, getPctColor } from '@/lib/formatters';
import TradingViewChart from './TradingViewChart';
import FinancialStatements from './FinancialStatements';
import PatternPanel from './PatternPanel';

interface StockAnalysisTabProps {
  selectedSymbol: string;
  setSelectedSymbol: (sym: string) => void;
  watchlist: string[];
  toggleWatchlist: (sym: string) => void;
  darkMode?: boolean;
}

export default function StockAnalysisTab({
  selectedSymbol,
  setSelectedSymbol,
  watchlist,
  toggleWatchlist,
  darkMode = false,
}: StockAnalysisTabProps) {
  const [query, setQuery] = useState<string>('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [subTab, setSubTab] = useState<'overview' | 'valuation' | 'technical' | 'financials' | 'peers'>('overview');
  
  // Data States
  const [overview, setOverview] = useState<any>(null);
  const [valuation, setValuation] = useState<any>(null);
  const [technicals, setTechnicals] = useState<any>(null);
  const [financials, setFinancials] = useState<any>(null);
  const [peers, setPeers] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  
  // Chart timeframe
  const [chartPeriod, setChartPeriod] = useState<string>('1y');
  const [chartInterval, setChartInterval] = useState<string>('1d');

  // DCF Simulator Sliders
  const [dcfGrowth1, setDcfGrowth1] = useState<number>(12.0);
  const [dcfTerminal, setDcfTerminal] = useState<number>(4.5);
  const [dcfWacc, setDcfWacc] = useState<number>(11.5);
  const [dcfMos, setDcfMos] = useState<number>(20.0);
  const [liveDcfResult, setLiveDcfResult] = useState<any>(null);

  // Search autocomplete
  useEffect(() => {
    const timer = setTimeout(async () => {
      try {
        const res = await api.searchStocks(query);
        setSearchResults(res || []);
      } catch (err) {
        console.error(err);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [query]);

  // Load Stock Data: each section renders as soon as its own data arrives.
  // Peers are slow and only shown on the Peers sub-tab, so they load on demand.
  const loadStockData = async (symbol: string) => {
    setLoading(true);
    const overviewJob = api.getStockOverview(symbol)
      .then((over) => setOverview(over))
      .catch((err) => { console.error('overview', err); });
    const valuationJob = api.getStockValuation(symbol)
      .then((val) => {
        setValuation(val);
        setLiveDcfResult(val?.dcf?.is_applicable ? val.dcf : null);
      })
      .catch((err) => { console.error('valuation', err); });
    const technicalJob = api.getStockTechnicals(symbol, chartPeriod, chartInterval)
      .then((tech) => setTechnicals(tech))
      .catch((err) => { console.error('technicals', err); });
    const financialJob = api.getStockFinancials(symbol)
      .then((fin) => setFinancials(fin))
      .catch((err) => { console.error('financials', err); });
    await Promise.allSettled([overviewJob, valuationJob, technicalJob, financialJob]);
    setLoading(false);
  };

  // Peers load when the Peers sub-tab is opened (or the stock changes while it is open)
  useEffect(() => {
    if (subTab !== 'peers' || !selectedSymbol) return;
    api.getStockPeers(selectedSymbol)
      .then((prs) => setPeers(Array.isArray(prs) ? prs : []))
      .catch((err) => { console.error('peers', err); setPeers([]); });
  }, [subTab, selectedSymbol]);

  // Recalculate the simulator once the valuation has arrived
  useEffect(() => {
    if (valuation) handleRecalculateDCF();
  }, [valuation]);

  useEffect(() => {
    if (selectedSymbol) {
      loadStockData(selectedSymbol);
    }
  }, [selectedSymbol, chartPeriod, chartInterval]);

  // Handle DCF Slider Change
  const handleRecalculateDCF = async () => {
    if (!valuation?.valuation_multiples) return;
    const fcfCr = valuation.valuation_multiples.fcfe_cr || 5000;
    const cmp = overview?.fundamentals?.current_price || 1000;
    const mcapCr = (overview?.fundamentals?.market_cap || 1e11) / 1e7;
    const sharesCr = mcapCr / cmp || 100;

    try {
      const res = await api.recalculateDCF({
        fcf_cr: fcfCr,
        shares_cr: sharesCr,
        growth_rate_stage1: dcfGrowth1 / 100,
        growth_rate_stage2: (dcfGrowth1 / 100) * 0.6,
        terminal_growth: dcfTerminal / 100,
        wacc: dcfWacc / 100,
        cash_cr: 0,
        debt_cr: 0,
        margin_of_safety_pct: dcfMos / 100
      });
      setLiveDcfResult(res);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    handleRecalculateDCF();
  }, [dcfGrowth1, dcfTerminal, dcfWacc, dcfMos]);

  const isSaved = watchlist.includes(selectedSymbol);

  return (
    <div className="space-y-8 pb-16">
      {/* Search Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 dark:text-white flex items-center gap-2">
            <span>🔎 Stock Deep-Dive & Valuation Suite</span>
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Universal search across NSE equities with intrinsic value, technical analysis and TradingView charts.
          </p>
        </div>

        {/* Search Bar with Autocomplete Dropdown */}
        <div className="relative w-full sm:w-80">
          <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
            <Search className="w-4 h-4 text-slate-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search Name or Symbol (e.g. TCS)..."
              className="bg-transparent border-none text-xs text-slate-900 dark:text-white focus:outline-none w-full"
            />
          </div>

          {searchResults.length > 0 && query && (
            <div className="absolute top-full mt-1 left-0 right-0 z-30 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-2xl max-h-60 overflow-y-auto divide-y divide-slate-100 dark:divide-slate-800">
              {searchResults.map((s) => (
                <button
                  key={s.symbol}
                  onClick={() => {
                    setSelectedSymbol(s.symbol);
                    setQuery('');
                    setSearchResults([]);
                  }}
                  className="w-full text-left p-2.5 hover:bg-indigo-50 dark:hover:bg-slate-800 flex items-center justify-between text-xs"
                >
                  <div>
                    <span className="font-bold text-slate-900 dark:text-white">{s.name}</span>
                    <span className="block text-[10px] text-slate-400">{s.symbol} • {s.sector}</span>
                  </div>
                  <span className="text-[10px] font-semibold text-indigo-600 dark:text-indigo-400">{s.category}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {loading && !overview ? (
        <div className="flex flex-col items-center justify-center min-h-[400px] space-y-3">
          <RefreshCw className="w-8 h-8 text-indigo-600 animate-spin" />
          <p className="text-sm text-slate-500 font-medium">Analyzing financials, balance sheet, and technical signals for {selectedSymbol}...</p>
        </div>
      ) : overview ? (
        <div className="space-y-6">
          {/* Stock Header Banner */}
          <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-2xl font-black text-slate-900 dark:text-white">{overview.name}</h2>
                <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                  {overview.symbol}
                </span>
                <span className="px-2 py-0.5 rounded text-xs font-semibold bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400">
                  {overview.sector}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-1">{overview.industry} • {overview.category}</p>
            </div>

            <div className="flex items-center gap-6">
              <div>
                <span className="text-3xl font-black text-slate-900 dark:text-white">
                  {formatINR(overview.fundamentals?.current_price)}
                </span>
                <div className={`text-xs font-bold ${getPctColor(overview.fundamentals?.change_1d_pct)} mt-0.5`}>
                  {formatPct(overview.fundamentals?.change_1d_pct)} ({formatINR(overview.fundamentals?.change_1d, false)})
                </div>
              </div>

              <button
                onClick={() => toggleWatchlist(selectedSymbol)}
                className={`p-3 rounded-xl border transition flex items-center gap-1.5 text-xs font-semibold ${
                  isSaved
                    ? 'bg-indigo-50 dark:bg-indigo-950/80 border-indigo-300 text-indigo-600 dark:text-indigo-300'
                    : 'bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-200'
                }`}
              >
                {isSaved ? <BookmarkCheck className="w-4 h-4 text-indigo-600" /> : <Bookmark className="w-4 h-4" />}
                <span>{isSaved ? 'Watchlisted' : 'Add to Watchlist'}</span>
              </button>
            </div>
          </div>

          {/* Sub-Navigation Strip */}
          <div className="flex border-b border-slate-200 dark:border-slate-800 gap-2 overflow-x-auto text-xs font-bold">
            {[
              { id: 'overview', label: '📌 Overview & Verdict' },
              { id: 'valuation', label: '🏢 Fundamental & Intrinsic Value' },
              { id: 'technical', label: '📈 Technical & Charts' },
              { id: 'financials', label: '📑 Financial Statements' },
              { id: 'peers', label: '👥 Peer Comparison' }
            ].map((t) => (
              <button
                key={t.id}
                onClick={() => setSubTab(t.id as any)}
                className={`pb-3 px-3 transition-colors relative ${
                  subTab === t.id
                    ? 'text-indigo-600 dark:text-indigo-400 border-b-2 border-indigo-600'
                    : 'text-slate-500 hover:text-slate-900 dark:hover:text-slate-200'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* SUBTAB 1: Overview */}
          {subTab === 'overview' && (
            <div className="space-y-6">
              {/* Combined Verdict Card */}
              <div className="p-6 rounded-2xl bg-gradient-to-r from-indigo-500/10 via-purple-500/10 to-emerald-500/10 border border-indigo-200 dark:border-indigo-900 space-y-3">
                <div className="flex items-center gap-2 font-bold text-sm text-indigo-900 dark:text-indigo-200">
                  <Award className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                  <span>Institutional Combined Verdict (Fundamental + Technical + Macro)</span>
                </div>
                <p className="text-sm text-slate-800 dark:text-slate-200 leading-relaxed font-medium">
                  {overview.combined_verdict}
                </p>
                <div className="flex flex-wrap gap-2 pt-2">
                  <span className="px-3 py-1 rounded-full text-xs font-bold bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 shadow-sm border border-slate-200 dark:border-slate-700">
                    Valuation: <strong>{overview.valuation_summary?.valuation_label}</strong>
                  </span>
                  <span className="px-3 py-1 rounded-full text-xs font-bold bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 shadow-sm border border-slate-200 dark:border-slate-700">
                    Quality Grade: <strong>{overview.valuation_summary?.grade} ({overview.valuation_summary?.quality_score}/100)</strong>
                  </span>
                  <span className="px-3 py-1 rounded-full text-xs font-bold bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 shadow-sm border border-slate-200 dark:border-slate-700">
                    Technical Signal: <strong>{overview.technical_summary?.overall_rating}</strong>
                  </span>
                </div>
              </div>

              {/* Quick Fundamental & Valuation Matrix */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
                  <span className="text-xs text-slate-500">Market Capitalization</span>
                  <div className="text-lg font-bold text-slate-900 dark:text-white mt-1">
                    {formatINR(overview.fundamentals?.market_cap)}
                  </div>
                </div>
                <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
                  <span className="text-xs text-slate-500">Trailing P/E Ratio</span>
                  <div className="text-lg font-bold text-slate-900 dark:text-white mt-1">
                    {formatNumber(overview.fundamentals?.trailing_pe)}x
                  </div>
                </div>
                <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
                  <span className="text-xs text-slate-500">Price to Book (P/B)</span>
                  <div className="text-lg font-bold text-slate-900 dark:text-white mt-1">
                    {formatNumber(overview.fundamentals?.price_to_book)}x
                  </div>
                </div>
                <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
                  <span className="text-xs text-slate-500">52-Week Range</span>
                  <div className="text-xs font-bold text-slate-900 dark:text-white mt-1">
                    ₹{overview.fundamentals?.low_52w} - ₹{overview.fundamentals?.high_52w}
                  </div>
                </div>
              </div>

              {/* Upcoming Actions for this stock */}
              {overview.upcoming_actions && overview.upcoming_actions.length > 0 && (
                <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-3">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">Upcoming Corporate Actions</h3>
                  {overview.upcoming_actions.map((act: any, idx: number) => (
                    <div key={idx} className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800 flex items-center justify-between text-xs">
                      <div>
                        <span className="font-bold text-slate-900 dark:text-white">{act.action_type}: {act.details}</span>
                        <p className="text-[11px] text-slate-500">Ex-Date: {act.ex_date || 'TBA'}</p>
                      </div>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300">
                        {act.signal}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* SUBTAB 2: Fundamental & Intrinsic Value */}
          {subTab === 'valuation' && valuation && (
            <div className="space-y-8">
              {/* Intrinsic Value Summary Header */}
              <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-6">
                <div>
                  <span className="text-xs text-slate-500 uppercase font-bold tracking-wider">Intrinsic Value</span>
                  <div className="mt-1 flex items-baseline gap-2">
                    <span className="text-3xl font-black text-slate-900 dark:text-white">
                      {formatINR(valuation.blended_intrinsic_value)}
                    </span>
                    <span className="text-xs text-slate-400">vs CMP {formatINR(overview.fundamentals?.current_price)}</span>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">{valuation.confidence_reason}</p>
                </div>

                <div className="text-right">
                  <span className="text-xs text-slate-400 block font-medium">Margin of Safety</span>
                  <span className={`text-2xl font-black ${valuation.margin_of_safety_pct >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                    {formatPct(valuation.margin_of_safety_pct)}
                  </span>
                  <span className="text-xs font-bold block text-slate-700 dark:text-slate-300 mt-0.5">
                    {valuation.valuation_label}
                  </span>
                </div>
              </div>

              {/* Interactive DCF Model with Sliders */}
              <div className="p-6 rounded-2xl border border-indigo-200 dark:border-indigo-900 bg-indigo-50/40 dark:bg-indigo-950/20 space-y-6">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sliders className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                    <h3 className="text-base font-bold text-slate-900 dark:text-white">
                      Intrinsic Value Simulator (Live Recalculation)
                    </h3>
                  </div>
                  {liveDcfResult && (
                    <div className="text-right">
                      <span className="text-xs text-slate-500 block">Simulated Intrinsic Value</span>
                      <span className="text-xl font-black text-indigo-600 dark:text-indigo-400">
                        {formatINR(liveDcfResult.intrinsic_value)}
                      </span>
                    </div>
                  )}
                </div>

                {/* Slider Controls */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 text-xs">
                  <div>
                    <div className="flex justify-between font-semibold text-slate-700 dark:text-slate-300 mb-1">
                      <span>Stage 1 Growth (Yrs 1-5):</span>
                      <span className="font-bold text-indigo-600">{dcfGrowth1}%</span>
                    </div>
                    <input
                      type="range"
                      min="2"
                      max="30"
                      step="0.5"
                      value={dcfGrowth1}
                      onChange={(e) => setDcfGrowth1(parseFloat(e.target.value))}
                      className="w-full accent-indigo-600 cursor-pointer"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between font-semibold text-slate-700 dark:text-slate-300 mb-1">
                      <span>Terminal Growth:</span>
                      <span className="font-bold text-indigo-600">{dcfTerminal}%</span>
                    </div>
                    <input
                      type="range"
                      min="2"
                      max="7"
                      step="0.1"
                      value={dcfTerminal}
                      onChange={(e) => setDcfTerminal(parseFloat(e.target.value))}
                      className="w-full accent-indigo-600 cursor-pointer"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between font-semibold text-slate-700 dark:text-slate-300 mb-1">
                      <span>Discount Rate / WACC:</span>
                      <span className="font-bold text-indigo-600">{dcfWacc}%</span>
                    </div>
                    <input
                      type="range"
                      min="8"
                      max="18"
                      step="0.25"
                      value={dcfWacc}
                      onChange={(e) => setDcfWacc(parseFloat(e.target.value))}
                      className="w-full accent-indigo-600 cursor-pointer"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between font-semibold text-slate-700 dark:text-slate-300 mb-1">
                      <span>Margin of Safety:</span>
                      <span className="font-bold text-indigo-600">{dcfMos}%</span>
                    </div>
                    <input
                      type="range"
                      min="5"
                      max="40"
                      step="1"
                      value={dcfMos}
                      onChange={(e) => setDcfMos(parseFloat(e.target.value))}
                      className="w-full accent-indigo-600 cursor-pointer"
                    />
                  </div>
                </div>
              </div>

              {/* Company Valuation & Cash Flow Details (EV/EBITDA, FCFF, FCFE) */}
              <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-4">
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">
                  Company Valuation Multiples & Free Cash Flows
                </h3>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                    <span className="text-slate-500 block">Enterprise Value (EV)</span>
                    <span className="text-base font-bold text-slate-900 dark:text-white mt-1 block">
                      ₹{valuation.valuation_multiples?.enterprise_value_cr?.toLocaleString('en-IN')} Cr
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                    <span className="text-slate-500 block">EV / EBITDA Multiple</span>
                    <span className="text-base font-bold text-slate-900 dark:text-white mt-1 block">
                      {formatNumber(valuation.valuation_multiples?.ev_to_ebitda)}x
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                    <span className="text-slate-500 block">Trailing P/E</span>
                    <span className="text-base font-bold text-slate-900 dark:text-white mt-1 block">
                      {formatNumber(overview.fundamentals?.trailing_pe)}x
                    </span>
                    <span className="text-[10px] text-slate-400">Forward P/E: {formatNumber(overview.fundamentals?.forward_pe)}x</span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                    <span className="text-slate-500 block">Price to Book (P/B)</span>
                    <span className="text-base font-bold text-slate-900 dark:text-white mt-1 block">
                      {formatNumber(overview.fundamentals?.price_to_book)}x
                    </span>
                    <span className="text-[10px] text-slate-400">Book value/share: ₹{formatNumber(overview.fundamentals?.book_value)}</span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                    <span className="text-slate-500 block">Free Cash Flow to Firm (FCFF)</span>
                    <span className="text-base font-bold text-slate-900 dark:text-white mt-1 block">
                      ₹{valuation.valuation_multiples?.fcff_cr?.toLocaleString('en-IN')} Cr
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                    <span className="text-slate-500 block">Free Cash Flow to Equity (FCFE)</span>
                    <span className="text-base font-bold text-slate-900 dark:text-white mt-1 block">
                      ₹{valuation.valuation_multiples?.fcfe_cr?.toLocaleString('en-IN')} Cr
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                    <span className="text-slate-500 block">Operating Cash Flow (CFO)</span>
                    <span className="text-base font-bold text-slate-900 dark:text-white mt-1 block">
                      ₹{valuation.valuation_multiples?.operating_cash_flow_cr?.toLocaleString('en-IN')} Cr
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                    <span className="text-slate-500 block">Capital Expenditures (CapEx)</span>
                    <span className="text-base font-bold text-slate-900 dark:text-white mt-1 block">
                      ₹{valuation.valuation_multiples?.capex_cr?.toLocaleString('en-IN')} Cr
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                    <span className="text-slate-500 block">FCF Yield (%)</span>
                    <span className="text-base font-bold text-emerald-600 dark:text-emerald-400 mt-1 block">
                      {formatPct(valuation.valuation_multiples?.fcf_yield_pct)}
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                    <span className="text-slate-500 block">Price to Free Cash Flow (P/FCF)</span>
                    <span className="text-base font-bold text-slate-900 dark:text-white mt-1 block">
                      {formatNumber(valuation.valuation_multiples?.price_to_fcf)}x
                    </span>
                  </div>
                </div>
              </div>

              {/* Quality Scorecard & Piotroski F-Score */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold uppercase text-slate-600 dark:text-slate-400">Quality Scorecard (0-100)</h3>
                    <span className="text-xl font-black text-indigo-600 dark:text-indigo-400">
                      {valuation.quality_scorecard?.quality_score}/100 (Grade {valuation.quality_scorecard?.grade})
                    </span>
                  </div>
                  <ul className="space-y-1.5 text-xs text-slate-600 dark:text-slate-400">
                    {valuation.quality_scorecard?.breakdown?.map((b: string, i: number) => (
                      <li key={i} className="flex items-center gap-2">
                        <span className="text-emerald-500 font-bold">✓</span> {b}
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold uppercase text-slate-600 dark:text-slate-400">Piotroski F-Score (0-9)</h3>
                    <span className="text-xl font-black text-emerald-600 dark:text-emerald-400">
                      {valuation.quality_scorecard?.piotroski_f_score}/9 ({valuation.quality_scorecard?.piotroski_rating})
                    </span>
                  </div>
                  <ul className="space-y-1.5 text-xs text-slate-600 dark:text-slate-400">
                    {valuation.quality_scorecard?.piotroski_reasons?.map((r: string, i: number) => (
                      <li key={i} className="flex items-center gap-2">
                        <span className="text-indigo-500 font-bold">•</span> {r}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* SUBTAB 3: Technical Analysis & Candlestick Charts */}
          {subTab === 'technical' && technicals && (
            <div className="space-y-8">
              {/* Technical Chart Card */}
              <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <h3 className="text-sm font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">
                      Interactive Candlestick Chart (TradingView Engine)
                    </h3>
                    <span className={`px-2.5 py-0.5 rounded text-xs font-bold ${
                      technicals.overall_rating.includes('Buy')
                        ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                        : technicals.overall_rating.includes('Sell')
                        ? 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
                        : 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                    }`}>
                      {technicals.overall_rating} (Score: {technicals.technical_score}/100)
                    </span>
                  </div>

                  {/* Timeframe selector */}
                  <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg text-xs font-semibold">
                    {['1mo', '3mo', '6mo', '1y', '2y'].map((p) => (
                      <button
                        key={p}
                        onClick={() => setChartPeriod(p)}
                        className={`px-2.5 py-1 rounded ${chartPeriod === p ? 'bg-white dark:bg-slate-900 text-indigo-600 shadow-sm' : 'text-slate-500'}`}
                      >
                        {p.toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>

                {/* TradingView Chart Component */}
                <TradingViewChart data={technicals.candlesticks || []} darkMode={darkMode} />
              </div>

              {/* Technical Indicator Dashboard Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
                <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                  <span className="text-slate-400">RSI (14-Day)</span>
                  <span className="text-lg font-bold text-slate-900 dark:text-white mt-1 block">
                    {technicals.indicators?.rsi_14}
                  </span>
                </div>
                <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                  <span className="text-slate-400">MACD (12, 26, 9)</span>
                  <span className="text-lg font-bold text-slate-900 dark:text-white mt-1 block">
                    {technicals.indicators?.macd}
                  </span>
                </div>
                <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                  <span className="text-slate-400">200-Day DMA</span>
                  <span className="text-lg font-bold text-slate-900 dark:text-white mt-1 block">
                    ₹{technicals.indicators?.sma_200}
                  </span>
                </div>
                <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                  <span className="text-slate-400">Average True Range (ATR)</span>
                  <span className="text-lg font-bold text-slate-900 dark:text-white mt-1 block">
                    ₹{technicals.indicators?.atr_14}
                  </span>
                </div>
              </div>

              {/* Signals & Fibonacci Levels */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Signals List */}
                <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-3">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">Active Technical Signals</h3>
                  <div className="space-y-2">
                    {technicals.signals?.map((s: any, idx: number) => (
                      <div key={idx} className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800 flex items-center justify-between text-xs">
                        <div>
                          <span className="font-bold text-slate-900 dark:text-white">{s.name}</span>
                          <p className="text-[11px] text-slate-500">{s.desc}</p>
                        </div>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          s.type.includes('Bullish') ? 'text-emerald-600 bg-emerald-50 dark:bg-emerald-950' : 'text-rose-600 bg-rose-50 dark:bg-rose-950'
                        }`}>
                          {s.weight}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                <PatternPanel technicals={technicals} />

                {/* Fibonacci Retracements */}
                <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-3">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">Fibonacci Retracement Levels</h3>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {Object.entries(technicals.fibonacci_levels || {}).map(([fib, price]: [string, any]) => (
                      <div key={fib} className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800 flex items-center justify-between">
                        <span className="text-slate-500 font-medium">{fib}</span>
                        <span className="font-bold text-slate-900 dark:text-white">₹{price}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* SUBTAB 4: Financial Statements */}
          {subTab === 'financials' && financials && (
            <FinancialStatements data={financials} />
          )}

          {/* SUBTAB 5: Peer Comparison */}
          {subTab === 'peers' && (
            <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-4">
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">
                Sector Peers Comparison ({overview.sector})
              </h3>
              <div className="overflow-x-auto text-xs">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800 text-slate-500 uppercase text-[10px] font-bold">
                      <th className="p-2.5">Company</th>
                      <th className="p-2.5 text-right">Price</th>
                      <th className="p-2.5 text-right">1D %</th>
                      <th className="p-2.5 text-right">Trailing P/E</th>
                      <th className="p-2.5 text-right">Price to Book</th>
                      <th className="p-2.5 text-right">EV/EBITDA</th>
                      <th className="p-2.5 text-right">Market Cap</th>
                      <th className="p-2.5 text-center">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {peers.map((p) => (
                      <tr key={p.symbol} className="hover:bg-slate-50/50">
                        <td className="p-2.5 font-bold text-slate-900 dark:text-white">
                          {p.name}
                          <span className="block text-[10px] text-slate-400 font-normal">{p.symbol}</span>
                        </td>
                        <td className="p-2.5 text-right font-semibold">{formatINR(p.price)}</td>
                        <td className={`p-2.5 text-right font-bold ${getPctColor(p.change_1d_pct)}`}>{formatPct(p.change_1d_pct)}</td>
                        <td className="p-2.5 text-right font-semibold">{formatNumber(p.trailing_pe)}x</td>
                        <td className="p-2.5 text-right font-semibold">{formatNumber(p.price_to_book)}x</td>
                        <td className="p-2.5 text-right font-semibold">{formatNumber(p.ev_to_ebitda)}x</td>
                        <td className="p-2.5 text-right font-bold">₹{p.market_cap_cr} Cr</td>
                        <td className="p-2.5 text-center">
                          <button
                            onClick={() => setSelectedSymbol(p.symbol)}
                            className="px-2.5 py-1 text-[11px] font-semibold rounded bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400"
                          >
                            Analyze
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
