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

/**
 * Intelligently extracts only the user input / description portion of a prompt,
 * stripping away institutional system prompt guidelines, schemas, and form prefixes.
 */
export function extractCleanUserInput(text) {
  if (!text) return '';
  let str = text.trim();

  // 1. If it has a 'user:' message block, strip out the system prompt preceding it
  const userMatch = str.match(/(?:^|\n)user:\s*([\s\S]+)$/i);
  if (userMatch && userMatch[1]) {
    str = userMatch[1].trim();
  }

  // 2. If it's structured like a form (Title: ..., Location: ..., Description: ...)
  // extract specifically the Description part where the user typed
  const descMatch = str.match(/(?:^|\n)Description:\s*([\s\S]+)$/i);
  if (descMatch && descMatch[1]) {
    return descMatch[1].trim();
  }

  return str;
}

export default function DiffViewer({
  originalText,
  optimizedText,
  title = 'Visual Diff',
  copyLabel = 'Copy Clean Rewrite',
}) {
  const [copyState, setCopyState] = useState('idle'); // 'idle' | 'copied' | 'failed'
  const [diffMode, setDiffMode] = useState('focused'); // 'focused' | 'full'
  const [scopeMode, setScopeMode] = useState('inputOnly'); // 'inputOnly' | 'fullPrompt'

  const segments = useMemo(
    () => computeWordDiff(originalText, optimizedText),
    [originalText, optimizedText]
  );

  const removedText = useMemo(() => {
    const deleted = segments.filter((s) => s.type === 'delete');
    let raw = deleted.map((s) => s.text).join('').trim();
    return raw.replace(/^(Description|user):\s*/i, '').trim();
  }, [segments]);

  const cleanDescription = useMemo(
    () => extractCleanUserInput(optimizedText),
    [optimizedText]
  );

  const hasExtractedScope = cleanDescription !== (optimizedText || '').trim();
  const displayRewriteText = (hasExtractedScope && scopeMode === 'inputOnly') ? cleanDescription : optimizedText;

  const canCopy = typeof displayRewriteText === 'string' && displayRewriteText.trim().length > 0;

  const handleCopy = async () => {
    if (!canCopy) return;
    try {
      await navigator.clipboard.writeText(displayRewriteText);
      setCopyState('copied');
      setTimeout(() => setCopyState('idle'), 2500);
    } catch {
      setCopyState('failed');
      setTimeout(() => setCopyState('idle'), 2500);
    }
  };

  return (
    <div className="diff-viewer-container">
      {/* View Switcher: Focused (Removed & Rewrite only) vs Full Diff */}
      <div className="box-header" style={{ marginBottom: '8px' }}>
        <div className="diff-view-mode-toggle">
          <button
            type="button"
            className={diffMode === 'focused' ? 'active' : ''}
            onClick={() => setDiffMode('focused')}
          >
            Focused (Removed & Rewrite)
          </button>
          <button
            type="button"
            className={diffMode === 'full' ? 'active' : ''}
            onClick={() => setDiffMode('full')}
          >
            Full Prompt Diff
          </button>
        </div>

        {diffMode === 'full' && canCopy && (
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

      {diffMode === 'focused' ? (
        <div className="focused-diff-container">
          {/* 1. REMOVED BLOAT */}
          <div className="diff-card diff-card-removed">
            <div className="diff-card-header">
              <span className="diff-card-title text-danger">
                <span className="dot-indicator dot-danger" />
                Waste Removed
              </span>
            </div>
            <div className="diff-card-body">
              {removedText ? (
                <del className="diff-deleted-block">{removedText}</del>
              ) : (
                <span className="text-muted italic" style={{ fontSize: '12px' }}>
                  No text removed
                </span>
              )}
            </div>
          </div>

          {/* 2. CLEAN REWRITE WITH PROMINENT COPY BUTTON */}
          <div className="diff-card diff-card-rewrite">
            <div className="diff-card-header">
              <span className="diff-card-title text-success">
                <span className="dot-indicator dot-success" />
                {hasExtractedScope && scopeMode === 'inputOnly' ? 'Clean Description' : 'Clean Rewrite'}
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {hasExtractedScope && (
                  <button
                    type="button"
                    className="btn-toggle-scope"
                    onClick={() => setScopeMode(scopeMode === 'inputOnly' ? 'fullPrompt' : 'inputOnly')}
                    title="Toggle between showing only the clean user description vs full prompt"
                  >
                    {scopeMode === 'inputOnly' ? 'Show Full Prompt' : 'Show Clean Description Only'}
                  </button>
                )}
                {canCopy && (
                  <button
                    type="button"
                    className="btn-copy-prominent"
                    onClick={handleCopy}
                    disabled={copyState === 'copied'}
                    title="Copy to clipboard"
                  >
                    {copyState === 'copied' && '✓ Copied to Clipboard!'}
                    {copyState === 'failed' && '✗ Copy Failed'}
                    {copyState === 'idle' && (hasExtractedScope && scopeMode === 'inputOnly' ? '📋 Copy Clean Description' : '📋 Copy Clean Rewrite')}
                  </button>
                )}
              </div>
            </div>
            <div className="diff-card-body">
              <pre className="clean-rewrite-pre">{displayRewriteText}</pre>
            </div>
          </div>
        </div>
      ) : (
        /* Full Diff with Legend */
        <>
          <div className="diff-legend" style={{ marginBottom: '6px' }}>
            <span className="legend-item">
              <span className="legend-swatch swatch-deleted" /> Removed
            </span>
            <span className="legend-item">
              <span className="legend-swatch swatch-added" /> Updated
            </span>
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
        </>
      )}
    </div>
  );
}
