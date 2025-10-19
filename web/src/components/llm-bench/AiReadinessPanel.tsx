"use client";

import { useState, useEffect, useRef } from "react";
import {
  fetchAiReady,
  fetchAiReadyLayer,
  type AiReadyResponse,
  type AiReadyLight,
  type LayerDiagnosticResponse,
  getTrafficLightColor,
  getTopFailureReason,
} from "@/lib/llmBenchApi";

export function AiReadinessPanel() {
  const [data, setData] = useState<AiReadyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [copied, setCopied] = useState(false);

  // Diagnostic drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedLayer, setSelectedLayer] = useState<"devx" | "ucnrr" | "core" | "core_e2e" | null>(null);
  const [diagnosticData, setDiagnosticData] = useState<LayerDiagnosticResponse | null>(null);
  const [diagnosticLoading, setDiagnosticLoading] = useState(false);
  const [diagnosticError, setDiagnosticError] = useState<string | null>(null);
  const [diagnosticCopied, setDiagnosticCopied] = useState(false);

  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch function
  const loadAiReadiness = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await fetchAiReady();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch AI readiness");
    } finally {
      setIsLoading(false);
    }
  };

  // Initial load
  useEffect(() => {
    loadAiReadiness();
  }, []);

  // Auto-refresh effect
  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = setInterval(loadAiReadiness, 10000); // 10 seconds
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [autoRefresh]);

  const handleRunProbe = () => {
    loadAiReadiness();
  };

  const handleCopyDiagnostics = () => {
    if (!data) return;

    const diagnostics = JSON.stringify(data, null, 2);
    navigator.clipboard.writeText(diagnostics).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleDiagnoseLayer = async (layer: "devx" | "ucnrr" | "core" | "core_e2e") => {
    setSelectedLayer(layer);
    setDrawerOpen(true);
    setDiagnosticLoading(true);
    setDiagnosticError(null);
    setDiagnosticData(null);

    try {
      const result = await fetchAiReadyLayer(layer, true, false);
      setDiagnosticData(result);
    } catch (err) {
      setDiagnosticError(err instanceof Error ? err.message : "Failed to fetch diagnostic");
    } finally {
      setDiagnosticLoading(false);
    }
  };

  const handleCopyDiagnostic = () => {
    if (!diagnosticData) return;

    const diagnostics = JSON.stringify(diagnosticData, null, 2);
    navigator.clipboard.writeText(diagnostics).then(() => {
      setDiagnosticCopied(true);
      setTimeout(() => setDiagnosticCopied(false), 2000);
    });
  };

  const handleCloseDrawer = () => {
    setDrawerOpen(false);
    setSelectedLayer(null);
    setDiagnosticData(null);
    setDiagnosticError(null);
    setDiagnosticCopied(false);
  };

  // Extract E2E status from core.details
  const getE2EStatus = (core: AiReadyLight): AiReadyLight | null => {
    if (!core.details?.e2e) return null;
    return core.details.e2e as AiReadyLight;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-gray-900">AI Readiness</h2>
          <p className="text-sm text-gray-600 mt-1">
            Traffic-light status for all AI ingestion layers
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Auto-refresh toggle */}
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            Auto-refresh (10s)
          </label>

          {/* Run Probe button */}
          <button
            onClick={handleRunProbe}
            disabled={isLoading}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 transition-colors"
          >
            {isLoading ? "Probing..." : "Run Probe"}
          </button>

          {/* Copy Diagnostics button */}
          <button
            onClick={handleCopyDiagnostics}
            disabled={!data}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:bg-gray-50 disabled:text-gray-400 transition-colors"
          >
            {copied ? "✓ Copied!" : "Copy Diagnostics"}
          </button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 w-5 h-5 text-red-600">⚠</div>
            <div className="flex-1">
              <h3 className="text-sm font-medium text-red-900">Probe Failed</h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Loading State */}
      {isLoading && !data && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
          <div className="inline-block w-6 h-6 border-3 border-blue-600 border-t-transparent rounded-full animate-spin mb-3"></div>
          <p className="text-sm text-gray-600">Running AI readiness probe...</p>
        </div>
      )}

      {/* Success State */}
      {data && (
        <div className="space-y-4">
          {/* Overall Status Badge */}
          {data.result === "ALL-GOOD" ? (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <div className="flex items-center gap-2">
                <span className="text-2xl">✅</span>
                <span className="text-lg font-semibold text-green-900">
                  AI-alive — All systems operational
                </span>
              </div>
              <p className="text-sm text-green-700 mt-1">
                Probe completed in {data.probe_duration_ms}ms
              </p>
            </div>
          ) : (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <span className="text-2xl">❌</span>
                <div className="flex-1">
                  <span className="text-lg font-semibold text-red-900">
                    Needs Fix — System degraded
                  </span>
                  <p className="text-sm text-red-700 mt-1">
                    {getTopFailureReason(data) || "Unknown issue detected"}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Service Status Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* HC/DevX */}
            <ServiceCard
              title="HC/DevX Backend"
              subtitle="Northstar intake"
              light={data.hc_devx}
              details={[
                {
                  label: "Status",
                  value: String((data.hc_devx.details?.status as string | undefined) ?? "unknown"),
                },
              ]}
              onDiagnose={() => handleDiagnoseLayer("devx")}
            />

            {/* UCNRR */}
            <ServiceCard
              title="UCNRR Processing"
              subtitle="LLM extraction"
              light={data.ucnrr}
              details={[
                {
                  label: "LLM Configured",
                  value: String(data.ucnrr.details?.llm_configured || false),
                },
                {
                  label: "Provider",
                  value: String(data.ucnrr.details?.llm_provider || "none"),
                },
                {
                  label: "Model",
                  value: String(data.ucnrr.details?.llm_model || "none"),
                },
              ]}
              onDiagnose={() => handleDiagnoseLayer("ucnrr")}
            />

            {/* Core */}
            <ServiceCard
              title="Core Processing"
              subtitle="Resolver & storage"
              light={data.core}
              details={[
                {
                  label: "RR Mode",
                  value: String(data.core.details?.rr_mode || "unknown"),
                },
                {
                  label: "UCNRR Enabled",
                  value: String(data.core.details?.ucnrr_enabled || false),
                },
              ]}
              onDiagnose={() => handleDiagnoseLayer("core")}
            />
          </div>

          {/* E2E Status (if Core is green) */}
          {data.core.details?.e2e && (
            <E2EStatusCard
              e2e={getE2EStatus(data.core)}
              onDiagnose={() => handleDiagnoseLayer("core_e2e")}
            />
          )}

          {/* Metadata */}
          <div className="text-xs text-gray-500 text-right">
            Last probe: {new Date(data.ts).toLocaleString()} · Duration:{" "}
            {data.probe_duration_ms}ms
          </div>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !data && !error && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
          <p className="text-gray-600">Click "Run Probe" to check AI readiness</p>
        </div>
      )}

      {/* Diagnostic Drawer */}
      {drawerOpen && (
        <DiagnosticDrawer
          layer={selectedLayer}
          data={diagnosticData}
          loading={diagnosticLoading}
          error={diagnosticError}
          copied={diagnosticCopied}
          onCopy={handleCopyDiagnostic}
          onClose={handleCloseDrawer}
        />
      )}
    </div>
  );
}

