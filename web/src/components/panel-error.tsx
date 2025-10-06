'use client';

interface PanelErrorProps {
  message: string;
  onRetry?: () => void;
}

export function PanelError({ message, onRetry }: PanelErrorProps) {
  return (
    <div className="mb-4 flex items-center justify-between gap-3 rounded-xl border border-rose-500/60 bg-rose-500/10 px-3 py-2 text-xs text-rose-100">
      <span>{message}</span>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-full border border-rose-300 px-3 py-1 text-xs font-medium text-rose-100 hover:bg-rose-500/20"
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}
