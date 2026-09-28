import React, { useState, useEffect, useCallback } from 'react';
import FilterBar from './components/FilterBar';
import SummaryCards from './components/SummaryCards';
import UsageChart from './components/UsageChart';
import RequestsTable from './components/RequestsTable';
import RequestDetail from './components/RequestDetail';
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
    const controller = fetchDashboardData();
    return () => controller.abort();
  }, [fetchDashboardData]);

  useEffect(() => {
    const controller = fetchTableData();
    return () => controller.abort();
  }, [fetchTableData]);

  const hasGlobalError = summary.error || timeline.error || requests.error;

  return (
    <div className="app">
      <header>
        <h1>PromptLens <span className="subtitle">the API Auditor</span></h1>
      </header>

      <main>
        <FilterBar 
          provider={provider} setProvider={handleProviderChange}
          preset={preset} setPreset={handlePresetChange}
          bucket={bucket} setBucket={setBucket}
        />

        {hasGlobalError && (
          <div className="global-error state-box">
            <p>Error communicating with API. Make sure the backend is running.</p>
            <button onClick={() => {
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
      </main>

      {selectedId && (
        <RequestDetail id={selectedId} onClose={() => setSelectedId(null)} />
      )}
    </div>
  );
}
