import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Send, MessageSquare, Bot, User, Trash2, HelpCircle, Loader2, Download } from 'lucide-react';
import { api } from '../services/api';
import SourceList from './SourceList';
import FormattedText from './FormattedText';

const SAMPLE_PROMPTS = [
  "What is the main purpose or objective of this document?",
  "What key findings, conclusions, or recommendations are stated?",
  "Are there specific metrics, dates, or methodologies mentioned?",
  "What limitations or risks are discussed?",
];

export default function ChatPanel({ activeDoc, onError }) {
  const [messages, setMessages] = useState(() => {
    if (!activeDoc) return [];
    return [
      {
        id: `welcome-${activeDoc.document_id}`,
        sender: 'assistant',
        text: `Document **${activeDoc.filename}** loaded with ${activeDoc.page_count} pages and indexed into ${activeDoc.chunk_count} vector chunks. Ask me any question grounded in its content!`,
        sources: [],
      },
    ];
  });
  const [inputQuery, setInputQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const abortControllerRef = useRef(null);

  // Auto scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Clean up in-flight requests on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const handleSend = useCallback(
    async (queryText) => {
      const query = (queryText !== undefined ? queryText : inputQuery).trim();
      if (!query || isLoading || !activeDoc?.document_id) return;

      if (query.length < 2) {
        if (onError) onError('Please enter a question with at least 2 characters.');
        return;
      }

      const msgId = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : String(Math.random());
      const userMessage = {
        id: `user-${msgId}`,
        sender: 'user',
        text: query,
      };

      // Assistant placeholder for streaming
      const assistantId = `assistant-${typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : String(Math.random())}`;
      const assistantPlaceholder = {
        id: assistantId,
        sender: 'assistant',
        text: '',
        sources: [],
        isStreaming: true,
      };

      // Prepare multi-turn history from preceding messages
      const historyPayload = messages
        .filter((m) => !m.isError && !m.id.startsWith('welcome-'))
        .map((m) => ({
          role: m.sender === 'user' ? 'user' : 'assistant',
          content: m.text,
        }));

      setMessages((prev) => [...prev, userMessage, assistantPlaceholder]);
      setInputQuery('');
      setIsLoading(true);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        // Attempt real-time SSE streaming
        await api.askQuestionStream(
          activeDoc.document_id,
          query,
          historyPayload,
          {
            onSources: (sources) => {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantId ? { ...msg, sources: sources || [] } : msg
                )
              );
            },
            onToken: (token) => {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantId ? { ...msg, text: msg.text + token } : msg
                )
              );
            },
            onDone: () => {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantId ? { ...msg, isStreaming: false } : msg
                )
              );
            },
            onError: (err) => {
              throw err;
            },
            signal: controller.signal,
          }
        );
      } catch (err) {
        if (err.name === 'AbortError') return;

        // Fallback to standard non-streaming request if stream is unavailable
        try {
          const fallbackRes = await api.askQuestion(
            activeDoc.document_id,
            query,
            historyPayload,
            controller.signal
          );
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? {
                    ...msg,
                    text: fallbackRes.answer,
                    sources: fallbackRes.sources || [],
                    isStreaming: false,
                  }
                : msg
            )
          );
        } catch (fallbackErr) {
          if (fallbackErr.name === 'AbortError') return;
          const errDetail = fallbackErr.message || err.message || 'Unable to retrieve answer from document.';
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? {
                    ...msg,
                    isError: true,
                    text: `Error: ${errDetail}`,
                    isStreaming: false,
                  }
                : msg
            )
          );
          if (onError) onError(errDetail);
        }
      } finally {
        setIsLoading(false);
      }
    },
    [activeDoc, inputQuery, isLoading, messages, onError]
  );

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const clearHistory = () => {
    setMessages([]);
  };

  const handleExportChat = () => {
    if (messages.length <= 1) return;
    const dateStr = new Date().toLocaleDateString();
    let md = `# DocuLens Q&A Transcript\n\n`;
    md += `**Document:** ${activeDoc?.filename || 'Document'}\n`;
    md += `**Date:** ${dateStr}\n\n---\n\n`;

    messages.forEach((m) => {
      if (m.id.startsWith('welcome-') || m.isError) return;
      if (m.sender === 'user') {
        md += `### 👤 Question\n${m.text}\n\n`;
      } else {
        md += `### 🤖 Grounded Answer\n${m.text}\n\n`;
        if (m.sources && m.sources.length > 0) {
          md += `*Sources:*\n`;
          m.sources.forEach((s) => {
            md += `- **Page ${s.page_number}**: "${s.excerpt}"\n`;
          });
          md += `\n`;
        }
        md += `---\n\n`;
      }
    });

    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `doculens-chat-${activeDoc?.filename ? activeDoc.filename.replace(/\.pdf$/i, '') : 'export'}.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (!activeDoc) {
    return (
      <div className="panel-empty-state">
        <MessageSquare size={36} className="empty-icon" />
        <p>Upload a document above to ask questions with verified source citations.</p>
      </div>
    );
  }

  return (
    <div className="chat-card">
      <div className="chat-header">
        <div className="header-title">
          <MessageSquare size={18} className="chat-icon" />
          <h3>Ask DocuLens</h3>
          <span className="rag-badge">Streaming RAG</span>
        </div>
        <div className="header-actions">
          {messages.length > 1 && (
            <button
              type="button"
              className="icon-btn"
              onClick={handleExportChat}
              title="Export chat as Markdown"
            >
              <Download size={15} />
              <span>Export</span>
            </button>
          )}
          {messages.length > 1 && (
            <button type="button" className="icon-btn" onClick={clearHistory} title="Clear conversation">
              <Trash2 size={15} />
              <span>Clear</span>
            </button>
          )}
        </div>
      </div>

      <div className="chat-messages">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`message-bubble ${msg.sender === 'user' ? 'user-msg' : 'assistant-msg'} ${
              msg.isError ? 'error-msg' : ''
            }`}
          >
            <div className="msg-avatar">
              {msg.sender === 'user' ? <User size={16} /> : <Bot size={16} />}
            </div>
            <div className="msg-body">
              {msg.text ? (
                <FormattedText text={msg.text} className="msg-text" />
              ) : (
                <div className="streaming-cursor-wrap">
                  <span className="streaming-cursor"></span>
                </div>
              )}
              {msg.sources && msg.sources.length > 0 && <SourceList sources={msg.sources} />}
            </div>
          </div>
        ))}

        {isLoading && !messages[messages.length - 1]?.isStreaming && (
          <div className="message-bubble assistant-msg loading-bubble">
            <div className="msg-avatar">
              <Bot size={16} />
            </div>
            <div className="msg-body">
              <div className="typing-indicator">
                <Loader2 size={18} className="spin" />
                <span>Searching vector index & retrieving passages...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {messages.length <= 1 && !isLoading && (
        <div className="suggested-prompts">
          <div className="suggested-title">
            <HelpCircle size={14} />
            <span>Suggested Questions:</span>
          </div>
          <div className="prompt-chips">
            {SAMPLE_PROMPTS.map((prompt, idx) => (
              <button
                type="button"
                key={idx}
                className="prompt-chip"
                onClick={() => handleSend(prompt)}
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="chat-input-bar">
        <textarea
          rows={1}
          value={inputQuery}
          onChange={(e) => setInputQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question or follow-up (Enter to send)..."
          disabled={isLoading}
          maxLength={500}
          aria-label="Ask a question about the document"
        />
        <button
          type="button"
          className="send-button"
          onClick={() => handleSend()}
          disabled={!inputQuery.trim() || isLoading}
          title="Send question"
          aria-label="Send question"
        >
          {isLoading ? <Loader2 size={18} className="spin" /> : <Send size={18} />}
        </button>
      </div>
    </div>
  );
}
