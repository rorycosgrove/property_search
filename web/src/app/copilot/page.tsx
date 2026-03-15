'use client';

import Link from 'next/link';

export default function CopilotPage() {
  return (
    <div className="p-6 max-w-3xl mx-auto min-h-[40vh] flex items-center justify-center">
      <div className="w-full rounded-xl border border-[var(--card-border)] ai-glass p-6 text-center">
        <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--muted)]">Atlas AI</p>
        <h1 className="text-2xl font-bold mt-1">AI query lives in the dedicated workspace</h1>
        <p className="text-sm text-[var(--muted)] mt-3">
          Ask Atlas inside the advanced workspace while keeping shortlist and decision context visible, without making the homepage carry the full interface.
        </p>

        <div className="mt-4 flex items-center justify-center gap-2">
          <Link
            href="/workspace?focus=ask"
            className="px-4 py-2 rounded-lg border border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent-strong)] hover:bg-[var(--accent-soft-strong)] text-sm"
          >
            Go to workspace AI query
          </Link>
        </div>
      </div>
    </div>
  );
}
