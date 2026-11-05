'use client';

import React, { useState } from 'react';

type Row = { label: string; items: string[]; unit?: 'cr' | 'eps' };

const SECTIONS: { title: string; rows: Row[]; cashFlowFallback?: boolean }[] = [
  {
    title: 'Income statement',
    rows: [
      { label: 'Total revenue', items: ['Total Revenue', 'Operating Revenue'] },
      { label: 'EBITDA', items: ['EBITDA', 'Normalized EBITDA'] },
      { label: 'EBIT (operating profit)', items: ['EBIT', 'Operating Income'] },
      { label: 'Interest expense', items: ['Interest Expense'] },
      { label: 'Net income', items: ['Net Income Common Stockholders', 'Net Income'] },
      { label: 'Diluted EPS (₹)', items: ['Diluted EPS', 'Basic EPS'], unit: 'eps' },
    ],
  },
  {
    title: 'Balance sheet',
    rows: [
      { label: 'Total assets', items: ['Total Assets'] },
      { label: 'Total liabilities', items: ['Total Liabilities Net Minority Interest'] },
      { label: "Shareholders' equity", items: ['Stockholders Equity', 'Common Stock Equity'] },
      { label: 'Total debt', items: ['Total Debt'] },
      { label: 'Cash & short-term investments', items: ['Cash Cash Equivalents And Short Term Investments', 'Cash And Cash Equivalents'] },
      { label: 'Current assets', items: ['Current Assets'] },
      { label: 'Current liabilities', items: ['Current Liabilities'] },
    ],
  },
  {
    title: 'Cash flow',
    rows: [
      { label: 'Operating cash flow', items: ['Operating Cash Flow', 'Cash Flow From Continuing Operating Activities'] },
      { label: 'Capital expenditure', items: ['Capital Expenditure'] },
      { label: 'Free cash flow', items: ['Free Cash Flow'] },
      { label: 'Investing cash flow', items: ['Investing Cash Flow', 'Cash Flow From Continuing Investing Activities'] },
      { label: 'Financing cash flow', items: ['Financing Cash Flow', 'Cash Flow From Continuing Financing Activities'] },
      { label: 'Dividends paid', items: ['Cash Dividends Paid', 'Common Stock Dividend Paid'] },
    ],
  },
];

const STATEMENT_KEY: Record<string, string> = {
  'Income statement': 'income_statement',
  'Balance sheet': 'balance_sheet',
  'Cash flow': 'cash_flow',
};

function pick(period: Record<string, number> | undefined, items: string[]): number | null {
  if (!period) return null;
  for (const k of items) {
    const v = period[k];
    if (typeof v === 'number' && !Number.isNaN(v)) return v;
  }
  return null;
}

function currencyNote(c: any): string {
  if (!c) return 'Amounts in ₹ Crore';
  if (c.converted && c.reported_currency) {
    return `Amounts in ₹ Crore • reported in ${c.reported_currency}, converted at ${c.fx_rate} ${c.display_currency} per ${c.reported_currency}`;
  }
  return `Amounts in ₹ Crore • reported in ${c.reported_currency ?? 'INR'}`;
}

function fmt(v: number | null, unit?: 'cr' | 'eps'): string {
  if (v === null) return '—';
  if (unit === 'eps') return v.toLocaleString('en-IN', { maximumFractionDigits: 2 });
  return (v / 1e7).toLocaleString('en-IN', { maximumFractionDigits: 0 });
}

export default function FinancialStatements({ data }: { data: any }) {
  const [frequency, setFrequency] = useState<'annual' | 'quarterly'>('annual');
  const suffix = frequency === 'annual' ? '' : '_quarterly';
  const maxCols = frequency === 'annual' ? 4 : 6;

  const periodsFor = (statement: string): string[] => {
    const block = data?.[`${statement}${suffix}`] || {};
    return Object.keys(block).sort().reverse().slice(0, maxCols);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">
            Financial statements (₹ Crore unless stated)
          </h3>
          <p className="text-xs text-slate-500 mt-1">Reported figures from Yahoo Finance annual and quarterly filings.</p>
        </div>
        <div className="inline-flex rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden text-xs font-semibold">
          {(['annual', 'quarterly'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFrequency(f)}
              className={`px-3 py-1.5 capitalize ${frequency === f ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300'}`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {SECTIONS.map((section) => {
        const statement = STATEMENT_KEY[section.title];
        const periods = periodsFor(statement);
        const block = data?.[`${statement}${suffix}`] || {};
        return (
          <div key={section.title} className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm overflow-hidden">
            <div className="px-4 py-3 bg-slate-50 dark:bg-slate-950 flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">{section.title}</span>
              <span className="text-[11px] text-slate-500">{currencyNote(data?.currency)}</span>
            </div>
            {periods.length === 0 ? (
              <div className="p-4 text-xs text-slate-500">No {frequency} data reported for this statement.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-500">
                      <th className="p-2.5 text-left font-semibold">Line item</th>
                      {periods.map((p) => (
                        <th key={p} className="p-2.5 text-right font-semibold whitespace-nowrap">{p}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {section.rows.map((row) => {
                      const values = periods.map((p) => pick(block[p], row.items));
                      if (values.every((v) => v === null)) return null;
                      return (
                        <tr key={row.label} className="border-b border-slate-100 dark:border-slate-800/60 last:border-0">
                          <td className="p-2.5 font-medium text-slate-800 dark:text-slate-200">{row.label}</td>
                          {values.map((v, i) => (
                            <td
                              key={i}
                              className={`p-2.5 text-right font-semibold tabular-nums ${v !== null && v < 0 ? 'text-rose-600 dark:text-rose-400' : 'text-slate-900 dark:text-slate-100'}`}
                            >
                              {fmt(v, row.unit)}
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
