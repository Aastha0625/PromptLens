import React, { useState, useMemo } from 'react';

/**
 * Tokenize string into words and whitespace/newlines.
 */
function tokenize(str) {
  if (!str) return [];
  return str.match(/\S+|\s+/g) || [];
}

/**
 * Word-level Longest Common Subsequence (LCS) diff.
 */
function computeWordDiff(origText, modText) {
  const origTokens = tokenize(origText);
  const modTokens = tokenize(modText);

  const n = origTokens.length;
  const m = modTokens.length;

  // For very large texts, fall back to simple line diff or block diff to prevent memory blowup
  if (n * m > 250000) {
    return [
      { type: 'delete', value: origText },
      { type: 'insert', value: modText }
    ];
  }

  // DP table
  const dp = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));

  for (let i = 1; i <= n; i++) {
    for (let j = 1; j <= m; j++) {
      if (origTokens[i - 1] === modTokens[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  // Backtrack
  let i = n;
  let j = m;
  const diff = [];

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && origTokens[i - 1] === modTokens[j - 1]) {
      diff.unshift({ type: 'equal', value: origTokens[i - 1] });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      diff.unshift({ type: 'insert', value: modTokens[j - 1] });
      j--;
    } else if (i > 0 && (j === 0 || dp[i][j - 1] < dp[i - 1][j])) {
      diff.unshift({ type: 'delete', value: origTokens[i - 1] });
      i--;
    }
  }

  // Merge consecutive tokens of the same type for cleaner DOM rendering
  const merged = [];
  for (const token of diff) {
    if (merged.length > 0 && merged[merged.length - 1].type === token.type) {
      merged[merged.length - 1].value += token.value;
    } else {
      merged.push({ ...token });
    }
  }

  return merged;
}

export default function DiffViewer({ 
  originalText = '', 
  modifiedText = '', 
  titleOriginal = 'Original Prompt',
  titleModified = 'Optimized Prompt',
  showCopy = true,
  initialMode = 'diff' 
}) {
  const [viewMode, setViewMode] = useState(initialMode); // 'diff' | 'side-by-side'
  const [copyState, setCopyState] = useState('idle'); // 'idle' | 'copied' | 'failed'

  const diffItems = useMemo(() => {
    return computeWordDiff(originalText, modifiedText);
  }, [originalText, modifiedText]);

  const handleCopy = async () => {
    if (!modifiedText) return;
    try {
      await navigator.clipboard.writeText(modifiedText);
      setCopyState('copied');
      setTimeout(() => setCopyState('idle'), 2500);
    } catch {
      setCopyState('failed');
      setTimeout(() => setCopyState('idle'), 2500);
    }
  };

  const hasModifications = originalText.trim() !== modifiedText.trim();

  return (
    <div className="diff-viewer-component">
      {/* View Switcher & Action Header */}
      <div className="diff-toolbar">
        <div className="diff-mode-toggles">
          <button
            type="button"
            className={`diff-toggle-btn ${viewMode === 'diff' ? 'active' : ''}`}
            onClick={() => setViewMode('diff')}
          >
            Visual Diff
          </button>
          <button
            type="button"
            className={`diff-toggle-btn ${viewMode === 'side-by-side' ? 'active' : ''}`}
            onClick={() => setViewMode('side-by-side')}
          >
            Side-by-Side
          </button>
        </div>

        <div className="diff-toolbar-actions">
          <div className="diff-legend">
            <span className="legend-item legend-deleted">
              <span className="legend-swatch swatch-deleted" /> Removed bloat
            </span>
            <span className="legend-item legend-preserved">
              <span className="legend-swatch swatch-preserved" /> Preserved text
            </span>
          </div>

          {showCopy && modifiedText && (
            <button
              type="button"
              className="btn-copy btn-copy-prominent"
              onClick={handleCopy}
              disabled={copyState === 'copied'}
            >
              {copyState === 'copied' && '✓ Copied to clipboard!'}
              {copyState === 'failed' && '✗ Copy failed'}
              {copyState === 'idle' && 'Copy Optimized Prompt'}
            </button>
          )}
        </div>
      </div>

      {/* Visual Diff (Unified with Red Strikethrough) */}
      {viewMode === 'diff' && (
        <div className="diff-content diff-unified-container">
          <div className="diff-header-bar">
            <span className="diff-label">Highlighted Prompt Diff</span>
            {!hasModifications && (
              <span className="diff-notice">No differences detected (Prompt is already lean)</span>
            )}
          </div>
          <pre className="diff-unified-box">
            {diffItems.map((item, idx) => {
              if (item.type === 'delete') {
                return (
                  <del key={idx} className="diff-deleted" title="Removed waste / bloat">
                    {item.value}
                  </del>
                );
              }
              if (item.type === 'insert') {
                return (
                  <ins key={idx} className="diff-added" title="Added / reformatted">
                    {item.value}
                  </ins>
                );
              }
              return <span key={idx} className="diff-equal">{item.value}</span>;
            })}
          </pre>
        </div>
      )}

      {/* Side-by-Side View */}
      {viewMode === 'side-by-side' && (
        <div className="side-by-side diff-split-container">
          <div className="prompt-box-wrapper">
            <div className="box-header">
              <h4>{titleOriginal}</h4>
              <span className="box-token-count">{originalText.length} chars</span>
            </div>
            <pre className="prompt-box original-box">
              {originalText || '—'}
            </pre>
          </div>

          <div className="prompt-box-wrapper">
            <div className="box-header">
              <h4>{titleModified}</h4>
              <span className="box-token-count">{modifiedText.length} chars</span>
            </div>
            <pre className="prompt-box rewrite-box">
              {modifiedText || '—'}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
