import React, { useState } from 'react';
import { fetchFlags } from '../api';
import { FLAG_TYPE_LABELS } from '../labels';

function escapeCsvCell(value) {
  const str = value == null ? '' : String(value);
  if (str.includes('"') || str.includes(',') || str.includes('\n') || str.includes('\r')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function getWastedTokens(flag) {
  let detail = flag?.detail;
  if (typeof detail === 'string') {
    try {
      detail = JSON.parse(detail);
    } catch {
      detail = null;
    }
  }
  if (!detail) return 0;
  return detail.total_estimated_wasted_tokens ?? detail.estimated_wasted_tokens ?? 0;
}

export default function ExportModal({ filters, totalFlags, onClose }) {
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState(null);

  const handleDownloadCsv = async () => {
    setExporting(true);
    setError(null);

    try {
      const allItems = [];
      let page = 1;
      const pageSize = 100;
      let total = Infinity;

      while (allItems.length < total) {
        const res = await fetchFlags({
          page,
          page_size: pageSize,
          flag_type: filters.flag_type,
          severity: filters.severity,
          provider: filters.provider,
        });
        total = res.total || 0;
        const batch = res.items || [];
        allItems.push(...batch);
        if (batch.length < pageSize) break;
        page += 1;
      }

      const headers = [
        'Flag ID',
        'Request ID',
        'Provider',
        'Model',
        'Flag Type',
        'Severity',
        'Input Tokens',
        'Estimated Wasted Tokens',
        'Prompt Preview',
        'Flagged At',
      ];

      const rows = allItems.map((flag) => [
        flag.id,
        flag.request_id,
        flag.provider,
        flag.model,
        FLAG_TYPE_LABELS[flag.flag_type] || flag.flag_type,
        flag.severity,
        flag.input_tokens ?? '',
        getWastedTokens(flag),
        flag.prompt_preview || '',
        flag.created_at,
      ]);

      const csvContent = [headers, ...rows]
        .map((row) => row.map(escapeCsvCell).join(','))
        .join('\r\n');

      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `promptlens-audit-report-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to export CSV.');
    } finally {
      setExporting(false);
    }
  };

  const handlePrintPdf = () => {
    onClose();
    setTimeout(() => {
      window.print();
    }, 100);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content export-modal" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="close-button" onClick={onClose}>
          &times;
        </button>
        <h3>Export Audit Report</h3>
        <p className="text-muted-sm">
          Export {totalFlags ?? 0} flagged prompt(s) matching your current filters for documentation or project presentations.
        </p>

        {error && (
          <div className="banner banner-error" style={{ marginTop: '12px' }}>
            <p>{error}</p>
          </div>
        )}

        <div className="export-options">
          <div className="export-option-card">
            <div>
              <h4>CSV Spreadsheet</h4>
              <p className="text-muted-sm">
                Downloads all flagged requests, severities, input tokens, and estimated wasted tokens.
              </p>
            </div>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleDownloadCsv}
              disabled={exporting}
            >
              {exporting ? 'Exporting...' : 'Download CSV'}
            </button>
          </div>

          <div className="export-option-card">
            <div>
              <h4>Executive PDF Report</h4>
              <p className="text-muted-sm">
                Opens the browser print dialog formatted with PromptLens&apos;s clean print stylesheet.
              </p>
            </div>
            <button type="button" className="btn" onClick={handlePrintPdf}>
              Print / Save PDF
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
