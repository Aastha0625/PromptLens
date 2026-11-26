import React, { useState } from 'react';
import StatusBadge from './StatusBadge';
import DiffViewer, { extractCleanUserInput } from './DiffViewer';
import { formatNumber } from '../format';

export default function SuggestionView({ suggestion, originalPromptText }) {
  const [copyState, setCopyState] = useState('idle'); // 'idle' | 'copied' | 'failed'
  const [viewMode, setViewMode] = useState('diff'); // 'diff' | 'split'

  if (!suggestion) return null;

  const hasRewrite = suggestion.rewritten_prompt != null && suggestion.rewritten_prompt.trim().length > 0;
  const isLlm = suggestion.method === 'llm_rewrite';
  const originalText = originalPromptText || suggestion.original_prompt_excerpt || '—';
  const cleanRewrite = extractCleanUserInput(suggestion.rewritten_prompt);

  const handleCopy = async () => {
    if (!hasRewrite) return;
    try {
      await navigator.clipboard.writeText(cleanRewrite || suggestion.rewritten_prompt);
      setCopyState('copied');
      setTimeout(() => setCopyState('idle'), 2500);
    } catch {
      setCopyState('failed');
      setTimeout(() => setCopyState('idle'), 2500);
    }
  };

  return (
    <div className="suggestion-view">
      <div className="suggestion-status-row">
        <div className="suggestion-status-container">
          <StatusBadge suggestion={suggestion} />
        </div>
        {hasRewrite && (
          <div className="view-mode-toggle" role="group" aria-label="Prompt comparison mode">
            <button
              type="button"
              className={viewMode === 'diff' ? 'active' : ''}
              onClick={() => setViewMode('diff')}
            >
              Visual Diff
            </button>
            <button
              type="button"
              className={viewMode === 'split' ? 'active' : ''}
              onClick={() => setViewMode('split')}
            >
              Side-by-Side
            </button>
          </div>
        )}
      </div>

      {hasRewrite && viewMode === 'diff' ? (
        <DiffViewer
          originalText={originalText}
          optimizedText={suggestion.rewritten_prompt}
          title="Visual Diff"
          copyLabel="Copy Optimized Prompt"
        />
      ) : (
        /* Side-by-side boxes (stacked on mobile via CSS) */
        <div className="side-by-side">
          <div className="prompt-box-wrapper">
            <div className="box-header">
              <h4>Original Description / Input</h4>
            </div>
            <pre className="prompt-box original-box">{extractCleanUserInput(originalText)}</pre>
          </div>

          {hasRewrite && (
            <div className="prompt-box-wrapper">
              <div className="box-header">
                <h4>Clean Description</h4>
                <button
                  type="button"
                  className="btn-copy"
                  onClick={handleCopy}
                  disabled={copyState === 'copied'}
                >
                  {copyState === 'copied' && '✓ Copied!'}
                  {copyState === 'failed' && '✗ Copy failed'}
                  {copyState === 'idle' && '📋 Copy Clean Description'}
                </button>
              </div>
              <pre className="prompt-box rewrite-box">
                {cleanRewrite || suggestion.rewritten_prompt}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Token Savings line */}
      {hasRewrite && suggestion.estimated_token_savings > 0 && (
        <div className="savings-badge">
          Estimated token savings: <strong>{formatNumber(suggestion.estimated_token_savings)} tokens</strong>
        </div>
      )}

      {/* Message callout if no rewritten prompt was produced */}
      {!hasRewrite && suggestion.message && (
        <div className="suggestion-message-box">
          <p>{suggestion.message}</p>
        </div>
      )}

      {/* Disclaimer note under any LLM rewrite */}
      {isLlm && (
        <p className="llm-disclaimer-note">
          Note: Similarity compares replies from two different models, so treat it as a guide, not a guarantee.
        </p>
      )}
    </div>
  );
}
