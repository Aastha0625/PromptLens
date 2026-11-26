import React from 'react';
import { formatNumber } from '../format';

export default function InsightsSummary({ flagsSummary, suggestionsSummary, loading }) {
  if (loading) {
    return (
      <div className="summary-grid insights-grid-simple">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="card card-skeleton">
            <div className="skeleton-line" />
            <div className="skeleton-title" />
          </div>
        ))}
      </div>
    );
  }

  const fSum = flagsSummary || {};
  const sSum = suggestionsSummary || {};

  const analyzedCount = fSum.analyzed_requests ?? 0;
  const flaggedCount = fSum.flagged_requests ?? 0;
  const totalWasted = fSum.total_estimated_wasted_tokens ?? 0;
  const totalSavings = sSum.total_estimated_token_savings ?? 0;
  const bySev = fSum.by_severity || {};

  return (
    <div className="summary-grid insights-grid-simple">
      {/* 1. Audited Requests */}
      <div className="card stat-card-simple">
        <span className="card-label">Requests Intercepted & Audited</span>
        <div className="card-value">{formatNumber(analyzedCount)}</div>
        <span className="card-subtext">live calls routed through proxy</span>
      </div>

      {/* 2. Flagged Inefficiencies */}
      <div className="card stat-card-simple">
        <span className="card-label">Prompts with Detected Waste</span>
        <div className="card-value text-danger">{formatNumber(flaggedCount)}</div>
        <span className="card-subtext severity-breakdown">
          <span className="sev-item text-danger">High: {bySev.high ?? 0}</span>
          <span className="sev-divider">•</span>
          <span className="sev-item text-warning">Med: {bySev.medium ?? 0}</span>
          <span className="sev-divider">•</span>
          <span className="sev-item text-primary">Low: {bySev.low ?? 0}</span>
        </span>
      </div>

      {/* 3. Wasted Tokens */}
      <div className="card stat-card-simple">
        <span className="card-label">Wasted Prompt Tokens</span>
        <div className="card-value text-danger">{formatNumber(totalWasted)}</div>
        <span className="card-subtext">lost to fluff, duplicates & loops</span>
      </div>

      {/* 4. Optimized Savings */}
      <div className="card stat-card-simple">
        <span className="card-label">Potential Token Savings</span>
        <div className="card-value text-success">{formatNumber(totalSavings)}</div>
        <span className="card-subtext">recoverable using clean rewrites</span>
      </div>
    </div>
  );
}
