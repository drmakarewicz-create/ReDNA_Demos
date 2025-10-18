'use client';

import { useEffect, useMemo, useState } from 'react';
import { BacklogTable } from '../../../components/llm-bench/BacklogTable';
import { ReportsPanel } from '../../../components/llm-bench/ReportsPanel';
import { ModelStatusCard } from '../../../components/llm-bench/ModelStatusCard';
import { CostsPanel } from '../../../components/llm-bench/CostsPanel';
import { RunPaidPanel } from '../../../components/llm-bench/RunPaidPanel';
import { UCNRRConnectivityCard } from '../../../components/llm-bench/UCNRRConnectivityCard';
import { RoundtripChart } from '../../../components/metrics/RoundtripChart';
import { GlobalMetricsContext } from '../../../components/metrics/GlobalMetricsContext';
import {
  fetchMonthlyCosts,
  formatCost,
  fetchRoundtripMetrics,
  type MonthlyCosts,
  type RoundtripMetrics,
} from '../../../lib/llmBenchApi';

type UcnrrStatusLite = {
  alive?: boolean;
  llm_configured?: boolean;
  reason?: string;
  last_check?: string | null;
};

const DEVX_BASE = process.env.NEXT_PUBLIC_DEVX_BASE ?? 'http://127.0.0.1:8012';

async function fetchUcnrrStatusLite(): Promise<UcnrrStatusLite | null> {
  try {
    const response = await fetch(`${DEVX_BASE}/devx/api/stack/ucnrr/status`);
    if (!response.ok) {
      return null;
    }
    return response.json();
  } catch {
    return null;
  }
}

export function PulseOverlay({ totalP95 }: { totalP95?: number | null }) {
  const fast = typeof totalP95 === 'number' && totalP95 > 0 && totalP95 < 1000;
  const pulseClass = fast
    ? 'bg-emerald-400 opacity-90 shadow-lg shadow-emerald-400/40'
    : 'bg-gray-300 opacity-50 shadow-md shadow-gray-300/50';

  return (
    <div className="pointer-events-none fixed bottom-6 right-6 flex flex-col items-center gap-1">
      <div
        className={`h-10 w-10 animate-pulse rounded-full transition-all duration-500 ${pulseClass}`}
        title={fast ? 'Roundtrip p95 < 1s' : 'Roundtrip p95 ≥ 1s'}
      />
      <span className={`text-[11px] font-medium ${fast ? 'text-emerald-600' : 'text-gray-500'}`}>
        ReDNA Pulse
      </span>
    </div>
  );
}

