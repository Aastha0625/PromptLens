import React, { useMemo, useState } from 'react';

/**
 * Computes a word-and-whitespace-preserving diff between `original` and `optimized`.
 * Falls back to line-level diff when token count is very large to keep rendering instant.
 */
function computeWordDiff(original, optimized) {
  const orig = original || '';
  const opt = optimized || '';

  if (orig === opt) {
    return [{ type: 'equal', text: opt }];
  }

  let tokensA = orig.split(/(\s+)/).filter((t) => t.length > 0);
  let tokensB = opt.split(/(\s+)/).filter((t) => t.length > 0);

  // Guard DP table size for very large prompts by switching to line tokens
  if (tokensA.length * tokensB.length > 250000) {
    tokensA = orig.split(/(\n)/).filter((t) => t.length > 0);
    tokensB = opt.split(/(\n)/).filter((t) => t.length > 0);
  }

  const m = tokensA.length;
  const n = tokensB.length;
  const dp = Array.from({ length: m + 1 }, () => new Uint32Array(n + 1));

  for (let i = m - 1; i >= 0; i -= 1) {
    for (let j = n - 1; j >= 0; j -= 1) {
      if (tokensA[i] === tokensB[j]) {
        dp[i][j] = dp[i + 1][j + 1] + 1;
      } else {
        dp[i][j] = dp[i + 1][j] >= dp[i][j + 1] ? dp[i + 1][j] : dp[i][j + 1];
      }
    }
  }

  const rawOps = [];
  let i = 0;
  let j = 0;
  while (i < m && j < n) {
    if (tokensA[i] === tokensB[j]) {
      rawOps.push({ type: 'equal', text: tokensA[i] });
      i += 1;
      j += 1;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      rawOps.push({ type: 'delete', text: tokensA[i] });
      i += 1;
    } else {
      rawOps.push({ type: 'insert', text: tokensB[j] });
      j += 1;
    }
  }
  while (i < m) {
    rawOps.push({ type: 'delete', text: tokensA[i] });
    i += 1;
  }
  while (j < n) {
    rawOps.push({ type: 'insert', text: tokensB[j] });
    j += 1;
  }

  // Coalesce adjacent operations of the same type
  const merged = [];
  for (const op of rawOps) {
    if (merged.length > 0 && merged[merged.length - 1].type === op.type) {
      merged[merged.length - 1].text += op.text;
    } else {
      merged.push({ ...op });
    }
  }
  return merged;
}

export default function DiffViewer({
  originalText,
  optimizedText,
  title = 'Visual Diff',
  copyLabel = 'Copy Optimized Prompt',
}) {
  const [copyState, setCopyState] = useState('idle'); // 'idle' | 'copied' | 'failed'
  const segments = useMemo(
    () => computeWordDiff(originalText, optimizedText),
    [originalText, optimizedText]
  );

  const canCopy = typeof optimizedText === 'string' && optimizedText.trim().length > 0;

  const handleCopy = async () => {
    if (!canCopy) return;
    try {
      await navigator.clipboard.writeText(optimizedText);
      setCopyState('copied');
      setTimeout(() => setCopyState('idle'), 2500);
    } catch {
      setCopyState('failed');
      setTimeout(() => setCopyState('idle'), 2500);
    }
  };

  return (
    <div className="diff-viewer-container">
      <div className="box-header">
        <div className="diff-title-group">
          <h4>{title}</h4>
          <div className="diff-legend">
            <span className="legend-item">
              <span className="legend-swatch swatch-deleted" /> Removed
            </span>
            <span className="legend-item">
              <span className="legend-swatch swatch-added" /> Updated
            </span>
          </div>
        </div>
        {canCopy && (
          <button
            type="button"
            className="btn-copy"
            onClick={handleCopy}
            disabled={copyState === 'copied'}
          >
            {copyState === 'copied' && '✓ Copied!'}
            {copyState === 'failed' && '✗ Copy failed'}
            {copyState === 'idle' && copyLabel}
          </button>
        )}
      </div>

      <div className="prompt-box diff-box" aria-label="Prompt visual diff">
        {segments.map((seg, idx) => {
          if (seg.type === 'delete') {
            return (
              <del key={idx} className="diff-deleted">
                {seg.text}
              </del>
            );
          }
          if (seg.type === 'insert') {
            return (
              <ins key={idx} className="diff-added">
                {seg.text}
              </ins>
            );
          }
          return (
            <span key={idx} className="diff-equal">
              {seg.text}
            </span>
          );
        })}
      </div>
    </div>
  );
}
