import React, { useState } from 'react';
import { BookOpen, ChevronDown, ChevronUp } from 'lucide-react';

export default function SourceList({ sources }) {
  const [expanded, setExpanded] = useState(false);

  if (!sources || sources.length === 0) {
    return null;
  }

  return (
    <div className="source-list-container">
      <button
        type="button"
        className="source-list-header"
        onClick={() => setExpanded((prev) => !prev)}
        aria-expanded={expanded}
      >
        <div className="source-list-title">
          <BookOpen size={16} className="source-icon" />
          <span>
            {sources.length} Referenced Source{sources.length > 1 ? 's' : ''} (Verified from document)
          </span>
        </div>
        <div className="expand-indicator">
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </button>

      {expanded && (
        <div className="source-cards">
          {sources.map((src, index) => (
            <div key={src.chunk_id || index} className="source-card">
              <div className="source-badge">
                <span className="page-chip">Page {src.page_number}</span>
                <span className="chunk-id-tag">ID: {src.chunk_id}</span>
              </div>
              <p className="source-excerpt">"{src.excerpt}"</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
