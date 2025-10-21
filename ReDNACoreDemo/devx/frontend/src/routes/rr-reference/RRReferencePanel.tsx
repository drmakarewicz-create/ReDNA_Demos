import { useEffect, useMemo, useState } from 'react'
import { toast } from 'react-toastify'
import {
  fetchReferenceConfig,
  fetchReferenceSamples,
  fetchReferenceStatus,
  ReferenceConfig,
  ReferenceSamplesResponse,
  ReferenceStatusResponse,
  saveReferenceConfig,
} from '../../lib/referenceApi'

type TraitCheckResult = {
  traitId: string
  status?: ReferenceStatusResponse
  samples?: ReferenceSamplesResponse
  error?: string
}

const UNIVERSE_OPTIONS: Array<{ value: ReferenceConfig['universe']; label: string; note: string }> = [
  { value: 'combined', label: 'Combined', note: 'Full synthetic population' },
  { value: 'low', label: 'Low Refinement', note: 'Exploratory / low RR' },
  { value: 'medium', label: 'Medium Refinement', note: 'Balanced variance' },
  { value: 'high', label: 'High Refinement', note: 'Polished candidates' },
]

const COHORT_OPTIONS: Array<{ key: string; label: string; description: string }> = [
  { key: 'age', label: 'Age Band', description: 'Age-based cohort splits' },
  { key: 'region', label: 'Region', description: 'Regional segmentation' },
  { key: 'language', label: 'Language', description: 'Primary language grouping' },
]

const MIN_ACTUAL_THRESHOLD = 60

