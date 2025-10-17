'use client';

import { useState, useEffect } from 'react';
import { Card } from '../ui/card';
import { Badge } from '../ui/badge';
import { ScrollArea } from '../ui/scroll-area';
import {
  runLocalBenchmark,
  fetchBenchmarkProgress,
  type RunLocalResponse,
  type ProgressResponse,
} from '../../lib/llmBenchApi';

const ALLOWED_LOCAL_MODELS = ["phi3:mini", "llama3.1:8b", "mistral:7b", "gemma2:9b"];

interface RunLocalPanelProps {
  onRunComplete?: () => void;
}

export function RunLocalPanel({ onRunComplete }: RunLocalPanelProps) {
  const [model, setModel] = useState('phi3:mini');
  const [limit, setLimit] = useState(10);
  const [dryRun, setDryRun] = useState(true);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<RunLocalResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progressLines, setProgressLines] = useState<string[]>([]);
  const [showProgress, setShowProgress] = useState(false);

  // Poll progress while running
  useEffect(() => {
    if (!running) {
      return;
    }

    const intervalId = setInterval(async () => {
      try {
        const progress = await fetchBenchmarkProgress();
        if (progress.status === 'ok' && progress.lines) {
          setProgressLines(progress.lines);
        }
      } catch (err) {
        // Silently fail on progress errors
      }
    }, 2000);  // Poll every 2 seconds

    return () => clearInterval(intervalId);
  }, [running]);

  const handleStartRun = async () => {
    try {
      setRunning(true);
      setResult(null);
      setError(null);
      setProgressLines([]);
      setShowProgress(true);

      const response = await runLocalBenchmark({
        model,
        limit,
        dry_run: dryRun,
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

  return (
    <Card className="p-4">
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900">Run Local Benchmark</h3>
          <Badge className="bg-green-100 text-green-800">
            Ollama-only • Free
          </Badge>
        </div>

        {/* Model Selector */}
        <div>
          <label htmlFor="model-select" className="block text-sm font-medium text-gray-700 mb-1">
            Model
          </label>
          <select
            id="model-select"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            disabled={running}
            className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
          >
            {ALLOWED_LOCAL_MODELS.map((m) => (
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

        {/* Dry Run Toggle */}
        <div className="flex items-center justify-between">
          <label htmlFor="dry-run-toggle" className="text-sm font-medium text-gray-700">
            Dry Run Mode
          </label>
          <button
            id="dry-run-toggle"
            type="button"
            onClick={() => setDryRun(!dryRun)}
            disabled={running}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors disabled:opacity-50 ${
              dryRun ? 'bg-blue-600' : 'bg-gray-200'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                dryRun ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>
        <p className="text-xs text-gray-500">
          {dryRun
            ? 'Preview only - no actual benchmark execution'
            : 'Will execute actual benchmark with selected model'}
        </p>

        {/* Start Button */}
        <button
          onClick={handleStartRun}
          disabled={running}
          className="w-full px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
        >
          {running ? (
            <>
              <div className="h-4 w-4 mr-2 animate-spin rounded-full border-2 border-solid border-current border-r-transparent"></div>
              Running...
            </>
          ) : (
            'Start Run'
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
          <div className="rounded-lg bg-green-50 p-3 border border-green-200">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-green-800 font-semibold text-sm">
                ✅ Run Complete
              </span>
              {result.dry_run && (
                <Badge className="bg-blue-100 text-blue-800 text-xs">
                  Dry Run
                </Badge>
              )}
            </div>
            <div className="text-xs text-green-700 space-y-1">
              <div>Batch: <span className="font-mono">{result.batch_id}</span></div>
              <div>Model: {result.model}</div>
              <div>Cases: {result.limit}</div>
              <div>Cost: ${result.cost_usd.toFixed(4)}</div>
              {result.report_path && (
                <div>
                  <a
                    href={`/docs/reports/${result.report_path.split('/').pop()}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-green-800 underline hover:text-green-900"
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
          <strong>Note:</strong> Local runs use Ollama models (free, no API key required). Cost is always $0.
        </div>
      </div>
    </Card>
  );
}
