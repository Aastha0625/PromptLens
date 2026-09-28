import React, { useEffect, useState } from 'react';
import { fetchRequestDetail } from '../api';
import { formatCost, formatLatency, formatNumber, formatDate } from '../format';

export default function RequestDetail({ id, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Esc key listener
  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  // Fetch logic with abort controller
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    
    fetchRequestDetail(id, controller.signal)
      .then(res => {
        setData(res);
        setLoading(false);
      })
      .catch(err => {
        if (err.name === 'AbortError') return;
        setError(err.message);
        setLoading(false);
      });

    return () => controller.abort();
  }, [id]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <button className="close-button" onClick={onClose}>&times;</button>
        
        <h2>Request Details</h2>
        
        {loading && <div className="loading state-box">Loading details...</div>}
        
        {error && (
          <div className="error-box">
            <p>Failed to load: {error}</p>
            <button onClick={() => {
              setError(null);
              setLoading(true);
              fetchRequestDetail(id).then(setData).catch(e => setError(e.message)).finally(() => setLoading(false));
            }}>Retry</button>
          </div>
        )}
        
        {data && !loading && !error && (
          <div className="detail-grid">
            <div className="detail-item">
              <label>Time</label>
              <span>{formatDate(data.created_at)}</span>
            </div>
            <div className="detail-item">
              <label>Provider</label>
              <span>{data.provider}</span>
            </div>
            <div className="detail-item">
              <label>Model</label>
              <span>{data.model}</span>
            </div>
            <div className="detail-item">
              <label>Status</label>
              <span>{data.status_code}</span>
            </div>
            <div className="detail-item">
              <label>Latency</label>
              <span>{formatLatency(data.latency_ms)}</span>
            </div>
            <div className="detail-item">
              <label>Cost</label>
              <span>{formatCost(data.cost_usd)}</span>
            </div>
            <div className="detail-item">
              <label>Tokens (In / Out / Total)</label>
              <span>{formatNumber(data.input_tokens)} / {formatNumber(data.output_tokens)} / {formatNumber(data.total_tokens)}</span>
            </div>
            
            {data.error && (
              <div className="detail-full red">
                <label>Error Message</label>
                <pre>{data.error}</pre>
              </div>
            )}
            
            <div className="detail-full">
              <label>Prompt</label>
              <pre>{data.prompt_text || "No prompt logged."}</pre>
            </div>
            
            <div className="detail-full">
              <label>Reply</label>
              <pre>{data.reply_text || "No reply logged."}</pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