// Service Card Component
interface ServiceCardProps {
  title: string;
  subtitle: string;
  light: AiReadyLight;
  details: Array<{ label: string; value: string }>;
  onDiagnose: () => void;
}

function ServiceCard({ title, subtitle, light, details, onDiagnose }: ServiceCardProps) {
  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-white shadow-sm">
      {/* Title */}
      <div className="mb-3 flex items-start justify-between">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
          <p className="text-xs text-gray-500">{subtitle}</p>
        </div>
        <button
          onClick={onDiagnose}
          className="text-xs text-blue-600 hover:text-blue-800 font-medium px-2 py-1 rounded hover:bg-blue-50 transition-colors"
          title="Run detailed diagnostic"
        >
          Diagnose
        </button>
      </div>

      {/* Status Pill */}
      <div
        className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium border mb-3 ${getTrafficLightColor(light.status)}`}
      >
        <span className="w-2 h-2 rounded-full bg-current"></span>
        {light.status === "green" ? "Green" : "Red"}
      </div>

      {/* Details */}
      <div className="space-y-1.5">
        {details.map((detail) => (
          <div key={detail.label} className="flex justify-between text-xs">
            <span className="text-gray-600">{detail.label}:</span>
            <span className="font-medium text-gray-900">{detail.value}</span>
          </div>
        ))}
      </div>

      {/* Reason (if red) */}
      {light.reason && (
        <div className="mt-3 pt-3 border-t border-gray-100">
          <p className="text-xs text-red-600">{light.reason}</p>
        </div>
      )}
    </div>
  );
}

// E2E Status Card Component
interface E2EStatusCardProps {
  e2e: AiReadyLight | null;
  onDiagnose: () => void;
}

function E2EStatusCard({ e2e, onDiagnose }: E2EStatusCardProps) {
  if (!e2e) return null;

  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-white shadow-sm">
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <div className="flex items-center justify-between mb-2">
            <div>
              <h3 className="text-sm font-semibold text-gray-900">
                End-to-End Test
              </h3>
              <p className="text-xs text-gray-500">Promotion + Why-Card generation</p>
            </div>
            <button
              onClick={onDiagnose}
              className="text-xs text-blue-600 hover:text-blue-800 font-medium px-2 py-1 rounded hover:bg-blue-50 transition-colors"
              title="Run detailed E2E diagnostic"
            >
              Diagnose
            </button>
          </div>

          <div
            className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium border ${getTrafficLightColor(e2e.status)}`}
          >
            <span className="w-2 h-2 rounded-full bg-current"></span>
            {e2e.status === "green" ? "Green" : "Red"}
          </div>
        </div>
      </div>

      {/* E2E Details */}
      <div className="space-y-1.5 text-xs">
        {e2e.details?.rescore_rr !== undefined && (
          <div className="flex justify-between">
            <span className="text-gray-600">Rescore RR:</span>
            <span className="font-medium text-gray-900">
              {String(e2e.details.rescore_rr)}
            </span>
          </div>
        )}

        {e2e.details?.why_excerpt !== undefined && (
          <div className="mt-2 pt-2 border-t border-gray-100">
            <p className="text-gray-600 mb-1">Why-Card excerpt:</p>
            <p className="text-gray-800 italic">
              &quot;{String(e2e.details.why_excerpt)}&quot;
            </p>
          </div>
        )}

        {e2e.details?.skipped === true && (
          <p className="text-gray-500 italic">
            E2E test skipped ({e2e.reason})
          </p>
        )}
      </div>

      {/* Reason (if red) */}
      {e2e.reason && !e2e.details?.skipped && (
        <div className="mt-3 pt-3 border-t border-gray-100">
          <p className="text-xs text-red-600">{e2e.reason}</p>
        </div>
      )}
    </div>
  );
}

