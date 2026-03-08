'use client';

interface Props {
  autoCompareTargetCount: number;
  guidanceMessage: string;
  analysisStale: boolean;
  canRunCompare: boolean;
  compareLoading: boolean;
  askPanelOpen: boolean;
  onUseContext: () => void;
  onRunCompare: () => void;
  onToggleAskPanel: () => void;
}

export default function WorkspaceStatusStrip({
  autoCompareTargetCount,
  guidanceMessage,
  analysisStale,
  canRunCompare,
  compareLoading,
  askPanelOpen,
  onUseContext,
  onRunCompare,
  onToggleAskPanel,
}: Props) {
  return (
    <div className="px-4 py-3 border-b border-[var(--card-border)] bg-[var(--card-bg)]/85">
      <div className="flex flex-wrap items-center gap-2">
        <div className="px-3 py-1 rounded-full text-xs border border-[var(--card-border)] bg-[var(--background)]">
          Workspace flow: shortlist to compare to decide
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
        <button
          type="button"
          onClick={onToggleAskPanel}
          className="px-3 py-1.5 rounded-full border border-[var(--card-border)] bg-[var(--card-bg)] text-[var(--foreground)] hover:bg-[var(--background)] text-xs"
        >
          {askPanelOpen ? 'Hide AI panel' : 'Show AI panel'}
        </button>
        <button
          type="button"
          onClick={onRunCompare}
          disabled={!canRunCompare || compareLoading}
          className="px-3 py-1.5 rounded-full border border-[var(--card-border)] bg-[var(--card-bg)] text-[var(--foreground)] hover:bg-[var(--background)] text-xs disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {compareLoading ? 'Running analysis...' : analysisStale ? 'Re-run analysis' : 'Run analysis'}
        </button>
      </div>
    </div>
  );
}
