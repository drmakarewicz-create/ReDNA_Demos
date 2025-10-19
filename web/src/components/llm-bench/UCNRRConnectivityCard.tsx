'use client';

import { useState, useEffect } from 'react';
import { Card } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { ScrollArea } from '../ui/scroll-area';

type UCNRRStatus = {
  alive: boolean;
  llm_configured: boolean;
  reason: string;
  restarts_last_10m: number;
  restart_capped: boolean;
  backoff_sec_remaining: number;
  last_check: string | null;
  pid: number | null;
};

type UCNRRLogResponse = {
  log_file: string;
  lines: string[];
  total_lines: number;
};

const DEVX_BASE = process.env.NEXT_PUBLIC_DEVX_API_BASE || 'http://127.0.0.1:8100';

async function fetchUCNRRStatus(): Promise<UCNRRStatus> {
  const response = await fetch(`${DEVX_BASE}/devx/api/stack/ucnrr/status`);
  if (!response.ok) {
    throw new Error('Failed to fetch UCNRR status');
  }
  return response.json();
}

async function ensureUCNRR(forceRestart: boolean = false): Promise<any> {
  const response = await fetch(`${DEVX_BASE}/devx/api/stack/ucnrr/ensure`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ force_restart: forceRestart }),
  });
  if (!response.ok) {
    throw new Error('Failed to ensure UCNRR');
  }
  return response.json();
}

async function restartUCNRR(): Promise<any> {
  const response = await fetch(`${DEVX_BASE}/devx/api/stack/ucnrr/restart`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error('Failed to restart UCNRR');
  }
  return response.json();
}

async function fetchUCNRRLogs(tail: number = 100): Promise<UCNRRLogResponse> {
  const response = await fetch(`${DEVX_BASE}/devx/api/stack/ucnrr/logs?tail=${tail}`);
  if (!response.ok) {
    throw new Error('Failed to fetch UCNRR logs');
  }
  return response.json();
}

function getStatusColor(status: UCNRRStatus): string {
  if (status.alive && status.llm_configured) {
    return 'bg-green-100 text-green-800';
  }
  if (status.restart_capped || status.reason === 'conn_refused') {
    return 'bg-red-100 text-red-800';
  }
  return 'bg-amber-100 text-amber-800';
}

function getStatusLabel(status: UCNRRStatus): string {
  if (status.alive && status.llm_configured) {
    return 'Online';
  }
  if (status.restart_capped) {
    return 'Capped';
  }
  if (status.backoff_sec_remaining > 0) {
    return 'Backoff';
  }
  if (!status.alive) {
    return 'Offline';
  }
  return 'Degraded';
}

function getReasonMessage(status: UCNRRStatus): string {
  const reasonMap: Record<string, string> = {
    ok: 'All systems operational',
    bad_llm: 'LLM not configured',
    conn_refused: 'Connection refused - service not running',
    timeout: 'Health check timed out',
    ollama_offline: 'Ollama not reachable',
    ollama_conn_refused: 'Ollama connection refused',
  };
  return reasonMap[status.reason] || status.reason;
}

