'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { api } from '@/lib/api';
import { formatNumber } from '@/lib/formatters';

type Row = {
  key: string;
  company: string;
  symbol: string;
  sector: string;
  label: string;
  entry: string;
  stop: number | null;
  target: number | null;
};

export default function DailyPicksTab() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [running, setRunning] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await api.getDailyPicks();
      setData(res);
      setRunning(res?.status?.state === 'running');
      setError(null);
      return res;
    } catch {
      setError('Could not reach the picks service. Check that the backend is running.');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const startPolling = () => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      const res = await load();
      if (res && res.status?.state !== 'running') stopPolling();
    }, 8000);
  };

  const refresh = async () => {
    try {
      await api.refreshDailyPicks();
      setRunning(true);
      startPolling();
    } catch {
      setError('Could not start a new run.');
    }
  };

  useEffect(() => {
    load().then((res) => {
      if (res?.status?.state === 'running') startPolling();
    });
    return stopPolling;
  }, [load]);

  const result = data?.result;
  const rows: any[] = result?.top_ten ?? [];

  return (
    <div className="space-y-6 pb-12">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-100">Top 10 Stock Picks</h2>
          {result && (
            <p className="text-sm text-slate-500 mt-1">
              As of {new Date(result.generated_at).toLocaleString('en-IN')}
            </p>
          )}
        </div>
        <button
          onClick={refresh}
          disabled={running}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white self-start sm:self-auto"
        >
          <RefreshCw className={`w-4 h-4 ${running ? 'animate-spin' : ''}`} />
          {running ? 'Updating…' : 'Update picks'}
        </button>
      </div>

      {running && (
        <div className="p-4 rounded-xl bg-indigo-50 dark:bg-indigo-950/30 text-xs text-indigo-800 dark:text-indigo-200">
          Updating picks. This takes a few minutes; the list refreshes automatically.
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/30 text-xs text-rose-800 dark:text-rose-200">{error}</div>
      )}

      {loading && <div className="text-sm text-slate-500">Loading picks…</div>}

      {!loading && !result && !running && (
        <div className="p-8 rounded-2xl border border-dashed border-slate-300 dark:border-slate-700 text-center text-sm text-slate-500">
          No picks yet. Click “Update picks” to generate today’s list.
        </div>
      )}

      {result && rows.length > 0 && (
        <div className="overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-950 text-xs text-slate-500 uppercase tracking-wider">
              <tr>
                <th className="p-3 text-left">#</th>
                <th className="p-3 text-left">Company</th>
                <th className="p-3 text-left">Sector</th>
                <th className="p-3 text-left">Conviction</th>
                <th className="p-3 text-right">Score</th>
                <th className="p-3 text-left">Signal</th>
                <th className="p-3 text-right">Entry</th>
                <th className="p-3 text-right">Stop loss</th>
                <th className="p-3 text-right">Target</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r: any) => (
                <tr key={r.symbol} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="p-3 font-bold text-slate-500">{r.rank}</td>
                  <td className="p-3">
                    <div className="font-semibold text-slate-900 dark:text-slate-100">{r.company_name}</div>
                    <div className="text-[11px] text-slate-500">{r.symbol}</div>
                  </td>
                  <td className="p-3 text-xs text-slate-600 dark:text-slate-400">{r.sector}</td>
                  <td className="p-3 text-xs font-semibold">{r.conviction}</td>
                  <td className="p-3 text-right text-xs">{formatNumber(r.composite_score)}</td>
                  <td className="p-3 text-xs">{r.signal || '—'}</td>
                  <td className="p-3 text-right text-xs">{r.entry_zone ?? '—'}</td>
                  <td className="p-3 text-right text-xs text-rose-600">{r.stop_loss != null ? `₹${formatNumber(r.stop_loss)}` : '—'}</td>
                  <td className="p-3 text-right text-xs text-emerald-600">{r.target_1 != null ? `₹${formatNumber(r.target_1)}` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {result && rows.length === 0 && (
        <div className="p-6 rounded-2xl border border-dashed border-slate-300 dark:border-slate-700 text-center text-sm text-slate-500">
          No picks yet. Click “Update picks” to generate the list.
        </div>
      )}

      {result?.disclaimer && <p className="text-[11px] text-slate-500">{result.disclaimer}</p>}
    </div>
  );
}
