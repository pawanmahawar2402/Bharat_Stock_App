const API_BASE = '/api';

export async function fetchJson(endpoint: string, options: RequestInit = {}) {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });
    if (!res.ok) {
      throw new Error(`API error ${res.status}: ${res.statusText}`);
    }
    return await res.json();
  } catch (err) {
    console.error(`Fetch failed for ${endpoint}:`, err);
    throw err;
  }
}

export const api = {
  // Tab 1: Macro
  getMacroOverview: () => fetchJson('/macro/overview'),
  getSectorHeatmap: () => fetchJson('/macro/sectors'),
  getRegime: () => fetchJson('/macro/regime'),

  // Tab 2: Market Pulse
  getCorporateActions: (params: { action_type?: string; market_cap?: string; symbol?: string } = {}) => {
    const q = new URLSearchParams();
    if (params.action_type) q.append('action_type', params.action_type);
    if (params.market_cap) q.append('market_cap', params.market_cap);
    if (params.symbol) q.append('symbol', params.symbol);
    return fetchJson(`/market-pulse/actions?${q.toString()}`);
  },
  getQuarterlyResults: () => fetchJson('/market-pulse/results'),
  getBulkDeals: () => fetchJson('/market-pulse/deals'),
  getMarketActivity: () => fetchJson('/market-pulse/activity'),

  // Page 2: Daily Two Picks (triangulated fundamental + technical + macro)
  getDailyPicks: () => fetchJson('/daily-picks/today'),
  refreshDailyPicks: () => fetchJson('/daily-picks/refresh', { method: 'POST' }),

  // Page 1 add-on: stock-specific macro sentiment
  getStockMacroSentiment: (symbol: string) => fetchJson(`/macro/stock-sentiment/${encodeURIComponent(symbol)}`),

  // Stock deep-dive research note (valuation method, technicals, macro, verdict)
  getResearchNote: (symbol: string) => fetchJson(`/stock-analysis/research/${encodeURIComponent(symbol)}`),

  // Tab 3: Swing Scanner (legacy)
  getSwingPicks: (regime: string = 'Risk-On') => fetchJson(`/swing-scanner/picks?regime=${encodeURIComponent(regime)}`),
  getBacktestStats: () => fetchJson('/swing-scanner/backtest'),
  getWatchlistAlerts: (symbols: string[]) => fetchJson('/swing-scanner/watchlist-alerts', {
    method: 'POST',
    body: JSON.stringify({ symbols })
  }),

  // Tab 4: Stock Analysis
  searchStocks: (query: string) => fetchJson(`/stock-analysis/search?q=${encodeURIComponent(query)}`),
  getStockOverview: (symbol: string) => fetchJson(`/stock-analysis/overview/${encodeURIComponent(symbol)}`),
  getStockValuation: (symbol: string) => fetchJson(`/stock-analysis/valuation/${encodeURIComponent(symbol)}`),
  recalculateDCF: (payload: any) => fetchJson('/stock-analysis/dcf-recalculate', {
    method: 'POST',
    body: JSON.stringify(payload)
  }),
  getStockTechnicals: (symbol: string, period: string = '1y', interval: string = '1d') =>
    fetchJson(`/stock-analysis/technical/${encodeURIComponent(symbol)}?period=${period}&interval=${interval}`),
  getStockFinancials: (symbol: string) => fetchJson(`/stock-analysis/financials/${encodeURIComponent(symbol)}`),
  getStockPeers: (symbol: string) => fetchJson(`/stock-analysis/peers/${encodeURIComponent(symbol)}`),
};
