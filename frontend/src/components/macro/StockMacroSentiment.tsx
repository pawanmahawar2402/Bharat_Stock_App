'use client';

import React, { useState } from 'react';
import { Search, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { api } from '@/lib/api';

const STANCE_CLASS: Record<string, string> = {
  Positive: 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-900',
  Negative: 'text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-900',
  Mixed: 'text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-900',
  Neutral: 'text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700',
};

export default function StockMacroSentiment() {
  const [query, setQuery] = useState<string>('');
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const analyse = async (e: React.FormEvent) => {
    e.preventDefault();
    const sym = query.trim();
    if (!sym) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await api.getStockMacroSentiment(sym));
    } catch {
      setError('Could not compute macro sentiment for that symbol.');
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const Icon = result?.sentiment === 'Positive' ? TrendingUp : result?.sentiment === 'Negative' ? TrendingDown : Minus;

  return (
    <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-4">
      <div>
        <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">Macro sentiment for a stock</h3>
        <p className="text-xs text-slate-500 mt-1">
          Enter an NSE symbol (e.g. INFY, MARUTI). The current market indicators above are mapped to its sector to give a positive or negative read.
        </p>
      </div>

      <form onSubmit={analyse} className="flex gap-2">
        <div className="relative flex-1 max-w-xs">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Symbol, e.g. INFY"
            className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950"
          />
        </div>
        <button type="submit" disabled={loading} className="px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white">
          {loading ? 'Analysing…' : 'Analyse'}
        </button>
      </form>

      {error && <div className="text-xs text-rose-600 dark:text-rose-400">{error}</div>}

      {result && (
        <div className="space-y-3">
          <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-bold ${STANCE_CLASS[result.sentiment] || STANCE_CLASS.Neutral}`}>
            <Icon className="w-4 h-4" />
            {result.company_name}: {result.sentiment} macro sentiment (net {result.net_score > 0 ? '+' : ''}{result.net_score})
          </div>
          {result.factors.length === 0 ? (
            <p className="text-xs text-slate-500">No current macro condition moves this sector beyond its normal range.</p>
          ) : (
            <ul className="space-y-2 text-xs">
              {result.factors.map((f: any) => (
                <li key={f.rule} className="flex gap-2 p-3 rounded-lg bg-slate-50 dark:bg-slate-950">
                  <span className={`font-bold ${f.stance === 'positive' ? 'text-emerald-600' : 'text-rose-600'}`}>
                    {f.stance === 'positive' ? '▲' : '▼'}
                  </span>
                  <span>
                    <strong>{f.indicator}</strong> ({f.metric === 'change_1m_pct' ? '1M change' : 'level'}: {f.indicator_value}). {f.explanation}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <p className="text-[11px] text-slate-500">{result.note}</p>
        </div>
      )}
    </div>
  );
}
