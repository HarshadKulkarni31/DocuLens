import React, { useState, useEffect } from 'react';
import { Sparkles, RefreshCw, Copy, Check, AlertCircle } from 'lucide-react';
import { api } from '../services/api';
import FormattedText from './FormattedText';

export default function SummaryPanel({ activeDoc, onError }) {
  const [summaryData, setSummaryData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(null);
  const [refreshCount, setRefreshCount] = useState(0);

  useEffect(() => {
    let ignore = false;
    const controller = new AbortController();

    async function loadSummary() {
      if (!activeDoc?.document_id) return;
      setLoading(true);
      setError(null);

      try {
        const data = await api.getSummary(activeDoc.document_id, controller.signal);
        if (!ignore) {
          setSummaryData(data);
        }
      } catch (err) {
        if (!ignore && err.name !== 'AbortError') {
          setError(err.message || 'Failed to generate summary.');
          if (onError) onError(err.message);
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    loadSummary();

    return () => {
      ignore = true;
      controller.abort();
    };
  }, [activeDoc?.document_id, refreshCount, onError]);

  const handleCopy = () => {
    if (!summaryData) return;
    const textToCopy = `${summaryData.summary}\n\nKey Takeaways:\n${summaryData.key_points
      .map((p) => `• ${p}`)
      .join('\n')}`;
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleRegenerate = () => {
    setRefreshCount((c) => c + 1);
  };

  if (!activeDoc) {
    return (
      <div className="panel-empty-state">
        <Sparkles size={36} className="empty-icon" />
        <p>Upload a document to view an AI-generated executive summary and key findings.</p>
      </div>
    );
  }

  return (
    <div className="summary-card">
      <div className="summary-header">
        <div className="header-title">
          <Sparkles size={18} className="sparkle-icon" />
          <h3>Executive Summary</h3>
        </div>
        <div className="header-actions">
          {summaryData && (
            <button type="button" className="icon-btn" onClick={handleCopy} title="Copy summary">
              {copied ? <Check size={16} className="text-green" /> : <Copy size={16} />}
              <span>{copied ? 'Copied' : 'Copy'}</span>
            </button>
          )}
          <button
            type="button"
            className="icon-btn"
            onClick={handleRegenerate}
            disabled={loading}
            title="Regenerate summary"
          >
            <RefreshCw size={16} className={loading ? 'spin' : ''} />
            <span>Regenerate</span>
          </button>
        </div>
      </div>

      {loading && (
        <div className="summary-loading">
          <div className="skeleton-line full"></div>
          <div className="skeleton-line half"></div>
          <div className="skeleton-line full"></div>
          <p className="loading-label">Synthesizing document insights with Gemini...</p>
        </div>
      )}

      {error && !loading && (
        <div className="summary-error">
          <AlertCircle size={20} />
          <div>
            <p className="error-text">
              {error.includes('rate limit') || error.includes('quota') || error.includes('429')
                ? 'Gemini free-tier rate limit reached. Please wait a few moments and click retry.'
                : error}
            </p>
            <button type="button" className="retry-link" onClick={handleRegenerate}>
              Click to retry
            </button>
          </div>
        </div>
      )}

      {summaryData && !loading && (
        <div className="summary-content">
          <div className="summary-text">
            <FormattedText text={summaryData.summary} />
          </div>

          {summaryData.key_points && summaryData.key_points.length > 0 && (
            <div className="key-points-section">
              <h4>Key Findings & Insights</h4>
              <ul className="key-points-list">
                {summaryData.key_points.map((point, idx) => (
                  <li key={idx}>
                    <span className="bullet-point"></span>
                    <FormattedText text={point} />
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
