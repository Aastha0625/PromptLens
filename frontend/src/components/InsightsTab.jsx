import React, { useState, useEffect, useCallback, useRef } from 'react';
import InsightsSummary from './InsightsSummary';
import FlagsTable from './FlagsTable';
import FlagDetail from './FlagDetail';
import ExportModal from './ExportModal';
import { 
  fetchFlags, 
  fetchFlagsSummary, 
  fetchSuggestionsSummary, 
  triggerAnalysis 
} from '../api';

export default function InsightsTab() {
  // Summary Cards State
  const [flagsSummary, setFlagsSummary] = useState(null);
  const [suggestionsSummary, setSuggestionsSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(true);

  // Table State
  const [flagsData, setFlagsData] = useState(null);
  const [tableLoading, setTableLoading] = useState(true);
  const [tableError, setTableError] = useState(null);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({
    flag_type: 'all',
    severity: 'all',
    provider: 'all',
  });

  // Modal State
  const [selectedFlag, setSelectedFlag] = useState(null);
  const [showExportModal, setShowExportModal] = useState(false);

  // Live Auto-Refresh State (polls every 6s so live finAI calls show up automatically)
  const [autoRefresh, setAutoRefresh] = useState(true);
  const autoRefreshTimerRef = useRef(null);

  // Run Analysis State
  const [analysisState, setAnalysisState] = useState({
    running: false,
    resultText: null,
    semanticCheckSkipped: false,
    error: null,
  });

  // Fetch summaries
  const loadSummaries = useCallback((isBackground = false) => {
    const controller = new AbortController();
    if (!isBackground) setSummaryLoading(true);

    Promise.all([
      fetchFlagsSummary(controller.signal),
      fetchSuggestionsSummary(controller.signal),
    ])
      .then(([fSum, sSum]) => {
        setFlagsSummary(fSum);
        setSuggestionsSummary(sSum);
        setSummaryLoading(false);
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        setSummaryLoading(false);
      });

    return controller;
  }, []);

  // Fetch table data
  const loadFlags = useCallback((isBackground = false) => {
    const controller = new AbortController();
    if (!isBackground) setTableLoading(true);
    setTableError(null);

    fetchFlags({
      page,
      page_size: 20,
      flag_type: filters.flag_type,
      severity: filters.severity,
      provider: filters.provider,
    }, controller.signal)
      .then((res) => {
        setFlagsData(res);
        setTableLoading(false);
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        setTableError(err.message);
        setTableLoading(false);
      });

    return controller;
  }, [page, filters]);

  // Initial load
  useEffect(() => {
    const c1 = loadSummaries();
    const c2 = loadFlags();
    return () => {
      c1.abort();
      c2.abort();
    };
  }, [loadSummaries, loadFlags]);

  // Live auto-refresh polling every 6 seconds
  useEffect(() => {
    if (!autoRefresh) return;
    autoRefreshTimerRef.current = setInterval(() => {
      loadSummaries(true);
      loadFlags(true);
    }, 6000);

    return () => {
      if (autoRefreshTimerRef.current) clearInterval(autoRefreshTimerRef.current);
    };
  }, [autoRefresh, loadSummaries, loadFlags]);

  // Handle Run Analysis click (POST is not aborted)
  const handleRunAnalysis = async () => {
    setAnalysisState({
      running: true,
      resultText: null,
      semanticCheckSkipped: false,
      error: null,
    });

    try {
      const res = await triggerAnalysis({ reanalyze: true });
      const durationSec = (res.duration_ms / 1000).toFixed(2);
      const resultMsg = `Analyzed ${res.requests_analyzed} requests, found ${res.flags_created} flags in ${durationSec}s.`;

      setAnalysisState({
        running: false,
        resultText: resultMsg,
        semanticCheckSkipped: res.semantic_check_ran === false,
        error: null,
      });

      // Refetch summaries and flags table
      loadSummaries();
      loadFlags();
    } catch (err) {
      setAnalysisState({
        running: false,
        resultText: null,
        semanticCheckSkipped: false,
        error: err.message || "Analysis failed.",
      });
    }
  };

  const handleSuggestionGenerated = () => {
    loadSummaries();
    loadFlags();
  };

  return (
    <div className="insights-tab">
      {/* Sleek Live Header */}
      <div className="insights-header-bar">
        <div>
          <h2>Live Interceptor & Prompt Auditor</h2>
          <p className="text-muted-sm">
            Auditing every prompt routed through <code>http://localhost:8000/proxy/...</code> in real time.
          </p>
        </div>

        <div className="insights-header-actions">
          {/* Live Polling Toggle */}
          <button
            type="button"
            className={`btn-live-toggle ${autoRefresh ? 'active' : ''}`}
            onClick={() => setAutoRefresh(!autoRefresh)}
            title="Toggle live auto-refresh every 6 seconds"
          >
            <span className={`live-pulse-dot ${autoRefresh ? 'pulse' : ''}`} />
            {autoRefresh ? 'Live Auto-Audit: ON' : 'Live Auto-Audit: PAUSED'}
          </button>

          <button
            type="button"
            className="btn btn-export-report"
            onClick={() => setShowExportModal(true)}
          >
            Export Report
          </button>

          <button 
            type="button" 
            className="btn btn-run-analysis"
            onClick={handleRunAnalysis}
            disabled={analysisState.running}
            style={{ fontSize: '13px' }}
          >
            {analysisState.running ? 'Scanning...' : 'Re-scan History'}
          </button>
        </div>
      </div>

      {/* Analysis Result or Warning Banners */}
      {analysisState.resultText && (
        <div className="banner banner-success">
          <p>✓ {analysisState.resultText}</p>
        </div>
      )}

      {analysisState.semanticCheckSkipped && (
        <div className="banner banner-warning">
          <p>
            ⚠ Notice: Semantic near-duplicate check was skipped because the embedding model is not loaded. Exact duplicate and template verbosity checks were executed normally.
          </p>
        </div>
      )}

      {analysisState.error && (
        <div className="banner banner-error">
          <p>Error running analysis: {analysisState.error}</p>
        </div>
      )}

      {/* 1. Simplified Summary Cards */}
      <InsightsSummary 
        flagsSummary={flagsSummary} 
        suggestionsSummary={suggestionsSummary} 
        loading={summaryLoading} 
      />

      {/* 2. Modern Flags Table */}
      <FlagsTable 
        data={flagsData} 
        loading={tableLoading} 
        error={tableError} 
        page={page} 
        setPage={setPage} 
        filters={filters} 
        setFilters={setFilters} 
        onRowClick={setSelectedFlag} 
        onRetry={loadFlags} 
      />

      {/* 3. Sleek Flag Detail Drawer / Modal */}
      {selectedFlag && (
        <FlagDetail 
          key={selectedFlag.id}
          flag={selectedFlag} 
          onClose={() => setSelectedFlag(null)} 
          onSuggestionGenerated={handleSuggestionGenerated}
        />
      )}

      {showExportModal && (
        <ExportModal
          filters={filters}
          totalFlags={flagsData?.total ?? flagsSummary?.total_flags ?? 0}
          onClose={() => setShowExportModal(false)}
        />
      )}
    </div>
  );
}
