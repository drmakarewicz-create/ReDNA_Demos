import { useState } from 'react'
import { TraitDefinition, devxApi } from '@/lib/devxApi'
import SemanticsEditor from './SemanticsEditor'

interface DefinitionEditorProps {
  definition: TraitDefinition
  onSave: (updated: TraitDefinition) => void
}

export default function DefinitionEditor({ definition, onSave }: DefinitionEditorProps) {
  const [activeTab, setActiveTab] = useState<'metadata' | 'value_model' | 'semantics'>('metadata')
  const [valueModel, setValueModel] = useState<Record<string, any>>(
    definition.value_model || { canonical_type: 'numeric', range: [0, 100], unit: 'none' }
  )
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)

  const handleSaveValueModel = async () => {
    try {
      setSaving(true)
      setSaveError(null)
      setSaveSuccess(false)

      await devxApi.assertTraitValue(definition.path, valueModel)

      // Reload definition
      const updated = await devxApi.getTraitDefinition(definition.path)
      onSave(updated)

      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  const handleSemanticsApplied = async () => {
    try {
      const updated = await devxApi.getTraitDefinition(definition.path)
      onSave(updated)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to refresh trait after applying semantics.')
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
        <h3 className="text-lg font-semibold text-gray-900">{definition.container.name}</h3>
        <p className="text-sm text-gray-600 mt-1">{definition.path}</p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex -mb-px">
          {[
            { id: 'metadata', label: 'Metadata', icon: '📄' },
            { id: 'value_model', label: 'Value Model', icon: '🎯' },
            { id: 'semantics', label: 'Semantics', icon: '🧠' },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <span className="mr-2">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Content */}
      <div className="p-6">
        {/* Success Alert */}
        {saveSuccess && (
          <div className="mb-4 bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex">
              <svg className="h-5 w-5 text-green-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <div className="ml-3">
                <p className="text-sm font-medium text-green-800">Saved successfully!</p>
              </div>
            </div>
          </div>
        )}

        {/* Error Alert */}
        {saveError && (
          <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex">
              <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <div className="ml-3">
                <p className="text-sm font-medium text-red-800">{saveError}</p>
              </div>
            </div>
          </div>
        )}

        {/* Metadata Tab */}
        {activeTab === 'metadata' && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Namespace</label>
                <input
                  type="text"
                  value={definition.container.namespace}
                  readOnly
                  className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-600"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Version</label>
                <input
                  type="text"
                  value={definition.container.version || 'v1'}
                  readOnly
                  className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-600"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
                <input
                  type="text"
                  value={definition.container.status || 'prototype'}
                  readOnly
                  className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-600"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">ID</label>
                <input
                  type="text"
                  value={definition.container.id}
                  readOnly
                  className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-600"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
              <textarea
                value={definition.container.description || ''}
                readOnly
                rows={4}
                className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-600"
              />
            </div>
          </div>
        )}

        {/* Value Model Tab */}
        {activeTab === 'value_model' && (
          <div className="space-y-4">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
              <p className="text-sm text-blue-800">
                <strong>Value Model</strong> defines the canonical data type and constraints for this trait.
              </p>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Canonical Type</label>
                <select
                  value={valueModel.canonical_type}
                  onChange={(e) => setValueModel({ ...valueModel, canonical_type: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                >
                  <option value="numeric">Numeric</option>
                  <option value="categorical">Categorical</option>
                  <option value="ordinal">Ordinal</option>
                  <option value="boolean">Boolean</option>
                  <option value="text">Text</option>
                  <option value="composite">Composite</option>
                </select>
              </div>

              {valueModel.canonical_type === 'numeric' && (
                <>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Min</label>
                      <input
                        type="number"
                        value={valueModel.range?.[0] || 0}
                        onChange={(e) => setValueModel({
                          ...valueModel,
                          range: [parseFloat(e.target.value), valueModel.range?.[1] || 100]
                        })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Max</label>
                      <input
                        type="number"
                        value={valueModel.range?.[1] || 100}
                        onChange={(e) => setValueModel({
                          ...valueModel,
                          range: [valueModel.range?.[0] || 0, parseFloat(e.target.value)]
                        })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Unit</label>
                    <input
                      type="text"
                      value={valueModel.unit || 'none'}
                      onChange={(e) => setValueModel({ ...valueModel, unit: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      placeholder="e.g., meters, seconds, none"
                    />
                  </div>
                </>
              )}

              {valueModel.canonical_type === 'categorical' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Categories (JSON array)</label>
                  <textarea
                    value={JSON.stringify(valueModel.categories || [], null, 2)}
                    onChange={(e) => {
                      try {
                        const parsed = JSON.parse(e.target.value)
                        setValueModel({ ...valueModel, categories: parsed })
                      } catch {}
                    }}
                    rows={6}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm"
                  />
                </div>
              )}

              <div className="pt-4 border-t border-gray-200">
                <button
                  onClick={handleSaveValueModel}
                  disabled={saving}
                  className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                >
                  {saving ? 'Saving...' : 'Save Value Model'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Semantics Tab */}
        {/* Semantics Tab */}
        {activeTab === 'semantics' && (
          <SemanticsEditor
            traitPath={definition.path}
            initialSemantics={definition.trait_semantics ?? null}
            onApplied={handleSemanticsApplied}
          />
        )}
      </div>
    </div>
  )
}
