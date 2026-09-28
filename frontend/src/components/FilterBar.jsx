import React from 'react';

// Hardcoded providers as requested to save an unnecessary backend roundtrip
const PROVIDERS = ['groq', 'openai', 'anthropic', 'ollama', 'gemini'];
const PRESETS = ['Last 24h', 'Last 7 days', 'Last 14 days', 'All'];

export default function FilterBar({ 
  provider, 
  setProvider, 
  preset, 
  setPreset, 
  bucket, 
  setBucket 
}) {
  return (
    <div className="filter-bar">
      <div className="filter-group">
        <label>Provider:</label>
        <select value={provider} onChange={e => setProvider(e.target.value)}>
          <option value="all">All Providers</option>
          {PROVIDERS.map(p => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </div>

      <div className="filter-group">
        <label>Time Range:</label>
        <div className="preset-buttons">
          {PRESETS.map(p => (
            <button 
              key={p} 
              className={preset === p ? 'active' : ''} 
              onClick={() => setPreset(p)}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      <div className="filter-group">
        <label>Chart Bucket:</label>
        <select 
          value={bucket} 
          onChange={e => setBucket(e.target.value)}
          disabled={preset !== 'Last 24h'} // Disables dropdown if hour is logically invalid
        >
          <option value="day">Day</option>
          {preset === 'Last 24h' && <option value="hour">Hour</option>}
        </select>
      </div>
    </div>
  );
}
