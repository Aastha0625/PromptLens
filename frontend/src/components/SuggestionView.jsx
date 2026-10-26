import React, { useState } from 'react';
import StatusBadge from './StatusBadge';
import { formatNumber } from '../format';

export default function SuggestionView({ suggestion, originalPromptText }) {
  const [copyState, setCopyState] = useState('idle'); // 'idle' | 'copied' | 'failed'

  if (!suggestion) return null;

  const hasRewrite = suggestion.rewritten_prompt != null && suggestion.rewritten_prompt.trim().length > 0;
  const isLlm = suggestion.method === 'llm_rewrite';

  const handleCopy = async () => {
    if (!hasRewrite) return;
    try {
      await navigator.clipboard.writeText(suggestion.rewritten_prompt);
      setCopyState('copied');
      setTimeout(() => setCopyState('idle'), 2500);
    } catch {
      setCopyState('failed');
      setTimeout(() => setCopyState('idle'), 2500);
    }
  };

  return (
    <div className="suggestion-view">
      <div className="suggestion-status-container">
        <StatusBadge suggestion={suggestion} />
      </div>

      {/* Side-by-side boxes (stacked on mobile via CSS) */}
      <div className="side-by-side">
        <div className="prompt-box-wrapper">
          <div className="box-header">
            <h4>Original Prompt</h4>
          </div>
          <pre className="prompt-box original-box">
            {originalPromptText || suggestion.original_prompt_excerpt || "—"}
          </pre>
        </div>

        {hasRewrite && (
          <div className="prompt-box-wrapper">
            <div className="box-header">
              <h4>Suggested Rewrite</h4>
              <button 
                type="button"
                className="btn-copy"
                onClick={handleCopy}
                disabled={copyState === 'copied'}
              >
                {copyState === 'copied' && "✓ Copied!"}
                {copyState === 'failed' && "✗ Copy failed"}
                {copyState === 'idle' && "Copy rewritten prompt"}
              </button>
            </div>
            <pre className="prompt-box rewrite-box">
              {suggestion.rewritten_prompt}
            </pre>
          </div>
        )}
      </div>

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
