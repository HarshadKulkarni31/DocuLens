import React, { useState, useEffect } from 'react';
import { Layers, FileSearch, Sparkles, MessageSquare, AlertCircle, ShieldCheck } from 'lucide-react';
import UploadPanel from '../components/UploadPanel';
import SummaryPanel from '../components/SummaryPanel';
import ChatPanel from '../components/ChatPanel';
import { api } from '../services/api';

export default function Home() {
  const [activeDoc, setActiveDoc] = useState(null);
  const [activeTab, setActiveTab] = useState('chat'); // 'summary' or 'chat'
  const [errorMessage, setErrorMessage] = useState(null);
  const [apiStatus, setApiStatus] = useState('checking'); // 'connected', 'error', 'checking'

  useEffect(() => {
    const checkBackend = async () => {
      try {
        const health = await api.checkHealth();
        if (health && health.status === 'healthy') {
          setApiStatus('connected');
        } else {
          setApiStatus('error');
        }
      } catch {
        setApiStatus('error');
      }
    };
    checkBackend();
  }, []);

  const handleReset = () => {
    setActiveDoc(null);
    setErrorMessage(null);
  };

  return (
    <div className="doculens-app">
      {/* Top Navbar */}
      <header className="app-header">
        <div className="header-container">
          <div className="brand-group">
            <div className="logo-icon-wrapper">
              <FileSearch size={24} className="brand-icon" />
            </div>
            <div>
              <div className="brand-title-row">
                <h1 className="brand-name">DocuLens</h1>
                <span className="platform-tag">AI Document Intelligence</span>
              </div>
              <p className="brand-subtitle">
                Context-grounded RAG with page citations & Gemini summarization
              </p>
            </div>
          </div>

          <div className="system-status">
            {apiStatus === 'connected' ? (
              <div className="status-indicator online" title="Backend API is running and connected">
                <span className="status-dot"></span>
                <span>FastAPI + FAISS Online</span>
              </div>
            ) : apiStatus === 'checking' ? (
              <div className="status-indicator checking">
                <span className="status-dot"></span>
                <span>Connecting...</span>
              </div>
            ) : (
              <div className="status-indicator offline" title="Could not connect to FastAPI server at /api">
                <span className="status-dot"></span>
                <span>Backend Offline</span>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="main-content">
        {errorMessage && (
          <div className="global-error-banner">
            <AlertCircle size={20} className="error-icon" />
            <div className="error-details">
              <strong>Error:</strong> {errorMessage}
            </div>
            <button className="dismiss-btn" onClick={() => setErrorMessage(null)}>
              ✕
            </button>
          </div>
        )}

        {/* Upload & Document Header Section */}
        <UploadPanel
          activeDoc={activeDoc}
          setActiveDoc={(doc) => {
            setActiveDoc(doc);
            setErrorMessage(null);
          }}
          onError={(msg) => setErrorMessage(msg)}
          clearError={() => setErrorMessage(null)}
          onReset={handleReset}
        />

        {/* Workspace Panels (Summary + Q&A) */}
        {activeDoc && (
          <div className="workspace-container">
            {/* Tab switchers for tablet / mobile or flexible toggle */}
            <div className="tab-navigation">
              <button
                className={`tab-btn ${activeTab === 'chat' ? 'active' : ''}`}
                onClick={() => setActiveTab('chat')}
              >
                <MessageSquare size={16} />
                <span>Ask DocuLens (RAG)</span>
              </button>
              <button
                className={`tab-btn ${activeTab === 'summary' ? 'active' : ''}`}
                onClick={() => setActiveTab('summary')}
              >
                <Sparkles size={16} />
                <span>Executive Summary</span>
              </button>
            </div>

            {/* Content view: Desktop side-by-side or Tabbed */}
            <div className="panels-grid">
              <div className={`panel-col ${activeTab !== 'summary' ? 'hidden-on-mobile' : ''}`}>
                <SummaryPanel
                  activeDoc={activeDoc}
                  onError={(msg) => setErrorMessage(msg)}
                />
              </div>

              <div className={`panel-col ${activeTab !== 'chat' ? 'hidden-on-mobile' : ''}`}>
                <ChatPanel
                  activeDoc={activeDoc}
                  onError={(msg) => setErrorMessage(msg)}
                />
              </div>
            </div>
          </div>
        )}

        {/* Workflow Hints when no document is uploaded */}
        {!activeDoc && (
          <div className="features-preview">
            <div className="feature-item">
              <div className="feat-icon-wrap">
                <Layers size={20} />
              </div>
              <h4>1. Page-Aware Chunking</h4>
              <p>PyMuPDF preserves 1-based page coordinates across sentences and paragraphs.</p>
            </div>
            <div className="feature-item">
              <div className="feat-icon-wrap">
                <FileSearch size={20} />
              </div>
              <h4>2. FAISS Similarity Search</h4>
              <p>Sentence Transformers embedding model indexes document vectors for high-precision retrieval.</p>
            </div>
            <div className="feature-item">
              <div className="feat-icon-wrap">
                <ShieldCheck size={20} />
              </div>
              <h4>3. Grounded Verification</h4>
              <p>Gemini generates answers strictly from retrieved passages, citing exact source pages.</p>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="app-footer">
        <p>DocuLens • End-to-End AI Document Intelligence Platform</p>
      </footer>
    </div>
  );
}
