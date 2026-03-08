'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  createConversation,
  getConversation,
  sendConversationMessage,
  type Conversation,
} from '@/lib/api';

const STORAGE_KEY = 'property_search_conversation_id';

export default function CopilotPage() {
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const messageCount = useMemo(() => conversation?.messages?.length ?? 0, [conversation]);

  useEffect(() => {
    const boot = async () => {
      setLoading(true);
      setError(null);

      try {
        const savedConversationId = window.localStorage.getItem(STORAGE_KEY);
        if (savedConversationId) {
          const existing = await getConversation(savedConversationId);
          setConversation(existing);
          return;
        }

        const userIdentifier = window.navigator.userAgent || 'web-user';
        const created = await createConversation(userIdentifier, 'Property Assistant Session');
        window.localStorage.setItem(STORAGE_KEY, created.id);
        setConversation(created);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to initialize conversation');
      } finally {
        setLoading(false);
      }
    };

    boot().catch(console.error);
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!conversation || !input.trim() || sending) {
      return;
    }

    setSending(true);
    setError(null);

    try {
      await sendConversationMessage(conversation.id, input.trim());
      const updated = await getConversation(conversation.id);
      setConversation(updated);
      setInput('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to send message');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto h-[calc(100vh-52px)] flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Copilot Chat</h1>
        <p className="text-sm text-[var(--muted)]">{messageCount} messages</p>
      </div>

      <div className="flex-1 bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4 overflow-y-auto">
        {loading && <p className="text-[var(--muted)]">Loading conversation...</p>}

        {!loading && !conversation && (
          <p className="text-red-400">Unable to load chat conversation.</p>
        )}

        {!loading && conversation && conversation.messages.length === 0 && (
          <p className="text-[var(--muted)]">
            Ask about locations, pricing strategy, market trends, BER upgrades, or grant eligibility.
          </p>
        )}

        {!loading && conversation && (
          <div className="space-y-3">
            {conversation.messages.map((message) => (
              <div
                key={message.id}
                className={[
                  'rounded-md p-3 border',
                  message.role === 'user'
                    ? 'bg-neutral-900 border-neutral-700 ml-8'
                    : 'bg-neutral-950 border-neutral-800 mr-8',
                ].join(' ')}
              >
                <p className="text-xs uppercase tracking-wide text-[var(--muted)] mb-1">
                  {message.role}
                </p>
                <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask Copilot about this market..."
          className="flex-1 bg-[var(--card-bg)] border border-[var(--card-border)] rounded px-3 py-2"
          disabled={loading || sending || !conversation}
        />
        <button
          type="submit"
          disabled={loading || sending || !conversation || !input.trim()}
          className="px-4 py-2 bg-brand-600 hover:bg-brand-700 disabled:opacity-60 rounded text-sm font-medium transition-colors"
        >
          {sending ? 'Sending...' : 'Send'}
        </button>
      </form>

      {error && <p className="text-sm text-red-400">{error}</p>}
    </div>
  );
}
