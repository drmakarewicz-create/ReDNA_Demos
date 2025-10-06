'use client';

/**
 * Head Coach Conversation Panel (HC v2 Sprint 1c)
 *
 * Displays recent conversation history and allows user to send messages.
 *
 * Features:
 * - Recent 30 messages from conversation history
 * - Input box + Send button
 * - Message bubbles with role (user/assistant)
 * - Provenance tooltip on hover for task-linked messages
 * - Auto-scroll to bottom on new messages
 */

import { useEffect, useState, useRef } from 'react';

interface ConversationMessage {
  ts: string;
  role: 'user' | 'assistant';
  content: string;
  task_id?: string;
  provenance?: {
    source?: string;
    reason?: string;
    [key: string]: any;
  };
}

interface HCConversationProps {
  userId: string;
  className?: string;
}

export function HCConversation({ userId, className = '' }: HCConversationProps) {
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchHistory();
  }, [userId]);

  useEffect(() => {
    // Auto-scroll to bottom when messages change
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function fetchHistory() {
    setLoading(true);
    try {
      const response = await fetch(`/api/hc/conversation/history?userId=${encodeURIComponent(userId)}&limit=30`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      setMessages(data.messages || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch conversation');
    } finally {
      setLoading(false);
    }
  }

  async function handleSend() {
    if (!inputMessage.trim() || sending) return;

    const userMessage = inputMessage.trim();
    setInputMessage('');
    setSending(true);

    try {
      const response = await fetch(`/api/hc/say?userId=${encodeURIComponent(userId)}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMessage,
          role: 'user',
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      // Refresh conversation after sending
      await fetchHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message');
      // Restore message on error
      setInputMessage(userMessage);
    } finally {
      setSending(false);
    }
  }

  function handleKeyPress(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function formatTimestamp(ts: string) {
    try {
      const date = new Date(ts);
      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
      });
    } catch {
      return ts;
    }
  }

  if (loading) {
    return (
      <section className={`rounded-2xl border border-slate-800 bg-slate-950/60 p-4 shadow-sm ${className}`}>
        <p className="text-sm text-slate-400">Loading conversation...</p>
      </section>
    );
  }

  return (
    <section className={`flex h-[600px] flex-col rounded-2xl border border-slate-800 bg-slate-950/60 p-4 shadow-sm ${className}`}>
      {/* Header */}
      <header className="flex flex-shrink-0 items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Conversation</h2>
          <p className="text-xs text-slate-500">{messages.length} messages</p>
        </div>
        <button
          type="button"
          onClick={fetchHistory}
          className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 transition hover:border-slate-500 hover:text-slate-100"
          title="Refresh"
        >
          ↻
        </button>
      </header>

      {error && (
        <div className="mt-3 flex-shrink-0 rounded-lg border border-red-800 bg-red-950/40 p-2">
          <p className="text-xs text-red-300">{error}</p>
        </div>
      )}

      {/* Messages - scrollable area */}
      <div className="mt-4 flex-1 space-y-2 overflow-y-auto">
        {messages.length === 0 ? (
          <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4 text-center">
            <p className="text-sm text-slate-400">No messages yet</p>
            <p className="mt-1 text-xs text-slate-500">Start a conversation with your Head Coach</p>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div
              key={idx}
              className={`rounded-lg border p-2 ${
                msg.role === 'user'
                  ? 'border-blue-800/50 bg-blue-950/20'
                  : 'border-green-800/50 bg-green-950/20'
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs font-semibold uppercase ${
                        msg.role === 'user' ? 'text-blue-300' : 'text-green-300'
                      }`}
                    >
                      {msg.role}
                    </span>
                    {msg.task_id && (
                      <span
                        className="cursor-help rounded border border-purple-700 bg-purple-950/40 px-1 py-0.5 text-xs text-purple-300"
                        title={`Task: ${msg.task_id}${msg.provenance?.reason ? ` · ${msg.provenance.reason}` : ''}`}
                      >
                        task
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-sm text-slate-200">{msg.content}</p>
                  <p className="mt-1 text-xs text-slate-500">{formatTimestamp(msg.ts)}</p>
                </div>
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input - fixed at bottom */}
      <div className="mt-4 flex flex-shrink-0 gap-2">
        <input
          type="text"
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Ask your Head Coach..."
          disabled={sending}
          className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 transition focus:border-slate-500 focus:outline-none disabled:border-slate-800 disabled:bg-slate-950/40 disabled:text-slate-600"
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={!inputMessage.trim() || sending}
          className="rounded-lg border border-cyan-700 bg-cyan-950/40 px-4 py-2 text-sm font-medium text-cyan-300 transition hover:border-cyan-500 hover:text-cyan-100 disabled:border-slate-800 disabled:bg-slate-950/40 disabled:text-slate-600"
        >
          {sending ? 'Sending...' : 'Send'}
        </button>
      </div>
    </section>
  );
}
