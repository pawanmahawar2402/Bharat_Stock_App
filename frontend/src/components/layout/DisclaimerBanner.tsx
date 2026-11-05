import React from 'react';
import { AlertCircle } from 'lucide-react';

export default function DisclaimerBanner() {
  return (
    <div className="bg-amber-500/10 border-y border-amber-500/20 text-amber-800 dark:text-amber-200 px-4 py-2 text-xs flex items-center justify-between">
      <div className="flex items-center gap-2 max-w-7xl mx-auto w-full">
        <AlertCircle className="w-4 h-4 flex-shrink-0 text-amber-500" />
        <span>
          <strong>SEBI Compliance / Educational Disclaimer:</strong> BharatStock Analyzer is an analytical and educational research tool. It is <strong>not</strong> an investment advisory service or SEBI-registered recommendation. Market data from Yahoo Finance and free public APIs may be delayed or approximate. Short-term swing setups involve capital risk.
        </span>
      </div>
    </div>
  );
}
