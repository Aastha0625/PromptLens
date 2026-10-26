import React from 'react';
import { formatNumber, formatCost } from '../format';

export default function InsightsSummary({ flagsSummary, suggestionsSummary, loading }) {
  if (loading) {
    return (
      <div className="summary-grid">
        {[1, 2, 3, 4, 5, 6].map(i => (
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
  const totalFlags = fSum.total_flags ?? 0;
  const bySev = fSum.by_severity || {};

  const totalWasted = fSum.total_estimated_wasted_tokens ?? 0;

  const totalSuggestions = sSum.total_suggestions ?? 0;
  const usableCount = (sSum.verified_count ?? 0) + (sSum.by_status?.ok ? (sSum.by_status.ok - (sSum.verified_count ?? 0)) : 0);
  
  const ruleSavings = sSum.rule_based_savings ?? 0;
  const llmSavings = sSum.verified_llm_savings ?? 0;

  const toolCost = sSum.optimizer_total_cost_usd ?? 0.0;

  return (
    <div className="summary-grid insights-grid">
      {/* 1. Flagged Requests */}
      <div className="card stat-card">
        <span className="card-label">Flagged Requests</span>
        <div className="card-value">{formatNumber(flaggedCount)}</div>
        <span className="card-subtext">of {formatNumber(analyzedCount)} analyzed</span>
      </div>

      {/* 2. Total Flags with Severity Breakdown */}
      <div className="card stat-card">
        <span className="card-label">Total Flags</span>
        <div className="card-value">{formatNumber(totalFlags)}</div>
        <span className="card-subtext severity-breakdown">
          <span className="sev-item text-danger">H: {bySev.high ?? 0}</span>
          <span className="sev-divider">|</span>
          <span className="sev-item text-warning">M: {bySev.medium ?? 0}</span>
          <span className="sev-divider">|</span>
          <span className="sev-item text-primary">L: {bySev.low ?? 0}</span>
        </span>
      </div>

      {/* 3. Estimated Wasted Tokens */}
      <div className="card stat-card">
        <span className="card-label">Estimated Wasted Tokens</span>
        <div className="card-value text-danger">{formatNumber(totalWasted)}</div>
        <span className="card-subtext">estimated across all flags</span>
      </div>

      {/* 4. Suggestions Generated */}
      <div className="card stat-card">
        <span className="card-label">Suggestions Generated</span>
        <div className="card-value">{formatNumber(totalSuggestions)}</div>
        <span className="card-subtext">{formatNumber(usableCount)} usable suggestions</span>
      </div>

      {/* 5. Estimated Savings (Two separate lines, never combined) */}
      <div className="card stat-card">
        <span className="card-label">Estimated Savings</span>
        <div className="savings-lines">
          <div className="savings-line">
            <span className="line-label">rule-based (not model-checked):</span>
            <strong className="line-val text-success">{formatNumber(ruleSavings)}</strong>
          </div>
          <div className="savings-line">
            <span className="line-label">LLM, verified:</span>
            <strong className="line-val text-success">{formatNumber(llmSavings)}</strong>
          </div>
        </div>
      </div>

      {/* 6. Tool Overhead */}
      <div className="card stat-card">
        <span className="card-label">Tool Overhead</span>
        <div className="card-value">{formatCost(toolCost)}</div>
        <span className="card-subtext">what PromptLens itself spent</span>
      </div>
    </div>
  );
}
