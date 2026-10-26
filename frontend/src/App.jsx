import React, { useState, useEffect, useCallback } from 'react';
import FilterBar from './components/FilterBar';
import SummaryCards from './components/SummaryCards';
import UsageChart from './components/UsageChart';
import RequestsTable from './components/RequestsTable';
import RequestDetail from './components/RequestDetail';
import InsightsTab from './components/InsightsTab';
import { fetchSummary, fetchTimeline, fetchRequests } from './api';
import './App.css';

function getDatesForPreset(preset) {
  const to = new Date();
  const from = new Date();
  
  if (preset === 'Last 24h') {
    from.setHours(from.getHours() - 24);
    return { from: from.toISOString(), to: to.toISOString(), forceBucket: 'hour' };
  } else if (preset === 'Last 7 days') {
    from.setDate(from.getDate() - 7);
    return { from: from.toISOString(), to: to.toISOString(), forceBucket: 'day' };
  } else if (preset === 'Last 14 days') {
    from.setDate(from.getDate() - 14);
    return { from: from.toISOString(), to: to.toISOString(), forceBucket: 'day' };
  } else if (preset === 'All') {
    return { from: null, to: null, forceBucket: 'day' };
  }
  return { from: null, to: null, forceBucket: 'day' };
}

export default function App() {
  // Navigation Tabs State (Change 3)
  const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'insights'
  const [hasMountedOverview, setHasMountedOverview] = useState(true);
  const [hasMountedInsights, setHasMountedInsights] = useState(false);

  // Overview Filters & State (Preserved across tab switches)
  const [provider, setProvider] = useState('all');
  const [preset, setPreset] = useState('Last 14 days');
  const [bucket, setBucket] = useState('day');
  const [statusFilter, setStatusFilter] = useState('all');
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState(null);

  const [dateRange, setDateRange] = useState(() => getDatesForPreset('Last 14 days'));

  const [summary, setSummary] = useState({ data: null, loading: true, error: null });
  const [timeline, setTimeline] = useState({ data: null, loading: true, error: null });
  const [requests, setRequests] = useState({ data: null, loading: true, error: null });

  const handleTabSwitch = (tab) => {
    setActiveTab(tab);
    if (tab === 'insights') {
      setHasMountedInsights(true);
    } else if (tab === 'overview') {
      setHasMountedOverview(true);
    }
  };

  const handlePresetChange = (newPreset) => {
    setPreset(newPreset);
    const range = getDatesForPreset(newPreset);
    setDateRange(range);
    setBucket(range.forceBucket);
    setPage(1); 
  };

  const handleProviderChange = (newProv) => {
    setProvider(newProv);
    setPage(1);
  };
  
  const handleStatusChange = (newStatus) => {
    setStatusFilter(newStatus);
    setPage(1);
  };

  const fetchDashboardData = useCallback(() => {
    const controller = new AbortController();
    const signal = controller.signal;
    const commonParams = { provider, from: dateRange.from, to: dateRange.to };

    setSummary(s => ({ ...s, loading: true, error: null }));
    fetchSummary(commonParams, signal)
      .then(data => setSummary({ data, loading: false, error: null }))
      .catch(err => {
        if (err.name === 'AbortError') return;
        setSummary({ data: null, loading: false, error: err.message });
      });

    setTimeline(s => ({ ...s, loading: true, error: null }));
    const timelineParams = { ...commonParams, bucket };
    if (!timelineParams.from) {
      const fallbackFrom = new Date();
      fallbackFrom.setDate(fallbackFrom.getDate() - 30);
      timelineParams.from = fallbackFrom.toISOString();
      timelineParams.to = new Date().toISOString();
    }
    
    fetchTimeline(timelineParams, signal)
      .then(data => setTimeline({ data, loading: false, error: null }))
      .catch(err => {
        if (err.name === 'AbortError') return;
        setTimeline({ data: null, loading: false, error: err.message });
      });

    return controller;
  }, [provider, dateRange, bucket]);

  const fetchTableData = useCallback(() => {
    const controller = new AbortController();
    
    setRequests(s => ({ ...s, loading: true, error: null }));
    fetchRequests({
      provider,
      from: dateRange.from,
      to: dateRange.to,
      status: statusFilter,
      page,
      page_size: 20
    }, controller.signal)
      .then(data => setRequests({ data, loading: false, error: null }))
      .catch(err => {
        if (err.name === 'AbortError') return;
        setRequests({ data: null, loading: false, error: err.message });
      });

    return controller;
  }, [provider, dateRange, statusFilter, page]);

  useEffect(() => {
    if (!hasMountedOverview) return;
    const controller = fetchDashboardData();
    return () => controller.abort();
  }, [hasMountedOverview, fetchDashboardData]);

  useEffect(() => {
    if (!hasMountedOverview) return;
    const controller = fetchTableData();
    return () => controller.abort();
  }, [hasMountedOverview, fetchTableData]);

  const hasGlobalError = summary.error || timeline.error || requests.error;

  return (
    <div className="app">
      <header>
        <div className="header-top">
          <h1>PromptLens <span className="subtitle">the API Auditor</span></h1>
        </div>

        {/* Tab Navigation (Change 3) */}
        <nav className="tab-navigation">
          <button 
            type="button"
            className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => handleTabSwitch('overview')}
          >
            Overview
          </button>
          <button 
            type="button"
            className={`tab-btn ${activeTab === 'insights' ? 'active' : ''}`}
            onClick={() => handleTabSwitch('insights')}
          >
            Prompt Insights
          </button>
        </nav>
      </header>

      <main>
        {/* OVERVIEW TAB (Kept mounted, hidden via CSS when inactive) */}
        {hasMountedOverview && (
          <div style={{ display: activeTab === 'overview' ? 'block' : 'none' }}>
            <FilterBar 
              provider={provider} setProvider={handleProviderChange}
              preset={preset} setPreset={handlePresetChange}
              bucket={bucket} setBucket={setBucket}
            />

            {hasGlobalError && (
              <div className="global-error state-box">
                <p>Error communicating with API. Make sure the backend is running.</p>
                <button type="button" onClick={() => {
                  fetchDashboardData();
                  fetchTableData();
                }}>Retry</button>
              </div>
            )}

            <SummaryCards data={summary.data} loading={summary.loading} />
            
            <UsageChart data={timeline.data} loading={timeline.loading} bucket={bucket} />

            <RequestsTable 
              data={requests.data} 
              loading={requests.loading} 
              page={page} 
              setPage={setPage}
              statusFilter={statusFilter}
              setStatusFilter={handleStatusChange}
              onRowClick={setSelectedId}
            />

            {selectedId && (
              <RequestDetail id={selectedId} onClose={() => setSelectedId(null)} />
            )}
          </div>
        )}

        {/* PROMPT INSIGHTS TAB (Mounted on first open, kept mounted, hidden via CSS when inactive) */}
        {hasMountedInsights && (
          <div style={{ display: activeTab === 'insights' ? 'block' : 'none' }}>
            <InsightsTab />
          </div>
        )}
      </main>
    </div>
  );
}
