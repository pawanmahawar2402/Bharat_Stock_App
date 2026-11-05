'use client';

import React from 'react';

const BIAS_STYLE: Record<string, string> = {
  Bullish: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800',
  Bearish: 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 border-rose-300 dark:border-rose-800',
  Neutral: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-300 dark:border-slate-700',
};

const STATUS_STYLE: Record<string, string> = {
  Confirmed: 'bg-indigo-600 text-white',
  Forming: 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300',
  'Candle signal': 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200',
};

function PatternCard({ p }: { p: any }) {
  const bias = p.bias || 'Neutral';
  return (
    <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100">{p.pattern}</h4>
        <div className="flex gap-1.5 shrink-0">
          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${BIAS_STYLE[bias] || BIAS_STYLE.Neutral}`}>{bias}</span>
          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${STATUS_STYLE[p.status] || STATUS_STYLE['Candle signal']}`}>{p.status}</span>
        </div>
      </div>
      <p className="text-xs text-slate-600 dark:text-slate-400">{p.description}</p>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-500">
        <span>Date: <strong className="text-slate-700 dark:text-slate-300">{p.date}</strong></span>
        {p.level != null && <span>Level: <strong className="text-slate-700 dark:text-slate-300">₹{Number(p.level).toLocaleString('en-IN')}</strong></span>}
        {p.trend_before && <span>Trend before: <strong className="text-slate-700 dark:text-slate-300">{p.trend_before}</strong></span>}
      </div>
    </div>
  );
}

export default function PatternPanel({ technicals }: { technicals: any }) {
  const candles: any[] = technicals?.candlestick_patterns || [];
  const charts: any[] = technicals?.chart_patterns || [];
  const none = candles.length === 0 && charts.length === 0;

  return (
    <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-6 lg:col-span-2">
      <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">Breakout & reversal patterns</h3>

      {none && (
        <p className="text-xs text-slate-500">No candlestick or chart pattern is present on the latest bars.</p>
      )}

      {charts.length > 0 && (
        <div className="space-y-3">
          <div className="text-xs font-bold text-slate-600 dark:text-slate-400">Chart patterns</div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {charts.map((p, i) => <PatternCard key={`c-${i}`} p={p} />)}
          </div>
        </div>
      )}

      {candles.length > 0 && (
        <div className="space-y-3">
          <div className="text-xs font-bold text-slate-600 dark:text-slate-400">Candlestick patterns (latest sessions)</div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {candles.map((p, i) => <PatternCard key={`k-${i}`} p={p} />)}
          </div>
        </div>
      )}

      <p className="text-[11px] text-slate-500">
        Patterns describe what price did; they are signals to check, not orders. A pattern is “Confirmed” only when
        the close breaks its neckline or level.
      </p>
    </div>
  );
}
