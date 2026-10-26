import React, { useState, useEffect, useCallback } from 'react';
import InsightsSummary from './InsightsSummary';
import FlagsTable from './FlagsTable';
import FlagDetail from './FlagDetail';
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

  // Run Analysis State
  const [analysisState, setAnalysisState] = useState({
    running: false,
    resultText: null,
    semanticCheckSkipped: false,
    error: null,
  });

  // Fetch summaries
  const loadSummaries = useCallback(() => {
    const controller = new AbortController();
    setSummaryLoading(true);

    Promise.all([
      fetchFlagsSummary(controller.signal),
      fetchSuggestionsSummary(controller.signal),
    ])
      .then(([fSum, sSum]) => {
        setFlagsSummary(fSum);
        setSuggestionsSummary(sSum);
        setSummaryLoading(false);
      })
      .catch(err => {
        if (err.name === 'AbortError') return;
        setSummaryLoading(false);
      });

    return controller;
  }, []);

  // Fetch table data
  const loadFlags = useCallback(() => {
    const controller = new AbortController();
    setTableLoading(true);
    setTableError(null);

    fetchFlags({
      page,
      page_size: 20,
      flag_type: filters.flag_type,
      severity: filters.severity,
      provider: filters.provider,
    }, controller.signal)
      .then(res => {
        setFlagsData(res);
        setTableLoading(false);
      })
      .catch(err => {
        if (err.name === 'AbortError') return;
        setTableError(err.message);
        setTableLoading(false);
      });

    return controller;
  }, [page, filters]);

  // Initial load on mount
  useEffect(() => {
    const c1 = loadSummaries();
    const c2 = loadFlags();
    return () => {
      c1.abort();
      c2.abort();
    };
  }, [loadSummaries, loadFlags]);

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
      {/* Top Header & Run Analysis Action */}
      <div className="insights-header-bar">
        <div>
          <h2>Prompt Insights</h2>
          <p className="text-muted-sm">Audit prompt waste, view flags, and review optimized rewrites.</p>
        </div>

        <div className="run-analysis-container">
          <button 
            type="button" 
            className="btn btn-primary btn-run-analysis"
            onClick={handleRunAnalysis}
            disabled={analysisState.running}
          >
            {analysisState.running ? (
              <span className="spinner-text">
                <span className="spinner-icon" /> Running analysis...
              </span>
            ) : (
              "Run analysis"
            )}
          </button>
          {analysisState.running && (
            <span className="analysis-subnote">
              first run may take a few minutes (model download)
            </span>
          )}
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

      {/* 1. Summary Cards */}
      <InsightsSummary 
        flagsSummary={flagsSummary} 
        suggestionsSummary={suggestionsSummary} 
        loading={summaryLoading} 
      />

      {/* 2. Flags Table */}
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

      {/* 3. Flag Detail Modal (Keyed by flag.id so switching flags never displays stale state) */}
      {selectedFlag && (
        <FlagDetail 
          key={selectedFlag.id}
          flag={selectedFlag} 
          onClose={() => setSelectedFlag(null)} 
          onSuggestionGenerated={handleSuggestionGenerated}
        />
      )}
    </div>
  );
}
