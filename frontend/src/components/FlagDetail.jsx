import React, { useState, useEffect, useRef } from 'react';
import SuggestionView from './SuggestionView';
import { fetchRequestDetail, fetchSuggestions, triggerSuggestion } from '../api';
import { FLAG_TYPE_LABELS, SEVERITY_COLORS, getPlainEnglishFlagExplanation } from '../labels';

export default function FlagDetail({ flag, onClose, onSuggestionGenerated }) {
  const [requestData, setRequestData] = useState({ data: null, loading: true, error: null });
  const [suggestionData, setSuggestionData] = useState({ data: null, loading: true, error: null });
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState(null);

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
      .then((data) => setRequestData({ data, loading: false, error: null }))
      .catch((err) => {
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
      .then((res) => {
        const existing = res.items && res.items.length > 0 ? res.items[0] : null;
        setSuggestionData({ data: existing, loading: false, error: null });
      })
      .catch((err) => {
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
        const confirmed = window.confirm(
          'Regenerating will call the optimizer model again and consume API quota. Continue?'
        );
        if (!confirmed) return;
        regenerate = true;
      } else {
        regenerate = true;
      }
    }

    setActionLoading(true);
    setActionError(null);

    const targetFlagId = flag.id;

    try {
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

  const currentSug = suggestionData.data;
  let buttonLabel = 'Generate Suggestion';
  if (currentSug) {
    if (currentSug.status === 'disabled' || currentSug.status === 'failed') {
      buttonLabel = 'Retry Optimization';
    } else {
      buttonLabel = 'Regenerate Rewrite';
    }
  }

  const sevColor = SEVERITY_COLORS[flag.severity] || SEVERITY_COLORS.low;
  const originalPromptText = requestData.data?.prompt_text || flag.prompt_preview || '';

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="header-tags">
            <span
              className="badge"
              style={{
                backgroundColor: sevColor.bg,
                color: sevColor.text,
                borderColor: sevColor.border,
              }}
            >
              {flag.severity.toUpperCase()}
            </span>
            <h3>{FLAG_TYPE_LABELS[flag.flag_type] || flag.flag_type}</h3>
            <span className="api-chip" style={{ marginLeft: '6px' }}>
              Req #{flag.request_id} • {flag.provider} / {flag.model}
            </span>
          </div>
          <button type="button" className="close-btn" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>

        <div className="modal-content">
          {/* Explanation Banner */}
          <div className="detail-explanation-card">
            <h4>Audit Diagnosis</h4>
            <p>{getPlainEnglishFlagExplanation(flag)}</p>
          </div>

          {actionError && (
            <div className="state-box error-box" style={{ marginBottom: '14px' }}>
              <p>Failed to generate suggestion: {actionError}</p>
            </div>
          )}

          {/* Suggestion view if available */}
          {suggestionData.loading ? (
            <div className="state-box">Loading clean rewrite...</div>
          ) : suggestionData.data ? (
            <SuggestionView
              suggestion={suggestionData.data}
              originalPromptText={originalPromptText}
            />
          ) : (
            <div className="suggestion-action-row" style={{ marginTop: '14px' }}>
              <div>
                <h4>No rewrite generated yet</h4>
                <p className="text-muted-sm">
                  Click generate to produce an optimized, lean prompt recommendation.
                </p>
              </div>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleAction}
                disabled={actionLoading}
              >
                {actionLoading ? 'Optimizing...' : buttonLabel}
              </button>
            </div>
          )}

          {/* Secondary regenerate option if suggestion already exists */}
          {suggestionData.data && (
            <div className="detail-modal-footer">
              <span className="text-muted-sm">
                Cleaned by PromptLens optimizer engine.
              </span>
              <button
                type="button"
                className="btn btn-secondary-sm"
                onClick={handleAction}
                disabled={actionLoading}
              >
                {actionLoading ? 'Working...' : buttonLabel}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
