import React, { useState, useEffect, useRef } from 'react';
import SuggestionView from './SuggestionView';
import { fetchRequestDetail, fetchSuggestions, triggerSuggestion } from '../api';
import { FLAG_TYPE_LABELS, SEVERITY_COLORS, getPlainEnglishFlagExplanation } from '../labels';

export default function FlagDetail({ flag, onClose, onSuggestionGenerated }) {
  const [requestData, setRequestData] = useState({ data: null, loading: true, error: null });
  const [suggestionData, setSuggestionData] = useState({ data: null, loading: true, error: null });
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState(null);

  // Ref tracking current flag id to discard POST response if flag changed
  const currentFlagIdRef = useRef(flag.id);
  currentFlagIdRef.current = flag.id;

  // Esc key listener
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // Load Request details
  useEffect(() => {
    const controller = new AbortController();
    setRequestData({ data: null, loading: true, error: null });

    fetchRequestDetail(flag.request_id, controller.signal)
      .then(data => setRequestData({ data, loading: false, error: null }))
      .catch(err => {
        if (err.name === 'AbortError') return;
        setRequestData({ data: null, loading: false, error: err.message });
      });

    return () => controller.abort();
  }, [flag.request_id]);

  // Load existing suggestion for this flag
  useEffect(() => {
    const controller = new AbortController();
    setSuggestionData({ data: null, loading: true, error: null });

    fetchSuggestions({ flag_id: flag.id }, controller.signal)
      .then(res => {
        const existing = res.items && res.items.length > 0 ? res.items[0] : null;
        setSuggestionData({ data: existing, loading: false, error: null });
      })
      .catch(err => {
        if (err.name === 'AbortError') return;
        setSuggestionData({ data: null, loading: false, error: err.message });
      });

    return () => controller.abort();
  }, [flag.id]);

  // Handle Generate / Regenerate
  const handleAction = async () => {
    const currentSug = suggestionData.data;
    let regenerate = false;

    if (currentSug) {
      const { status, method } = currentSug;
      if (status === 'disabled' || status === 'failed') {
        regenerate = false;
      } else if (method === 'llm_rewrite' && (status === 'ok' || status === 'not_verified_safe')) {
        const confirmed = window.confirm("Regenerating will call the optimizer model again and consume API quota. Continue?");
        if (!confirmed) return;
        regenerate = true;
      } else {
        // rule_based or no_change
        regenerate = true;
      }
    }

    setActionLoading(true);
    setActionError(null);

    const targetFlagId = flag.id;

    try {
      // POST is NOT aborted to ensure server batching completes
      const newSug = await triggerSuggestion(targetFlagId, regenerate);
      if (currentFlagIdRef.current === targetFlagId) {
        setSuggestionData({ data: newSug, loading: false, error: null });
      }
      if (onSuggestionGenerated) {
        onSuggestionGenerated();
      }
    } catch (err) {
      if (currentFlagIdRef.current === targetFlagId) {
        setActionError(err.message);
      }
    } finally {
      if (currentFlagIdRef.current === targetFlagId) {
        setActionLoading(false);
      }
    }
  };

  // Determine button label
  let buttonLabel = "Generate suggestion";
  if (suggestionData.data) {
    const { status, method } = suggestionData.data;
    if (status === 'failed') {
      buttonLabel = "Retry";
    } else if (status === 'disabled') {
      buttonLabel = "Generate";
    } else {
      buttonLabel = "Regenerate";
    }
  }

  const sevColor = SEVERITY_COLORS[flag.severity] || SEVERITY_COLORS.low;
  const originalPromptText = requestData.data?.prompt_text || flag.prompt_preview || "";

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="header-tags">
            <span 
              className="badge" 
              style={{ backgroundColor: sevColor.bg, color: sevColor.text, borderColor: sevColor.border }}
            >
              {flag.severity.toUpperCase()}
            </span>
            <h3>{FLAG_TYPE_LABELS[flag.flag_type] || flag.flag_type}</h3>
          </div>
          <button type="button" className="close-btn" onClick={onClose}>&times;</button>
        </div>

        <div className="modal-content">
          {/* Explanation Banner */}
          <div className="detail-explanation-card">
            <h4>Why this was flagged</h4>
            <p>{getPlainEnglishFlagExplanation(flag)}</p>
          </div>

          {/* Action Row */}
          <div className="suggestion-action-row">
            <div>
              <h4>Prompt Shortening & Optimization</h4>
              <p className="text-muted-sm">
                {flag.flag_type === 'verbose_for_template' 
                  ? "Uses the configured optimizer model to safely shorten the prompt." 
                  : "Uses deterministic rules to remove duplicate sentences and formatting bloat."}
              </p>
            </div>
            <button 
              type="button" 
              className="btn btn-primary"
              onClick={handleAction}
              disabled={actionLoading || suggestionData.loading}
            >
              {actionLoading ? "Processing..." : buttonLabel}
            </button>
          </div>

          {actionError && (
            <div className="state-box error-box">
              <p>Failed to generate suggestion: {actionError}</p>
            </div>
          )}

          {/* Suggestion view if available */}
          {suggestionData.loading ? (
            <div className="state-box">Loading suggestion status...</div>
          ) : (
            <SuggestionView 
              suggestion={suggestionData.data} 
              originalPromptText={originalPromptText} 
            />
          )}
        </div>
      </div>
    </div>
  );
}
