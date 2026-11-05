import React, { useState, useEffect } from 'react';
import { Target, ShieldAlert, Award, Download, Filter, RefreshCw, ChevronRight, BarChart2, CheckCircle, Clock } from 'lucide-react';
import { api } from '@/lib/api';
import { formatINR, formatPct } from '@/lib/formatters';

export default function SwingPicksTab({
  onSelectStock,
  watchlist
}: {
  onSelectStock: (sym: string) => void;
  watchlist: string[];
}) {
  const [picks, setPicks] = useState<any[]>([]);
  const [backtest, setBacktest] = useState<any>(null);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  
  // Modals & Filters
  const [selectedPlan, setSelectedPlan] = useState<any | null>(null);
  const [showBacktestModal, setShowBacktestModal] = useState<boolean>(false);
  const [setupFilter, setSetupFilter] = useState<string>('all');
  const [sectorFilter, setSectorFilter] = useState<string>('all');
  const [regime, setRegime] = useState<string>('Risk-On');

  const loadSwingData = async () => {
    setLoading(true);
    try {
      const [picksRes, btRes] = await Promise.all([
        api.getSwingPicks(regime),
        api.getBacktestStats()
      ]);
      setPicks(picksRes.picks || []);
      setBacktest(btRes);

      if (watchlist.length > 0) {
        const alertRes = await api.getWatchlistAlerts(watchlist);
        setAlerts(alertRes || []);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSwingData();
  }, [regime]);

  // Filtered Picks
  const filteredPicks = picks.filter((p) => {
    if (setupFilter !== 'all' && p.setup_type !== setupFilter) return false;
    if (sectorFilter !== 'all' && p.sector !== sectorFilter) return false;
    return true;
  });

  // CSV Export
  const exportCSV = () => {
    if (!filteredPicks.length) return;
    const headers = ['Symbol', 'Company', 'Setup', 'Current Price', 'Entry Zone', 'Stop Loss', 'Target 1', 'Target 2', 'Risk Reward', 'Holding Days', 'Score'];
    const rows = filteredPicks.map(p => [
      p.symbol,
      `"${p.company_name}"`,
      `"${p.setup_type}"`,
      p.current_price,
      `"${p.entry_zone}"`,
      p.stop_loss,
      p.target_1,
      p.target_2,
      p.risk_reward,
      p.holding_period_days,
      p.signal_score
    ]);
    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `BharatStock_Swing_Picks_${new Date().toISOString().slice(0,10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-8 pb-16">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 dark:text-white flex items-center gap-2">
            <span>💎 Top Picks for Short-Term Profit Booking</span>
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Systematic swing setups (1-15 day horizon) across the liquid Nifty 500 universe with ATR stop-loss and staged profit plans.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowBacktestModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100 transition"
          >
            <BarChart2 className="w-3.5 h-3.5" />
            <span>2Y Backtest Evidence</span>
          </button>

          <button
            onClick={exportCSV}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 transition"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export CSV</span>
          </button>

          <button
            onClick={loadSwingData}
            disabled={loading}
            className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Watchlist Profit-Booking Alerts Bar */}
      {alerts.length > 0 && (
        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-900 dark:text-amber-200 space-y-2">
          <div className="flex items-center gap-2 font-bold text-xs">
            <ShieldAlert className="w-4 h-4 text-amber-500" />
            <span>Watchlist Profit-Booking Alerts ({alerts.length})</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {alerts.map((a, i) => (
              <div key={i} className="p-2 rounded bg-white/70 dark:bg-slate-900/70 text-xs flex items-center justify-between">
                <span>{a.message}</span>
                <button
                  onClick={() => onSelectStock(a.symbol)}
                  className="px-2 py-0.5 rounded bg-indigo-600 text-white text-[10px] font-bold"
                >
                  View
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filters Bar */}
      <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-wrap items-center gap-4 text-xs">
        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-indigo-500" />
          <span className="font-bold text-slate-700 dark:text-slate-300">Setup Strategy:</span>
          <select
            value={setupFilter}
            onChange={(e) => setSetupFilter(e.target.value)}
            className="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2.5 py-1 text-xs font-medium text-slate-800 dark:text-slate-200"
          >
            <option value="all">All 6 Setups</option>
            <option value="Volume Breakout">Volume Breakout</option>
            <option value="Pullback to 20/50 EMA">Pullback to 20/50 EMA</option>
            <option value="RSI Oversold Reversal">RSI Oversold Reversal</option>
            <option value="MACD Trend Crossover">MACD Trend Crossover</option>
            <option value="Bollinger Squeeze Breakout">Bollinger Squeeze Breakout</option>
            <option value="Support Level Bounce">Support Level Bounce</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <span className="font-bold text-slate-700 dark:text-slate-300">Macro Filter:</span>
          <select
            value={regime}
            onChange={(e) => setRegime(e.target.value)}
            className="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2.5 py-1 text-xs font-medium text-slate-800 dark:text-slate-200"
          >
            <option value="Risk-On">Risk-On (Standard R:R &gt;= 1.5)</option>
            <option value="Risk-Off">Risk-Off (Strict Filter Score &gt;= 75)</option>
          </select>
        </div>

        <span className="ml-auto text-[11px] text-slate-400">
          Showing {filteredPicks.length} high-probability trade setups
        </span>
      </div>

      {/* Picks Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredPicks.map((pick) => (
          <div
            key={pick.id}
            className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm hover:border-indigo-400 dark:hover:border-indigo-600 transition flex flex-col justify-between space-y-4"
          >
            <div>
              {/* Card Header */}
              <div className="flex items-start justify-between">
                <div>
                  <span className="px-2 py-0.5 rounded text-[10px] font-extrabold uppercase bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                    {pick.setup_type}
                  </span>
                  <h3 className="text-base font-bold text-slate-900 dark:text-white mt-2">{pick.company_name}</h3>
                  <span className="text-xs text-slate-500 font-mono">{pick.symbol} • {pick.sector}</span>
                </div>
                <div className="text-right">
                  <span className="text-xs text-slate-400 block font-medium">Signal Score</span>
                  <span className="text-base font-black text-indigo-600 dark:text-indigo-400">
                    {pick.signal_score}/100
                  </span>
                </div>
              </div>

              {/* Price & Entry Zone */}
              <div className="mt-4 p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800 grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-[10px] text-slate-400 block">Current CMP</span>
                  <span className="text-sm font-black text-slate-900 dark:text-white">{formatINR(pick.current_price)}</span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 block">Entry Zone</span>
                  <span className="text-xs font-bold text-indigo-600 dark:text-indigo-400">{pick.entry_zone}</span>
                </div>
              </div>

              {/* Targets & Stop Loss Matrix */}
              <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
                <div className="p-2 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-100 dark:border-rose-900">
                  <span className="text-[9px] font-bold text-rose-600 uppercase block">Stop-Loss (ATR)</span>
                  <span className="font-bold text-slate-900 dark:text-white">{formatINR(pick.stop_loss)}</span>
                  <span className="text-[9px] text-rose-500 block">{pick.stop_loss_pct}%</span>
                </div>
                <div className="p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-100 dark:border-emerald-900">
                  <span className="text-[9px] font-bold text-emerald-600 uppercase block">Target 1 (50%)</span>
                  <span className="font-bold text-slate-900 dark:text-white">{formatINR(pick.target_1)}</span>
                  <span className="text-[9px] text-emerald-500 block">+{pick.target_1_pct}%</span>
                </div>
                <div className="p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-100 dark:border-emerald-900">
                  <span className="text-[9px] font-bold text-emerald-600 uppercase block">Target 2 (Runner)</span>
                  <span className="font-bold text-slate-900 dark:text-white">{formatINR(pick.target_2)}</span>
                  <span className="text-[9px] text-emerald-500 block">+{pick.target_2_pct}%</span>
                </div>
              </div>

              {/* R:R and Holding Period */}
              <div className="mt-3 flex items-center justify-between text-[11px] text-slate-500">
                <span className="font-semibold text-slate-700 dark:text-slate-300">
                  Risk/Reward: <strong className="text-indigo-600 font-bold">{pick.risk_reward}:1</strong>
                </span>
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3 text-slate-400" /> Horizon: ~{pick.holding_period_days} Days
                </span>
              </div>

              {/* Why this pick */}
              <p className="mt-3 text-xs text-slate-600 dark:text-slate-400 line-clamp-2 leading-relaxed">
                {pick.why_pick}
              </p>
            </div>

            {/* Card Action Buttons */}
            <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center gap-2">
              <button
                onClick={() => setSelectedPlan(pick)}
                className="flex-1 py-2 text-center text-xs font-semibold rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 transition"
              >
                Profit-Booking Plan
              </button>
              <button
                onClick={() => onSelectStock(pick.symbol)}
                className="flex-1 py-2 text-center text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white transition flex items-center justify-center gap-1"
              >
                Deep-Dive <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Staged Profit-Booking Plan Modal */}
      {selectedPlan && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 rounded-2xl max-w-lg w-full p-6 border border-slate-200 dark:border-slate-800 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900 dark:text-white">
                Staged Profit-Booking Execution Plan
              </h3>
              <button onClick={() => setSelectedPlan(null)} className="text-slate-400 hover:text-slate-600">✕</button>
            </div>

            <div className="p-3 rounded-xl bg-indigo-50 dark:bg-indigo-950/50 text-indigo-900 dark:text-indigo-200 text-xs">
              <span className="font-bold">{selectedPlan.company_name} ({selectedPlan.symbol})</span>
              <p className="mt-0.5">{selectedPlan.setup_type} Setup • Risk/Reward {selectedPlan.risk_reward}:1</p>
            </div>

            <div className="space-y-3 text-xs text-slate-700 dark:text-slate-300">
              <div className="flex items-start gap-2">
                <CheckCircle className="w-4 h-4 text-emerald-500 flex-shrink-0 mt-0.5" />
                <div>
                  <strong>Step 1 (Entry):</strong> Enter in the zone of <strong>{selectedPlan.entry_zone}</strong>. Set strict Initial Stop-Loss at <strong>{formatINR(selectedPlan.stop_loss)}</strong>.
                </div>
              </div>
              <div className="flex items-start gap-2">
                <CheckCircle className="w-4 h-4 text-emerald-500 flex-shrink-0 mt-0.5" />
                <div>
                  <strong>Step 2 (Target 1 Reached):</strong> When stock reaches <strong>Target 1 ({formatINR(selectedPlan.target_1)})</strong>, book <strong>50% position profits</strong> immediately.
                </div>
              </div>
              <div className="flex items-start gap-2">
                <CheckCircle className="w-4 h-4 text-indigo-500 flex-shrink-0 mt-0.5" />
                <div>
                  <strong>Step 3 (Risk Elimination):</strong> Move the Stop-Loss of the remaining 50% shares to <strong>Breakeven ({formatINR(selectedPlan.current_price)})</strong> so the trade is 100% risk-free.
                </div>
              </div>
              <div className="flex items-start gap-2">
                <CheckCircle className="w-4 h-4 text-indigo-500 flex-shrink-0 mt-0.5" />
                <div>
                  <strong>Step 4 (Target 2 / Runner):</strong> Hold remaining 50% for <strong>Target 2 ({formatINR(selectedPlan.target_2)})</strong> or trail along the daily 20 EMA.
                </div>
              </div>
            </div>

            <button
              onClick={() => setSelectedPlan(null)}
              className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold"
            >
              Close Plan
            </button>
          </div>
        </div>
      )}

      {/* 2-Year Backtest Evidence Modal */}
      {showBacktestModal && backtest && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 rounded-2xl max-w-2xl w-full p-6 border border-slate-200 dark:border-slate-800 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-white">
                  Empirical 2-Year Historical Backtest Evidence
                </h3>
                <p className="text-xs text-slate-500">{backtest.timeframe} on {backtest.universe}</p>
              </div>
              <button onClick={() => setShowBacktestModal(false)} className="text-slate-400 hover:text-slate-600">✕</button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800 text-slate-500 uppercase text-[10px] font-bold">
                    <th className="p-2.5">Setup Strategy</th>
                    <th className="p-2.5 text-right">Win Rate</th>
                    <th className="p-2.5 text-right">Avg Return</th>
                    <th className="p-2.5 text-right">Profit Factor</th>
                    <th className="p-2.5 text-right">Max DD</th>
                    <th className="p-2.5 text-right">Sample (N)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {backtest.setups?.map((s: any, idx: number) => (
                    <tr key={idx} className="hover:bg-slate-50/50">
                      <td className="p-2.5 font-bold text-slate-900 dark:text-white">{s.setup_name}</td>
                      <td className="p-2.5 text-right font-bold text-emerald-600">{s.win_rate_pct}%</td>
                      <td className="p-2.5 text-right font-semibold text-slate-800 dark:text-slate-200">+{s.avg_return_pct}%</td>
                      <td className="p-2.5 text-right font-bold text-indigo-600">{s.profit_factor}x</td>
                      <td className="p-2.5 text-right text-rose-500">{s.max_drawdown_pct}%</td>
                      <td className="p-2.5 text-right text-slate-500">{s.sample_size}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="text-[11px] text-slate-500 italic">
              *Note: Past backtest performance does not guarantee future results. Backtests include transaction cost & slippage modeling on daily timeframe.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
