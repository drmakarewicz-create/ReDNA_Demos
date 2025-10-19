import { useState, useEffect } from 'react'
import { DEVX_API_BASE } from '@/lib/env'

const API_BASE = DEVX_API_BASE

interface MetadataTabProps {
  coachId: string
  coachLabel: string
}

interface CoachMetadata {
  coach_id: string
  devx_registry: {
    id: string
    label: string
    filename: string
    source: string
  }
  core_yaml: {
    category?: string
    capabilities?: string[]
    icon?: string
    description?: string
    source?: string
    error?: string
  }
  filesystem: {
    prompt_path: string
    features_path: string
    prompt_exists: boolean
    features_exists: boolean
    prompt_size_bytes: number
    features_size_bytes: number
    prompt_modified_at?: string
    source: string
  }
}

export default function MetadataTab({ coachId, coachLabel }: MetadataTabProps) {
  const [metadata, setMetadata] = useState<CoachMetadata | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadMetadata()
  }, [coachId])

  const loadMetadata = async () => {
    setLoading(true)
    try {
      const response = await fetch(`${API_BASE}/coaches/${encodeURIComponent(coachId)}/metadata`)
      if (response.ok) {
        const data = await response.json()
        setMetadata(data)
      }
    } catch (error) {
      console.error('Failed to load metadata:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B'
    const units = ['B', 'KB', 'MB']
    const index = Math.floor(Math.log(bytes) / Math.log(1024))
    return `${(bytes / Math.pow(1024, index)).toFixed(1)} ${units[index]}`
  }

  const formatDate = (isoString?: string) => {
    if (!isoString) return 'N/A'
    try {
      return new Date(isoString).toLocaleString()
    } catch {
      return isoString
    }
  }

  return (
    <div className="space-y-6">
      {/* Coach Header */}
      <div className="pb-3 border-b border-gray-200">
        <h2 className="text-xl font-bold text-gray-900">{coachLabel}</h2>
        <p className="text-sm text-gray-500 mt-1">Registry metadata and configuration</p>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading metadata...</div>
      ) : metadata ? (
        <>
          {/* DevX Registry Section */}
          <div>
            <div className="flex items-center space-x-2 mb-3">
              <h3 className="text-md font-semibold text-gray-900">DevX Registry</h3>
              <span className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                {metadata.devx_registry.source}
              </span>
            </div>
            <div className="border border-gray-200 rounded-md overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <tbody className="bg-white divide-y divide-gray-200">
                  <tr>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900 w-1/3">Coach ID</td>
                    <td className="px-4 py-3 text-sm text-gray-700 font-mono">{metadata.devx_registry.id}</td>
                  </tr>
                  <tr>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Display Label</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{metadata.devx_registry.label}</td>
                  </tr>
                  <tr>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Filename</td>
                    <td className="px-4 py-3 text-sm text-gray-700 font-mono">{metadata.devx_registry.filename}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Core YAML Section */}
          <div>
            <div className="flex items-center space-x-2 mb-3">
              <h3 className="text-md font-semibold text-gray-900">Core YAML</h3>
              {metadata.core_yaml.source && (
                <span className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800">
                  {metadata.core_yaml.source}
                </span>
              )}
            </div>
            {metadata.core_yaml.error ? (
              <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4 text-sm text-yellow-800">
                {metadata.core_yaml.error}
              </div>
            ) : Object.keys(metadata.core_yaml).length > 0 ? (
              <div className="border border-gray-200 rounded-md overflow-hidden">
                <table className="min-w-full divide-y divide-gray-200">
                  <tbody className="bg-white divide-y divide-gray-200">
                    {metadata.core_yaml.category && metadata.core_yaml.category !== 'N/A' && (
                      <tr>
                        <td className="px-4 py-3 text-sm font-medium text-gray-900 w-1/3">Category</td>
                        <td className="px-4 py-3 text-sm text-gray-700">{metadata.core_yaml.category}</td>
                      </tr>
                    )}
                    {metadata.core_yaml.description && metadata.core_yaml.description !== 'N/A' && (
                      <tr>
                        <td className="px-4 py-3 text-sm font-medium text-gray-900">Description</td>
                        <td className="px-4 py-3 text-sm text-gray-700">{metadata.core_yaml.description}</td>
                      </tr>
                    )}
                    {metadata.core_yaml.icon && metadata.core_yaml.icon !== 'N/A' && (
                      <tr>
                        <td className="px-4 py-3 text-sm font-medium text-gray-900">Icon</td>
                        <td className="px-4 py-3 text-sm text-gray-700">{metadata.core_yaml.icon}</td>
                      </tr>
                    )}
                    {metadata.core_yaml.capabilities && metadata.core_yaml.capabilities.length > 0 && (
                      <tr>
                        <td className="px-4 py-3 text-sm font-medium text-gray-900">Capabilities</td>
                        <td className="px-4 py-3 text-sm text-gray-700">
                          <div className="flex flex-wrap gap-1">
                            {metadata.core_yaml.capabilities.map((cap, idx) => (
                              <span key={idx} className="inline-flex px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-700">
                                {cap}
                              </span>
                            ))}
                          </div>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="bg-gray-50 border border-gray-200 rounded-md p-4 text-sm text-gray-500">
                No Core YAML data available
              </div>
            )}
          </div>

          {/* Filesystem Section */}
          <div>
            <div className="flex items-center space-x-2 mb-3">
              <h3 className="text-md font-semibold text-gray-900">Filesystem</h3>
              <span className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                {metadata.filesystem.source}
              </span>
            </div>
            <div className="border border-gray-200 rounded-md overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <tbody className="bg-white divide-y divide-gray-200">
                  <tr>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900 w-1/3">Prompt File</td>
                    <td className="px-4 py-3 text-sm">
                      <div className="flex items-center space-x-2">
                        <span className="font-mono text-xs text-gray-600">{metadata.filesystem.prompt_path}</span>
                        {metadata.filesystem.prompt_exists ? (
                          <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                            ✓ exists
                          </span>
                        ) : (
                          <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                            ✗ missing
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                  <tr>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Prompt Size</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{formatBytes(metadata.filesystem.prompt_size_bytes)}</td>
                  </tr>
                  <tr>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Last Modified</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{formatDate(metadata.filesystem.prompt_modified_at)}</td>
                  </tr>
                  <tr>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Features File</td>
                    <td className="px-4 py-3 text-sm">
                      <div className="flex items-center space-x-2">
                        <span className="font-mono text-xs text-gray-600">{metadata.filesystem.features_path}</span>
                        {metadata.filesystem.features_exists ? (
                          <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                            ✓ exists
                          </span>
                        ) : (
                          <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                            ✗ missing
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                  <tr>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Features Size</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{formatBytes(metadata.filesystem.features_size_bytes)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </>
      ) : (
        <div className="text-center py-12 text-gray-500">No metadata available</div>
      )}
    </div>
  )
}
