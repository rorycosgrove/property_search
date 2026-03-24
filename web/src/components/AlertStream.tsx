'use client';

import { useEffect, useRef, useState } from 'react';
import type { DiscoverySignal } from '@/lib/api';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Toast {
  id: string;
  signal: DiscoverySignal;
}

const SIGNAL_LABELS: Record<string, string> = {
  price_drop: '📉 Price drop',
  high_value: '⭐ Strong value',
  stale: '⏳ Stale listing',
  new_listing: '🆕 New listing',
};

export default function AlertStream() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const seenIds = useRef<Set<string>>(new Set());
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    // Only run in browser, skip if SSE not supported
    if (typeof EventSource === 'undefined') return;

    function connect() {
      const es = new EventSource(`${API_BASE}/api/v1/events/stream`);
      esRef.current = es;

      es.addEventListener('signal', (e: MessageEvent) => {
        try {
          const signal: DiscoverySignal = JSON.parse(e.data);
          const cardId = `${signal.signal_type}:${signal.property_id}`;
          if (seenIds.current.has(cardId)) return;
          seenIds.current.add(cardId);

          // Only toast high-severity signals to avoid noise
          if (signal.severity !== 'high') return;

          const toast: Toast = { id: cardId, signal };
          setToasts((prev) => [toast, ...prev].slice(0, 3));

          // Auto-dismiss after 8s
          setTimeout(() => {
            setToasts((prev) => prev.filter((t) => t.id !== cardId));
          }, 8000);
        } catch {
          // Ignore malformed events
        }
      });

      es.addEventListener('close', () => {
        es.close();
        // Reconnect after 30s
        setTimeout(connect, 30_000);
      });

      es.onerror = () => {
        es.close();
        // Reconnect after 60s on error
        setTimeout(connect, 60_000);
      };
    }

    connect();
    return () => {
      esRef.current?.close();
    };
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div
      aria-live="polite"
      className="fixed bottom-24 right-4 z-[100] flex flex-col gap-2 lg:bottom-6"
    >
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className="flex items-start gap-3 rounded-2xl border border-[var(--card-border)] bg-[var(--card-bg)] p-3 shadow-[0_8px_32px_rgba(27,36,48,0.12)] backdrop-blur-sm"
          style={{ maxWidth: '18rem' }}
        >
          <div className="flex-1 min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-[var(--accent)]">
              {SIGNAL_LABELS[toast.signal.signal_type] ?? toast.signal.signal_type}
            </p>
            <p className="mt-0.5 text-xs font-medium leading-snug truncate">
              {toast.signal.headline}
            </p>
            <p className="mt-0.5 truncate text-[11px] text-[var(--muted)]">
              {toast.signal.address}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setToasts((prev) => prev.filter((t) => t.id !== toast.id))}
            className="flex-shrink-0 text-[var(--muted)] hover:text-[var(--foreground)] text-lg leading-none"
            aria-label="Dismiss"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
