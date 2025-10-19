'use client';

import { useState, useEffect } from 'react';
import { Card } from '../ui/card';
import { Badge } from '../ui/badge';
import { ScrollArea } from '../ui/scroll-area';
import {
  costPrecheck,
  runPaidBenchmark,
  fetchBenchmarkProgress,
  type CostPrecheckResponse,
  type RunPaidResponse,
} from '../../lib/llmBenchApi';

// Provider and model configurations
const PROVIDERS = {
  ollama: {
    label: 'Ollama (Local)',
    models: ['phi3:mini', 'llama3.1:8b', 'mistral:7b', 'gemma2:9b'],
    isPaid: false,
    badge: { bg: 'bg-green-100', text: 'text-green-800', label: 'Free • Local' },
  },
  openai: {
    label: 'OpenAI',
    models: ['gpt-4o-mini', 'gpt-4o'],
    isPaid: true,
    badge: { bg: 'bg-red-100', text: 'text-red-800', label: 'Paid • Guarded' },
    rates: {
      'gpt-4o-mini': '$0.15/$0.60 per 1M tokens',
      'gpt-4o': '$2.50/$10.00 per 1M tokens',
    },
  },
  anthropic: {
    label: 'Anthropic',
    models: ['claude-3-5-sonnet-20240620', 'claude-3-haiku-20240307'],
    isPaid: true,
    badge: { bg: 'bg-red-100', text: 'text-red-800', label: 'Paid • Guarded' },
    rates: {
      'claude-3-5-sonnet-20240620': '$3.00/$15.00 per 1M tokens',
      'claude-3-haiku-20240307': '$0.25/$1.25 per 1M tokens',
    },
  },
} as const;

type Provider = keyof typeof PROVIDERS;

interface RunPaidPanelProps {
  onRunComplete?: () => void;
}