export default function LLMBenchmarksPageClient() {
  const [costs, setCosts] = useState<MonthlyCosts | null>(null);
  const [roundtripMetrics, setRoundtripMetrics] = useState<RoundtripMetrics | null>(null);
  const [ucnrrStatus, setUcnrrStatus] = useState<UcnrrStatusLite | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    async function loadCosts() {
      try {
        const data = await fetchMonthlyCosts();
        setCosts(data);
      } catch {
        // Costs panel shows errors; keep header quiet
      }
    }

    loadCosts();
  }, [refreshKey]);

  useEffect(() => {
    let cancelled = false;

    async function loadMetrics() {
      try {
        const [rtMetrics, status] = await Promise.all([
          fetchRoundtripMetrics().catch(() => null),
          fetchUcnrrStatusLite(),
        ]);
        if (!cancelled) {
          setRoundtripMetrics(rtMetrics);
          setUcnrrStatus(status);
        }
      } catch {
        if (!cancelled) {
          setRoundtripMetrics(null);
        }
      }
    }

    loadMetrics();
    const interval = setInterval(loadMetrics, 15000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const handleRunComplete = () => {
    setRefreshKey((prev) => prev + 1);
  };

  const capPercent = costs?.monthly_cap_usd
    ? (costs.mtd_total_usd / costs.monthly_cap_usd) * 100
    : 0;

  const getMeterDotColor = () => {
    if (!costs?.monthly_cap_usd) return '#9ca3af';
    if (capPercent >= 90) return '#ef4444';
    if (capPercent >= 50) return '#eab308';
    return '#22c55e';
  };

  const globalMetricsValue = useMemo(
    () => ({
      data: {
        roundtrip: roundtripMetrics,
        ucnrrStatus,
      },
      refresh: () => setRefreshKey((prev) => prev + 1),
    }),
    [roundtripMetrics, ucnrrStatus],
  );

  return (
    <GlobalMetricsContext.Provider value={globalMetricsValue}>
      <div className="min-h-screen bg-gray-50">
        <div className="bg-white border-b border-gray-200">
          <div className="mx-auto max-w-7xl px-6 py-6">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-gray-900">LLM Benchmark Suite</h1>
              <p className="mt-1 text-sm text-gray-500">
                Track and compare LLM extraction quality across models
              </p>
            </div>
            <div className="flex items-center gap-2">
              {costs && (
                <div className="flex items-center gap-1 rounded-md bg-gray-100 px-3 py-1.5">
                  <span className="text-xs text-gray-600">This month:</span>
                  <span className="text-sm font-semibold">{formatCost(costs.mtd_total_usd)}</span>
                  {costs.monthly_cap_usd && (
                    <div
                      className="ml-1 h-2 w-2 rounded-full"
                      style={{ backgroundColor: getMeterDotColor() }}
                      title={`${capPercent.toFixed(1)}% of ${formatCost(costs.monthly_cap_usd)} cap`}
                    />
                  )}
                </div>
              )}
              <span className="inline-flex items-center rounded-md bg-orange-50 px-2.5 py-1 text-xs font-medium text-orange-700">
                Phase 3: Guarded Paid Execution (OpenAI/Anthropic)
              </span>
            </div>
          </div>
          </div>
        </div>

        <div className="mx-auto max-w-7xl px-6 py-8">
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <div>
              <h2 className="mb-4 text-lg font-semibold text-gray-900">Test Case Backlog</h2>
              <BacklogTable />
            </div>
          </div>

          <div className="space-y-6">
            <div>
              <h2 className="mb-4 text-lg font-semibold text-gray-900">Model Status</h2>
              <ModelStatusCard />
            </div>

            <div>
              <h2 className="mb-4 text-lg font-semibold text-gray-900">UCNRR Connectivity</h2>
              <UCNRRConnectivityCard />
            </div>

            <div>
              <h2 className="mb-4 text-lg font-semibold text-gray-900">Pipeline Performance</h2>
              <RoundtripChart />
            </div>

            <div>
              <h2 className="mb-4 text-lg font-semibold text-gray-900">Execute Benchmark</h2>
              <RunPaidPanel onRunComplete={handleRunComplete} />
            </div>

            <div>
              <h2 className="mb-4 text-lg font-semibold text-gray-900">Cost Tracking</h2>
              <CostsPanel key={refreshKey} />
            </div>

            <div>
              <h2 className="mb-4 text-lg font-semibold text-gray-900">Benchmark Reports</h2>
              <ReportsPanel refreshToken={refreshKey} />
            </div>
          </div>
        </div>
        </div>

        <div className="mx-auto max-w-7xl px-6 py-8">
        <div className="mt-8 rounded-lg border border-orange-200 bg-orange-50 p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-orange-400" viewBox="0 0 20 20" fill="currentColor">
                <path
                  fillRule="evenodd"
                  d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div className="ml-3 flex-1">
              <h3 className="text-sm font-medium text-orange-800">
                Phase 3: Guarded Paid Execution (OpenAI/Anthropic)
              </h3>
              <div className="mt-2 text-sm text-orange-700">
                <p>
                  You can now run benchmarks with paid models (OpenAI/Anthropic) with strict safety guardrails.
                  Local Ollama runs remain free.
                </p>
                <ul className="mt-2 list-inside list-disc space-y-1">
                  <li>Free local runs: Ollama (phi3:mini, llama3.1:8b, mistral:7b, gemma2:9b)</li>
                  <li>Paid runs: OpenAI (gpt-4o-mini, gpt-4o), Anthropic (Claude Sonnet, Haiku)</li>
                  <li>Double confirmation required for paid runs + budget cap enforcement</li>
                  <li>Monthly cap check prevents overspend (set ALTLLM_MONTHLY_CAP_USD)</li>
                  <li>Auto-revert to local model after every paid run (success or error)</li>
                  <li>Full audit trail in ~/.redna/audit_llm_bench.jsonl</li>
                </ul>
                <p className="mt-3">
                  <a
                    href="/docs/LLM_Benchmarking.md"
                    className="font-medium underline hover:text-orange-900"
                  >
                    View documentation →
                  </a>
                </p>
              </div>
            </div>
          </div>
        </div>
        </div>
      </div>
      {/* Northstar Phase 5.1: wire this PulseOverlay and metrics context into Northstar UI to show ReDNA Pulse. */}
      <PulseOverlay totalP95={roundtripMetrics?.hop_ms.total?.p95 ?? null} />
    </GlobalMetricsContext.Provider>
  );
}
