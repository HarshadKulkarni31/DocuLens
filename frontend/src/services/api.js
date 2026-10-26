const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

/**
 * Helper to handle fetch responses and parse error messages
 */
async function handleResponse(response) {
  if (!response.ok) {
    let errorDetail = `Error ${response.status}: ${response.statusText}`;
    try {
      const data = await response.json();
      if (data && data.detail) {
        errorDetail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      // response wasn't JSON
    }
    const error = new Error(errorDetail);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

/**
 * Wraps fetch to provide human-friendly error messages on network failure
 */
async function safeFetch(url, options = {}) {
  try {
    return await fetch(url, options);
  } catch (err) {
    if (err.name === 'AbortError') {
      throw err;
    }
    throw new Error(
      'Unable to connect to the DocuLens server. Please ensure the backend is running at http://127.0.0.1:8000.'
    );
  }
}

export const api = {
  /**
   * Health check
   */
  async checkHealth() {
    try {
      const res = await safeFetch(`${API_BASE}/health`);
      return await handleResponse(res);
    } catch (err) {
      return { status: 'unreachable', error: err.message };
    }
  },

  /**
   * List all persisted documents from SQLite
   */
  async getDocuments(signal) {
    const res = await safeFetch(`${API_BASE}/documents`, { signal });
    return await handleResponse(res);
  },

  /**
   * Upload and index PDF
   */
  async uploadDocument(file, signal) {
    const formData = new FormData();
    formData.append('file', file);

    const res = await safeFetch(`${API_BASE}/documents`, {
      method: 'POST',
      body: formData,
      signal,
    });
    return await handleResponse(res);
  },

  /**
   * Extract text only
   */
  async extractDocument(file, signal) {
    const formData = new FormData();
    formData.append('file', file);

    const res = await safeFetch(`${API_BASE}/documents/extract`, {
      method: 'POST',
      body: formData,
      signal,
    });
    return await handleResponse(res);
  },

  /**
   * Get document summary
   */
  async getSummary(documentId, signal) {
    const res = await safeFetch(`${API_BASE}/documents/${documentId}/summary`, {
      method: 'POST',
      signal,
    });
    return await handleResponse(res);
  },

  /**
   * Ask question grounded in document context (non-streaming)
   */
  async askQuestion(documentId, question, history = [], signal) {
    const res = await safeFetch(`${API_BASE}/documents/${documentId}/ask`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ question, history }),
      signal,
    });
    return await handleResponse(res);
  },

  /**
   * Ask question with real-time SSE streaming
   */
  async askQuestionStream(documentId, question, history = [], { onSources, onToken, onDone, onError, signal }) {
    const response = await safeFetch(`${API_BASE}/documents/${documentId}/ask/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ question, history }),
      signal,
    });

    if (!response.ok) {
      let errorDetail = `Error ${response.status}: ${response.statusText}`;
      try {
        const data = await response.json();
        if (data && data.detail) errorDetail = data.detail;
      } catch {}
      throw new Error(errorDetail);
    }

    if (!response.body) {
      throw new Error('ReadableStream not supported by this browser.');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        for (const part of parts) {
          if (!part.trim()) continue;
          const lines = part.split('\n');
          let eventType = 'message';
          let dataText = '';

          for (const line of lines) {
            if (line.startsWith('event:')) {
              eventType = line.slice(6).trim();
            } else if (line.startsWith('data:')) {
              dataText += line.slice(5).trim();
            }
          }

          if (dataText) {
            try {
              const parsed = JSON.parse(dataText);
              if (eventType === 'sources' && onSources) {
                onSources(parsed);
              } else if (eventType === 'token' && onToken) {
                onToken(parsed);
              } else if (eventType === 'error') {
                if (onError) onError(new Error(parsed.error || 'Streaming error'));
              } else if (eventType === 'done' && onDone) {
                onDone();
              }
            } catch (err) {
              console.warn('Failed to parse SSE JSON:', err, dataText);
            }
          }
        }
      }
    } finally {
      if (onDone) onDone();
    }
  },

  /**
   * Delete document from persistent storage
   */
  async deleteDocument(documentId) {
    const res = await safeFetch(`${API_BASE}/documents/${documentId}`, {
      method: 'DELETE',
    });
    return await handleResponse(res);
  },
};
