import { useState, useEffect } from 'react'
import { devxApi, TraitSummary, TraitDefinition } from '@/lib/devxApi'
import { devxUrl } from '@/lib/env'
import TraitBrowser from './panels/TraitBrowser'
import DefinitionEditor from './panels/DefinitionEditor'

export default function TraitWorkshop() {
  const [traits, setTraits] = useState<TraitSummary[]>([])
  const [selectedTrait, setSelectedTrait] = useState<TraitDefinition | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [usingSynthetic, setUsingSynthetic] = useState(false)
  const [syntheticSource, setSyntheticSource] = useState<string | null>(null)
  const [infoMessage, setInfoMessage] = useState<string | null>(null)

  // Load traits on mount
  useEffect(() => {
    loadTraits()
  }, [])

  const loadTraits = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await devxApi.listTraits()
      if (!data || data.length === 0) {
        await loadSyntheticTraits('empty-registry')
      } else {
        setTraits(data)
        setUsingSynthetic(false)
        setSyntheticSource(null)
        setInfoMessage(null)
      }
    } catch (err) {
      await loadSyntheticTraits(err instanceof Error ? err.message : 'Failed to load traits')
    } finally {
      setLoading(false)
    }
  }

  const loadSyntheticTraits = async (reason: string) => {
    try {
      const response = await fetch(devxUrl('/synthetic/traits'))
      if (!response.ok) {
        throw new Error(`Synthetic traits unavailable: ${response.statusText}`)
      }
      const payload = await response.json()
      const containers = Array.isArray(payload.containers) ? payload.containers : []
      const syntheticTraits = containers.map((container: any, index: number): TraitSummary => {
        const path = container.path || `Synthetic/Container${index + 1}`
        const namespace = path.includes('/') ? path.split('/')[0] : 'Synthetic'
        return {
          path,
          namespace,
          name: container.label || container.name || path.split('/').pop() || `Synthetic Trait ${index + 1}`,
          version: 'synthetic',
          status: 'synthetic',
          has_value_model: false,
          has_trait_semantics: false,
        }
      })
      setTraits(syntheticTraits)
      setUsingSynthetic(true)
      setSyntheticSource(reason)
      setSelectedTrait(null)
      setInfoMessage('Using synthetic trait catalog for demo purposes. Connect to DevX backend to edit live traits.')
      setError(null)
    } catch (syntheticError) {
      setError(
        syntheticError instanceof Error
          ? syntheticError.message
          : 'Failed to load synthetic traits. Please start the DevX backend.'
      )
    }
  }

  const handleTraitSelect = async (path: string) => {
    try {
      setLoading(true)
      setError(null)
      setInfoMessage(null)
      if (usingSynthetic) {
        setSelectedTrait(null)
        setError('Synthetic mode: trait definitions are not editable. Start DevX backend to load live definitions.')
        return
      }
      const definition = await devxApi.getTraitDefinition(path)
      setSelectedTrait(definition)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load trait definition')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-3xl font-bold text-gray-900">🧬 Trait Workshop</h2>
        <p className="mt-2 text-sm text-gray-600">
          Edit and validate trait definitions with value models and semantics
        </p>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Error</h3>
              <div className="mt-2 text-sm text-red-700">{error}</div>
            </div>
          </div>
        </div>
      )}

      {/* Info Alert */}
      {infoMessage && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex">
            <svg className="h-5 w-5 text-blue-400" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M18 10A8 8 0 11.001 9.999 8 8 0 0118 10zm-9-4a1 1 0 100 2 1 1 0 000-2zm.75 3.75a.75.75 0 00-1.5 0v4.5a.75.75 0 001.5 0v-4.5z" clipRule="evenodd" />
            </svg>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-blue-800">Synthetic Preview</h3>
              <div className="mt-1 text-sm text-blue-700">{infoMessage}</div>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="grid grid-cols-12 gap-6">
        {/* Trait Browser - Left Column */}
        <div className="col-span-4">
          <TraitBrowser
            traits={traits}
            loading={loading}
            onSelect={handleTraitSelect}
            selectedPath={selectedTrait?.path}
          />
        </div>

        {/* Definition Editor - Right Column */}
        <div className="col-span-8">
          {usingSynthetic ? (
            <div className="bg-white rounded-lg border border-dashed border-blue-200 p-8 text-center">
              <p className="text-lg font-semibold text-blue-700">Synthetic Preview Mode</p>
              <p className="mt-2 text-sm text-blue-600">
                Trait definitions are read-only when DevX backend is unavailable. Start the DevX backend and refresh to edit real traits.
              </p>
              {syntheticSource && (
                <p className="mt-2 text-xs text-blue-500">Reason: {syntheticSource}</p>
              )}
            </div>
          ) : selectedTrait ? (
            <DefinitionEditor
              definition={selectedTrait}
              onSave={(updatedDef) => {
                setSelectedTrait(updatedDef)
                loadTraits() // Reload list
              }}
            />
          ) : (
            <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
              <svg
                className="mx-auto h-12 w-12 text-gray-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              <h3 className="mt-2 text-sm font-medium text-gray-900">No trait selected</h3>
              <p className="mt-1 text-sm text-gray-500">
                Select a trait from the browser to view and edit its definition
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