const formatTimestamp = (value?: string) => {
  if (!value) return '—'
  try {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) {
      return value
    }
    return `${date.toLocaleDateString()} ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
  } catch {
    return value
  }
}

const parseTraitInput = (input: string): string[] =>
  input
    .split(/[\n,]+/)
    .map((value) => value.trim())
    .filter(Boolean)

const pluckString = (payload: Record<string, unknown> | undefined, keys: string[]): string | undefined => {
  if (!payload) return undefined
  for (const key of keys) {
    const value = payload[key]
    if (typeof value === 'string' && value.trim().length > 0) {
      return value
    }
    if (Array.isArray(value)) {
      const joined = value.map((entry) => String(entry).trim()).filter(Boolean).join(', ')
      if (joined) {
        return joined
      }
    }
  }
  return undefined
}

const clampSamples = (value?: number) => {
  if (!value || Number.isNaN(value) || value < 0) return 0
  return value
}

const RRReferencePanel = () => {
  const [config, setConfig] = useState<ReferenceConfig | null>(null)
  const [restartHint, setRestartHint] = useState<string | undefined>()
  const [configLoading, setConfigLoading] = useState<boolean>(true)
  const [saving, setSaving] = useState<boolean>(false)
  const [checking, setChecking] = useState<boolean>(false)
  const [traitInput, setTraitInput] = useState<string>('')
  const [cohortOverride, setCohortOverride] = useState<string>('')
  const [results, setResults] = useState<TraitCheckResult[]>([])

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const payload = await fetchReferenceConfig()
        if (!cancelled) {
          setConfig(payload.config)
          setRestartHint(payload.restart_hint)
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to load RR reference configuration.'
        toast.error(message)
      } finally {
        if (!cancelled) {
          setConfigLoading(false)
        }
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  const handleSourceChange = (source: ReferenceConfig['source']) => {
    setConfig((prev) => {
      if (!prev) return prev
      if (prev.source === source) {
        return prev
      }
      return {
        ...prev,
        source,
        cohort_keys: source === 'ACTUAL' ? prev.cohort_keys : [],
      }
    })
  }

  const handleUniverseChange = (universe: ReferenceConfig['universe']) => {
    setConfig((prev) => (prev ? { ...prev, universe } : prev))
  }

  const handleCohortToggle = (key: string) => {
    setConfig((prev) => {
      if (!prev) return prev
      if (prev.source !== 'ACTUAL') return prev
      const exists = prev.cohort_keys.includes(key)
      const updated = exists ? prev.cohort_keys.filter((item) => item !== key) : [...prev.cohort_keys, key]
      return { ...prev, cohort_keys: updated }
    })
  }

  const handleSave = async () => {
    if (!config) return
    setSaving(true)
    try {
      const payload = await saveReferenceConfig(config)
      setConfig(payload.config)
      setRestartHint(payload.restart_hint)
      setResults([])
      toast.success(payload.message ?? 'Reference configuration saved. Restart Core via CP++ Nuclear to apply.')
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to save reference configuration.'
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  const handleCheck = async () => {
    if (!config) {
      toast.error('Configuration not loaded yet.')
      return
    }
    const traitIds = parseTraitInput(traitInput)
    if (traitIds.length === 0) {
      toast.warn('Enter at least one trait ID.')
      return
    }

    const cohortParam =
      cohortOverride.trim().length > 0
        ? cohortOverride.trim()
        : config.source === 'ACTUAL' && config.cohort_keys.length > 0
        ? config.cohort_keys.join(',')
        : undefined

    setChecking(true)
    try {
      const nextResults = await Promise.all(
        traitIds.map(async (traitId) => {
          try {
            const [status, samples] = await Promise.all([
              fetchReferenceStatus(traitId, cohortParam),
              fetchReferenceSamples(traitId),
            ])
            return {
              traitId,
              status,
              samples,
            } satisfies TraitCheckResult
          } catch (error) {
            const message = error instanceof Error ? error.message : String(error)
            return {
              traitId,
              error: message,
            } satisfies TraitCheckResult
          }
        })
      )
      setResults(nextResults)
      if (nextResults.every((entry) => entry.error)) {
        toast.error('Trait checks failed. Review errors below.')
      } else {
        toast.success('Trait samples refreshed.')
      }
    } finally {
      setChecking(false)
    }
  }

  const maxSamples = useMemo(() => {
    const values = results
      .map((entry) => clampSamples(entry.samples?.n_samples))
      .filter((value) => value > 0)
    if (values.length === 0) return 0
    return Math.max(...values)
  }, [results])

  const sampleBarWidth = (value?: number) => {
    const samples = clampSamples(value)
    if (!samples || !maxSamples) return '4px'
    const ratio = Math.min(1, samples / maxSamples)
    return `${Math.max(4, Math.round(ratio * 100))}%`
  }

  const statusCohortKeys =
    config?.source === 'ACTUAL' && config?.cohort_keys.length
      ? config.cohort_keys.join(', ')
      : '—'

  if (configLoading) {
    return (
      <div className="space-y-6">
        <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm text-slate-500">Loading RR reference configuration…</p>
        </div>
      </div>
    )
  }

  if (!config) {
    return (
      <div className="space-y-6">
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 shadow-sm">
          <p className="text-sm text-red-700">Unable to load RR reference configuration. Check backend logs.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <header className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">RR Reference Controls</h2>
            <p className="text-sm text-slate-500">
              Switch between synthetic and actual reference populations. Save to persist and reboot Core via CP++
              Nuclear to apply.
            </p>
          </div>
          <div className="text-right text-xs text-slate-400 leading-tight">
            <div>Config path</div>
            <code className="font-mono text-[11px] text-slate-500">config/rr_reference.json</code>
            <div className="mt-1">Updated: {formatTimestamp(config.updated_at || undefined)}</div>
          </div>
        </header>

        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <div className="space-y-4">
            <div>
              <span className="text-xs uppercase font-semibold text-slate-500">Reference Source</span>
              <div className="mt-3 grid grid-cols-2 gap-3">
                {(['SYNTHETIC', 'ACTUAL'] as const).map((option) => {
                  const active = config.source === option
                  return (
                    <button
                      key={option}
                      type="button"
                      onClick={() => handleSourceChange(option)}
                      className={[
                        'rounded-lg border px-4 py-3 text-left transition shadow-sm',
                        active
                          ? 'border-blue-500 bg-blue-50 text-blue-900'
                          : 'border-slate-200 bg-white text-slate-600 hover:border-blue-300 hover:text-blue-700',
                      ].join(' ')}
                    >
                      <div className="text-sm font-semibold">
                        {option === 'SYNTHETIC' ? 'Synthetic Population' : 'Actual Cohort'}
                      </div>
                      <div className="text-xs text-slate-500 mt-1">
                        {option === 'SYNTHETIC'
                          ? 'Uses calibrated synthetic universes with guardrails.'
                          : 'Samples from live production cohorts filtered by keys.'}
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>

            {config.source === 'SYNTHETIC' ? (
              <div>
                <span className="text-xs uppercase font-semibold text-slate-500">Synthetic Universe</span>
                <div className="mt-3 space-y-2">
                  {UNIVERSE_OPTIONS.map((option) => (
                    <label
                      key={option.value}
                      className={[
                        'flex cursor-pointer items-start gap-3 rounded-lg border px-4 py-3 shadow-sm transition',
                        config.universe === option.value
                          ? 'border-blue-500 bg-blue-50 text-blue-900'
                          : 'border-slate-200 bg-white hover:border-blue-300 hover:text-blue-700',
                      ].join(' ')}
                    >
                      <input
                        type="radio"
                        className="mt-1 h-4 w-4 text-blue-600"
                        checked={config.universe === option.value}
                        onChange={() => handleUniverseChange(option.value)}
                      />
                      <div>
                        <div className="text-sm font-semibold">{option.label}</div>
                        <div className="text-xs text-slate-500">{option.note}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            ) : (
              <div>
                <span className="text-xs uppercase font-semibold text-slate-500">Cohort Keys</span>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  {COHORT_OPTIONS.map((option) => {
                    const checked = config.cohort_keys.includes(option.key)
                    return (
                      <label
                        key={option.key}
                        className={[
                          'flex cursor-pointer items-start gap-3 rounded-lg border px-4 py-3 shadow-sm transition',
                          checked
                            ? 'border-blue-500 bg-blue-50 text-blue-900'
                            : 'border-slate-200 bg-white hover:border-blue-300 hover:text-blue-700',
                        ].join(' ')}
                      >
                        <input
                          type="checkbox"
                          className="mt-1 h-4 w-4 text-blue-600"
                          checked={checked}
                          onChange={() => handleCohortToggle(option.key)}
                        />
                        <div>
                          <div className="text-sm font-semibold">{option.label}</div>
                          <div className="text-xs text-slate-500">{option.description}</div>
                        </div>
                      </label>
                    )
                  })}
                </div>
              </div>
            )}
          </div>

          <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
            <h3 className="text-sm font-semibold text-slate-700">Guardrails</h3>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-slate-500">
              <li>FaceDNA correlations stay positive versus NoseDNA to avoid contradictory profiles.</li>
              <li>Cross-umbrella correlations remain modest so PaDNA.Face only nudges BehDNA.Chronotype.</li>
              <li>High refinement universes lift means without saturating (avoid values &gt; 0.95).</li>
              <li>All traits are clamped between 0–1 (UCN 0–1000) after sampling to maintain RR ranges.</li>
              <li>Calibration scripts ship alongside this panel for quantile and correlation inspection.</li>
            </ul>
            {restartHint && (
              <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                {restartHint}
              </div>
            )}
          </div>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-blue-500 disabled:opacity-60"
          >
            {saving ? 'Saving…' : 'Save & Restart Hint'}
          </button>
          <span className="text-xs text-slate-500">
            Changes write to <code className="font-mono text-[11px]">config/rr_reference.json</code>. Restart Core via
            CP++ Nuclear after saving.
          </span>
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <header>
          <h2 className="text-lg font-semibold text-slate-900">Trait Sample Check</h2>
          <p className="text-sm text-slate-500">
            Fetch the active reference metadata for one or more traits. The panel will show current sample counts,
            universes, and fallback reasons.
          </p>
        </header>

        <div className="mt-4 grid gap-4 md:grid-cols-[2fr,1fr]">
          <div className="space-y-2">
            <label className="text-xs uppercase font-semibold text-slate-500">Trait IDs</label>
            <textarea
              value={traitInput}
              onChange={(event) => setTraitInput(event.target.value)}
              rows={4}
              placeholder="PaDNA.Sleep.Chronotype"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
            />
            <p className="text-xs text-slate-500">One per line or comma separated.</p>
          </div>
          <div className="space-y-2">
            <label className="text-xs uppercase font-semibold text-slate-500">Cohort Override (optional)</label>
            <input
              type="text"
              value={cohortOverride}
              onChange={(event) => setCohortOverride(event.target.value)}
              placeholder="age,region"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
            />
            <p className="text-xs text-slate-500">
              Leave blank to use the configured cohort keys ({statusCohortKeys || '—'}).
            </p>
          </div>
        </div>

        <div className="mt-4 flex items-center gap-3">
          <button
            type="button"
            onClick={handleCheck}
            disabled={checking}
            className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-slate-800 disabled:opacity-60"
          >
            {checking ? 'Checking…' : 'Check Trait'}
          </button>
          <span className="text-xs text-slate-500">
            We proxy <code className="font-mono text-[11px]">/core/rr/reference/status</code> and{' '}
            <code className="font-mono text-[11px]">/core/rr/reference/samples</code>. Sparkline scales to the largest
            sample size returned.
          </span>
        </div>

        {results.length > 0 && (
          <div className="mt-6 overflow-hidden rounded-lg border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2 text-left font-semibold">Trait</th>
                  <th className="px-3 py-2 text-left font-semibold">Source</th>
                  <th className="px-3 py-2 text-left font-semibold">Universe / Cohort</th>
                  <th className="px-3 py-2 text-left font-semibold">Samples</th>
                  <th className="px-3 py-2 text-left font-semibold">Generated</th>
                  <th className="px-3 py-2 text-left font-semibold">Fallback</th>
                  <th className="px-3 py-2 text-left font-semibold">Reference Path</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm text-slate-700">
                {results.map((entry) => {
                  const nSamples = clampSamples(entry.samples?.n_samples)
                  const source =
                    entry.samples?.source ||
                    pluckString(entry.status?.core, ['source', 'reference_source']) ||
                    config.source
                  const universe =
                    pluckString(entry.status?.core, ['universe', 'reference_universe']) ||
                    (config.source === 'SYNTHETIC' ? config.universe : undefined)
                  const cohort =
                    pluckString(entry.status?.core, ['cohort', 'cohort_keys']) ||
                    (config.source === 'ACTUAL' ? statusCohortKeys : undefined)
                  const referencePath =
                    pluckString(entry.status?.core, ['reference_path', 'rr_meta_path', 'rr_meta_reference']) || '—'
                  const fallback = entry.samples?.fallback_reason ?? '—'
                  const generated = formatTimestamp(entry.samples?.generated_at)

                  return (
                    <tr key={entry.traitId} className="bg-white">
                      <td className="px-3 py-3 font-medium text-slate-900">{entry.traitId}</td>
                      <td className="px-3 py-3">
                        <span
                          className={[
                            'inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium uppercase',
                            source === 'ACTUAL'
                              ? 'bg-emerald-100 text-emerald-700'
                              : 'bg-blue-100 text-blue-700',
                          ].join(' ')}
                        >
                          {source || '—'}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-sm text-slate-600">
                        <div>{universe || '—'}</div>
                        <div className="text-xs text-slate-400">{cohort || '—'}</div>
                      </td>
                      <td className="px-3 py-3 text-sm">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-800">{nSamples ? nSamples.toLocaleString() : '0'}</span>
                          <div className="h-2 w-32 rounded-full bg-slate-200">
                            <div
                              className="h-2 rounded-full bg-blue-500 transition-all"
                              style={{ width: sampleBarWidth(nSamples) }}
                            />
                          </div>
                        </div>
                        {source === 'ACTUAL' && nSamples > 0 && nSamples < MIN_ACTUAL_THRESHOLD && (
                          <div className="mt-1 rounded border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] text-amber-700">
                            Low sample count ({nSamples}). Consider broadening cohorts.
                          </div>
                        )}
                        {entry.error && (
                          <div className="mt-1 rounded border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-600">
                            {entry.error}
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-3 text-sm text-slate-600">{generated}</td>
                      <td className="px-3 py-3 text-sm">
                        <span
                          className={[
                            'inline-flex items-center rounded-full px-2 py-1 text-xs',
                            fallback !== '—' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-500',
                          ].join(' ')}
                        >
                          {fallback}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-xs text-slate-500">
                        <code className="font-mono text-[11px]">{referencePath}</code>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}

export default RRReferencePanel
