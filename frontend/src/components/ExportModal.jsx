import React, { useState } from 'react';
import { fetchFlags } from '../api';
import { FLAG_TYPE_LABELS } from '../labels';

export default function ExportModal({ onClose, flagsSummary, suggestionsSummary }) {
  const [downloading, setDownloading] = useState(false);
  const [exportScope, setExportScope] = useState('all'); // 'all' | 'high_severity'
  const [error, setError] = useState(null);

  const handleExportCSV = async () => {
    try {
      setDownloading(true);
      setError(null);

      // Fetch flags up to 100 items (max allowed page_size is 100)
      const res = await fetchFlags({
        page: 1,
        page_size: 100,
        severity: exportScope === 'high_severity' ? 'high' : 'all'
      });

      const items = res.items || [];
      if (items.length === 0) {
        setError('No audit flags found matching the selected scope. Try running analysis first.');
        setDownloading(false);
        return;
      }

      // Build CSV content
      const headers = [
        'Flag ID',
        'Request ID',
        'Provider',
        'Model',
        'Flag Type',
        'Severity',
        'Est Token Savings',
        'Created At',
        'Details'
      ];

      const csvRows = [headers.join(',')];

      for (const item of items) {
        const flagType = FLAG_TYPE_LABELS[item.flag_type] || item.flag_type;
        const severity = item.severity ? (item.severity.charAt(0).toUpperCase() + item.severity.slice(1)) : 'Normal';
        const details = (item.detail_text || '').replace(/"/g, '""');

        const row = [
          item.id,
          item.request_id,
          `"${item.provider || ''}"`,
          `"${item.model || ''}"`,
          `"${flagType}"`,
          `"${severity}"`,
          item.estimated_token_savings || 0,
          `"${item.created_at || ''}"`,
          `"${details}"`
        ];
        csvRows.push(row.join(','));
      }

      const csvContent = '\uFEFF' + csvRows.join('\r\n');
      const csvBlob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(csvBlob);
      const link = document.createElement('a');
      const timestamp = new Date().toISOString().slice(0, 10);
      link.setAttribute('href', url);
      link.setAttribute('download', `promptlens-audit-report-${timestamp}.csv`);
      document.body.appendChild(link);
      link.click();

      setTimeout(() => {
        if (document.body.contains(link)) {
          document.body.removeChild(link);
        }
        URL.revokeObjectURL(url);
      }, 1000);

      setDownloading(false);
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to export CSV report.');
      setDownloading(false);
    }
  };

  const handlePrintPDF = () => {
    onClose();
    // Allow modal to unmount before triggering print dialog
    setTimeout(() => {
      window.print();
    }, 150);
  };

  const totalFlags = flagsSummary?.total_flags || 0;
  const totalSavings = suggestionsSummary?.total_tokens_saved || 0;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content export-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h3>Export Executive Audit Report</h3>
            <p className="text-muted-sm">Download or print verified prompt waste audit reports for presentation.</p>
          </div>
          <button type="button" className="btn-close" onClick={onClose}>×</button>
        </div>

        <div className="export-modal-body">
          {/* Quick Summary Highlights */}
          <div className="export-stat-strip">
            <div className="export-stat-card">
              <span className="export-stat-label">Total Flags</span>
              <strong className="export-stat-value">{totalFlags}</strong>
            </div>
            <div className="export-stat-card">
              <span className="export-stat-label">Total Tokens Saved</span>
              <strong className="export-stat-value text-success">{totalSavings.toLocaleString()}</strong>
            </div>
          </div>

          <div className="export-options-group">
            <label className="export-label">Report Scope:</label>
            <div className="export-scope-radios">
              <label>
                <input 
                  type="radio" 
                  name="scope" 
                  value="all" 
                  checked={exportScope === 'all'} 
                  onChange={() => setExportScope('all')} 
                />
                All Audited Flags ({totalFlags})
              </label>
              <label>
                <input 
                  type="radio" 
                  name="scope" 
                  value="high_severity" 
                  checked={exportScope === 'high_severity'} 
                  onChange={() => setExportScope('high_severity')} 
                />
                High Severity Waste Only
              </label>
            </div>
          </div>

          {error && <div className="banner banner-error">{error}</div>}

          <div className="export-actions-grid">
            <div className="export-action-card">
              <div className="export-action-icon">📊</div>
              <h4>Export Spreadsheet (CSV)</h4>
              <p>Raw tabular export including token counts, flag types, and savings for Excel or Google Sheets.</p>
              <button 
                type="button" 
                className="btn btn-primary"
                onClick={handleExportCSV}
                disabled={downloading}
              >
                {downloading ? 'Preparing CSV...' : 'Download CSV (.csv)'}
              </button>
            </div>

            <div className="export-action-card">
              <div className="export-action-icon">📄</div>
              <h4>Executive Report (PDF / Print)</h4>
              <p>Clean executive presentation format with metrics, summaries, and print stylesheet.</p>
              <button 
                type="button" 
                className="btn btn-secondary"
                onClick={handlePrintPDF}
              >
                Print / Save as PDF
              </button>
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
