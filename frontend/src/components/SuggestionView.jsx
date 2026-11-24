import React from 'react';
import StatusBadge from './StatusBadge';
import DiffViewer from './DiffViewer';
import { formatNumber } from '../format';

export default function SuggestionView({ suggestion, originalPromptText }) {
  if (!suggestion) return null;

  const hasRewrite = suggestion.rewritten_prompt != null && suggestion.rewritten_prompt.trim().length > 0;
  const isLlm = suggestion.method === 'llm_rewrite';
  const original = originalPromptText || suggestion.original_prompt_excerpt || '';

  return (
    <div className="suggestion-view">
      <div className="suggestion-status-container">
        <StatusBadge suggestion={suggestion} />
      </div>

      {/* Visual Diff / Side-by-side component */}
      {hasRewrite ? (
        <DiffViewer
          originalText={original}
          modifiedText={suggestion.rewritten_prompt}
          titleOriginal="Original Prompt"
          titleModified="Suggested Rewrite"
          showCopy={true}
          initialMode="diff"
        />
      ) : (
        <div className="side-by-side">
          <div className="prompt-box-wrapper">
            <div className="box-header">
              <h4>Original Prompt</h4>
            </div>
            <pre className="prompt-box original-box">
              {original || '—'}
            </pre>
          </div>
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
