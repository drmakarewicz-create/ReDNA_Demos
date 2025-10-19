'use client';

import { useState, useEffect } from 'react';
import { ChevronRight, Play, Download, CheckCircle, AlertCircle, Info, Sparkles } from 'lucide-react';

// Types
interface Coach {
  id: string;
  display_name: string;
  description: string;
  purpose: string;
  manifest_path: string | null;
  manifest_exists: boolean;
  manifest_valid: boolean;
  status: 'ready' | 'draft' | 'no_manifest' | 'legacy_adapter';
  last_updated: string | null;
  source: 'delegation' | 'legacy';
}

interface Manifest {
  coach_id: string;
  manifest_data: any;
  manifest_yaml: string;
  schema_version: string;
  renderer_version: string;
  manifest_version: string;
}

type WorkshopStep = 'pick_coach' | 'preview' | 'tweak' | 'simulate' | 'export' | 'help';

const STEP_INFO = {
  pick_coach: {
    title: 'Pick a Coach',
    description: 'Select Career Coach, Personality Test Coach, or any other coach to start working.',
    example: 'Try: Career Coach to explore "Change Jobs" vs "Improve Current Job" layouts.'
  },
  preview: {
    title: 'Preview Panel',
    description: 'See the live panel exactly as users will see it, with real or sample data.',
    example: 'Toggle between Live (real data), Stub (fixtures), or Hybrid mode.'
  },
  tweak: {
    title: 'Tweak Layout & Widgets',
    description: 'Drag widgets between zones, pin/hide them, edit conditions without touching code.',
    example: 'Drag "Skill Curiosity Map" to the Header zone to make it always visible.'
  },
  simulate: {
    title: 'Simulate User',
    description: 'Use sliders to change SkillDNA RR to 40; watch which widgets become a priority.',
    example: 'Lower SkillDNA RR to 40 to see the Skill Curiosity Map move to the top.'
  },
  export: {
    title: 'Export & Promote',
    description: 'Bundle includes the manifest, fixtures, and screenshots you can share or promote.',
    example: 'Click Export to download a ZIP with everything needed for deployment.'
  },
  help: {
    title: 'Help & Examples',
    description: 'Take the 2-minute tour or load example presets like "Career Change."',
    example: 'Click "Tour" for a guided walkthrough with callouts.'
  }
};

const SCENARIOS = [
  { id: 'career_change', label: 'New job seeker', description: 'User exploring career transitions' },
  { id: 'skill_development', label: 'Improve current job', description: 'User focused on learning' },
  { id: 'career_planning', label: 'Track progress this month', description: 'User planning long-term' }
];

