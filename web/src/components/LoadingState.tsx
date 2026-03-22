interface LoadingBlockProps {
  className?: string;
}

export function LoadingBlock({ className = '' }: LoadingBlockProps) {
  return <div className={`skeleton skeleton-soft ${className}`.trim()} aria-hidden="true" />;
}

interface LoadingCardGridProps {
  cards?: number;
}

export function LoadingCardGrid({ cards = 3 }: LoadingCardGridProps) {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      {Array.from({ length: cards }).map((_, index) => (
        <div key={index} className="rounded-lg border border-[var(--card-border)] bg-[var(--card-bg)] p-4">
          <LoadingBlock className="h-3 w-20" />
          <LoadingBlock className="mt-3 h-8 w-24" />
          <LoadingBlock className="mt-3 h-3 w-32" />
        </div>
      ))}
    </div>
  );
}

interface LoadingRowsProps {
  rows?: number;
}

export function LoadingRows({ rows = 6 }: LoadingRowsProps) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="rounded-lg border border-[var(--card-border)] bg-[var(--card-bg)] p-3">
          <LoadingBlock className="h-3 w-24" />
          <LoadingBlock className="mt-2 h-3 w-4/5" />
          <LoadingBlock className="mt-2 h-3 w-2/5" />
        </div>
      ))}
    </div>
  );
}
