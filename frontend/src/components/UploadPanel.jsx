import React, { useState, useRef, useEffect } from 'react';
import { UploadCloud, FileText, CheckCircle2, RefreshCw, Trash2, BookOpen } from 'lucide-react';
import { api } from '../services/api';

export default function UploadPanel({
  activeDoc,
  setActiveDoc,
  onError,
  clearError,
  onReset,
}) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [savedDocs, setSavedDocs] = useState([]);
  const fileInputRef = useRef(null);

  // Load saved documents from SQLite database
  useEffect(() => {
    let ignore = false;
    async function fetchSaved() {
      try {
        const docs = await api.getDocuments();
        if (!ignore && Array.isArray(docs)) {
          setSavedDocs(docs);
        }
      } catch (err) {
        console.warn('Failed to load saved docs:', err);
      }
    }
    fetchSaved();
    return () => {
      ignore = true;
    };
  }, [activeDoc]);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      processFile(files[0]);
    }
  };

  const handleFileChange = (e) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      processFile(files[0]);
    }
    // Reset file input value so selecting the same file works again
    if (e.target) {
      e.target.value = '';
    }
  };

  const triggerFileInput = () => {
    if (fileInputRef.current && !isUploading) {
      fileInputRef.current.click();
    }
  };

  const processFile = async (file) => {
    clearError();

    // Client-side validation
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      onError('Please upload a valid PDF file (.pdf extension).');
      return;
    }

    if (file.size > 15 * 1024 * 1024) {
      onError('File size exceeds the 15MB limit.');
      return;
    }

    if (file.size === 0) {
      onError('Selected file is empty (0 bytes).');
      return;
    }

    try {
      setIsUploading(true);
      const result = await api.uploadDocument(file);
      const newDoc = {
        document_id: result.document_id,
        filename: result.filename,
        page_count: result.page_count,
        chunk_count: result.chunk_count,
        size: (file.size / (1024 * 1024)).toFixed(2) + ' MB',
      };
      setActiveDoc(newDoc);
    } catch (err) {
      onError(err.message || 'Failed to upload and index document.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleSelectSaved = (doc) => {
    clearError();
    setActiveDoc({
      document_id: doc.document_id,
      filename: doc.filename,
      page_count: doc.page_count,
      chunk_count: doc.chunk_count,
      size: doc.file_size ? (doc.file_size / (1024 * 1024)).toFixed(2) + ' MB' : 'Saved',
    });
  };

  const handleDeleteSaved = async (e, docId) => {
    e.stopPropagation();
    try {
      await api.deleteDocument(docId);
      setSavedDocs((prev) => prev.filter((d) => d.document_id !== docId));
      if (activeDoc?.document_id === docId) {
        onReset();
      }
    } catch (err) {
      onError(err.message || 'Failed to delete saved document.');
    }
  };

  const handleRemove = async () => {
    if (activeDoc?.document_id) {
      try {
        await api.deleteDocument(activeDoc.document_id);
        setSavedDocs((prev) => prev.filter((d) => d.document_id !== activeDoc.document_id));
      } catch (err) {
        console.warn('Failed to delete on backend:', err);
      }
    }
    onReset();
  };

  return (
    <div className="upload-section">
      {/* Hidden single file input for both fresh upload and document replacement */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept=".pdf,application/pdf"
        style={{ display: 'none' }}
        aria-hidden="true"
      />

      {!activeDoc ? (
        <div
          className={`dropzone ${isDragging ? 'dropzone-active' : ''} ${
            isUploading ? 'dropzone-uploading' : ''
          }`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={triggerFileInput}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              triggerFileInput();
            }
          }}
          role="button"
          tabIndex={0}
          aria-label="Upload PDF Document"
        >
          {isUploading ? (
            <div className="upload-loading">
              <div className="spinner"></div>
              <h4>Analyzing and indexing document...</h4>
              <p>Extracting text pages, generating embeddings & persisting to SQLite</p>
            </div>
          ) : (
            <div className="dropzone-content">
              <div className="icon-wrapper">
                <UploadCloud size={40} className="upload-icon" />
              </div>
              <h3 className="dropzone-title">Upload a PDF Document</h3>
              <p className="dropzone-subtitle">
                Drag and drop your file here, or <span className="highlight-text">browse</span>
              </p>
              <div className="file-constraints">
                <span>PDF up to 15MB</span> • <span>Text-based PDFs with selectable text</span>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="active-doc-card">
          <div className="doc-info-left">
            <div className="doc-icon-badge">
              <FileText size={28} className="doc-file-icon" />
            </div>
            <div className="doc-details">
              <h3 className="doc-filename" title={activeDoc.filename}>
                {activeDoc.filename}
              </h3>
              <div className="doc-metadata">
                <span className="meta-badge">{activeDoc.page_count} Pages</span>
                <span className="meta-badge">{activeDoc.chunk_count} Chunks</span>
                <span className="meta-badge">{activeDoc.size}</span>
                <span className="status-badge ready">
                  <CheckCircle2 size={13} /> Saved in Database
                </span>
              </div>
            </div>
          </div>

          <div className="doc-actions">
            <button
              type="button"
              className="action-btn secondary"
              onClick={triggerFileInput}
              disabled={isUploading}
              title="Replace current document"
            >
              <RefreshCw size={15} className={isUploading ? 'spin' : ''} />
              <span>Replace</span>
            </button>
            <button
              type="button"
              className="action-btn danger"
              onClick={handleRemove}
              disabled={isUploading}
              title="Remove document"
            >
              <Trash2 size={15} />
              <span>Remove</span>
            </button>
          </div>
        </div>
      )}

      {/* Persistent Document Library */}
      {savedDocs.length > 0 && (
        <div className="library-strip">
          <div className="flex-row items-center gap-1">
            <BookOpen size={14} className="text-muted" />
            <span className="library-label">Saved Library ({savedDocs.length}):</span>
          </div>
          <div className="library-pills">
            {savedDocs.map((doc) => (
              <div
                key={doc.document_id}
                className={`library-pill ${activeDoc?.document_id === doc.document_id ? 'active' : ''}`}
                onClick={() => handleSelectSaved(doc)}
                title={`Open ${doc.filename} (${doc.page_count} pages)`}
              >
                <FileText size={13} />
                <span className="pill-name">{doc.filename}</span>
                <span className="pill-pages">{doc.page_count}p</span>
                <button
                  type="button"
                  className="pill-del-btn"
                  onClick={(e) => handleDeleteSaved(e, doc.document_id)}
                  title="Delete from database"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