export function WorkshopClient() {
  const [currentStep, setCurrentStep] = useState<WorkshopStep>('pick_coach');
  const [guidedMode, setGuidedMode] = useState(true);

  // Data
  const [coaches, setCoaches] = useState<Coach[]>([]);
  const [selectedCoach, setSelectedCoach] = useState<Coach | null>(null);
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [source, setSource] = useState<'delegation' | 'legacy'>('delegation');

  // Preview state
  const [dataMode, setDataMode] = useState<'live' | 'stub' | 'hybrid'>('live');
  const [previewData, setPreviewData] = useState<any>(null);
  const [performance, setPerformance] = useState<any>(null);

  // Simulate state
  const [selectedIntent, setSelectedIntent] = useState<string | null>(null);
  const [rrSliders, setRrSliders] = useState({ SkillDNA: 50, ProfDNA: 50, PsyDNA: 50 });

  // UI state
  const [loading, setLoading] = useState(false);
  const [showTour, setShowTour] = useState(false);

  // Fetch coaches on mount
  useEffect(() => {
    fetchCoaches();
  }, [source]);

  async function fetchCoaches() {
    try {
      setLoading(true);
      const baseUrl = process.env.NEXT_PUBLIC_CORE_API_BASE || 'http://127.0.0.1:8000';
      const response = await fetch(`${baseUrl}/api/workshop/coaches?source=${source}`);
      const data = await response.json();
      setCoaches(data.coaches || []);
    } catch (error) {
      console.error('Failed to fetch coaches:', error);
    } finally {
      setLoading(false);
    }
  }

  async function selectCoach(coach: Coach) {
    setSelectedCoach(coach);

    // Fetch manifest if exists
    if (coach.manifest_exists) {
      try {
        const baseUrl = process.env.NEXT_PUBLIC_CORE_API_BASE || 'http://127.0.0.1:8000';
        const response = await fetch(`${baseUrl}/api/workshop/coaches/${coach.id}/manifest`);
        const data = await response.json();
        setManifest(data);
      } catch (error) {
        console.error('Failed to fetch manifest:', error);
      }
    }

    // Auto-advance to preview in guided mode
    if (guidedMode) {
      setCurrentStep('preview');
    }
  }

  async function loadPreview() {
    if (!selectedCoach) return;

    try {
      setLoading(true);
      const baseUrl = process.env.NEXT_PUBLIC_CORE_API_BASE || 'http://127.0.0.1:8000';
      const intentParam = selectedIntent ? `&intent=${selectedIntent}` : '';
      const response = await fetch(
        `${baseUrl}/api/workshop/coaches/${selectedCoach.id}/preview?user_id=TEST&data_mode=${dataMode}${intentParam}`
      );
      const data = await response.json();
      setPreviewData(data.panel_data);
      setPerformance(data.performance);
    } catch (error) {
      console.error('Failed to load preview:', error);
    } finally {
      setLoading(false);
    }
  }

  async function exportBundle() {
    if (!selectedCoach) return;

    try {
      const baseUrl = process.env.NEXT_PUBLIC_CORE_API_BASE || 'http://127.0.0.1:8000';
      const response = await fetch(`${baseUrl}/api/workshop/coaches/${selectedCoach.id}/export`, {
        method: 'POST'
      });

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${selectedCoach.id}_workshop_bundle.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Failed to export bundle:', error);
    }
  }

  const stepInfo = STEP_INFO[currentStep];

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100">
      {/* Left Navigation */}
      <div className="w-64 border-r border-slate-800 flex flex-col">
        <div className="p-4 border-b border-slate-800">
          <h1 className="text-xl font-bold text-blue-400">Coach Workshop</h1>
          <p className="text-xs text-slate-400 mt-1">Preview, tweak, simulate, export</p>
        </div>

        {/* Mode Toggle */}
        <div className="p-4 border-b border-slate-800">
          <div className="flex items-center gap-2 text-sm">
            <button
              onClick={() => setGuidedMode(!guidedMode)}
              className={`flex-1 px-3 py-2 rounded ${
                guidedMode ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400'
              }`}
            >
              Guided
            </button>
            <button
              onClick={() => setGuidedMode(!guidedMode)}
              className={`flex-1 px-3 py-2 rounded ${
                !guidedMode ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400'
              }`}
            >
              Expert
            </button>
          </div>
        </div>

        {/* Navigation Steps */}
        <nav className="flex-1 overflow-y-auto">
          {Object.entries(STEP_INFO).map(([step, info]) => (
            <button
              key={step}
              onClick={() => setCurrentStep(step as WorkshopStep)}
              className={`w-full px-4 py-3 text-left border-b border-slate-800 hover:bg-slate-900 transition-colors ${
                currentStep === step ? 'bg-slate-900 border-l-4 border-l-blue-500' : ''
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">{info.title}</span>
                {currentStep === step && <ChevronRight className="w-4 h-4 text-blue-400" />}
              </div>
            </button>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 text-xs text-slate-500">
          <p>RPUF v1.0</p>
          <p className="mt-1">Same renderer as production</p>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col">
        {/* Header with Step Info */}
        <div className="border-b border-slate-800 bg-slate-900 p-6">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-2xl font-bold text-blue-400">{stepInfo.title}</h2>
              <p className="text-slate-300 mt-2">{stepInfo.description}</p>
              {guidedMode && (
                <div className="mt-3 flex items-start gap-2 text-sm text-amber-300 bg-amber-950/30 border border-amber-700/30 rounded-lg p-3">
                  <Sparkles className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <span>{stepInfo.example}</span>
                </div>
              )}
            </div>
            {selectedCoach && (
              <div className="text-right">
                <p className="text-sm text-slate-400">Selected Coach</p>
                <p className="font-semibold text-blue-300">{selectedCoach.display_name}</p>
              </div>
            )}
          </div>
        </div>

        {/* Step Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {currentStep === 'pick_coach' && (
            <div>
              {/* Source Selector */}
              <div className="mb-6">
                <label className="text-sm font-medium text-slate-300 mb-2 block">Coach Source</label>
                <div className="flex gap-2">
                  <button
                    onClick={() => setSource('delegation')}
                    className={`px-4 py-2 rounded-lg font-medium ${
                      source === 'delegation'
                        ? 'bg-blue-600 text-white'
                        : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                    }`}
                  >
                    Delegation (recommended)
                  </button>
                  <button
                    onClick={() => setSource('legacy')}
                    className={`px-4 py-2 rounded-lg font-medium ${
                      source === 'legacy'
                        ? 'bg-blue-600 text-white'
                        : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                    }`}
                  >
                    Legacy (adapter)
                  </button>
                </div>
                <p className="text-xs text-slate-500 mt-2">
                  {source === 'delegation'
                    ? 'Reads coaches/coach_registry.yaml - shows all modern coaches'
                    : 'Shows legacy personas with minimal adapters'}
                </p>
              </div>

              {/* Coach Table */}
              <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
                <table className="w-full">
                  <thead className="bg-slate-800 text-slate-300 text-sm">
                    <tr>
                      <th className="px-4 py-3 text-left">Coach</th>
                      <th className="px-4 py-3 text-left">Purpose</th>
                      <th className="px-4 py-3 text-left">Manifest</th>
                      <th className="px-4 py-3 text-left">Status</th>
                      <th className="px-4 py-3 text-left">Action</th>
                    </tr>
                  </thead>
                  <tbody className="text-sm">
                    {loading ? (
                      <tr>
                        <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                          Loading coaches...
                        </td>
                      </tr>
                    ) : coaches.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                          No coaches found
                        </td>
                      </tr>
                    ) : (
                      coaches.map((coach) => (
                        <tr key={coach.id} className="border-t border-slate-800 hover:bg-slate-800/50">
                          <td className="px-4 py-3">
                            <div>
                              <div className="font-medium text-slate-200">{coach.display_name}</div>
                              <div className="text-xs text-slate-500">{coach.description}</div>
                            </div>
                          </td>
                          <td className="px-4 py-3 text-slate-400">{coach.purpose}</td>
                          <td className="px-4 py-3">
                            {coach.manifest_valid ? (
                              <CheckCircle className="w-4 h-4 text-green-500" />
                            ) : coach.manifest_exists ? (
                              <AlertCircle className="w-4 h-4 text-amber-500" />
                            ) : (
                              <span className="text-slate-600">—</span>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className={`px-2 py-1 rounded text-xs font-medium ${
                                coach.status === 'ready'
                                  ? 'bg-green-900/30 text-green-300'
                                  : coach.status === 'draft'
                                  ? 'bg-amber-900/30 text-amber-300'
                                  : 'bg-slate-700 text-slate-400'
                              }`}
                            >
                              {coach.status.replace('_', ' ')}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <button
                              onClick={() => selectCoach(coach)}
                              className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-medium transition-colors"
                            >
                              Select
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {currentStep === 'preview' && (
            <div>
              {!selectedCoach ? (
                <div className="text-center py-12 text-slate-500">
                  Please select a coach first
                </div>
              ) : (
                <>
                  {/* Data Mode Toggle */}
                  <div className="mb-6">
                    <label className="text-sm font-medium text-slate-300 mb-2 block">Data Mode</label>
                    <div className="flex gap-2">
                      {(['live', 'stub', 'hybrid'] as const).map((mode) => (
                        <button
                          key={mode}
                          onClick={() => setDataMode(mode)}
                          className={`px-4 py-2 rounded-lg capitalize ${
                            dataMode === mode
                              ? 'bg-blue-600 text-white'
                              : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                          }`}
                        >
                          {mode}
                        </button>
                      ))}
                    </div>
                    <p className="text-xs text-slate-500 mt-2">
                      {dataMode === 'live' && 'Calls /api/coach/<id>/panel with real user data'}
                      {dataMode === 'stub' && 'Loads workshop_fixtures/*.json for testing'}
                      {dataMode === 'hybrid' && 'Live RR/Curiosity + fixture widget data'}
                    </p>
                  </div>

                  {/* Load Button */}
                  <button
                    onClick={loadPreview}
                    disabled={loading}
                    className="mb-6 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors disabled:opacity-50"
                  >
                    <Play className="w-4 h-4" />
                    {loading ? 'Loading...' : 'Load Preview'}
                  </button>

                  {/* Performance Metrics */}
                  {performance && (
                    <div className="mb-6 grid grid-cols-4 gap-4">
                      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
                        <div className="text-xs text-slate-500 mb-1">Compose Time</div>
                        <div className="text-2xl font-bold text-blue-400">{performance.compose_ms}ms</div>
                        <div className="text-xs text-slate-600 mt-1">Target: ≤200ms</div>
                      </div>
                      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
                        <div className="text-xs text-slate-500 mb-1">API Time</div>
                        <div className="text-2xl font-bold text-blue-400">{performance.api_ms}ms</div>
                      </div>
                      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
                        <div className="text-xs text-slate-500 mb-1">FCP</div>
                        <div className="text-2xl font-bold text-blue-400">
                          {performance.fcp_ms || '—'}
                        </div>
                        <div className="text-xs text-slate-600 mt-1">Target: ≤300ms</div>
                      </div>
                      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
                        <div className="text-xs text-slate-500 mb-1">Parity</div>
                        <div className="text-2xl font-bold text-green-400">
                          {performance.parity_ok ? '✓ OK' : '⚠'}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Preview Panel */}
                  {previewData && (
                    <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
                      <div className="text-sm text-slate-400 mb-4">
                        Panel preview will render here using production renderer
                      </div>
                      <pre className="text-xs text-slate-500 overflow-auto max-h-96">
                        {JSON.stringify(previewData, null, 2)}
                      </pre>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {currentStep === 'tweak' && (
            <div className="text-slate-400">
              <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
                <h3 className="text-lg font-semibold text-slate-200 mb-4">Layout & Widget Controls</h3>
                <p className="text-sm mb-4">Drag/drop widgets, edit conditions, and customize theme (coming soon)</p>

                {manifest && (
                  <div className="mt-6">
                    <h4 className="text-sm font-medium text-slate-300 mb-2">Current Widgets</h4>
                    <div className="space-y-2">
                      {manifest.manifest_data.widgets?.map((widget: any) => (
                        <div key={widget.id} className="bg-slate-800 border border-slate-700 rounded p-3 flex items-center justify-between">
                          <div>
                            <div className="font-medium text-slate-200">{widget.title || widget.id}</div>
                            <div className="text-xs text-slate-500">
                              Zone: {widget.zone} | Priority: {widget.zone_priority}
                            </div>
                          </div>
                          <div className="flex gap-2">
                            <button className="px-2 py-1 bg-slate-700 hover:bg-slate-600 rounded text-xs">
                              Pin
                            </button>
                            <button className="px-2 py-1 bg-slate-700 hover:bg-slate-600 rounded text-xs">
                              Hide
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {currentStep === 'simulate' && (
            <div>
              {!selectedCoach ? (
                <div className="text-center py-12 text-slate-500">
                  Please select a coach first
                </div>
              ) : (
                <>
                  {/* Intent Chips */}
                  <div className="mb-6">
                    <label className="text-sm font-medium text-slate-300 mb-2 block">User Intent</label>
                    <div className="flex flex-wrap gap-2">
                      {SCENARIOS.map((scenario) => (
                        <button
                          key={scenario.id}
                          onClick={() => setSelectedIntent(scenario.id)}
                          className={`px-4 py-2 rounded-lg ${
                            selectedIntent === scenario.id
                              ? 'bg-violet-600 text-white'
                              : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                          }`}
                        >
                          {scenario.label}
                        </button>
                      ))}
                    </div>
                    {selectedIntent && (
                      <p className="text-xs text-slate-500 mt-2">
                        {SCENARIOS.find((s) => s.id === selectedIntent)?.description}
                      </p>
                    )}
                  </div>

                  {/* RR Sliders */}
                  <div className="mb-6">
                    <label className="text-sm font-medium text-slate-300 mb-3 block">
                      RR (Resolution/Reliability) Sliders
                    </label>
                    <div className="space-y-4">
                      {Object.entries(rrSliders).map(([domain, value]) => (
                        <div key={domain}>
                          <div className="flex justify-between text-sm mb-1">
                            <span className="text-slate-400">{domain}</span>
                            <span className="text-blue-400 font-mono">{value}</span>
                          </div>
                          <input
                            type="range"
                            min="0"
                            max="100"
                            value={value}
                            onChange={(e) =>
                              setRrSliders({ ...rrSliders, [domain]: parseInt(e.target.value) })
                            }
                            className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
                          />
                          <p className="text-xs text-slate-600 mt-1">
                            {value < 40 && 'Low RR - high curiosity widgets prioritized'}
                            {value >= 40 && value < 70 && 'Medium RR - balanced widget mix'}
                            {value >= 70 && 'High RR - insight/progress widgets prioritized'}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Apply Button */}
                  <button
                    onClick={loadPreview}
                    className="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg font-medium transition-colors"
                  >
                    Apply Simulation → Preview
                  </button>
                </>
              )}
            </div>
          )}

          {currentStep === 'export' && (
            <div>
              {!selectedCoach ? (
                <div className="text-center py-12 text-slate-500">
                  Please select a coach first
                </div>
              ) : (
                <>
                  <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 mb-6">
                    <h3 className="text-lg font-semibold text-slate-200 mb-2">Export Bundle</h3>
                    <p className="text-sm text-slate-400 mb-4">
                      Download a ZIP containing manifest, fixtures, performance report, and screenshots
                    </p>
                    <button
                      onClick={exportBundle}
                      className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
                    >
                      <Download className="w-4 h-4" />
                      Download Bundle
                    </button>
                  </div>

                  <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
                    <h3 className="text-lg font-semibold text-slate-200 mb-2">Promote to Stable</h3>
                    <p className="text-sm text-slate-400 mb-4">
                      Move _dev manifest to stable (creates backup automatically)
                    </p>
                    <button className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors">
                      Promote to Stable
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {currentStep === 'help' && (
            <div>
              <div className="grid grid-cols-2 gap-6">
                <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
                  <h3 className="text-lg font-semibold text-slate-200 mb-2">Take the Tour</h3>
                  <p className="text-sm text-slate-400 mb-4">
                    2-minute guided walkthrough with callouts showing key features
                  </p>
                  <button
                    onClick={() => setShowTour(true)}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
                  >
                    Start Tour
                  </button>
                </div>

                <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
                  <h3 className="text-lg font-semibold text-slate-200 mb-2">Example Presets</h3>
                  <p className="text-sm text-slate-400 mb-4">
                    Load curated examples: "Career Change", "Discover Self"
                  </p>
                  <div className="space-y-2">
                    <button className="w-full px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm transition-colors">
                      Career Coach - Change Jobs
                    </button>
                    <button className="w-full px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm transition-colors">
                      PTC - Discover Self
                    </button>
                  </div>
                </div>
              </div>

              <div className="mt-6 bg-slate-900 border border-slate-800 rounded-lg p-6">
                <h3 className="text-lg font-semibold text-slate-200 mb-4">Glossary</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <div className="font-medium text-blue-300">RR (Resolution/Reliability)</div>
                    <div className="text-slate-400">0-100 score showing how well we know a trait</div>
                  </div>
                  <div>
                    <div className="font-medium text-blue-300">Curiosity</div>
                    <div className="text-slate-400">Priority score for collecting more data</div>
                  </div>
                  <div>
                    <div className="font-medium text-blue-300">Intent</div>
                    <div className="text-slate-400">User's current goal (career_change, etc.)</div>
                  </div>
                  <div>
                    <div className="font-medium text-blue-300">Zone</div>
                    <div className="text-slate-400">Layout area: header, actions, primary, secondary</div>
                  </div>
                  <div>
                    <div className="font-medium text-blue-300">Widget</div>
                    <div className="text-slate-400">Individual UI component (map, card, etc.)</div>
                  </div>
                  <div>
                    <div className="font-medium text-blue-300">Manifest</div>
                    <div className="text-slate-400">YAML file defining coach's widgets & layouts</div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Guided Mode Progress Footer */}
        {guidedMode && (
          <div className="border-t border-slate-800 bg-slate-900 p-4">
            <div className="flex items-center justify-between">
              <div className="text-sm text-slate-400">
                Step {Object.keys(STEP_INFO).indexOf(currentStep) + 1} of {Object.keys(STEP_INFO).length}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    const steps = Object.keys(STEP_INFO) as WorkshopStep[];
                    const currentIndex = steps.indexOf(currentStep);
                    if (currentIndex > 0) setCurrentStep(steps[currentIndex - 1]);
                  }}
                  disabled={currentStep === 'pick_coach'}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm transition-colors disabled:opacity-50"
                >
                  Previous
                </button>
                <button
                  onClick={() => {
                    const steps = Object.keys(STEP_INFO) as WorkshopStep[];
                    const currentIndex = steps.indexOf(currentStep);
                    if (currentIndex < steps.length - 1) setCurrentStep(steps[currentIndex + 1]);
                  }}
                  disabled={currentStep === 'help'}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm transition-colors disabled:opacity-50"
                >
                  Next Step
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
