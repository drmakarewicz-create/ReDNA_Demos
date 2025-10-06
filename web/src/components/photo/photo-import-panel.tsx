'use client';

import { useCallback, useState, useRef, useEffect } from 'react';
import {
  importPhotoData,
  fetchCoreHealth,
  applyInferences,
  type PhotoImportResult,
  type InferredTrait
} from '../../lib/api';

interface PhotoImportPanelProps {
  userId: string;
  onImportComplete?: () => void;
}

export function PhotoImportPanel({ userId, onImportComplete }: PhotoImportPanelProps) {
  const [jsonText, setJsonText] = useState('');
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<PhotoImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [featureAvailable, setFeatureAvailable] = useState<boolean | null>(null);
  const [checkingHealth, setCheckingHealth] = useState(true);
  const [selectedInferences, setSelectedInferences] = useState<Set<number>>(new Set());
  const [applyingInferences, setApplyingInferences] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Check if photo import feature is available
  useEffect(() => {
    let mounted = true;

    const checkHealth = async () => {
      try {
        const health = await fetchCoreHealth();
        if (mounted) {
          setFeatureAvailable(health.photo_import_available ?? false);
          setCheckingHealth(false);
        }
      } catch (err) {
        if (mounted) {
          setFeatureAvailable(false);
          setCheckingHealth(false);
        }
      }
    };

    checkHealth();

    return () => {
      mounted = false;
    };
  }, []);

  const handleImport = useCallback(async (data: any) => {
    if (!userId?.trim()) {
      setError('No user selected');
      return;
    }

    setImporting(true);
    setError(null);
    setResult(null);

    try {
      const importResult = await importPhotoData({
        user_id: userId,
        data,
        source: 'photo-import-ui',
      });

      setResult(importResult);

      if (onImportComplete) {
        onImportComplete();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed');
    } finally {
      setImporting(false);
    }
  }, [userId, onImportComplete]);

  const handleTextImport = useCallback(async () => {
    if (!jsonText.trim()) {
      setError('Please enter JSON data or text description');
      return;
    }

    let parsedData: any;

    // Try to parse as JSON first
    try {
      parsedData = JSON.parse(jsonText);
    } catch {
      // If not JSON, treat as plain text description
      parsedData = jsonText;
    }

    await handleImport(parsedData);
  }, [jsonText, handleImport]);

  const handleFileImport = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      const text = await file.text();
      let parsedData: any;

      try {
        parsedData = JSON.parse(text);
      } catch {
        parsedData = text;
      }

      await handleImport(parsedData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to read file');
    }

    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [handleImport]);

  const clearResults = useCallback(() => {
    setResult(null);
    setError(null);
    setSelectedInferences(new Set());
  }, []);

  const toggleInference = useCallback((index: number) => {
    setSelectedInferences(prev => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  }, []);

  const selectAllInferences = useCallback(() => {
    if (!result?.inferences?.traits) return;
    setSelectedInferences(new Set(result.inferences.traits.map((_, idx) => idx)));
  }, [result]);

  const deselectAllInferences = useCallback(() => {
    setSelectedInferences(new Set());
  }, []);

  const handleApplyInferences = useCallback(async () => {
    if (!result?.inferences?.traits || selectedInferences.size === 0 || !userId) return;

    setApplyingInferences(true);
    setError(null);

    try {
      const inferencesToApply = result.inferences.traits.filter((_, idx) =>
        selectedInferences.has(idx)
      );

      const applyResult = await applyInferences({
        user_id: userId,
        inferences: inferencesToApply,
      });

      if (applyResult.ok) {
        // Clear selections and show success
        setSelectedInferences(new Set());
        alert(`✓ ${applyResult.message}`);

        if (onImportComplete) {
          onImportComplete();
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to apply inferences');
    } finally {
      setApplyingInferences(false);
    }
  }, [result, selectedInferences, userId, onImportComplete]);

  return (
    <section className="mt-6 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <header className="mb-4">
        <h3 className="text-base font-semibold text-slate-100">Import PaDNA Data</h3>
        <p className="mt-1 text-xs text-slate-400">
          Import traits from JSON files or plain text descriptions. Supports structured or unstructured formats.
        </p>
      </header>

      {/* Feature Availability Warning */}
      {checkingHealth ? (
        <div className="mb-4 rounded-lg border border-slate-700 bg-slate-900/50 p-3">
          <p className="text-sm text-slate-400">Checking photo import availability...</p>
        </div>
      ) : featureAvailable === false ? (
        <div className="mb-4 rounded-lg border border-amber-500/50 bg-amber-500/10 p-3">
          <div className="flex items-start gap-3">
            <svg className="h-5 w-5 flex-shrink-0 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div className="flex-1">
              <p className="text-sm font-semibold text-amber-300">Photo Import Feature Unavailable</p>
              <p className="mt-1 text-xs text-amber-200">
                The Core API photo import endpoint is not available. This usually means:
              </p>
              <ul className="mt-2 list-inside list-disc space-y-1 text-xs text-amber-200">
                <li>The Core API server needs to be restarted to load the new endpoint</li>
                <li>The PhotoRefinementCoach module failed to import</li>
                <li>The server was started before the photo import code was added</li>
              </ul>
              <p className="mt-2 text-xs text-amber-100">
                <strong>Solution:</strong> Restart the Core API server (port 8015) to enable this feature.
              </p>
            </div>
          </div>
        </div>
      ) : null}

      {/* File Upload */}
      <div className="mb-4">
        <input
          ref={fileInputRef}
          type="file"
          accept=".json,.txt"
          onChange={handleFileImport}
          className="hidden"
          id="photo-import-file"
        />
        <label htmlFor="photo-import-file">
          <span className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-purple-500/60 bg-purple-500/10 px-4 py-2 text-sm font-semibold text-purple-200 hover:bg-purple-500/20 disabled:opacity-40">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            Upload JSON File
          </span>
        </label>
      </div>

      {/* Text Input */}
      <div className="mb-4">
        <label htmlFor="json-text-input" className="mb-2 block text-xs font-medium text-slate-300">
          Or paste JSON / text description:
        </label>
        <textarea
          id="json-text-input"
          value={jsonText}
          onChange={(e) => setJsonText(e.target.value)}
          placeholder={`Structured JSON example:
{
  "observations": {
    "PaDNA.HairDNA.Color": {
      "resolved_value": "Auburn",
      "ucn": 920.5
    }
  }
}

OR plain text:
"Eyes are blue. Hair is brown and shoulder-length. She is 6 feet tall."`}
          className="h-48 w-full rounded-lg border border-slate-700 bg-slate-900 p-3 text-sm text-slate-200 placeholder-slate-600 focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
          disabled={importing || featureAvailable === false}
        />
      </div>

      {/* Action Buttons */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={handleTextImport}
          disabled={importing || !jsonText.trim() || !userId || featureAvailable === false}
          className="rounded-lg border border-purple-500/60 bg-purple-500/10 px-4 py-2 text-sm font-semibold text-purple-200 hover:bg-purple-500/20 disabled:opacity-40"
          title={featureAvailable === false ? 'Photo import feature is unavailable. Please restart Core API.' : ''}
        >
          {importing ? 'Importing...' : 'Import Data'}
        </button>

        {(result || error) && (
          <button
            type="button"
            onClick={clearResults}
            className="rounded-lg border border-slate-600 px-4 py-2 text-sm font-semibold text-slate-300 hover:bg-slate-800"
          >
            Clear Results
          </button>
        )}
      </div>

      {/* Error Display */}
      {error && (
        <div className="mt-4 rounded-lg border border-rose-500/50 bg-rose-500/10 p-3">
          <p className="text-sm font-semibold text-rose-300">Import Error</p>
          <p className="mt-1 text-xs text-rose-200">{error}</p>
        </div>
      )}

      {/* Success Display */}
      {result && (
        <div className="mt-4 space-y-3">
          <div className="rounded-lg border border-emerald-500/50 bg-emerald-500/10 p-3">
            <p className="text-sm font-semibold text-emerald-300">
              Import Successful - {result.imported} trait{result.imported !== 1 ? 's' : ''} imported
            </p>
            {result.rescore_triggered && (
              <p className="mt-1 text-xs text-emerald-200">RR/Curiosity rescore triggered</p>
            )}
          </div>

          {/* Imported Traits */}
          {result.traits.length > 0 && (
            <div className="rounded-lg border border-slate-700 bg-slate-900/50 p-3">
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Imported Traits</h4>
              <div className="space-y-2">
                {result.traits.map((trait, idx) => (
                  <div key={idx} className="flex items-start justify-between text-xs">
                    <span className="font-mono text-cyan-300">{trait.trait}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-slate-300">{JSON.stringify(trait.value)}</span>
                      <span className="rounded bg-purple-500/20 px-2 py-0.5 text-[10px] font-medium text-purple-200">
                        UCN {trait.ucn.toFixed(1)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Quarantined Items */}
          {result.quarantined.length > 0 && (
            <div className="rounded-lg border border-amber-500/50 bg-amber-500/10 p-3">
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-amber-400">
                Quarantined ({result.quarantined.length})
              </h4>
              <div className="space-y-2">
                {result.quarantined.slice(0, 5).map((item, idx) => (
                  <div key={idx} className="text-xs">
                    <div className="font-mono text-amber-300">{item.raw_path || '(no path)'}</div>
                    <div className="mt-0.5 text-[10px] text-amber-200">
                      Reasons: {item.reasons.join(', ')}
                    </div>
                  </div>
                ))}
                {result.quarantined.length > 5 && (
                  <p className="text-[10px] text-amber-200">
                    ... and {result.quarantined.length - 5} more
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Warnings */}
          {result.warnings.length > 0 && (
            <details className="rounded-lg border border-slate-700 bg-slate-900/50 p-3">
              <summary className="cursor-pointer text-xs font-semibold text-slate-400">
                Warnings ({result.warnings.length})
              </summary>
              <div className="mt-2 space-y-1">
                {result.warnings.map((warning, idx) => (
                  <p key={idx} className="text-[10px] text-slate-500">{warning}</p>
                ))}
              </div>
            </details>
          )}

          {/* LLM-Assisted Mappings */}
          {result.assisted.length > 0 && (
            <div className="rounded-lg border border-blue-500/50 bg-blue-500/10 p-3">
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-blue-400">
                LLM-Assisted Mappings ({result.assisted.length})
              </h4>
              <p className="text-[10px] text-blue-200">
                Some traits were automatically mapped to PaDNA paths using AI assistance.
              </p>
            </div>
          )}

          {/* AI-Inferred Traits */}
          {result.inferences && result.inferences.available && result.inferences.count > 0 && (
            <div className="rounded-lg border border-cyan-500/50 bg-cyan-500/5 p-4">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-semibold text-cyan-300">
                    🤖 AI-Inferred Traits ({result.inferences.count})
                  </h4>
                  <p className="mt-1 text-[10px] text-cyan-200">
                    {result.inferences.model_used && `Model: ${result.inferences.model_used} • `}
                    Based on imported traits, AI suggests these related characteristics
                  </p>
                </div>
              </div>

              {/* Bulk Actions */}
              <div className="mb-3 flex items-center gap-2 text-xs">
                <button
                  type="button"
                  onClick={selectAllInferences}
                  className="rounded border border-cyan-500/40 px-2 py-1 text-cyan-300 hover:bg-cyan-500/10"
                >
                  Select All
                </button>
                <button
                  type="button"
                  onClick={deselectAllInferences}
                  className="rounded border border-slate-600 px-2 py-1 text-slate-400 hover:bg-slate-700"
                >
                  Deselect All
                </button>
                <div className="flex-1" />
                <span className="text-slate-400">
                  {selectedInferences.size} selected
                </span>
              </div>

              {/* Inferences List */}
              <div className="space-y-2">
                {result.inferences.traits.map((inference, idx) => {
                  const isSelected = selectedInferences.has(idx);
                  const confidencePercent = Math.round(inference.confidence * 100);

                  return (
                    <div
                      key={idx}
                      className={`rounded-lg border p-3 transition-all ${
                        isSelected
                          ? 'border-cyan-500/60 bg-cyan-500/10'
                          : 'border-slate-700 bg-slate-900/50 hover:border-slate-600'
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        {/* Checkbox */}
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleInference(idx)}
                          className="mt-1 h-4 w-4 cursor-pointer rounded border-slate-600 bg-slate-800 text-cyan-500 focus:ring-2 focus:ring-cyan-500 focus:ring-offset-0"
                        />

                        {/* Content */}
                        <div className="flex-1">
                          {/* Trait Path and Value */}
                          <div className="mb-2 flex items-start justify-between gap-2">
                            <div className="flex-1">
                              <p className="font-mono text-xs text-cyan-300">{inference.trait_path}</p>
                              <p className="mt-0.5 text-sm font-semibold text-slate-200">
                                {JSON.stringify(inference.value)}
                              </p>
                            </div>

                            {/* Confidence Badge */}
                            <div className="flex-shrink-0">
                              <div
                                className={`rounded px-2 py-1 text-xs font-semibold ${
                                  confidencePercent >= 80
                                    ? 'bg-emerald-500/20 text-emerald-300'
                                    : confidencePercent >= 60
                                    ? 'bg-amber-500/20 text-amber-300'
                                    : 'bg-slate-500/20 text-slate-300'
                                }`}
                              >
                                {confidencePercent}% confident
                              </div>
                            </div>
                          </div>

                          {/* Confidence Bar */}
                          <div className="mb-2 h-1 w-full overflow-hidden rounded-full bg-slate-800">
                            <div
                              className={`h-full transition-all ${
                                confidencePercent >= 80
                                  ? 'bg-emerald-500'
                                  : confidencePercent >= 60
                                  ? 'bg-amber-500'
                                  : 'bg-slate-500'
                              }`}
                              style={{ width: `${confidencePercent}%` }}
                            />
                          </div>

                          {/* Reasoning */}
                          <div className="mb-2 text-[11px] text-slate-400">
                            <span className="font-semibold text-slate-300">Reasoning:</span>{' '}
                            {inference.reasoning}
                          </div>

                          {/* Source Traits */}
                          {inference.source_traits && inference.source_traits.length > 0 && (
                            <div className="flex flex-wrap gap-1">
                              {inference.source_traits.map((source, sourceIdx) => (
                                <span
                                  key={sourceIdx}
                                  className="rounded bg-slate-800 px-2 py-0.5 text-[10px] font-mono text-slate-400"
                                >
                                  {source}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Apply Button */}
              <div className="mt-4 flex items-center gap-3">
                <button
                  type="button"
                  onClick={handleApplyInferences}
                  disabled={selectedInferences.size === 0 || applyingInferences}
                  className="flex-1 rounded-lg border border-cyan-500/60 bg-cyan-500/10 px-4 py-2 text-sm font-semibold text-cyan-200 hover:bg-cyan-500/20 disabled:opacity-40"
                >
                  {applyingInferences
                    ? 'Applying...'
                    : `Apply ${selectedInferences.size} Selected Inference${selectedInferences.size !== 1 ? 's' : ''}`}
                </button>
              </div>

              {/* Warnings */}
              {result.inferences.warnings && result.inferences.warnings.length > 0 && (
                <details className="mt-3 rounded border border-slate-700 bg-slate-900/30 p-2">
                  <summary className="cursor-pointer text-[10px] font-semibold text-slate-400">
                    Inference Warnings ({result.inferences.warnings.length})
                  </summary>
                  <div className="mt-2 space-y-1">
                    {result.inferences.warnings.map((warning, idx) => (
                      <p key={idx} className="text-[10px] text-slate-500">{warning}</p>
                    ))}
                  </div>
                </details>
              )}
            </div>
          )}

          {/* No Inferences Generated */}
          {result.inferences && result.inferences.available && result.inferences.count === 0 && (
            <div className="rounded-lg border border-slate-700 bg-slate-900/50 p-3">
              <p className="text-xs text-slate-400">
                ℹ️ AI inference was enabled but no additional traits could be confidently inferred from the imported data.
              </p>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
