'use client';

import type { ReactNode } from 'react';

interface PanelSkeletonProps {
  rows?: number;
  columns?: number;
  className?: string;
  children?: ReactNode;
}

export function PanelSkeleton({ rows = 3, columns = 1, className, children }: PanelSkeletonProps) {
  const placeholders = Array.from({ length: rows });
  return (
    <div className={`animate-pulse space-y-2 ${className ?? ''}`}>
      {placeholders.map((_, rowIndex) => (
        <div key={`skeleton-row-${rowIndex}`} className="flex flex-wrap gap-2">
          {Array.from({ length: columns }).map((__, colIndex) => (
            <span
              key={`skeleton-row-${rowIndex}-col-${colIndex}`}
              className="h-4 rounded-lg bg-slate-800/70"
              style={{ flex: '1 0 120px' }}
            />
          ))}
        </div>
      ))}
      {children}
    </div>
  );
}
