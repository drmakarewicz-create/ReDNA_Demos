import { useState } from 'react'
import { TraitSummary } from '@/lib/devxApi'

interface TraitBrowserProps {
  traits: TraitSummary[]
  loading: boolean
  onSelect: (path: string) => void
  selectedPath?: string
}

export default function TraitBrowser({ traits, loading, onSelect, selectedPath }: TraitBrowserProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [namespaceFilter, setNamespaceFilter] = useState<string>('')

  // Filter traits
  const filteredTraits = traits.filter(trait => {
    const matchesSearch = trait.path.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         trait.name.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesNamespace = !namespaceFilter || trait.namespace === namespaceFilter
    return matchesSearch && matchesNamespace
  })

  // Get unique namespaces
  const namespaces = [...new Set(traits.map(t => t.namespace))].sort()

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
        <h3 className="text-sm font-semibold text-gray-700">Trait Browser</h3>
        <p className="text-xs text-gray-500 mt-1">{traits.length} traits total</p>
      </div>

      {/* Filters */}
      <div className="p-4 space-y-3 border-b border-gray-200">
        {/* Search */}
        <div>
          <input
            type="text"
            placeholder="Search traits..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Namespace Filter */}
        <div>
          <select
            value={namespaceFilter}
            onChange={(e) => setNamespaceFilter(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Namespaces</option>
            {namespaces.map(ns => (
              <option key={ns} value={ns}>{ns}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Trait List */}
      <div className="overflow-y-auto" style={{ maxHeight: '600px' }}>
        {loading ? (
          <div className="p-4 text-center text-gray-500">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto"></div>
            <p className="mt-2 text-sm">Loading traits...</p>
          </div>
        ) : filteredTraits.length === 0 ? (
          <div className="p-4 text-center text-gray-500">
            <p className="text-sm">No traits found</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {filteredTraits.map(trait => (
              <button
                key={trait.path}
                onClick={() => onSelect(trait.path)}
                className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors ${
                  selectedPath === trait.path ? 'bg-blue-50 border-l-4 border-blue-500' : ''
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {trait.name}
                    </p>
                    <p className="text-xs text-gray-500 mt-1 truncate">
                      {trait.path}
                    </p>
                  </div>
                  <div className="ml-2 flex-shrink-0">
                    {trait.has_value_model && (
                      <span className="inline-block w-2 h-2 bg-green-400 rounded-full" title="Has value model"></span>
                    )}
                  </div>
                </div>
                <div className="mt-2 flex items-center space-x-2">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
                    {trait.namespace}
                  </span>
                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                    trait.status === 'production' ? 'bg-green-100 text-green-800' :
                    trait.status === 'beta' ? 'bg-yellow-100 text-yellow-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {trait.status}
                  </span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
