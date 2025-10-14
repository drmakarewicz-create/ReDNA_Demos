import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { devxUrl } from './lib/env'
import { ToastContainer } from 'react-toastify'
import 'react-toastify/dist/ReactToastify.css'
import TraitWorkshop from './routes/trait-workshop/TraitWorkshop'
import PrivacyDashboard from './routes/privacy-dashboard/PrivacyDashboard'
import ConflictDashboard from './devx-conflicts/ConflictDashboard'
import UserOps from './routes/user-ops/UserOps'
import UserDetail from './routes/user-ops/UserDetail'
import HolisticSummary from './routes/holistic/HolisticSummary'
import SystemMonitor from './routes/system/SystemMonitor'
import CoachWorkshop from './routes/coach-workshop/CoachWorkshop'
import SelfImprovementPanel from './routes/self-improvement/SelfImprovementPanel'
import JarvisCodexPanel from './routes/jarvis-codex/JarvisCodexPanel'
import CoachBrainPanel from './routes/coach-brain/CoachBrainPanel'
import NarratorTimelinePanel from './routes/narrator-timeline/NarratorTimelinePanel'
import AgentControlPanel from './routes/agent-control/AgentControlPanel'
import LifeDashboard from './routes/life-dashboard/LifeDashboard'
import AdaptiveAnalyticsDashboard from './routes/adaptive-analytics/AdaptiveAnalyticsDashboard'

