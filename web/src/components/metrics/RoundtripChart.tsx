'use client';

import { useState, useEffect } from 'react';
import { Card } from '../ui/card';
import {
  fetchRoundtripMetrics,
  type RoundtripMetrics,
  type HopMetrics,
} from '../../lib/llmBenchApi';

const POLL_INTERVAL_MS = 12000; // 12 seconds

interface HopBar {
  name: string;
  label: string;
  p95: number;
  color: string;
}

export function RoundtripChart() {
  const [metrics, setMetrics] = useState<RoundtripMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadMetrics() {
      try {
        const data = await fetchRoundtripMetrics();
        setMetrics(data);
        setError(null);
      } catch (err) {
        console.error('Failed to load roundtrip metrics:', err);
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }

    // Initial load
    loadMetrics();

    // Poll for updates
    const interval = setInterval(loadMetrics, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <Card className="p-6">
        <h3 className="text-sm font-semibold text-gray-900 mb-4">
          Pipeline Roundtrip Timing
        </h3>
        <div className="flex items-center justify-center h-64">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-solid border-current border-r-transparent text-blue-600"></div>
        </div>
      </Card>
    );
  }

  if (error || !metrics) {
    return (
      <Card className="p-6">
        <h3 className="text-sm font-semibold text-gray-900 mb-4">
          Pipeline Roundtrip Timing
        </h3>
        <div className="text-sm text-red-600">
          {error || 'Failed to load metrics'}
        </div>
        <p className="text-xs text-gray-500 mt-2">
          Ensure Core service is running and has processed some requests.
        </p>
      </Card>
    );
  }

  const { hop_ms, ingest, window_seconds } = metrics;

  // Build hop bars data
  const bars: HopBar[] = [];
  if (hop_ms.preprocess) {
    bars.push({
      name: 'preprocess',
      label: 'Preprocess',
      p95: hop_ms.preprocess.p95,
      color: 'bg-blue-500',
    });
  }
  if (hop_ms.ucnrr) {
    bars.push({
      name: 'ucnrr',
      label: 'UCNRR',
      p95: hop_ms.ucnrr.p95,
      color: 'bg-purple-500',
    });
  }
  if (hop_ms.resolve) {
    bars.push({
      name: 'resolve',
      label: 'Resolve',
      p95: hop_ms.resolve.p95,
      color: 'bg-green-500',
    });
  }

  // Calculate max for scaling
  const maxP95 = hop_ms.total?.p95 || 1;

  const totalP95 = hop_ms.total?.p95 || 0;
  const totalCount = hop_ms.total?.count || 0;

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-900">
          Pipeline Roundtrip Timing
        </h3>
        <div className="flex items-center gap-4 text-xs text-gray-600">
          <span title="Number of requests in window">
            {totalCount} req{totalCount !== 1 ? 's' : ''}
          </span>
          <span title="Rolling window duration">
            {window_seconds}s window
          </span>
        </div>
      </div>

      {/* Total P95 prominently displayed */}
      <div className="mb-6">
        <div className="flex items-baseline gap-2">
          <div className="text-3xl font-bold text-gray-900">
            {totalP95.toFixed(1)}
            <span className="text-lg text-gray-500 ml-1">ms</span>
          </div>
          <div className="text-sm text-gray-600">p95 total</div>
        </div>
        {hop_ms.total?.p50 && (
          <div className="text-xs text-gray-500 mt-1">
            p50: {hop_ms.total.p50.toFixed(1)}ms • mean: {hop_ms.total.mean.toFixed(1)}ms
          </div>
        )}
      </div>

      {/* Hop breakdown bars */}
      {bars.length > 0 ? (
        <div className="space-y-3">
          {bars.map((bar) => {
            const widthPercent = (bar.p95 / maxP95) * 100;
            return (
              <div key={bar.name}>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-medium text-gray-700">{bar.label}</span>
                  <span className="text-gray-600">{bar.p95.toFixed(1)}ms p95</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full ${bar.color}`}
                    style={{ width: `${widthPercent}%` }}
                    title={`${bar.label}: ${bar.p95.toFixed(1)}ms p95`}
                  />
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-sm text-gray-500">
          No hop timing data available yet. Process some requests to see metrics.
        </div>
      )}

      {/* Ingest stats footer */}
      <div className="mt-6 pt-4 border-t border-gray-200 flex items-center justify-between text-xs text-gray-600">
        <div>
          <span className="font-medium">{ingest.requests}</span> total requests
        </div>
        {ingest.errors > 0 && (
          <div className="text-red-600">
            <span className="font-medium">{ingest.errors}</span> errors
          </div>
        )}
      </div>

      {/* Auto-refresh indicator */}
      <div className="mt-2 text-xs text-gray-400 text-center">
        Auto-refreshing every {POLL_INTERVAL_MS / 1000}s
      </div>
    </Card>
  );
}
