'use client';

interface Props {
  autoCompareTargetCount: number;
  guidanceMessage: string;
  onUseContext: () => void;
}

export default function WorkspaceStatusStrip({
  autoCompareTargetCount,
  guidanceMessage,
  onUseContext,
}: Props) {
  return (
    <div className="px-4 py-3 border-b border-[var(--card-border)] bg-[var(--card-bg)]/85">
      <div className="flex flex-wrap items-center gap-2">
        <div className="px-3 py-1 rounded-full text-xs border border-[var(--card-border)] bg-[var(--background)]">
          Workspace flow: shortlist -> compare -> decide
        </div>
        <div className="ml-auto text-[11px] text-[var(--muted)] px-2 py-1 border border-[var(--card-border)] rounded-full bg-[var(--background)]">
          Auto-compare target: {autoCompareTargetCount}/5
        </div>
      </div>

      <div className="mt-2 rounded-lg border border-[var(--card-border)] bg-[var(--background)]/70 px-3 py-2 flex flex-wrap items-center gap-2 text-sm">
        <span className="text-[var(--muted)]">{guidanceMessage}</span>
        <button
          type="button"
          onClick={onUseContext}
          className="ml-auto px-3 py-1.5 rounded-full border border-[var(--accent)] bg-cyan-900/10 text-[var(--accent-strong)] hover:bg-cyan-900/15 text-xs"
        >
          Add context to query
        </button>
      </div>
    </div>
  );
}