function App() {
  const [healthStatus, setHealthStatus] = useState<Record<string, { status: string; detail?: string; checked_at?: string }>>({
    devx: { status: 'unknown' },
    consent: { status: 'unknown' },
    core: { status: 'unknown' },
  })

  useEffect(() => {
    let cancelled = false

    const fetchStatus = async () => {
      try {
        const response = await fetch(devxUrl('/health/status'))
        if (!response.ok) {
          throw new Error(`Health check failed: ${response.status}`)
        }
        const payload = await response.json()
        if (!cancelled) {
          setHealthStatus(payload)
        }
      } catch (error) {
        if (!cancelled) {
          setHealthStatus((prev) => ({
            ...prev,
            consent: { status: 'red', detail: 'Consent unreachable' },
            core: { status: 'red', detail: 'Core unreachable' },
          }))
        }
      }
    }

    fetchStatus()
    const interval = setInterval(fetchStatus, 20000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  const statusStyles: Record<string, string> = {
    green: 'bg-emerald-100 text-emerald-700',
    amber: 'bg-amber-100 text-amber-700',
    red: 'bg-red-100 text-red-700',
    unknown: 'bg-gray-200 text-gray-700',
  }

  const serviceLabels: Record<string, string> = {
    devx: 'DevX',
    consent: 'Consent',
    core: 'Core',
  }

  return (
    <BrowserRouter>
      <ToastContainer position="top-right" autoClose={3000} />
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-gray-900">DevX</h1>
                <p className="text-sm text-gray-500">ReDNA Developer Tools</p>
              </div>
              <div className="flex items-center gap-2">
                {(['devx', 'consent', 'core'] as const).map((key) => {
                  const statusEntry = healthStatus[key] ?? { status: 'unknown' }
                  const badgeClass = statusStyles[statusEntry.status] ?? statusStyles.unknown
                  const tooltip = `${serviceLabels[key]} — ${statusEntry.detail || statusEntry.status} (${statusEntry.checked_at || 'not checked'})`
                  return (
                    <span
                      key={key}
                      className={`flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium ${badgeClass}`}
                      title={tooltip}
                    >
                      <span className="inline-block h-2 w-2 rounded-full bg-current/70" />
                      {serviceLabels[key]}
                    </span>
                  )
                })}
              </div>
            </div>
            <nav className="mt-4 flex space-x-4 text-sm font-medium">
              <NavLink
                to="/"
                end
                className={({ isActive }) =>
                  [
                    'px-3 py-2 rounded-md transition-colors',
                    isActive ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-blue-50 hover:text-blue-700',
                  ].join(' ')
                }
              >
                🧬 Trait Workshop
              </NavLink>
              <NavLink
                to="/privacy"
                className={({ isActive }) =>
                  [
                    'px-3 py-2 rounded-md transition-colors',
                    isActive ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-blue-50 hover:text-blue-700',
                  ].join(' ')
                }
              >
                🔒 Privacy Dashboard
              </NavLink>
              <NavLink
                to="/conflicts"
                className={({ isActive }) =>
                  [
                    'px-3 py-2 rounded-md transition-colors',
                    isActive ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-blue-50 hover:text-blue-700',
                  ].join(' ')
                }
              >
                ⚖️ Conflicts
              </NavLink>
              <NavLink
                to="/user-ops"
                className={({ isActive }) =>
                  [
                    'px-3 py-2 rounded-md transition-colors',
                    isActive ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-blue-50 hover:text-blue-700',
                  ].join(' ')
                }
              >
                🧰 User Ops
              </NavLink>
              <NavLink
                to="/holistic"
                className={({ isActive }) =>
                  [
                    'px-3 py-2 rounded-md transition-colors',
                    isActive ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-blue-50 hover:text-blue-700',
                  ].join(' ')
                }
              >
                📊 Holistic
              </NavLink>
              <NavLink
                to="/system"
                className={({ isActive }) =>
                  [
                    'px-3 py-2 rounded-md transition-colors',
                    isActive ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-blue-50 hover:text-blue-700',
                  ].join(' ')
                }
              >
                🖥️ System
              </NavLink>
              <NavLink
                to="/coaches"
                className={({ isActive }) =>
                  [
                    'px-3 py-2 rounded-md transition-colors',
                    isActive ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-blue-50 hover:text-blue-700',
                  ].join(' ')
                }
              >
                🎓 Coaches
              </NavLink>
              <NavLink
                to="/coach-brain"
                className={({ isActive }) =>
                  [
                    'px-3 py-2 rounded-md transition-colors',
                    isActive ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-blue-50 hover:text-blue-700',
                  ].join(' ')
                }
              >
                🧠 Coach Brain
              </NavLink>
              <NavLink
                to="/self-improvement"
                className={({ isActive }) =>
                  [
                    'px-3 py-2 rounded-md transition-colors',
                    isActive ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-blue-50 hover:text-blue-700',
                  ].join(' ')
                }
              >
                🧠 Self-Improvement
              </NavLink>
              <NavLink
                to="/jarvis-codex"
                className={({ isActive }) =>
                  [
                    'px-3 py-2 rounded-md transition-colors',
                    isActive ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-blue-50 hover:text-blue-700',
                  ].join(' ')
                }
              >
                🤖 Jarvis-Codex
              </NavLink>
              <NavLink
                to="/agents"
                className={({ isActive }) =>
                  [
                    'px-3 py-2 rounded-md transition-colors',
                    isActive ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-blue-50 hover:text-blue-700',
                  ].join(' ')
                }
              >
                🛰️ Agents
              </NavLink>
              <NavLink
                to="/narrator"
                className={({ isActive }) =>
                  [
                    'px-3 py-2 rounded-md transition-colors',
                    isActive ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-blue-50 hover:text-blue-700',
                  ].join(' ')
                }
              >
                🗣 Narrator
              </NavLink>
              <NavLink
                to="/life-dashboard"
                className={({ isActive }) =>
                  [
                    'px-3 py-2 rounded-md transition-colors',
                    isActive ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-blue-50 hover:text-blue-700',
                  ].join(' ')
                }
              >
                📈 Life OS
              </NavLink>
              <NavLink
                to="/adaptive-analytics"
                className={({ isActive }) =>
                  [
                    'px-3 py-2 rounded-md transition-colors',
                    isActive ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-blue-50 hover:text-blue-700',
                  ].join(' ')
                }
              >
                🔮 Adaptive Analytics
              </NavLink>
            </nav>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Routes>
            <Route path="/" element={<TraitWorkshop />} />
            <Route path="/privacy" element={<PrivacyDashboard />} />
            <Route path="/conflicts" element={<ConflictDashboard />} />
            <Route path="/user-ops" element={<UserOps />} />
            <Route path="/user-ops/:userId/*" element={<UserDetail />} />
            <Route path="/holistic" element={<HolisticSummary />} />
            <Route path="/system" element={<SystemMonitor />} />
            <Route path="/coaches" element={<CoachWorkshop />} />
            <Route path="/coach-brain" element={<CoachBrainPanel />} />
            <Route path="/self-improvement" element={<SelfImprovementPanel />} />
            <Route path="/jarvis-codex" element={<JarvisCodexPanel />} />
            <Route path="/agents" element={<AgentControlPanel />} />
            <Route path="/narrator" element={<NarratorTimelinePanel />} />
            <Route path="/life-dashboard" element={<LifeDashboard />} />
            <Route path="/adaptive-analytics" element={<AdaptiveAnalyticsDashboard />} />
          </Routes>
        </main>

        <footer className="bg-white border-t border-gray-200 mt-12">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <p className="text-center text-sm text-gray-500">
              DevX v1.0.0 | Backend: http://127.0.0.1:8100
            </p>
          </div>
        </footer>
      </div>
    </BrowserRouter>
  )
}

export default App