export function RunPaidPanel({ onRunComplete }: RunPaidPanelProps) {
  const [provider, setProvider] = useState<Provider>('ollama');
  const [model, setModel] = useState('phi3:mini');
  const [limit, setLimit] = useState(10);
  const [budgetCap, setBudgetCap] = useState(1.0);

  // Confirmations
  const [confirmCosts, setConfirmCosts] = useState(false);
  const [confirmBudget, setConfirmBudget] = useState(false);

  // Cost precheck
  const [precheck, setPrecheck] = useState<CostPrecheckResponse | null>(null);
  const [precheckLoading, setPrecheckLoading] = useState(false);
  const [precheckError, setPrecheckError] = useState<string | null>(null);

  // Run state
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<RunPaidResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progressLines, setProgressLines] = useState<string[]>([]);
  const [showProgress, setShowProgress] = useState(false);

  const providerConfig = PROVIDERS[provider];
  const isPaid = providerConfig.isPaid;

  // Reset model when provider changes
  useEffect(() => {
    setModel(providerConfig.models[0]);
    setConfirmCosts(false);
    setConfirmBudget(false);
    setPrecheck(null);
  }, [provider]);

  // Run precheck whenever parameters change
  useEffect(() => {
    if (isPaid) {
      handlePrecheck();
    }
  }, [provider, model, limit]);

  // Poll progress while running
  useEffect(() => {
    if (!running) return;

    const intervalId = setInterval(async () => {
      try {
        const progress = await fetchBenchmarkProgress();
        if (progress.status === 'ok' && progress.lines) {
          setProgressLines(progress.lines);
        }
      } catch (err) {
        // Silently fail on progress errors
      }
    }, 2000);

    return () => clearInterval(intervalId);
  }, [running]);

  const handlePrecheck = async () => {
    if (provider === 'ollama') {
      // No precheck needed for local
      setPrecheck({
        est_cost_usd: 0,
        mtd_total_usd: 0,
        monthly_cap_usd: null,
        remaining_usd: null,
        can_run: true,
      });
      return;
    }

    try {
      setPrecheckLoading(true);
      setPrecheckError(null);
      const response = await costPrecheck(provider, model, limit);
      setPrecheck(response);
    } catch (err) {
      setPrecheckError(err instanceof Error ? err.message : 'Failed to check cost');
      setPrecheck(null);
    } finally {
      setPrecheckLoading(false);
    }
  };

  const handleStartRun = async () => {
    try {
      setRunning(true);
      setResult(null);
      setError(null);
      setProgressLines([]);
      setShowProgress(true);

      const response = await runPaidBenchmark({
        provider,
        model,
        limit,
        run: true,
        allow_paid: isPaid,
        ack_paid: isPaid ? 'I understand costs' : '',
        max_cost_usd: isPaid ? budgetCap : 0,
      });

      setResult(response);
      setRunning(false);

      // Notify parent to refresh
      if (onRunComplete) {
        onRunComplete();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run benchmark');
      setRunning(false);
    }
  };

  const canRun = isPaid
    ? confirmCosts && confirmBudget && precheck?.can_run && budgetCap > 0
    : true;

  const budgetCapLabel = isPaid ? `Max $${budgetCap.toFixed(2)}` : 'Free';

  return (
    <Card className="p-4">
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900">Run Benchmark</h3>
          <Badge className={`${providerConfig.badge.bg} ${providerConfig.badge.text}`}>
            {providerConfig.badge.label}
          </Badge>
        </div>

        {/* Provider Selector */}
        <div>
          <label htmlFor="provider-select" className="block text-sm font-medium text-gray-700 mb-1">
            Provider
          </label>
          <select
            id="provider-select"
            value={provider}
            onChange={(e) => setProvider(e.target.value as Provider)}
            disabled={running}
            className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
          >
            {Object.entries(PROVIDERS).map(([key, config]) => (
              <option key={key} value={key}>
                {config.label}
              </option>
            ))}
          </select>
        </div>

        {/* Model Selector */}
        <div>
          <label htmlFor="model-select" className="block text-sm font-medium text-gray-700 mb-1">
            Model
            {isPaid && providerConfig.rates && (
              <span className="ml-2 text-xs text-gray-500">
                ({providerConfig.rates[model as keyof typeof providerConfig.rates]})
              </span>
            )}
          </label>
          <select
            id="model-select"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            disabled={running}
            className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
          >
            {providerConfig.models.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>

        {/* Limit Slider */}
        <div>
          <label htmlFor="limit-slider" className="block text-sm font-medium text-gray-700 mb-1">
            Test Case Limit: {limit}
          </label>
          <input
            id="limit-slider"
            type="range"
            min="5"
            max="50"
            step="5"
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            disabled={running}
            className="w-full disabled:opacity-50"
          />
          <div className="flex justify-between text-xs text-gray-500 mt-1">
            <span>5</span>
            <span>50</span>
          </div>
        </div>

        {/* Cost Precheck (for paid providers) */}
        {isPaid && (
          <div className="rounded-lg bg-blue-50 p-3 border border-blue-200">
            <h4 className="text-xs font-semibold text-blue-900 mb-2">Cost Estimate</h4>
            {precheckLoading && <p className="text-xs text-blue-700">Calculating...</p>}
            {precheckError && <p className="text-xs text-red-700">{precheckError}</p>}
            {precheck && (
              <div className="text-xs text-blue-700 space-y-1">
                <div>Estimated cost: <strong>${precheck.est_cost_usd.toFixed(4)}</strong></div>
                <div>MTD total: ${precheck.mtd_total_usd.toFixed(4)}</div>
                {precheck.monthly_cap_usd !== null && (
                  <>
                    <div>Monthly cap: ${precheck.monthly_cap_usd.toFixed(2)}</div>
                    <div>
                      Remaining: <strong>${(precheck.remaining_usd ?? 0).toFixed(4)}</strong>
                    </div>
                    {!precheck.can_run && (
                      <div className="text-red-700 font-semibold mt-2">
                        ⚠️ Run would exceed monthly cap!
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        )}

        {/* Budget Cap Slider (for paid providers) */}
        {isPaid && (
          <div>
            <label htmlFor="budget-cap" className="block text-sm font-medium text-gray-700 mb-1">
              Per-Run Budget Cap: ${budgetCap.toFixed(2)}
            </label>
            <input
              id="budget-cap"
              type="range"
              min="0.5"
              max="5.0"
              step="0.5"
              value={budgetCap}
              onChange={(e) => setBudgetCap(Number(e.target.value))}
              disabled={running}
              className="w-full disabled:opacity-50"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>$0.50</span>
              <span>$5.00</span>
            </div>
          </div>
        )}

        {/* Confirmations (for paid providers) */}
        {isPaid && (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="confirm-costs"
                checked={confirmCosts}
                onChange={(e) => setConfirmCosts(e.target.checked)}
                disabled={running}
                className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <label htmlFor="confirm-costs" className="text-sm text-gray-700">
                I understand this may incur charges
              </label>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="confirm-budget"
                checked={confirmBudget}
                onChange={(e) => setConfirmBudget(e.target.checked)}
                disabled={running}
                className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <label htmlFor="confirm-budget" className="text-sm text-gray-700">
                I accept the per-run budget cap (${budgetCap.toFixed(2)})
              </label>
            </div>
          </div>
        )}

        {/* Auto-revert Banner (for paid providers) */}
        {isPaid && (
          <div className="rounded-lg bg-green-50 p-2 border border-green-200">
            <p className="text-xs text-green-800">
              ✅ Model will auto-revert to local after run (success or error)
            </p>
          </div>
        )}

        {/* Locked Warning (for paid providers without confirmations) */}
        {isPaid && !canRun && (
          <div className="rounded-lg bg-red-50 p-2 border border-red-200">
            <p className="text-xs text-red-800">
              ⚠️ Paid run locked until confirmations & budget cap are set
            </p>
          </div>
        )}

        {/* Start Button */}
        <button
          onClick={handleStartRun}
          disabled={running || !canRun}
          className="w-full px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
        >
          {running ? (
            <>
              <div className="h-4 w-4 mr-2 animate-spin rounded-full border-2 border-solid border-current border-r-transparent"></div>
              Running...
            </>
          ) : (
            `Run Benchmark (${budgetCapLabel})`
          )}
        </button>

        {/* Error Display */}
        {error && (
          <div className="rounded-lg bg-red-50 p-3 text-red-800">
            <p className="font-semibold text-sm">Error</p>
            <p className="mt-1 text-xs">{error}</p>
          </div>
        )}

        {/* Result Display */}
        {result && (
          <div className={`rounded-lg p-3 border ${isPaid ? 'bg-orange-50 border-orange-200' : 'bg-green-50 border-green-200'}`}>
            <div className="flex items-center gap-2 mb-2">
              <span className={`${isPaid ? 'text-orange-800' : 'text-green-800'} font-semibold text-sm`}>
                ✅ Run Complete
              </span>
              {isPaid && (
                <Badge className="bg-orange-100 text-orange-800 text-xs">
                  Paid
                </Badge>
              )}
            </div>
            <div className={`text-xs ${isPaid ? 'text-orange-700' : 'text-green-700'} space-y-1`}>
              <div>Batch: <span className="font-mono">{result.batch_id}</span></div>
              <div>Provider: {result.provider}</div>
              <div>Model: {result.model}</div>
              <div>Cases: {result.limit}</div>
              <div>Cost: <strong>${result.cost_usd.toFixed(4)}</strong></div>
              {result.report_path && (
                <div>
                  <a
                    href={`/docs/reports/${result.report_path.split('/').pop()}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`${isPaid ? 'text-orange-800' : 'text-green-800'} underline hover:no-underline`}
                  >
                    View Report →
                  </a>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Progress Viewer */}
        {showProgress && (
          <div className="border border-gray-200 rounded-lg">
            <button
              onClick={() => setShowProgress(!showProgress)}
              className="w-full px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 flex items-center justify-between"
            >
              <span>View Progress</span>
              <span>{showProgress ? '▼' : '▶'}</span>
            </button>
            {showProgress && (
              <div className="border-t border-gray-200">
                <ScrollArea className="h-[200px] p-3">
                  <div className="text-xs font-mono space-y-1">
                    {progressLines.length === 0 ? (
                      <div className="text-gray-500">Waiting for output...</div>
                    ) : (
                      progressLines.map((line, idx) => (
                        <div key={idx} className="text-gray-700">
                          {line}
                        </div>
                      ))
                    )}
                  </div>
                </ScrollArea>
              </div>
            )}
          </div>
        )}

        {/* Info Note */}
        <div className="text-xs text-gray-500 bg-gray-50 p-2 rounded">
          <strong>Note:</strong>{' '}
          {isPaid
            ? 'Paid runs require API keys set in environment. Cost tracked in monthly reports.'
            : 'Local runs use Ollama models (free, no API key required). Cost is always $0.'}
        </div>
      </div>
    </Card>
  );
}
