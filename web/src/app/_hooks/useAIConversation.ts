import { useCallback, useEffect, useState } from 'react';

import {
  createConversation,
  getConversation,
  sendConversationMessage,
  type Citation,
  type RetrievalContext,
} from '@/lib/api';

interface UseAIConversationArgs {
  selectedPropertyId: string | null;
  getRetrievalContext: () => RetrievalContext;
  initialQuery?: string;
  conversationStorageKey?: string;
}

export function useAIConversation({
  selectedPropertyId,
  getRetrievalContext,
  initialQuery,
  conversationStorageKey = 'property_search_conversation_id',
}: UseAIConversationArgs) {
  const [aiQuery, setAiQuery] = useState('');
  const [aiReply, setAiReply] = useState<string | null>(null);
  const [aiCitations, setAiCitations] = useState<Citation[]>([]);
  const [aiRetrievalContext, setAiRetrievalContext] = useState<RetrievalContext | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    const bootConversation = async () => {
      try {
        if (typeof window === 'undefined') {
          return;
        }

        const saved = window.localStorage.getItem(conversationStorageKey);
        if (saved) {
          await getConversation(saved);
          if (active) {
            setConversationId(saved);
          }
          return;
        }

        const userIdentifier = window.navigator.userAgent || 'web-user';
        const created = await createConversation(userIdentifier, 'Main Workspace AI Session');
        window.localStorage.setItem(conversationStorageKey, created.id);
        if (active) {
          setConversationId(created.id);
        }
      } catch {
        // Conversation can be created lazily on first ask if boot fails.
      }
    };

    bootConversation().catch(console.error);

    return () => {
      active = false;
    };
  }, [conversationStorageKey]);

  useEffect(() => {
    if (initialQuery) {
      setAiQuery(initialQuery);
    }
  }, [initialQuery]);

  const askAtlas = useCallback(async () => {
    const prompt = aiQuery.trim();
    if (!prompt || aiLoading) {
      return;
    }

    setAiLoading(true);
    setAiError(null);
    setAiCitations([]);

    try {
      let convId = conversationId;

      if (!convId && typeof window !== 'undefined') {
        const userIdentifier = window.navigator.userAgent || 'web-user';
        const created = await createConversation(userIdentifier, 'Main Workspace AI Session');
        convId = created.id;
        window.localStorage.setItem(conversationStorageKey, created.id);
        setConversationId(created.id);
      }

      if (!convId) {
        throw new Error('Could not initialize AI session.');
      }

      const retrievalContext = getRetrievalContext();
      const result = await sendConversationMessage(
        convId,
        prompt,
        selectedPropertyId || undefined,
        retrievalContext,
      );
      setAiReply(result.assistant_message.content);
      setAiCitations(result.assistant_message.citations || []);
      setAiRetrievalContext(result.retrieval_context || retrievalContext);
    } catch (err) {
      setAiError(err instanceof Error ? err.message : 'Failed to query Atlas AI.');
    } finally {
      setAiLoading(false);
    }
  }, [aiLoading, aiQuery, conversationId, conversationStorageKey, getRetrievalContext, selectedPropertyId]);

  return {
    aiQuery,
    setAiQuery,
    aiReply,
    aiCitations,
    aiRetrievalContext,
    aiLoading,
    aiError,
    setAiError,
    askAtlas,
  };
}
