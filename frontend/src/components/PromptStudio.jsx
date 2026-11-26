import React, { useState, useRef } from 'react';
import DiffViewer from './DiffViewer';
import { auditPrompt } from '../api';
import { formatNumber } from '../format';

const PRESET_PROMPTS = [
  {
    label: 'Conversational Bloat',
    text: 'Hello ChatGPT! I hope you are having an amazing and wonderful day today. Could you please kindly help me write a Python function to compute the Fibonacci series up to N terms? Thank you so much in advance for your assistance, I really appreciate your help!'
  },
  {
    label: 'Redundant Sentences',
    text: 'Please review the database schema for the user authentication system. Make sure the passwords are encrypted using bcrypt with at least 12 salt rounds. Please review the database schema for the user authentication system. Ensure indexes are created on email and username columns. Make sure the passwords are encrypted using bcrypt with at least 12 salt rounds.'
  },
  {
    label: 'Repeated Formatting & Whitespace',
    text: 'Summarize the quarterly financial report.\n\n\n\n\nFocus on revenue growth, operational expenses, and net profit margins.               Include bullet points for key takeaways.'
  }
];

export default function PromptStudio() {
  const [promptText, setPromptText] = useState(PRESET_PROMPTS[0].text);
  const [provider, setProvider] = useState('groq');
  const [model, setModel] = useState('openai/gpt-oss-20b');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [auditResult, setAuditResult] = useState(null);
  const resultsRef = useRef(null);

  const handleOptimize = async () => {
    console.log('[PromptStudio] Optimize button clicked! Prompt length:', promptText.length);
    if (!promptText.trim()) {
      setError('Please type or paste a prompt, or click a sample pill above.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await auditPrompt({
        prompt_text: promptText,
        provider,
        model
      });
      console.log('[PromptStudio] Audit response received:', res);
      setAuditResult(res);
      setLoading(false);
      setTimeout(() => {
        resultsRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    } catch (err) {
      console.error('[PromptStudio] Optimization error:', err);
      setError(err.message || 'Failed to optimize prompt.');
      setLoading(false);
    }
  };

  const handleApplyPreset = (text) => {
    setPromptText(text);
    setAuditResult(null);
    setError(null);
  };

  const handleClear = () => {
    setPromptText('');
    setAuditResult(null);
    setError(null);
  };

  // Efficiency score styling & rating
  const score = auditResult ? auditResult.efficiency_score : 100;
  let scoreClass = 'score-high';
  let scoreLabel = 'Highly Efficient';
  if (score < 60) {
    scoreClass = 'score-low';
    scoreLabel = 'High Waste Detected';
  } else if (score < 85) {
    scoreClass = 'score-medium';
    scoreLabel = 'Moderate Bloat';
  }

  const origTokens = auditResult?.tokens_original || 0;
  const savedTokens = auditResult?.tokens_saved || 0;
  const percentSaved = origTokens > 0 ? ((savedTokens / origTokens) * 100).toFixed(1) : '0';

  return (
    <div className="prompt-studio-container">
      {/* Header Banner */}
      <div className="studio-header">
        <div>
          <h2>Prompt Studio <span className="badge-studio-live">Interactive Optimizer</span></h2>
          <p className="text-muted-sm">
            Paste any AI prompt to audit bloat, strip conversational filler, remove duplicates, and preview live token savings.
          </p>
        </div>
      </div>

      {/* Preset Pill Bar */}
      <div className="studio-preset-bar">
        <span className="preset-label">Try sample prompt:</span>
        {PRESET_PROMPTS.map((preset, idx) => (
          <button
            key={idx}
            type="button"
            className="btn-preset-pill"
            onClick={() => handleApplyPreset(preset.text)}
          >
            {preset.label}
          </button>
        ))}
      </div>

      {/* Input Playground Box */}
      <div className="card studio-input-card">
        <div className="studio-input-toolbar">
          <div className="studio-model-selector">
            <label>Provider:
              <select value={provider} onChange={e => setProvider(e.target.value)}>
                <option value="groq">Groq (Free Tier)</option>
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="ollama">Ollama (Offline Local)</option>
                <option value="gemini">Google Gemini</option>
              </select>
            </label>

            <label>Model:
              <input
                type="text"
                className="input-model-name"
                value={model}
                onChange={e => setModel(e.target.value)}
                placeholder="Model name"
              />
            </label>
          </div>

          <div className="studio-char-stats">
            <span>{promptText.length} characters</span>
            {promptText.length > 0 && (
              <button type="button" className="btn-clear" onClick={handleClear}>
                Clear
              </button>
            )}
          </div>n


        </div>

        <textarea
          className="studio-textarea"
          rows={6}
          placeholder="Paste or type your raw AI prompt here (e.g. 'Hello AI! Could you please kindly help me with...')"
          value={promptText}
          onChange={e => setPromptText(e.target.value)}
        />

        <div className="studio-actions-footer">
          <button
            type="button"
            className="btn btn-primary btn-optimize"
            onClick={handleOptimize}
            disabled={loading}
          >
            {loading ? (
              <span className="spinner-text">
                <span className="spinner-icon" /> Optimizing prompt...
              </span>
            ) : (
              '⚡ Optimize Prompt'
            )}
          </button>
        </div>
      </div>

      {error && <div className="banner banner-error">{error}</div>}

      {/* Optimization Results Section */}
      {auditResult && (
        <div ref={resultsRef} className="studio-results-section card">
          <div className="results-header">
            <h3>Audit & Optimization Results</h3>
          </div>

          {/* Efficiency Score Gauge & Metrics Grid */}
          <div className="efficiency-score-grid">
            {/* Circular Gauge Card */}
            <div className={`efficiency-gauge-card ${scoreClass}`}>
              <div className="gauge-circle">
                <span className="gauge-number">{score}%</span>
                <span className="gauge-unit">Score</span>
              </div>
              <div className="gauge-info">
                <h4>{scoreLabel}</h4>
                <p className="text-muted-sm">
                  {score >= 85
                    ? 'Excellent prompt hygiene. Negligible token waste.'
                    : `${savedTokens} tokens (${percentSaved}%) recoverable by trimming bloat.`}
                </p>
              </div>
            </div>

            {/* Quick Metrics */}
            <div className="quick-metrics-container">
              <div className="metric-box">
                <span className="metric-title">Original Tokens</span>
                <strong className="metric-val">{formatNumber(auditResult.tokens_original)}</strong>
              </div>
              <div className="metric-box">
                <span className="metric-title">Optimized Tokens</span>
                <strong className="metric-val text-success">{formatNumber(auditResult.tokens_optimized)}</strong>
              </div>
              <div className="metric-box">
                <span className="metric-title">Tokens Saved</span>
                <strong className="metric-val text-success">
                  {formatNumber(auditResult.tokens_saved)} ({percentSaved}%)
                </strong>
              </div>
            </div>
          </div>

          {/* Flaws Detected Badges & Explanations */}
          <div className="studio-flaws-strip">
            <span className="flaws-label">Audit Diagnostics:</span>
            {auditResult.flaws_detected && auditResult.flaws_detected.length > 0 ? (
              auditResult.flaws_detected.map((flaw, idx) => (
                <span key={idx} className="badge-flaw">
                  ⚠ {flaw.replace(/_/g, ' ')}
                </span>
              ))
            ) : (
              <span className="badge-clean">✓ Zero waste detected</span>
            )}
          </div>

          {auditResult.explanations && auditResult.explanations.length > 0 && (
            <div className="studio-explanations-box">
              <h4>What was cleaned:</h4>
              <ul>
                {auditResult.explanations.map((exp, idx) => (
                  <li key={idx}>{exp}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Visual Red/Green Diff Viewer */}
          <div className="studio-diff-container">
            <h4>Word-Level Visual Diff</h4>
            <DiffViewer
              originalText={auditResult.original_prompt}
              modifiedText={auditResult.optimized_prompt}
              titleOriginal="Raw Input Prompt"
              titleModified="Optimized Clean Prompt"
              showCopy={true}
              initialMode="diff"
            />
          </div>
        </div>
      )}
    </div>
  );
}
