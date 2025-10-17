'use client';

import { useState, useEffect } from 'react';
import { Card } from '../ui/card';
import { Badge } from '../ui/badge';
import {
  fetchMonthlyCosts,
  formatCost,
  getProviderColor,
  getMeterColor,
  type MonthlyCosts,
  type BatchRun,
} from '../../lib/llmBenchApi';

export function CostsPanel() {
  const [costs, setCosts] = useState<MonthlyCosts | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load costs
  useEffect(() => {
    async function loadCosts() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchMonthlyCosts();
        setCosts(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load costs');
      } finally {
        setLoading(false);
      }
    }

    loadCosts();
  }, []);

  if (loading) {
    return (
      <Card className="p-6">
        <div className="flex items-center justify-center">
          <div className="h-6 w-6 animate-spin rounded-full border-4 border-solid border-current border-r-transparent"></div>
          <p className="ml-2 text-sm text-gray-500">Loading costs...</p>
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-6">
        <div className="rounded-lg bg-red-50 p-4 text-red-800">
          <p className="font-semibold">Error loading costs</p>
          <p className="mt-1 text-sm">{error}</p>
        </div>
      </Card>
    );
  }

  if (!costs) {
    return null;
  }

  const hasData = costs.mtd_total_usd > 0 || costs.total_requests > 0;
  const capPercent = costs.monthly_cap_usd
    ? (costs.mtd_total_usd / costs.monthly_cap_usd) * 100
    : 0;

  return (
    <div className="space-y-4">
      {/* MTD Total Card */}
      <Card className="p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">
          Month-to-Date ({costs.month})
        </h3>

        <div className="space-y-3">
          {/* Total cost */}
          <div>
            <div className="text-2xl font-bold text-gray-900">
              {formatCost(costs.mtd_total_usd)}
            </div>
            {costs.monthly_cap_usd && (
              <div className="text-xs text-gray-500">
                of {formatCost(costs.monthly_cap_usd)} cap ({capPercent.toFixed(1)}%)
              </div>
            )}
          </div>

          {/* Progress bar (if cap exists) */}
          {costs.monthly_cap_usd && (
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className={`h-2 rounded-full ${getMeterColor(costs.mtd_total_usd, costs.monthly_cap_usd)}`}
                style={{ width: `${Math.min(capPercent, 100)}%` }}
              />
            </div>
          )}

          {/* Stats */}
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <div className="text-gray-500">Requests</div>
              <div className="font-semibold">{costs.total_requests.toLocaleString()}</div>
            </div>
            <div>
              <div className="text-gray-500">Tokens</div>
              <div className="font-semibold">{costs.total_tokens.toLocaleString()}</div>
            </div>
          </div>
        </div>
      </Card>

      {/* Provider Breakdown */}
      {hasData && Object.keys(costs.by_provider).length > 0 && (
        <Card className="p-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">By Provider</h3>
          <div className="space-y-2">
            {Object.entries(costs.by_provider)
              .sort(([, a], [, b]) => b - a)
              .map(([provider, cost]) => (
                <div key={provider} className="flex items-center justify-between">
                  <Badge className={getProviderColor(provider)}>{provider}</Badge>
                  <span className="text-sm font-mono">{formatCost(cost)}</span>
                </div>
              ))}
          </div>
        </Card>
      )}

      {/* Model Breakdown */}
      {hasData && Object.keys(costs.by_model).length > 0 && (
        <Card className="p-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">By Model</h3>
          <div className="space-y-2">
            {Object.entries(costs.by_model)
              .sort(([, a], [, b]) => b - a)
              .slice(0, 5)
              .map(([model, cost]) => (
                <div key={model} className="flex items-center justify-between text-sm">
                  <span className="truncate font-mono text-xs">{model}</span>
                  <span className="font-mono ml-2">{formatCost(cost)}</span>
                </div>
              ))}
          </div>
        </Card>
      )}

      {/* Recent Batches */}
      {hasData && costs.runs.length > 0 && (
        <Card className="p-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">
            Recent Runs ({costs.runs.length})
          </h3>
          <div className="space-y-2 max-h-[300px] overflow-y-auto">
            {costs.runs.slice(0, 10).map((run) => (
              <div key={run.batch_id} className="text-sm border-b border-gray-100 pb-2 last:border-0">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-mono text-gray-600 truncate max-w-[150px]">
                    {run.batch_id}
                  </span>
                  <span className="font-semibold">{formatCost(run.total_cost_usd)}</span>
                </div>
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span>
                    {run.provider}/{run.model.split('/').pop()}
                  </span>
                  <span>
                    {run.cases} cases • {(run.prompt_tokens + run.completion_tokens).toLocaleString()} tok
                  </span>
                </div>
                {run.errors > 0 && (
                  <div className="text-xs text-red-600 mt-1">
                    {run.errors} error{run.errors > 1 ? 's' : ''}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Empty State */}
      {!hasData && (
        <Card className="p-6">
          <div className="text-center py-4">
            <div className="text-gray-400 mb-2">
              <svg className="mx-auto h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 className="text-sm font-medium text-gray-900 mb-1">No costs tracked yet</h3>
            <p className="text-sm text-gray-500">
              Run benchmarks with external LLMs to see cost tracking
            </p>
          </div>
        </Card>
      )}
    </div>
  );
}
