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

export const api = {
  /**
   * Health check
   */
  async checkHealth() {
    try {
      const res = await fetch(`${API_BASE}/health`);
      return await handleResponse(res);
    } catch (err) {
      return { status: 'unreachable', error: err.message };
    }
  },

  /**
   * Upload and index PDF
   */
  async uploadDocument(file) {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API_BASE}/documents`, {
      method: 'POST',
      body: formData,
    });
    return await handleResponse(res);
  },

  /**
   * Extract text only
   */
  async extractDocument(file) {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API_BASE}/documents/extract`, {
      method: 'POST',
      body: formData,
    });
    return await handleResponse(res);
  },

  /**
   * Get document summary
   */
  async getSummary(documentId) {
    const res = await fetch(`${API_BASE}/documents/${documentId}/summary`, {
      method: 'POST',
    });
    return await handleResponse(res);
  },

  /**
   * Ask question grounded in document context
   */
  async askQuestion(documentId, question) {
    const res = await fetch(`${API_BASE}/documents/${documentId}/ask`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ question }),
    });
    return await handleResponse(res);
  },

  /**
   * Delete document from memory
   */
  async deleteDocument(documentId) {
    const res = await fetch(`${API_BASE}/documents/${documentId}`, {
      method: 'DELETE',
    });
    return await handleResponse(res);
  },
};
