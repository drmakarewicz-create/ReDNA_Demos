'use client';

/**
 * Portrait Render Card
 *
 * UI component for generating photorealistic portraits from PaDNA traits using local ComfyUI.
 */

import { useState, useCallback, useEffect } from 'react';

type PromptStyle = 'photorealistic' | 'portrait' | 'cinematic' | 'artistic';

interface PortraitRenderCardProps {
  userId: string | null;
  className?: string;
}

interface GenerationResult {
  url: string;
  timestamp: string;
  prompt?: string;
}

export function PortraitRenderCard({ userId, className = '' }: PortraitRenderCardProps) {
  const [style, setStyle] = useState<PromptStyle>('photorealistic');
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [existingPortrait, setExistingPortrait] = useState<string | null>(null);

  // Check for existing portrait when userId changes
  useEffect(() => {
    if (!userId) {
      setExistingPortrait(null);
      setResult(null);
      return;
    }

    // Check if portrait already exists
    fetch(`/api/padna/portrait?userId=${encodeURIComponent(userId)}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.ok && data.exists) {
          setExistingPortrait(data.url);
        } else {
          setExistingPortrait(null);
        }
      })
      .catch(() => {
        // Ignore errors for existence check
      });
  }, [userId]);

  const handleGenerate = useCallback(async () => {
    if (!userId) return;

    setGenerating(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch('/api/padna/portrait', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          userId,
          style,
        }),
      });

      const data = await response.json();

      if (!response.ok || !data.ok) {
        // Handle specific error cases
        if (response.status === 503) {
          setError(
            data.help || 'ComfyUI is not running. Start it with: cd ~/Documents/ReDNA_Demos/ComfyUI && python3 main.py --force-fp16'
          );
        } else {
          setError(data.error || 'Failed to generate portrait');
        }
        return;
      }

      setResult({
        url: data.url,
        timestamp: data.timestamp,
        prompt: data.prompt,
      });
      setExistingPortrait(data.url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Network error occurred');
    } finally {
      setGenerating(false);
    }
  }, [userId, style]);

  if (!userId) {
    return (
      <div className={`rounded-lg border border-slate-700 bg-slate-900/50 p-6 ${className}`}>
        <h3 className="mb-2 text-lg font-semibold text-slate-200">Portrait (beta)</h3>
        <p className="text-sm text-slate-400">Select a user to render a portrait.</p>
      </div>
    );
  }

  return (
    <div className={`rounded-lg border border-slate-700 bg-slate-900/50 p-6 ${className}`}>
      <h3 className="mb-4 text-lg font-semibold text-slate-200">Portrait (beta)</h3>

      {/* Style selector */}
      <div className="mb-4">
        <label htmlFor="portrait-style" className="mb-2 block text-sm font-medium text-slate-300">
          Style
        </label>
        <select
          id="portrait-style"
          value={style}
          onChange={(e) => setStyle(e.target.value as PromptStyle)}
          disabled={generating}
          className="w-full rounded-md border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-200 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500 disabled:opacity-50"
        >
          <option value="photorealistic">Photorealistic</option>
          <option value="portrait">Portrait</option>
          <option value="cinematic">Cinematic</option>
          <option value="artistic">Artistic</option>
        </select>
      </div>

      {/* Generate button */}
      <button
        onClick={handleGenerate}
        disabled={generating}
        className="mb-4 w-full rounded-md bg-cyan-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 focus:ring-offset-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {generating ? (
          <span className="flex items-center justify-center">
            <svg
              className="-ml-1 mr-2 h-4 w-4 animate-spin text-white"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              ></path>
            </svg>
            Generating… ~30–60s
          </span>
        ) : (
          'Generate Portrait'
        )}
      </button>

      {/* Error message */}
      {error && (
        <div className="mb-4 rounded-md border border-red-800 bg-red-900/20 p-3">
          <p className="text-sm font-medium text-red-400">Error</p>
          <p className="mt-1 text-sm text-red-300">{error}</p>
        </div>
      )}

      {/* Success message and image */}
      {result && (
        <div className="mb-4 rounded-md border border-green-800 bg-green-900/20 p-3">
          <p className="text-sm font-medium text-green-400">Success!</p>
          <p className="mt-1 text-sm text-green-300">
            Portrait saved to <code className="rounded bg-slate-800 px-1">{result.url}</code>
          </p>
          <p className="mt-1 text-xs text-slate-400">{new Date(result.timestamp).toLocaleString()}</p>
        </div>
      )}

      {/* Display portrait */}
      {(result || existingPortrait) && (
        <div className="mt-4">
          <div className="relative overflow-hidden rounded-lg border border-slate-700">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={`${result?.url || existingPortrait}?t=${Date.now()}`}
              alt={`Portrait of ${userId}`}
              className="h-auto w-full object-contain"
              style={{ maxHeight: '600px' }}
            />
          </div>

          {result && !existingPortrait && (
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="mt-2 text-sm text-cyan-400 hover:text-cyan-300 hover:underline disabled:opacity-50"
            >
              Re-generate
            </button>
          )}
        </div>
      )}

      {/* Show existing portrait hint */}
      {existingPortrait && !result && (
        <div className="mt-4">
          <p className="mb-2 text-sm text-slate-400">Previous portrait exists. Click Generate to create a new one.</p>
          <div className="relative overflow-hidden rounded-lg border border-slate-700">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={`${existingPortrait}?t=${Date.now()}`}
              alt={`Portrait of ${userId}`}
              className="h-auto w-full object-contain"
              style={{ maxHeight: '600px' }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
