import React from 'react';
import { FLAG_TYPE_LABELS, SEVERITY_COLORS } from '../labels';
import { formatNumber } from '../format';

function extractWastedTokensFromFlag(flag) {
  if (!flag || !flag.detail) return null;
  let detail = flag.detail;
  if (typeof detail === 'string') {
    try {
      detail = JSON.parse(detail);
    } catch {
      return null;
    }
  }
  return detail.total_estimated_wasted_tokens ?? detail.estimated_wasted_tokens ?? null;
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
    setFilters((prev) => ({ ...prev, [key]: val }));
    setPage(1);
  };

  const items = data?.items || [];
  const total = data?.total || 0;
  const pageSize = data?.page_size || 20;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="card table-card">
      {/* Sleek Filter Bar */}
      <div className="table-filter-bar">
        <div className="filter-group">
          <label htmlFor="filter-flag-type">Issue Type:</label>
          <select
            id="filter-flag-type"
            value={filters.flag_type}
            onChange={(e) => handleFilterChange('flag_type', e.target.value)}
          >
            <option value="all">All Issues</option>
            <option value="redundant_sentences">Duplicate Sentences</option>
            <option value="repeated_content">Repeated Bloat</option>
            <option value="verbose_for_template">Template Outliers</option>
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="filter-severity">Severity:</label>
          <select
            id="filter-severity"
            value={filters.severity}
            onChange={(e) => handleFilterChange('severity', e.target.value)}
          >
            <option value="all">All Severities</option>
            <option value="high">High Waste</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="filter-provider">Provider:</label>
          <select
            id="filter-provider"
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
      {loading && <div className="state-box">Loading intercepted prompts...</div>}

      {error && (
        <div className="state-box error-box">
          <p>Failed to load audit logs: {error}</p>
          {onRetry && (
            <button type="button" onClick={onRetry}>
              Retry
            </button>
          )}
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && items.length === 0 && (
        <div className="state-box empty-box">
          <div style={{ fontSize: '24px', marginBottom: '8px' }}>✨</div>
          <p style={{ fontWeight: 600, margin: '0 0 4px 0' }}>No Inefficiencies Detected</p>
          <p className="text-muted-sm" style={{ margin: 0 }}>
            Incoming requests routed through <code>http://localhost:8000/proxy/...</code> are lean and clean.
          </p>
        </div>
      )}

      {/* Modern Developer Table */}
      {!loading && !error && items.length > 0 && (
        <>
          <div className="table-responsive">
            <table className="modern-audit-table">
              <thead>
                <tr>
                  <th style={{ width: '90px' }}>Severity</th>
                  <th style={{ width: '180px' }}>Detected Issue</th>
                  <th style={{ width: '140px' }}>Target API</th>
                  <th>Intercepted Prompt Snippet</th>
                  <th style={{ width: '120px', textAlign: 'right' }}>Est. Waste</th>
                  <th style={{ width: '110px', textAlign: 'center' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {items.map((flag) => {
                  const sev = SEVERITY_COLORS[flag.severity] || SEVERITY_COLORS.low;
                  const wastedTokens = extractWastedTokensFromFlag(flag);

                  return (
                    <tr
                      key={flag.id}
                      onClick={() => onRowClick(flag)}
                      className="clickable-row"
                    >
                      <td>
                        <span
                          className="badge"
                          style={{
                            backgroundColor: sev.bg,
                            color: sev.text,
                            borderColor: sev.border,
                          }}
                        >
                          {flag.severity.toUpperCase()}
                        </span>
                      </td>
                      <td className="font-medium">
                        {FLAG_TYPE_LABELS[flag.flag_type] || flag.flag_type}
                      </td>
                      <td>
                        <span className="api-chip">
                          {flag.provider} / {flag.model}
                        </span>
                      </td>
                      <td className="text-muted text-preview">
                        {flag.prompt_preview || '—'}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        {wastedTokens != null ? (
                          <span className="waste-pill">
                            -{formatNumber(wastedTokens)} tok
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <span className="view-fix-link">
                          View Fix →
                        </span>
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
              Page {page} of {totalPages} ({total} total flagged calls)
            </span>
            <div className="pagination-buttons">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </button>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
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
