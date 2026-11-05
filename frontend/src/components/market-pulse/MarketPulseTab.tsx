import React, { useState, useEffect } from 'react';
import { Calendar, ListFilter, TrendingUp, TrendingDown, Bell, Zap, Filter, RefreshCw, CheckCircle2, AlertCircle } from 'lucide-react';
import { api } from '@/lib/api';
import { formatINR, formatNumber, formatPct, getPctColor } from '@/lib/formatters';

export default function MarketPulseTab({ onSelectStock }: { onSelectStock: (sym: string) => void }) {
  const [actions, setActions] = useState<any[]>([]);
  const [results, setResults] = useState<any[]>([]);
  const [deals, setDeals] = useState<any[]>([]);
  const [activity, setActivity] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  
  // Filters & Views
  const [viewMode, setViewMode] = useState<'list' | 'calendar'>('list');
  const [actionFilter, setActionFilter] = useState<string>('all');
  const [marketCapFilter, setMarketCapFilter] = useState<string>('all');

  const loadPulseData = async () => {
    setLoading(true);
    // Each section loads independently: a slow or failed call no longer blanks the whole page.
    const jobs = [
      api.getCorporateActions({ action_type: actionFilter, market_cap: marketCapFilter })
        .then((acts) => setActions(Array.isArray(acts) ? acts : []))
        .catch((err) => { console.error('corporate actions', err); setActions([]); }),
      api.getQuarterlyResults()
        .then((res) => setResults(Array.isArray(res) ? res : []))
        .catch((err) => { console.error('results', err); setResults([]); }),
      api.getBulkDeals()
        .then((d) => setDeals(Array.isArray(d) ? d : []))
        .catch((err) => { console.error('deals', err); setDeals([]); }),
      api.getMarketActivity()
        .then((a) => setActivity(a && typeof a === 'object' ? a : null))
        .catch((err) => { console.error('activity', err); setActivity(null); }),
    ];
    await Promise.allSettled(jobs);
    setLoading(false);
  };

  useEffect(() => {
    loadPulseData();
  }, [actionFilter, marketCapFilter]);

  return (
    <div className="space-y-8 pb-16">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 dark:text-white flex items-center gap-2">
            <span>📊 Market Pulse: Corporate Actions & Results Tracker</span>
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Tracking dividends, stock splits, bonuses, buybacks, board meetings, quarterly earnings, and institutional bulk deals.
          </p>
        </div>

        {/* View Toggle & Refresh */}
        <div className="flex items-center gap-2">
          <div className="bg-slate-100 dark:bg-slate-800 p-1 rounded-lg flex items-center">
            <button
              onClick={() => setViewMode('list')}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition ${
                viewMode === 'list' ? 'bg-white dark:bg-slate-900 text-indigo-600 shadow-sm' : 'text-slate-500'
              }`}
            >
              List View
            </button>
            <button
              onClick={() => setViewMode('calendar')}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition ${
                viewMode === 'calendar' ? 'bg-white dark:bg-slate-900 text-indigo-600 shadow-sm' : 'text-slate-500'
              }`}
            >
              Calendar View
            </button>
          </div>

          <button
            onClick={loadPulseData}
            disabled={loading}
            className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Action Filters Bar */}
      <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-wrap items-center gap-4 text-xs">
        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-indigo-500" />
          <span className="font-bold text-slate-700 dark:text-slate-300">Action Type:</span>
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2.5 py-1 text-xs font-medium text-slate-800 dark:text-slate-200"
          >
            <option value="all">All Actions</option>
            <option value="Dividend">Dividends</option>
            <option value="Split">Stock Splits</option>
            <option value="Bonus">Bonus Issues</option>
            <option value="Buyback">Buybacks</option>
            <option value="Earnings">Quarterly Earnings</option>
            <option value="Board Meeting">Board Meetings</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <span className="font-bold text-slate-700 dark:text-slate-300">Market Cap:</span>
          <select
            value={marketCapFilter}
            onChange={(e) => setMarketCapFilter(e.target.value)}
            className="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2.5 py-1 text-xs font-medium text-slate-800 dark:text-slate-200"
          >
            <option value="all">All Market Caps</option>
            <option value="Large Cap">Large Cap</option>
            <option value="Mid Cap">Mid Cap</option>
            <option value="Small Cap">Small Cap</option>
          </select>
        </div>

        <span className="ml-auto text-[11px] text-slate-400">
          Showing {actions.length} corporate actions
        </span>
      </div>

      {/* Corporate Actions Feed (List or Calendar Mode) */}
      <div className="space-y-3">
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
          <Bell className="w-4 h-4 text-indigo-500" />
          <span>Upcoming & Recent Corporate Actions</span>
        </h2>

        {viewMode === 'list' ? (
          <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/60 text-slate-500 font-bold uppercase text-[10px]">
                  <th className="p-3">Company</th>
                  <th className="p-3">Action Type</th>
                  <th className="p-3">Action Details</th>
                  <th className="p-3">Ex-Date / Record</th>
                  <th className="p-3">Signal & Logic</th>
                  <th className="p-3 text-center">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {actions.map((act) => (
                  <tr key={act.id} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition">
                    <td className="p-3 font-bold text-slate-900 dark:text-white">
                      {act.company_name}
                      <span className="block text-[10px] text-indigo-600 dark:text-indigo-400 font-mono">
                        {act.symbol} • {act.market_cap_category}
                      </span>
                    </td>
                    <td className="p-3 font-semibold text-slate-700 dark:text-slate-300">
                      <span className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[10px] font-bold">
                        {act.action_type}
                      </span>
                    </td>
                    <td className="p-3 text-slate-800 dark:text-slate-200 font-medium max-w-xs">
                      {act.details}
                    </td>
                    <td className="p-3 text-slate-500 text-[11px]">
                      <div>Ex: <span className="font-semibold text-slate-700 dark:text-slate-300">{act.ex_date || 'TBA'}</span></div>
                      <div>Rec: <span className="text-slate-500">{act.record_date || 'TBA'}</span></div>
                    </td>
                    <td className="p-3 max-w-sm">
                      <div className="flex items-center gap-1.5">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          act.signal === 'Positive'
                            ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                            : act.signal === 'Negative'
                            ? 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
                            : 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                        }`}>
                          {act.signal}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1 leading-tight">
                        {act.signal_reason}
                      </p>
                    </td>
                    <td className="p-3 text-center">
                      <button
                        onClick={() => onSelectStock(act.symbol)}
                        className="px-2.5 py-1 text-[11px] font-semibold rounded bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100"
                      >
                        Deep-Dive
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          /* Calendar Timeline View */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {actions.map((act) => (
              <div
                key={act.id}
                className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm hover:border-indigo-400 transition flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold uppercase text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60 px-2 py-0.5 rounded">
                      {act.action_type}
                    </span>
                    <span className="text-xs font-semibold text-slate-500 flex items-center gap-1">
                      <Calendar className="w-3 h-3" /> {act.ex_date}
                    </span>
                  </div>
                  <h3 className="text-sm font-bold text-slate-900 dark:text-white mt-2">{act.company_name}</h3>
                  <p className="text-xs text-slate-700 dark:text-slate-300 mt-1">{act.details}</p>
                </div>

                <div className="mt-4 pt-2 border-t border-slate-100 dark:border-slate-800">
                  <p className="text-[11px] text-slate-500 italic">"{act.signal_reason}"</p>
                  <button
                    onClick={() => onSelectStock(act.symbol)}
                    className="mt-3 w-full py-1 text-center text-xs font-semibold text-indigo-600 dark:text-indigo-400 bg-slate-50 dark:bg-slate-800 rounded-lg hover:bg-indigo-50"
                  >
                    Analyze {act.symbol}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Quarterly Results Season Tracker */}
      <div className="space-y-3">
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
          <Zap className="w-4 h-4 text-amber-500" />
          <span>Results Season Tracker (Q2 FY25)</span>
        </h2>

        <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/60 text-slate-500 font-bold uppercase text-[10px]">
                <th className="p-3">Company</th>
                <th className="p-3">Quarter</th>
                <th className="p-3 text-right">Net Revenue</th>
                <th className="p-3 text-right">YoY Revenue %</th>
                <th className="p-3 text-right">Net Profit (PAT)</th>
                <th className="p-3 text-right">YoY PAT %</th>
                <th className="p-3 text-center">Beat / Miss</th>
                <th className="p-3 text-center">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {results.map((r, i) => (
                <tr key={i} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition">
                  <td className="p-3 font-bold text-slate-900 dark:text-white">
                    {r.company_name}
                    <span className="block text-[10px] text-slate-400">{r.symbol}</span>
                  </td>
                  <td className="p-3 font-semibold text-slate-600 dark:text-slate-300">{r.quarter}</td>
                  <td className="p-3 text-right font-semibold text-slate-800 dark:text-slate-200">{formatINR(r.revenue_cr * 1e7)}</td>
                  <td className={`p-3 text-right font-bold ${getPctColor(r.revenue_yoy_pct)}`}>{formatPct(r.revenue_yoy_pct)}</td>
                  <td className="p-3 text-right font-semibold text-slate-800 dark:text-slate-200">{formatINR(r.pat_cr * 1e7)}</td>
                  <td className={`p-3 text-right font-bold ${getPctColor(r.pat_yoy_pct)}`}>{formatPct(r.pat_yoy_pct)}</td>
                  <td className="p-3 text-center">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      r.beat_miss === 'Beat'
                        ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                        : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                    }`}>
                      {r.beat_miss}
                    </span>
                  </td>
                  <td className="p-3 text-center">
                    <button
                      onClick={() => onSelectStock(r.symbol)}
                      className="px-2.5 py-1 text-[11px] font-semibold rounded bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100"
                    >
                      Deep-Dive
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Institutional Deals & Volume Breakouts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Bulk Deals */}
        <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-3">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
            <TrendingUp className="w-4 h-4 text-emerald-500" />
            <span>Institutional Bulk & Block Deals</span>
          </h3>
          <div className="space-y-2">
            {deals.map((d, idx) => (
              <div key={idx} className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs">
                <div>
                  <span className="font-bold text-slate-900 dark:text-white">{d.company_name}</span>
                  <p className="text-[11px] text-slate-500">{d.client_name} • <span className="font-bold text-emerald-600">{d.deal_type}</span></p>
                </div>
                <div className="text-right">
                  <span className="font-bold text-slate-900 dark:text-white">₹{d.value_cr} Cr</span>
                  <p className="text-[10px] text-slate-400">@ ₹{d.price}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Volume Spikes */}
        {activity && activity.volume_spikes && (
          <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
              <Zap className="w-4 h-4 text-amber-500" />
              <span>Unusual Volume Spikes (&gt;1.5x 20-DMA)</span>
            </h3>
            <div className="space-y-2">
              {activity.volume_spikes.map((q: any, idx: number) => (
                <div key={idx} className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs">
                  <div>
                    <span className="font-bold text-slate-900 dark:text-white">{q.company_name}</span>
                    <p className="text-[11px] text-slate-500">{q.symbol}</p>
                  </div>
                  <div className="text-right">
                    <span className="font-bold text-slate-900 dark:text-white">₹{q.current_price}</span>
                    <p className={`text-[10px] font-bold ${getPctColor(q.change_1d_pct)}`}>{formatPct(q.change_1d_pct)}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
