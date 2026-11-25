import React, { useState } from 'react';
import DiffViewer from './DiffViewer';
import { auditPrompt } from '../api';
import { formatNumber } from '../format';

const SAMPLE_BLOATED_PROMPT =
  'Hey ChatGPT, I hope you are having a great day! Could you please kindly help me with explaining how database indexing improves SQL query performance? Please include B-tree index examples. Please include B-tree index examples. Keep the answer concise. Thank you so much in advance!';

const FLAW_LABELS = {
  conversational_fluff: 'Conversational Fluff',
  redundant_sentences: 'Duplicate Sentences',
  repeated_content: 'Repeated Formatting / Words',
  verbose_prompt: 'Verbose Phrasing (AI Rewrite)',
};

function getScoreMeta(score) {
  if (score >= 85) {
    return { label: 'Highly Efficient', color: '#16a34a', bg: '#dcfce7', border: '#86efac' };
  }
  if (score >= 65) {
    return { label: 'Moderate Waste', color: '#d97706', bg: '#fef3c7', border: '#fde68a' };
  }
  return { label: 'High Waste', color: '#dc2626', bg: '#fee2e2', border: '#fca5a5' };
}

export default function PromptStudio() {
  const [promptText, setPromptText] = useState('');
  const [provider, setProvider] = useState('groq');
  const [model, setModel] = useState('openai/gpt-oss-20b');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const handleOptimize = async (e) => {
    if (e) e.preventDefault();
    if (!promptText.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const data = await auditPrompt({
        prompt_text: promptText,
        provider,
        model,
      });
      setResult(data);
    } catch (err) {
      setError(err.message || 'Failed to optimize prompt.');
    } finally {
      setLoading(false);
    }
  };

  const handleLoadSample = () => {
    setPromptText(SAMPLE_BLOATED_PROMPT);
    setResult(null);
    setError(null);
  };

  const handleClear = () => {
    setPromptText('');
    setResult(null);
    setError(null);
  };

  const scoreMeta = result ? getScoreMeta(result.efficiency_score) : null;
  const pctSaved =
    result && result.tokens_original > 0
      ? Math.round((result.tokens_saved / result.tokens_original) * 100)
      : 0;

  return (
    <div className="prompt-studio">
      <div className="insights-header-bar">
        <div>
          <h2>Prompt Studio</h2>
          <p className="text-muted-sm">
            Test, audit, and optimize prompts in real time before sending them to an LLM.
          </p>
        </div>

        <div className="studio-header-actions">
          <button type="button" onClick={handleLoadSample} disabled={loading}>
            Load Sample Prompt
          </button>
          {promptText && (
            <button type="button" onClick={handleClear} disabled={loading}>
              Clear
            </button>
          )}
        </div>
      </div>

      <form className="card studio-input-card" onSubmit={handleOptimize}>
        <div className="studio-controls-row">
          <div className="filter-group">
            <label htmlFor="studio-provider">Target Provider</label>
            <select
              id="studio-provider"
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
            >
              <option value="groq">Groq (Free Tier)</option>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="gemini">Gemini</option>
              <option value="ollama">Ollama (Local)</option>
            </select>
          </div>

          <div className="filter-group">
            <label htmlFor="studio-model">Model</label>
            <input
              id="studio-model"
              type="text"
              className="studio-model-input"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="openai/gpt-oss-20b"
            />
          </div>
        </div>

        <label htmlFor="studio-prompt-input" className="studio-textarea-label">
          Raw Prompt
        </label>
        <textarea
          id="studio-prompt-input"
          className="studio-textarea"
          rows={7}
          value={promptText}
          onChange={(e) => setPromptText(e.target.value)}
          placeholder="Paste any raw prompt here to strip conversational fluff, duplicate sentences, and formatting waste..."
        />

        <div className="studio-submit-row">
          <span className="text-muted-sm">
            {promptText.length > 0
              ? `${promptText.length} chars (~${Math.max(1, Math.round(promptText.length / 4))} est. tokens)`
              : 'Runs locally with $0.00 API cost'}
          </span>
          <button
            type="submit"
            className="btn btn-primary btn-run-analysis"
            disabled={loading || !promptText.trim()}
          >
            {loading ? (
              <span className="spinner-text">
                <span className="spinner-icon" /> Optimizing...
              </span>
            ) : (
              'Optimize Prompt'
            )}
          </button>
        </div>
      </form>

      {error && (
        <div className="banner banner-error">
          <p>{error}</p>
        </div>
      )}

      {result && (
        <div className="studio-results">
          {/* Top Metrics Row: Circular Efficiency Score + Quick Stats */}
          <div className="studio-metrics-row">
            <div
              className="card efficiency-card"
              style={{ borderColor: scoreMeta.border }}
            >
              <div
                className="efficiency-ring"
                style={{
                  background: `conic-gradient(${scoreMeta.color} ${result.efficiency_score * 3.6}deg, #e5e7eb 0deg)`,
                }}
              >
                <div className="efficiency-ring-inner">
                  <span className="efficiency-pct" style={{ color: scoreMeta.color }}>
                    {result.efficiency_score}%
                  </span>
                </div>
              </div>
              <div className="efficiency-info">
                <span
                  className="efficiency-badge"
                  style={{
                    backgroundColor: scoreMeta.bg,
                    color: scoreMeta.color,
                    borderColor: scoreMeta.border,
                  }}
                >
                  {scoreMeta.label}
                </span>
                <p className="text-muted-sm">Efficiency Score</p>
              </div>
            </div>

            <div className="summary-cards studio-stats-grid">
              <div className="card">
                <h3>Original Tokens</h3>
                <p className="value">{formatNumber(result.tokens_original)}</p>
                <p className="sub-value">{result.original_prompt.length} characters</p>
              </div>
              <div className="card">
                <h3>Optimized Tokens</h3>
                <p className="value">{formatNumber(result.tokens_optimized)}</p>
                <p className="sub-value">{result.optimized_prompt.length} characters</p>
              </div>
              <div className="card">
                <h3>Tokens Saved</h3>
                <p className="value text-success">{formatNumber(result.tokens_saved)}</p>
                <p className="sub-value">{pctSaved}% reduction</p>
              </div>
            </div>
          </div>

          {/* Explanations & Flaws */}
          <div className="card studio-explanations-card">
            <div className="studio-explanations-header">
              <h4>Audit Breakdown</h4>
              {result.flaws_detected.length > 0 && (
                <div className="flaw-pills">
                  {result.flaws_detected.map((flaw) => (
                    <span key={flaw} className="tag flaw-pill">
                      {FLAW_LABELS[flaw] || flaw}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {result.explanations.length > 0 ? (
              <ul className="explanations-list">
                {result.explanations.map((item, idx) => (
                  <li key={idx}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="text-muted-sm">
                No conversational fluff, duplicate sentences, or formatting waste detected. Your prompt is already lean!
              </p>
            )}
          </div>

          {/* Visual Diff & Clean Output */}
          <div className="card">
            <DiffViewer
              originalText={result.original_prompt}
              optimizedText={result.optimized_prompt}
              title="Visual Optimization Diff"
              copyLabel="Copy Optimized Prompt"
            />

            <div className="studio-clean-output">
              <h4>Clean Optimized Prompt</h4>
              <pre className="prompt-box rewrite-box">{result.optimized_prompt}</pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
