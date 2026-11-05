import React from 'react';
import { X, Trash2, ArrowUpRight } from 'lucide-react';
import { formatINR } from '@/lib/formatters';

interface WatchlistDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  watchlist: string[];
  onRemove: (sym: string) => void;
  onSelectStock: (sym: string) => void;
}

export default function WatchlistDrawer({
  isOpen,
  onClose,
  watchlist,
  onRemove,
  onSelectStock,
}: WatchlistDrawerProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-900/40 backdrop-blur-sm transition-opacity">
      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-white dark:bg-slate-900 shadow-2xl border-l border-slate-200 dark:border-slate-800 flex flex-col">
          {/* Header */}
          <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-slate-900 dark:text-white">My Watchlist</h2>
              <p className="text-xs text-slate-500">Saved Indian equities for quick monitoring</p>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto p-4 space-y-2">
            {watchlist.length === 0 ? (
              <div className="text-center py-12 text-slate-400 dark:text-slate-500">
                <p className="text-sm">Your watchlist is currently empty.</p>
                <p className="text-xs mt-1">Search for any stock in Tab 4 and click "Add to Watchlist".</p>
              </div>
            ) : (
              watchlist.map((sym) => (
                <div
                  key={sym}
                  className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/50 flex items-center justify-between hover:border-indigo-300 dark:hover:border-indigo-700 transition"
                >
                  <div>
                    <span className="font-bold text-sm text-slate-900 dark:text-white">{sym}</span>
                    <p className="text-xs text-slate-500">NSE Listed Equity</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => {
                        onSelectStock(sym);
                        onClose();
                      }}
                      className="px-2.5 py-1 text-xs font-semibold rounded bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100 flex items-center gap-1"
                    >
                      Analyze <ArrowUpRight className="w-3 h-3" />
                    </button>
                    <button
                      onClick={() => onRemove(sym)}
                      className="p-1.5 rounded text-slate-400 hover:text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/40"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
