import React, { useState, useRef, useEffect } from 'react';
import { Send, MessageSquare, Bot, User, Trash2, HelpCircle, Loader2 } from 'lucide-react';
import { api } from '../services/api';
import SourceList from './SourceList';

const SAMPLE_PROMPTS = [
  "What is the main purpose or objective of this document?",
  "What key findings, conclusions, or recommendations are stated?",
  "Are there specific metrics, dates, or methodologies mentioned?",
  "What limitations or risks are discussed?",
];

export default function ChatPanel({ activeDoc, onError }) {
  const [messages, setMessages] = useState([]);
  const [inputQuery, setInputQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // Auto scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Reset chat when document changes
  useEffect(() => {
    if (activeDoc) {
      setMessages([
        {
          id: 'welcome',
          sender: 'assistant',
          text: `Document **${activeDoc.filename}** loaded with ${activeDoc.page_count} pages and indexed into ${activeDoc.chunk_count} vector chunks. Ask me any question grounded in its content!`,
          sources: [],
        },
      ]);
    } else {
      setMessages([]);
    }
  }, [activeDoc?.document_id]);

  const handleSend = async (queryText) => {
    const query = (queryText || inputQuery).trim();
    if (!query || isLoading || !activeDoc?.document_id) return;

    const userMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: query,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputQuery('');
    setIsLoading(true);

    try {
      const response = await api.askQuestion(activeDoc.document_id, query);
      const assistantMessage = {
        id: `assistant-${Date.now()}`,
        sender: 'assistant',
        text: response.answer,
        sources: response.sources || [],
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      const errorMessage = {
        id: `err-${Date.now()}`,
        sender: 'assistant',
        isError: true,
        text: `Error: ${err.message || 'Unable to retrieve answer from document.'}`,
        sources: [],
      };
      setMessages((prev) => [...prev, errorMessage]);
      if (onError) onError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const clearHistory = () => {
    setMessages([]);
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
          <span className="rag-badge">Grounded RAG</span>
        </div>
        {messages.length > 1 && (
          <button className="icon-btn" onClick={clearHistory} title="Clear conversation">
            <Trash2 size={16} />
            <span>Clear</span>
          </button>
        )}
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
              <div className="msg-text">{msg.text}</div>
              {msg.sources && msg.sources.length > 0 && <SourceList sources={msg.sources} />}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="message-bubble assistant-msg loading-bubble">
            <div className="msg-avatar">
              <Bot size={16} />
            </div>
            <div className="msg-body">
              <div className="typing-indicator">
                <Loader2 size={18} className="spin" />
                <span>Searching vector index & grounding answer with Gemini...</span>
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
          placeholder="Ask a question about this document (Enter to send)..."
          disabled={isLoading}
          maxLength={500}
        />
        <button
          className="send-button"
          onClick={() => handleSend()}
          disabled={!inputQuery.trim() || isLoading}
          title="Send question"
        >
          {isLoading ? <Loader2 size={18} className="spin" /> : <Send size={18} />}
        </button>
      </div>
    </div>
  );
}
