import React from 'react';
import { FLAG_TYPE_LABELS, SEVERITY_COLORS } from '../labels';
import { formatNumber } from '../format';

function extractWastedTokensFromFlag(flag) {
  if (!flag || !flag.detail) return "-";
  let detail = flag.detail;
  if (typeof detail === "string") {
    try {
      detail = JSON.parse(detail);
    } catch {
      return "-";
    }
  }
  const wasted = detail.total_estimated_wasted_tokens ?? detail.estimated_wasted_tokens;
  return wasted != null ? formatNumber(wasted) : "-";
}

export default function FlagsTable({
  data,
  loading,
  error,
  page,
  setPage,
  filters,
  setFilters,
  onRowClick,
  onRetry,
}) {
  const handleFilterChange = (key, val) => {
    setFilters(prev => ({ ...prev, [key]: val }));
    setPage(1);
  };

  const items = data?.items || [];
  const total = data?.total || 0;
  const pageSize = data?.page_size || 20;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="card table-card">
      {/* Filter Bar for Flags */}
      <div className="table-filter-bar">
        <div className="filter-group">
          <label>Flag Type:</label>
          <select 
            value={filters.flag_type} 
            onChange={(e) => handleFilterChange('flag_type', e.target.value)}
          >
            <option value="all">All Types</option>
            <option value="redundant_sentences">Redundant Sentences</option>
            <option value="repeated_content">Repeated Content</option>
            <option value="verbose_for_template">Verbose Template</option>
          </select>
        </div>

        <div className="filter-group">
          <label>Severity:</label>
          <select 
            value={filters.severity} 
            onChange={(e) => handleFilterChange('severity', e.target.value)}
          >
            <option value="all">All Severities</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>

        <div className="filter-group">
          <label>Provider:</label>
          <select 
            value={filters.provider} 
            onChange={(e) => handleFilterChange('provider', e.target.value)}
          >
            <option value="all">All Providers</option>
            <option value="groq">Groq</option>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="gemini">Gemini</option>
            <option value="ollama">Ollama</option>
          </select>
        </div>
      </div>

      {/* Loading & Error States */}
      {loading && <div className="state-box">Loading flagged prompts...</div>}
      
      {error && (
        <div className="state-box error-box">
          <p>Failed to load flags: {error}</p>
          {onRetry && <button type="button" onClick={onRetry}>Retry</button>}
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && items.length === 0 && (
        <div className="state-box empty-box">
          <p>No flags yet. Click <strong>Run analysis</strong> to scan logged requests for waste.</p>
        </div>
      )}

      {/* Table */}
      {!loading && !error && items.length > 0 && (
        <>
          <div className="table-responsive">
            <table>
              <thead>
                <tr>
                  <th style={{ width: '100px' }}>Severity</th>
                  <th>Flag Type</th>
                  <th>Provider</th>
                  <th>Model</th>
                  <th>Prompt Preview</th>
                  <th style={{ width: '140px', textAlign: 'right' }}>Est. Wasted Tokens</th>
                </tr>
              </thead>
              <tbody>
                {items.map(flag => {
                  const sev = SEVERITY_COLORS[flag.severity] || SEVERITY_COLORS.low;
                  const wastedStr = extractWastedTokensFromFlag(flag);

                  return (
                    <tr 
                      key={flag.id} 
                      onClick={() => onRowClick(flag)}
                      className="clickable-row"
                    >
                      <td>
                        <span 
                          className="badge" 
                          style={{ backgroundColor: sev.bg, color: sev.text, borderColor: sev.border }}
                        >
                          {flag.severity.toUpperCase()}
                        </span>
                      </td>
                      <td className="font-medium">
                        {FLAG_TYPE_LABELS[flag.flag_type] || flag.flag_type}
                      </td>
                      <td>{flag.provider}</td>
                      <td>{flag.model}</td>
                      <td className="text-muted text-preview">
                        {flag.prompt_preview || "—"}
                      </td>
                      <td style={{ textAlign: 'right', fontWeight: 500 }}>
                        {wastedStr}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls */}
          <div className="pagination">
            <span>
              Page {page} of {totalPages} ({total} total flags)
            </span>
            <div className="pagination-buttons">
              <button 
                type="button"
                disabled={page <= 1} 
                onClick={() => setPage(p => Math.max(1, p - 1))}
              >
                Previous
              </button>
              <button 
                type="button"
                disabled={page >= totalPages} 
                onClick={() => setPage(p => p + 1)}
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
