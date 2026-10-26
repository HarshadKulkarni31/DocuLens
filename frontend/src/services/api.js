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
   * Ask question grounded in document context
   */
  async askQuestion(documentId, question, signal) {
    const res = await safeFetch(`${API_BASE}/documents/${documentId}/ask`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ question }),
      signal,
    });
    return await handleResponse(res);
  },

  /**
   * Delete document from memory
   */
  async deleteDocument(documentId) {
    const res = await safeFetch(`${API_BASE}/documents/${documentId}`, {
      method: 'DELETE',
    });
    return await handleResponse(res);
  },
};
