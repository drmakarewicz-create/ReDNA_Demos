'use client';

import { useState, useEffect } from 'react';
import { Card } from '../ui/card';
import { Badge } from '../ui/badge';
import {
  fetchModelStatus,
  getProviderColor,
  type ModelStatus,
} from '../../lib/llmBenchApi';

export function ModelStatusCard() {
  const [status, setStatus] = useState<ModelStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadStatus() {
      try {
        const modelStatus = await fetchModelStatus();
        setStatus(modelStatus);
      } catch (err) {
        // Fallback handled in API client
        setStatus({
          provider: 'ollama',
          model: 'llama3.1:8b',
          source: 'fallback',
        });
      } finally {
        setLoading(false);
      }
    }

    loadStatus();
  }, []);

  if (loading) {
    return (
      <Card className="p-4">
        <div className="h-6 w-6 animate-spin rounded-full border-4 border-solid border-current border-r-transparent"></div>
      </Card>
    );
  }

  if (!status) {
    return null;
  }

  const isLocal = status.provider.toLowerCase() === 'ollama';

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <h3 className="text-sm font-semibold text-gray-900">Current Model</h3>
            <Badge className={getProviderColor(status.provider)}>
              {status.provider}
            </Badge>
            {isLocal && (
              <Badge className="bg-green-100 text-green-800">
                Local
              </Badge>
            )}
            {!isLocal && (
              <span className="text-xs text-orange-600" title="Paid external LLM">
                🔒
              </span>
            )}
          </div>
          <div className="text-sm font-mono text-gray-700 mb-1">
            {status.model}
          </div>
          {status.source === 'fallback' && (
            <div className="text-xs text-gray-500">
              (Using fallback detection)
            </div>
          )}
        </div>
      </div>

      <div className="mt-4 pt-4 border-t border-gray-200">
        <div className="flex items-center gap-2 text-xs text-gray-600">
          <span className="inline-block h-2 w-2 rounded-full bg-blue-500"></span>
          <span>Read-only view • Runs disabled in Phase 1</span>
        </div>
        <p className="mt-2 text-xs text-gray-500">
          Model execution will be available in Phase 2 (local) and Phase 3 (external).
        </p>
      </div>
    </Card>
  );
}
