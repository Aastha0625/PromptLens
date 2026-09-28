import React from 'react';
import { formatDate, formatCost, formatLatency, formatNumber } from '../format';

export default function RequestsTable({ 
  data, 
  loading, 
  page, 
  setPage, 
  statusFilter, 
  setStatusFilter,
  onRowClick
}) {
  if (loading) return <div className="loading state-box">Loading table...</div>;
  if (!data || !data.items || data.items.length === 0) return <div className="empty state-box">No requests found.</div>;

  const totalPages = Math.ceil(data.total / data.page_size) || 1;

  return (
    <div className="table-container card">
      <div className="table-header">
        <h3>Requests</h3>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          <option value="all">All Status</option>
          <option value="ok">OK (2xx)</option>
          <option value="error">Error (4xx+)</option>
        </select>
      </div>

      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Provider/Model</th>
              <th>Prompt Preview</th>
              <th>Tokens</th>
              <th>Latency</th>
              <th>Cost</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map(req => (
              <tr key={req.id} onClick={() => onRowClick(req.id)} className="clickable">
                <td>{formatDate(req.created_at)}</td>
                <td>
                  <div className="model-name">
                    {req.provider} <br/><small>{req.model}</small>
                    {req.is_demo && <span className="tag demo">demo</span>}
                  </div>
                </td>
                <td className="preview">
                  {req.prompt_preview ? req.prompt_preview.slice(0, 60) + '...' : '-'}
                </td>
                <td>{formatNumber(req.total_tokens)}</td>
                <td>{formatLatency(req.latency_ms)}</td>
                <td title={req.cost_usd == null ? "Pricing unknown" : ""}>
                  {formatCost(req.cost_usd)}
                </td>
                <td>
                  <span className={`tag status ${req.status_code >= 200 && req.status_code < 300 ? 'ok' : 'error'}`}>
                    {req.status_code}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="pagination">
        <button disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</button>
        <span>Page {page} of {totalPages}</span>
        <button disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next</button>
      </div>
    </div>
  );
}
