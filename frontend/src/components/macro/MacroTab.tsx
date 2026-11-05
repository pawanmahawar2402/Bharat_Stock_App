import React, { useState, useEffect } from 'react';
import { RefreshCw, TrendingUp, TrendingDown, ShieldAlert, Sparkles, Database, Clock, Layers } from 'lucide-react';
import { api } from '@/lib/api';
import { formatNumber, formatPct, getPctColor } from '@/lib/formatters';
import StockMacroSentiment from '@/components/macro/StockMacroSentiment';

export default function MacroTab() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getMacroOverview();
      setData(res);
    } catch (err: any) {
      setError('Could not load live macro data. Please ensure backend is running.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading && !data) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] space-y-3">
        <RefreshCw className="w-8 h-8 text-indigo-600 animate-spin" />
        <p className="text-sm text-slate-500 font-medium">Fetching live global & domestic macroeconomic indicators...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 rounded-2xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900 text-rose-800 dark:text-rose-200 max-w-xl mx-auto my-12 text-center">
        <ShieldAlert className="w-8 h-8 text-rose-500 mx-auto mb-2" />
        <p className="font-semibold text-sm">{error}</p>
        <button
          onClick={loadData}
          className="mt-4 px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-semibold"
        >
          Retry Loading
        </button>
      </div>
    );
  }

  const { regime, market_indicators = [], macro_indicators = {}, sector_heatmap = [], narrative_bullets = [] } = data || {};

  return (
    <div className="space-y-8 pb-16">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 dark:text-white flex items-center gap-2">
            <span>🌍 Macro Economy & Regime Outlook</span>
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Global market benchmarks, domestic macroeconomic indicators, and algorithmic risk regime modeling.
          </p>
        </div>
        <button
          onClick={loadData}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100 transition self-start sm:self-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Data</span>
        </button>
      </div>

      {/* 1. Macro Regime Gauge Card */}
      {regime && (
        <div className={`p-6 rounded-2xl border ${
          regime.regime === 'Risk-On'
            ? 'bg-emerald-500/5 border-emerald-500/30 dark:bg-emerald-950/20'
            : regime.regime === 'Risk-Off'
            ? 'bg-rose-500/5 border-rose-500/30 dark:bg-rose-950/20'
            : 'bg-amber-500/5 border-amber-500/30 dark:bg-amber-950/20'
        }`}>
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            <div className="space-y-2 max-w-2xl">
              <div className="flex items-center gap-3">
                <span className="text-xs uppercase tracking-wider font-bold text-slate-500 dark:text-slate-400">
                  Macro Market Regime
                </span>
                <span className={`px-3 py-1 rounded-full text-xs font-bold border ${
                  regime.regime === 'Risk-On'
                    ? 'bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-800'
                    : regime.regime === 'Risk-Off'
                    ? 'bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-950 dark:text-rose-300 dark:border-rose-800'
                    : 'bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-800'
                }`}>
                  {regime.badge}
                </span>
              </div>
              <p className="text-sm font-medium text-slate-700 dark:text-slate-300 leading-relaxed">
                {regime.description}
              </p>
            </div>

            {/* Factor attribution chips */}
            <div className="flex flex-wrap gap-2 lg:max-w-md">
              {regime.factors?.map((f: any, i: number) => (
                <div
                  key={i}
                  className="px-2.5 py-1 rounded-lg bg-white/80 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 text-[11px] shadow-sm flex items-center gap-1.5"
                >
                  <span className="font-bold text-slate-800 dark:text-slate-200">{f.factor}:</span>
                  <span className={f.status.includes('Bullish') ? 'text-emerald-600 dark:text-emerald-400 font-semibold' : f.status.includes('Bearish') ? 'text-rose-600 dark:text-rose-400 font-semibold' : 'text-slate-500'}>
                    {f.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 2. 10 Market Indicator Cards (Yahoo Finance) */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
            <TrendingUp className="w-4 h-4 text-indigo-500" />
            <span>Key Market Indicators (Yahoo Live / Delayed)</span>
          </h2>
          <span className="text-[11px] text-slate-400">1D / 1W / 1M / 1Y Trends</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {market_indicators.map((ind: any) => {
            const isUp = ind.change_1d >= 0;
            return (
              <div
                key={ind.name}
                className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm hover:border-indigo-400 dark:hover:border-indigo-600 transition flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 truncate">
                      {ind.name}
                    </span>
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                      isUp ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-400' : 'bg-rose-50 text-rose-600 dark:bg-rose-950/60 dark:text-rose-400'
                    }`}>
                      {formatPct(ind.change_1d_pct)}
                    </span>
                  </div>
                  <div className="mt-2 flex items-baseline gap-1">
                    <span className="text-lg font-black text-slate-900 dark:text-white">
                      {formatNumber(ind.current_value)}
                    </span>
                    <span className="text-[10px] text-slate-400 font-medium">{ind.unit}</span>
                  </div>
                </div>

                {/* Mini SVG Sparkline */}
                {ind.sparkline && ind.sparkline.length > 5 && (
                  <div className="mt-3 h-8 w-full">
                    <svg className="w-full h-full overflow-visible" viewBox="0 0 100 30" preserveAspectRatio="none">
                      {(() => {
                        const pts = ind.sparkline;
                        const min = Math.min(...pts);
                        const max = Math.max(...pts);
                        const range = max - min || 1;
                        const coords = pts.map((p: number, idx: number) => {
                          const x = (idx / (pts.length - 1)) * 100;
                          const y = 30 - ((p - min) / range) * 26 - 2;
                          return `${x},${y}`;
                        }).join(' ');
                        return (
                          <polyline
                            fill="none"
                            stroke={isUp ? '#10b981' : '#f43f5e'}
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            points={coords}
                          />
                        );
                      })()}
                    </svg>
                  </div>
                )}

                {/* Period Change Matrix */}
                <div className="mt-3 pt-2 border-t border-slate-100 dark:border-slate-800 grid grid-cols-3 text-[10px] text-center text-slate-500">
                  <div>
                    <span className="block text-[9px] text-slate-400 uppercase">1W</span>
                    <span className={`font-semibold ${getPctColor(ind.change_1w_pct)}`}>{formatPct(ind.change_1w_pct)}</span>
                  </div>
                  <div>
                    <span className="block text-[9px] text-slate-400 uppercase">1M</span>
                    <span className={`font-semibold ${getPctColor(ind.change_1m_pct)}`}>{formatPct(ind.change_1m_pct)}</span>
                  </div>
                  <div>
                    <span className="block text-[9px] text-slate-400 uppercase">1Y</span>
                    <span className={`font-semibold ${getPctColor(ind.change_1y_pct)}`}>{formatPct(ind.change_1y_pct)}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 3. Official Domestic Macro Indicators Grid */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
            <Database className="w-4 h-4 text-emerald-500" />
            <span>Official Macroeconomic Indicators (RBI / MOSPI / FRED / CCIL)</span>
          </h2>
          <span className="text-[11px] text-slate-400">Verified Primary Sources</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Repo Rate */}
          {macro_indicators.rbi_repo_rate && (
            <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
              <span className="text-xs font-semibold text-slate-500">RBI Repo Rate</span>
              <div className="mt-1 flex items-baseline gap-1">
                <span className="text-2xl font-black text-slate-900 dark:text-white">
                  {macro_indicators.rbi_repo_rate.value.toFixed(2)}%
                </span>
              </div>
              <p className="text-[11px] text-slate-500 mt-1">{macro_indicators.rbi_repo_rate.description}</p>
              <div className="mt-3 pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[10px]">
                <span className="text-indigo-600 dark:text-indigo-400 font-semibold">{macro_indicators.rbi_repo_rate.source}</span>
                <span className="text-slate-400 flex items-center gap-1"><Clock className="w-3 h-3" /> Live</span>
              </div>
            </div>
          )}

          {/* CPI Inflation */}
          {macro_indicators.cpi_inflation && (
            <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
              <span className="text-xs font-semibold text-slate-500">CPI Inflation (Headline)</span>
              <div className="mt-1 flex items-baseline gap-1">
                <span className="text-2xl font-black text-slate-900 dark:text-white">
                  {macro_indicators.cpi_inflation.value.toFixed(2)}%
                </span>
                <span className="text-xs text-slate-400">YoY</span>
              </div>
              <p className="text-[11px] text-slate-500 mt-1">{macro_indicators.cpi_inflation.description}</p>
              <div className="mt-3 pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[10px]">
                <span className="text-indigo-600 dark:text-indigo-400 font-semibold">{macro_indicators.cpi_inflation.source}</span>
                <span className="text-slate-400">Monthly</span>
              </div>
            </div>
          )}

          {/* India 10Y G-Sec */}
          {macro_indicators.india_10y_gsec && (
            <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
              <span className="text-xs font-semibold text-slate-500">India 10Y Benchmark G-Sec</span>
              <div className="mt-1 flex items-baseline gap-1">
                <span className="text-2xl font-black text-slate-900 dark:text-white">
                  {macro_indicators.india_10y_gsec.value.toFixed(2)}%
                </span>
              </div>
              <p className="text-[11px] text-slate-500 mt-1">{macro_indicators.india_10y_gsec.description}</p>
              <div className="mt-3 pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[10px]">
                <span className="text-indigo-600 dark:text-indigo-400 font-semibold">{macro_indicators.india_10y_gsec.source}</span>
                <span className="text-slate-400">Daily Benchmark</span>
              </div>
            </div>
          )}

          {/* Forex Reserves */}
          {macro_indicators.forex_reserves && (
            <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
              <span className="text-xs font-semibold text-slate-500">Foreign Exchange Reserves</span>
              <div className="mt-1 flex items-baseline gap-1">
                <span className="text-2xl font-black text-slate-900 dark:text-white">
                  ${macro_indicators.forex_reserves.value.toFixed(1)}B
                </span>
              </div>
              <p className="text-[11px] text-slate-500 mt-1">{macro_indicators.forex_reserves.description}</p>
              <div className="mt-3 pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[10px]">
                <span className="text-indigo-600 dark:text-indigo-400 font-semibold">{macro_indicators.forex_reserves.source}</span>
                <span className="text-slate-400">Weekly Release</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 4. Sector Rotation Heatmap & Relative Strength */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
            <Layers className="w-4 h-4 text-amber-500" />
            <span>Nifty Sector Rotation Heatmap & Relative Strength</span>
          </h2>
          <span className="text-[11px] text-slate-400">Benchmarked vs. Nifty 50</span>
        </div>

        <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400 font-bold uppercase text-[10px]">
                <th className="p-3">Sector Index</th>
                <th className="p-3 text-right">Current Value</th>
                <th className="p-3 text-right">1-Week Return</th>
                <th className="p-3 text-right">1-Month Return</th>
                <th className="p-3 text-right">3-Month Return</th>
                <th className="p-3 text-right">RS vs Nifty (1M)</th>
                <th className="p-3 text-center">Momentum Call</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {sector_heatmap.map((sec: any) => (
                <tr key={sec.name} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition">
                  <td className="p-3 font-bold text-slate-900 dark:text-white">
                    {sec.name}
                    <span className="block text-[10px] text-slate-400 font-normal">{sec.sector_key}</span>
                  </td>
                  <td className="p-3 text-right font-semibold text-slate-800 dark:text-slate-200">
                    {formatNumber(sec.current_index_value)}
                  </td>
                  <td className={`p-3 text-right font-bold ${getPctColor(sec.return_1w_pct)}`}>
                    {formatPct(sec.return_1w_pct)}
                  </td>
                  <td className={`p-3 text-right font-bold ${getPctColor(sec.return_1m_pct)}`}>
                    {formatPct(sec.return_1m_pct)}
                  </td>
                  <td className={`p-3 text-right font-bold ${getPctColor(sec.return_3m_pct)}`}>
                    {formatPct(sec.return_3m_pct)}
                  </td>
                  <td className={`p-3 text-right font-bold ${getPctColor(sec.rs_vs_nifty_1m)}`}>
                    {formatPct(sec.rs_vs_nifty_1m)}
                  </td>
                  <td className="p-3 text-center">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      sec.rs_signal === 'Outperforming'
                        ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                        : sec.rs_signal === 'Underperforming'
                        ? 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
                        : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                    }`}>
                      {sec.rs_signal}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 5. Institutional AI Macro Narrative Card */}
      <div className="p-6 rounded-2xl border border-indigo-200 dark:border-indigo-900 bg-indigo-50/50 dark:bg-indigo-950/20 space-y-4">
        <div className="flex items-center gap-2 text-indigo-700 dark:text-indigo-300 font-bold text-sm">
          <Sparkles className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
          <span>Macro Narrative: What this means for Indian Equities</span>
        </div>

        <ul className="space-y-2.5 text-xs text-slate-700 dark:text-slate-300">
          {narrative_bullets.map((bullet: string, idx: number) => (
            <li key={idx} className="flex items-start gap-2">
              <span className="text-indigo-500 font-bold">•</span>
              <span dangerouslySetInnerHTML={{ __html: bullet.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }} />
            </li>
          ))}
        </ul>
      </div>

      {/* 6. Stock-specific macro sentiment: positive / negative read for a chosen stock */}
      <StockMacroSentiment />
    </div>
  );
}