// Diagnostic Drawer Component
interface DiagnosticDrawerProps {
  layer: "devx" | "ucnrr" | "core" | "core_e2e" | null;
  data: LayerDiagnosticResponse | null;
  loading: boolean;
  error: string | null;
  copied: boolean;
  onCopy: () => void;
  onClose: () => void;
}

function DiagnosticDrawer({
  layer,
  data,
  loading,
  error,
  copied,
  onCopy,
  onClose,
}: DiagnosticDrawerProps) {
  const getLayerTitle = (layer: string | null): string => {
    const titles: Record<string, string> = {
      devx: "HC/DevX Backend",
      ucnrr: "UCNRR Processing",
      core: "Core Processing",
      core_e2e: "End-to-End Test",
    };
    return layer ? titles[layer] || layer : "Diagnostic";
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">
              {getLayerTitle(layer)} Diagnostic
            </h3>
            <p className="text-sm text-gray-600 mt-1">
              Detailed layer analysis with verbose diagnostic data
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl font-light leading-none"
            title="Close"
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <div className="inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
              <span className="ml-3 text-gray-600">Running diagnostic...</span>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <span className="text-red-600 text-xl">⚠</span>
                <div>
                  <h4 className="text-sm font-medium text-red-900">Diagnostic Failed</h4>
                  <p className="text-sm text-red-700 mt-1">{error}</p>
                </div>
              </div>
            </div>
          )}

          {data && !loading && !error && (
            <div className="space-y-4">
              {/* Status Banner */}
              <div
                className={`rounded-lg p-4 border ${
                  data.status === "green"
                    ? "bg-green-50 border-green-200"
                    : "bg-red-50 border-red-200"
                }`}
              >
                <div className="flex items-center gap-2">
                  <div
                    className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium ${getTrafficLightColor(data.status)}`}
                  >
                    <span className="w-2 h-2 rounded-full bg-current"></span>
                    {data.status === "green" ? "Green" : "Red"}
                  </div>
                  {data.reason && (
                    <span
                      className={`text-sm ${
                        data.status === "green" ? "text-green-800" : "text-red-800"
                      }`}
                    >
                      {data.reason}
                    </span>
                  )}
                </div>
              </div>

              {/* Suggestions */}
              {data.suggestions && data.suggestions.length > 0 && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <h4 className="text-sm font-semibold text-blue-900 mb-2">
                    Remediation Steps
                  </h4>
                  <ul className="space-y-1.5 text-sm text-blue-800">
                    {data.suggestions.map((suggestion, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <span className="text-blue-600 mt-0.5">•</span>
                        <span>{suggestion}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Details */}
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <h4 className="text-sm font-semibold text-gray-900 mb-2">Details</h4>
                <div className="space-y-1.5 text-sm">
                  {Object.entries(data.details).map(([key, value]) => (
                    <div key={key} className="flex justify-between gap-4">
                      <span className="text-gray-600 font-mono text-xs">{key}:</span>
                      <span className="text-gray-900 font-mono text-xs text-right break-all">
                        {typeof value === "object"
                          ? JSON.stringify(value)
                          : String(value)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Verbose Data */}
              {data.verbose_data && Object.keys(data.verbose_data).length > 0 && (
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                  <h4 className="text-sm font-semibold text-gray-900 mb-2">
                    Verbose Diagnostic Data
                  </h4>
                  <pre className="text-xs font-mono text-gray-700 overflow-x-auto bg-white p-3 rounded border border-gray-200">
                    {JSON.stringify(data.verbose_data, null, 2)}
                  </pre>
                </div>
              )}

              {/* Full JSON */}
              <div className="bg-gray-900 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-sm font-semibold text-gray-100">
                    Complete Diagnostic JSON
                  </h4>
                  <button
                    onClick={onCopy}
                    className="text-xs text-blue-400 hover:text-blue-300 font-medium px-3 py-1.5 rounded bg-gray-800 hover:bg-gray-700 transition-colors"
                  >
                    {copied ? "✓ Copied!" : "Copy to Clipboard"}
                  </button>
                </div>
                <pre className="text-xs font-mono text-green-400 overflow-x-auto max-h-64">
                  {JSON.stringify(data, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