export function UCNRRConnectivityCard() {
  const [status, setStatus] = useState<UCNRRStatus | null>(null);
  const [logs, setLogs] = useState<UCNRRLogResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadStatus = async () => {
    try {
      const ucnrrStatus = await fetchUCNRRStatus();
      setStatus(ucnrrStatus);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load status');
    } finally {
      setLoading(false);
    }
  };

  const loadLogs = async () => {
    try {
      const ucnrrLogs = await fetchUCNRRLogs(150);
      setLogs(ucnrrLogs);
    } catch (err) {
      console.error('Failed to load logs:', err);
    }
  };

  const handleEnsure = async () => {
    setActionLoading(true);
    try {
      await ensureUCNRR(false);
      await loadStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to ensure UCNRR');
    } finally {
      setActionLoading(false);
    }
  };

  const handleRestart = async () => {
    setActionLoading(true);
    try {
      await restartUCNRR();
      await loadStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to restart UCNRR');
    } finally {
      setActionLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
    const interval = setInterval(() => {
      if (status && (!status.alive || !status.llm_configured)) {
        // Refresh more frequently when degraded
        loadStatus();
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [status?.alive, status?.llm_configured]);

  useEffect(() => {
    if (showLogs) {
      loadLogs();
      const interval = setInterval(loadLogs, 3000);
      return () => clearInterval(interval);
    }
  }, [showLogs]);

  if (loading) {
    return (
      <Card className="p-4">
        <div className="flex items-center gap-2">
          <div className="h-5 w-5 animate-spin rounded-full border-4 border-solid border-current border-r-transparent"></div>
          <span className="text-sm text-gray-600">Loading UCNRR status...</span>
        </div>
      </Card>
    );
  }

  if (error || !status) {
    return (
      <Card className="p-4 border-red-200">
        <div className="flex items-start gap-2">
          <span className="text-red-600">⚠️</span>
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-red-900 mb-1">UCNRR Status Error</h3>
            <p className="text-xs text-red-700">{error || 'Failed to load status'}</p>
          </div>
        </div>
      </Card>
    );
  }

  const isHealthy = status.alive && status.llm_configured;
  const showOllamaHint = status.reason.includes('ollama');
  const showBackoffInfo = status.backoff_sec_remaining > 0;

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <h3 className="text-sm font-semibold text-gray-900">UCNRR Connectivity</h3>
            <Badge className={getStatusColor(status)}>
              {getStatusLabel(status)}
            </Badge>
          </div>
          <p className="text-xs text-gray-600 mb-1">
            {getReasonMessage(status)}
          </p>
          {status.pid && (
            <div className="text-xs text-gray-500">PID: {status.pid}</div>
          )}
        </div>
      </div>

      {/* Status details */}
      <div className="space-y-2 mb-3">
        {showOllamaHint && (
          <div className="bg-yellow-50 border border-yellow-200 rounded p-2">
            <p className="text-xs font-semibold text-yellow-900 mb-1">
              🔧 Ollama Required
            </p>
            <p className="text-xs text-yellow-800 font-mono">
              ollama serve & && ollama pull phi3:mini
            </p>
          </div>
        )}

        {status.restart_capped && (
          <div className="bg-red-50 border border-red-200 rounded p-2">
            <p className="text-xs font-semibold text-red-900 mb-1">
              🛑 Restart Cap Exceeded
            </p>
            <p className="text-xs text-red-800">
              Too many restarts in the last 10 minutes. Cooldown period in effect.
              Check logs for persistent errors.
            </p>
          </div>
        )}

        {showBackoffInfo && !status.restart_capped && (
          <div className="bg-blue-50 border border-blue-200 rounded p-2">
            <p className="text-xs text-blue-900">
              ⏳ Auto-restart in {status.backoff_sec_remaining}s
            </p>
          </div>
        )}

        {status.restarts_last_10m > 0 && (
          <div className="text-xs text-gray-600">
            Restarts in last 10m: <span className="font-semibold">{status.restarts_last_10m}</span>
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="flex gap-2 mb-3">
        <Button
          onClick={handleEnsure}
          disabled={actionLoading || (isHealthy && !status.restart_capped)}
          size="sm"
          variant="outline"
          className="text-xs"
        >
          {actionLoading ? 'Working...' : 'Ensure UCNRR'}
        </Button>
        <Button
          onClick={handleRestart}
          disabled={actionLoading || status.restart_capped}
          size="sm"
          variant="outline"
          className="text-xs"
        >
          Restart
        </Button>
        <Button
          onClick={() => setShowLogs(!showLogs)}
          size="sm"
          variant="ghost"
          className="text-xs"
        >
          {showLogs ? 'Hide Logs' : 'Show Logs'}
        </Button>
      </div>

      {/* Logs viewer */}
      {showLogs && (
        <div className="border-t pt-3">
          <h4 className="text-xs font-semibold text-gray-700 mb-2">Recent Logs</h4>
          <ScrollArea className="h-48 w-full rounded border bg-gray-50 p-2">
            {logs?.lines && logs.lines.length > 0 ? (
              <pre className="text-[10px] font-mono text-gray-700 whitespace-pre-wrap">
                {logs.lines.join('\n')}
              </pre>
            ) : (
              <p className="text-xs text-gray-500">No logs available</p>
            )}
          </ScrollArea>
          <p className="text-[10px] text-gray-500 mt-1">
            {logs?.log_file || '/tmp/ucnrr.log'} • {logs?.total_lines || 0} lines
          </p>
        </div>
      )}

      {/* Info footer */}
      <div className="mt-3 pt-3 border-t border-gray-200">
        <div className="flex items-center gap-2 text-xs text-gray-600">
          <span className="inline-block h-2 w-2 rounded-full bg-blue-500"></span>
          <span>Auto-recovery with backoff • Max 3 restarts per 10m</span>
        </div>
      </div>
    </Card>
  );
}
