'use client';

import { useState, useEffect } from 'react';
import { Search, Database, Network, GitBranch, ChevronRight, Sparkles } from 'lucide-react';

import PersonaLens from './PersonaLens';

interface OntologyStats {
  ok: boolean;
  stats: {
    total_containers: number;
    namespaces: Record<string, number>;
    status_breakdown: Record<string, number>;
    sensitive_containers: number;
    camouflage_containers: number;
    consent_required: number;
    metadata: {
      version: string;
      total_containers: number;
      last_updated: string;
    };
  };
}

interface Container {
  id: string;
  namespace: string;
  path: string;
  version: number;
  status: string;
  description: string;
  tags: string[];
  sensitive: boolean;
  camouflage: boolean;
  consent_required: boolean;
  parent_containers: Array<{ path: string; edge_type: string }>;
  created_at: string;
  updated_at: string;
}

interface SearchResults {
  ok: boolean;
  containers: Container[];
  count: number;
  total_available: number;
}

const API_BASE = 'http://localhost:8000';

export default function OntologyExplorerPage() {
  const [stats, setStats] = useState<OntologyStats | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedNamespace, setSelectedNamespace] = useState<string>('all');
  const [searchResults, setSearchResults] = useState<Container[]>([]);
  const [selectedContainer, setSelectedContainer] = useState<Container | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPersonaLens, setShowPersonaLens] = useState<boolean>(false);

  // Load stats on mount
  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ontology/stats`);
      const data = await res.json();
      setStats(data);
    } catch (err) {
      setError('Failed to load ontology stats. Is the core service running on port 8000?');
    }
  };

  const handleSearch = async () => {
    if (!searchQuery || searchQuery.length < 2) {
      setSearchResults([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const url = new URL(`${API_BASE}/api/ontology/containers`);
      url.searchParams.set('search', searchQuery);
      if (selectedNamespace !== 'all') {
        url.searchParams.set('namespace', selectedNamespace);
      }
      url.searchParams.set('limit', '50');

      const res = await fetch(url.toString());
      const data: SearchResults = await res.json();
      setSearchResults(data.containers);
    } catch (err) {
      setError('Search failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchQuery.length >= 2) {
        handleSearch();
      } else {
        setSearchResults([]);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [searchQuery, selectedNamespace]);

  const namespaces = stats?.stats.namespaces || {};
  const sortedNamespaces = Object.entries(namespaces).sort((a, b) => b[1] - a[1]);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                <Network className="w-6 h-6" />
                Ontology Explorer
              </h1>
              <p className="text-sm text-gray-600 mt-1">
                Browse {stats?.stats.total_containers.toLocaleString() || '...'} containers
                across {Object.keys(namespaces).length} namespaces
              </p>
            </div>
            <div className="text-right">
              <div className="text-sm text-gray-600">Version {stats?.stats.metadata.version || '...'}</div>
              <div className="text-xs text-gray-500">
                Sensitive: {stats?.stats.sensitive_containers.toLocaleString() || '...'}
              </div>
              <button
                onClick={() => setShowPersonaLens((prev) => !prev)}
                className={`mt-3 inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                  showPersonaLens
                    ? 'border-blue-500 bg-blue-50 text-blue-700'
                    : 'border-gray-200 bg-white text-gray-600 hover:border-blue-400 hover:text-blue-600'
                }`}
              >
                <Sparkles className="h-4 w-4" />
                {showPersonaLens ? 'Hide Persona Lens' : 'Show Persona Lens'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-6 py-6">
        <div className="grid grid-cols-12 gap-6">
          {/* Left Sidebar - Namespaces */}
          <div className="col-span-3">
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <h2 className="text-sm font-semibold text-gray-900 mb-3">Namespaces</h2>
              <div className="space-y-1">
                <button
                  onClick={() => setSelectedNamespace('all')}
                  className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                    selectedNamespace === 'all'
                      ? 'bg-blue-50 text-blue-700 font-medium'
                      : 'text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span>All Containers</span>
                    <span className="text-xs text-gray-500">{stats?.stats.total_containers}</span>
                  </div>
                </button>
                {sortedNamespaces.map(([namespace, count]) => (
                  <button
                    key={namespace}
                    onClick={() => setSelectedNamespace(namespace)}
                    className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                      selectedNamespace === namespace
                        ? 'bg-blue-50 text-blue-700 font-medium'
                        : 'text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span>{namespace}</span>
                      <span className="text-xs text-gray-500">{count}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Stats Card */}
            {stats && (
              <div className="bg-white rounded-lg border border-gray-200 p-4 mt-4">
                <h2 className="text-sm font-semibold text-gray-900 mb-3">Statistics</h2>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Total Containers</span>
                    <span className="font-medium">{stats.stats.total_containers.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Sensitive</span>
                    <span className="font-medium">{stats.stats.sensitive_containers.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Consent Required</span>
                    <span className="font-medium">{stats.stats.consent_required.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Camouflage</span>
                    <span className="font-medium">{stats.stats.camouflage_containers.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between pt-2 border-t border-gray-100">
                    <span className="text-gray-600">Namespaces</span>
                    <span className="font-medium">{Object.keys(namespaces).length}</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Main Content - Search & Results */}
          <div className="col-span-9">
            {/* Search Bar */}
            <div className="bg-white rounded-lg border border-gray-200 p-4 mb-4">
              <div className="flex items-center gap-3">
                <div className="flex-1 relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Search containers by path, description, or tags..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                {loading && (
                  <div className="text-sm text-gray-500">Searching...</div>
                )}
              </div>
              {searchResults.length > 0 && (
                <div className="mt-2 text-sm text-gray-600">
                  Found {searchResults.length} result{searchResults.length !== 1 ? 's' : ''}
                  {selectedNamespace !== 'all' && ` in ${selectedNamespace}`}
                </div>
              )}
            </div>

            {/* Results */}
            {searchResults.length > 0 ? (
              <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                <div className="divide-y divide-gray-100">
                  {searchResults.map((container) => (
                    <button
                      key={container.id}
                      onClick={() => setSelectedContainer(container)}
                      className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors ${
                        selectedContainer?.id === container.id ? 'bg-blue-50' : ''
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <Database className="w-4 h-4 text-gray-400" />
                            <span className="font-mono text-sm font-medium text-gray-900">
                              {container.path}
                            </span>
                            <span className="px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-700 rounded">
                              {container.namespace}
                            </span>
                          </div>
                          <p className="text-sm text-gray-600 mt-1 line-clamp-2">
                            {container.description}
                          </p>
                          {container.tags.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-2">
                              {container.tags.slice(0, 5).map((tag) => (
                                <span
                                  key={tag}
                                  className="px-2 py-0.5 text-xs bg-gray-50 text-gray-600 rounded"
                                >
                                  {tag}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                        <ChevronRight className="w-5 h-5 text-gray-400 flex-shrink-0 ml-2" />
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            ) : searchQuery.length >= 2 ? (
              <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
                <Search className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                <p className="text-gray-600">No containers found matching "{searchQuery}"</p>
                <p className="text-sm text-gray-500 mt-1">Try a different search term or namespace filter</p>
              </div>
            ) : (
              <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
                <GitBranch className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                <p className="text-gray-600">Start typing to search the ontology</p>
                <p className="text-sm text-gray-500 mt-1">
                  Search across {stats?.stats.total_containers.toLocaleString()} containers
                </p>
              </div>
            )}
          </div>

          {showPersonaLens && (
            <div className="col-span-12">
              <PersonaLens />
            </div>
          )}
        </div>
      </div>

      {/* Container Detail Modal */}
      {selectedContainer && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-2xl w-full max-h-[80vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Container Details</h2>
              <button
                onClick={() => setSelectedContainer(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>
            <div className="px-6 py-4">
              <div className="space-y-4">
                <div>
                  <label className="text-xs font-semibold text-gray-500 uppercase">ID</label>
                  <p className="font-mono text-sm mt-1">{selectedContainer.id}</p>
                </div>
                <div>
                  <label className="text-xs font-semibold text-gray-500 uppercase">Path</label>
                  <p className="font-mono text-sm mt-1">{selectedContainer.path}</p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-semibold text-gray-500 uppercase">Namespace</label>
                    <p className="text-sm mt-1">{selectedContainer.namespace}</p>
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-gray-500 uppercase">Version</label>
                    <p className="text-sm mt-1">v{selectedContainer.version}</p>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-semibold text-gray-500 uppercase">Status</label>
                    <p className="text-sm mt-1">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        selectedContainer.status === 'stable'
                          ? 'bg-green-100 text-green-800'
                          : selectedContainer.status === 'prototype'
                          ? 'bg-yellow-100 text-yellow-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}>
                        {selectedContainer.status}
                      </span>
                    </p>
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-gray-500 uppercase">Flags</label>
                    <div className="flex gap-1 mt-1">
                      {selectedContainer.sensitive && (
                        <span className="px-2 py-1 text-xs bg-red-100 text-red-800 rounded">Sensitive</span>
                      )}
                      {selectedContainer.camouflage && (
                        <span className="px-2 py-1 text-xs bg-purple-100 text-purple-800 rounded">Camouflage</span>
                      )}
                      {selectedContainer.consent_required && (
                        <span className="px-2 py-1 text-xs bg-orange-100 text-orange-800 rounded">Consent</span>
                      )}
                    </div>
                  </div>
                </div>
                <div>
                  <label className="text-xs font-semibold text-gray-500 uppercase">Description</label>
                  <p className="text-sm mt-1 leading-relaxed">{selectedContainer.description}</p>
                </div>
                {selectedContainer.parent_containers && selectedContainer.parent_containers.length > 0 && (
                  <div>
                    <label className="text-xs font-semibold text-gray-500 uppercase">Parent Containers</label>
                    <div className="space-y-1 mt-1">
                      {selectedContainer.parent_containers.map((parent, idx) => (
                        <div key={idx} className="flex items-center gap-2 text-sm">
                          <ChevronRight className="w-4 h-4 text-gray-400" />
                          <span className="font-mono">{parent.path}</span>
                          <span className="text-xs text-gray-500">({parent.edge_type})</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <div>
                  <label className="text-xs font-semibold text-gray-500 uppercase">Tags</label>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {selectedContainer.tags.map((tag) => (
                      <span
                        key={tag}
                        className="px-2 py-1 text-xs bg-gray-100 text-gray-700 rounded"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-200">
                  <div>
                    <label className="text-xs font-semibold text-gray-500 uppercase">Created</label>
                    <p className="text-xs mt-1 text-gray-600">{new Date(selectedContainer.created_at).toLocaleDateString()}</p>
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-gray-500 uppercase">Updated</label>
                    <p className="text-xs mt-1 text-gray-600">{new Date(selectedContainer.updated_at).toLocaleDateString()}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
