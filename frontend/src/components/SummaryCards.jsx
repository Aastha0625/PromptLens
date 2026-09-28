import React from 'react';
import { formatNumber, formatCost, formatLatency } from '../format';

export default function SummaryCards({ data, loading }) {
  if (loading) return <div className="loading state-box">Loading summary...</div>;
  if (!data) return null;

  // Guard against division by zero
  const errorRate = data.total_requests > 0 
    ? ((data.failed_requests / data.total_requests) * 100).toFixed(1) 
    : 0;

  return (
    <div className="summary-cards">
      <div className="card">
        <h3>Total Requests</h3>
        <p className="value">{formatNumber(data.total_requests)}</p>
      </div>
      <div className="card">
        <h3>Total Tokens</h3>
        <p className="value">{formatNumber(data.total_tokens)}</p>
        <p className="sub-value">
          In: {formatNumber(data.total_input_tokens)} | Out: {formatNumber(data.total_output_tokens)}
        </p>
      </div>
      <div className="card">
        <h3>Avg Latency</h3>
        <p className="value">{formatLatency(data.avg_latency_ms)}</p>
      </div>
      <div className="card">
        <h3>Error Rate</h3>
        <p className="value">{errorRate}%</p>
      </div>
      <div className="card">
        <h3>Total Cost</h3>
        <p className="value">{formatCost(data.total_cost_usd)}</p>
        {data.unpriced_requests > 0 && (
          <p className="sub-value warning" title="These requests used models not found in pricing.yaml">
            {data.unpriced_requests} requests not priced (unknown model)
          </p>
        )}
      </div>
    </div>
  );
}
