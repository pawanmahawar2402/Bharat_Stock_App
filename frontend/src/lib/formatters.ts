export function formatINR(val: number | string | null | undefined, showCr: boolean = true): string {
  if (val === null || val === undefined || val === 'N/A') return 'N/A';
  const num = typeof val === 'string' ? parseFloat(val) : val;
  if (isNaN(num)) return 'N/A';

  if (showCr && Math.abs(num) >= 1e7) {
    const cr = num / 1e7;
    if (Math.abs(cr) >= 100000) {
      return `₹ ${(cr / 100000).toFixed(2)} Lakh Cr`;
    }
    return `₹ ${cr.toLocaleString('en-IN', { maximumFractionDigits: 2 })} Cr`;
  }

  return `₹ ${num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatNumber(val: number | string | null | undefined): string {
  if (val === null || val === undefined || val === 'N/A') return 'N/A';
  const num = typeof val === 'string' ? parseFloat(val) : val;
  if (isNaN(num)) return 'N/A';
  return num.toLocaleString('en-IN', { maximumFractionDigits: 2 });
}

export function formatPct(val: number | string | null | undefined): string {
  if (val === null || val === undefined || val === 'N/A') return 'N/A';
  const num = typeof val === 'string' ? parseFloat(val) : val;
  if (isNaN(num)) return 'N/A';
  const sign = num > 0 ? '+' : '';
  return `${sign}${num.toFixed(2)}%`;
}

export function getPctColor(val: number | string | null | undefined): string {
  if (val === null || val === undefined || val === 'N/A') return 'text-slate-400';
  const num = typeof val === 'string' ? parseFloat(val) : val;
  if (isNaN(num)) return 'text-slate-400';
  if (num > 0) return 'text-emerald-600 dark:text-emerald-400';
  if (num < 0) return 'text-rose-600 dark:text-rose-400';
  return 'text-slate-500 dark:text-slate-400';
}
