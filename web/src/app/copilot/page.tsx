'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  createConversation,
  getConversation,
  sendConversationMessage,
  type Conversation,
} from '@/lib/api';

const STORAGE_KEY = 'property_search_conversation_id';
const PENDING_PROMPT_KEY = 'atlas_pending_prompt';

export default function CopilotPage() {
  const searchParams = useSearchParams();
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

  useEffect(() => {
    const queryPrompt = searchParams.get('prefill') || '';
    const localPrompt = typeof window !== 'undefined' ? window.localStorage.getItem(PENDING_PROMPT_KEY) || '' : '';
    const nextPrompt = queryPrompt || localPrompt;

    if (nextPrompt && !input) {
      setInput(nextPrompt);
    }

    if (localPrompt && typeof window !== 'undefined') {
      window.localStorage.removeItem(PENDING_PROMPT_KEY);
    }
  }, [searchParams, input]);

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
    <div className="p-6 max-w-6xl mx-auto h-[calc(100vh-52px)] flex flex-col gap-4 rise-in">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--muted)]">Decision Copilot</p>
          <h1 className="text-2xl font-bold">Talk to Atlas AI</h1>
        </div>
        <p className="text-sm text-[var(--muted)]">{messageCount} messages</p>
      </div>

      {input ? (
        <div className="rounded-md border border-[var(--card-border)] bg-[var(--card-bg)] px-3 py-2 text-xs text-[var(--muted)]">
          Mission context loaded. Edit the prompt before sending if needed.
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2 text-xs">
        <button type="button" onClick={() => setInput('Find 3 counties with best value under EUR500k and explain why.')} className="px-3 py-1.5 rounded-full border border-[var(--card-border)] bg-[var(--card-bg)] hover:border-[var(--accent)]">County strategy</button>
        <button type="button" onClick={() => setInput('Compare BER trade-offs: A2 apartment vs C1 house for long-term cost.')} className="px-3 py-1.5 rounded-full border border-[var(--card-border)] bg-[var(--card-bg)] hover:border-[var(--accent)]">BER trade-offs</button>
        <button type="button" onClick={() => setInput('Suggest grant-eligible property criteria for a first-time buyer.')} className="px-3 py-1.5 rounded-full border border-[var(--card-border)] bg-[var(--card-bg)] hover:border-[var(--accent)]">Grant playbook</button>
      </div>

      <div className="flex-1 ai-glass border border-[var(--card-border)] rounded-lg p-4 overflow-y-auto">
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
                    ? 'bg-[var(--background)] border-[var(--card-border)] ml-8'
                    : 'bg-cyan-900/10 border-cyan-800/20 mr-8',
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
          className="px-4 py-2 bg-[var(--accent)] text-white hover:bg-[var(--accent-strong)] disabled:opacity-60 rounded text-sm font-medium transition-colors"
        >
          {sending ? 'Sending...' : 'Send to Atlas'}
        </button>
      </form>

      {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
    </div>
  );
}
