import { useState, useEffect } from 'react'
import { DEVX_API_BASE } from '@/lib/env'

const API_BASE = DEVX_API_BASE

interface TestsTabProps {
  coachId: string
  coachLabel: string
}

interface TestResult {
  coach_id: string
  status: string
  message: string
}

export default function TestsTab({ coachId, coachLabel }: TestsTabProps) {
  const [lastTest, setLastTest] = useState<TestResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [validationInput, setValidationInput] = useState('')
  const [validationResult, setValidationResult] = useState<any>(null)

  useEffect(() => {
    loadLastTest()
  }, [coachId])

  const loadLastTest = async () => {
    setLoading(true)
    try {
      const response = await fetch(`${API_BASE}/coaches/${encodeURIComponent(coachId)}/tests/last`)
      if (response.ok) {
        const data = await response.json()
        setLastTest(data)
      }
    } catch (error) {
      console.error('Failed to load test data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleRunSanity = async () => {
    setRunning(true)
    setValidationResult(null)
    try {
      const response = await fetch(`${API_BASE}/coaches/${encodeURIComponent(coachId)}/tests/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'sanity' })
      })

      if (response.ok) {
        const data = await response.json()
        setValidationResult(data)
      }
    } catch (error) {
      console.error('Failed to run sanity test:', error)
    } finally {
      setRunning(false)
    }
  }

  const handleValidatePacket = async () => {
    setRunning(true)
    setValidationResult(null)
    try {
      const response = await fetch(`${API_BASE}/coaches/${encodeURIComponent(coachId)}/tests/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'validate_packet', input: validationInput })
      })

      if (response.ok) {
        const data = await response.json()
        setValidationResult(data)
      }
    } catch (error) {
      console.error('Failed to validate packet:', error)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Coach Header */}
      <div className="pb-3 border-b border-gray-200">
        <h2 className="text-xl font-bold text-gray-900">{coachLabel}</h2>
        <p className="text-sm text-gray-500 mt-1">Run diagnostics and validate coach behavior</p>
      </div>

      {/* Test Action Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Sanity Dialog */}
        <div className="border border-gray-200 rounded-md p-4">
          <h3 className="font-semibold text-gray-900 mb-2">🧪 Run Sanity Dialog</h3>
          <p className="text-sm text-gray-600 mb-4">
            Test coach with a minimal conversation stub (Hello → Response)
          </p>
          <button
            onClick={handleRunSanity}
            disabled={running}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-sm font-medium"
          >
            {running ? 'Running...' : 'Run Sanity Test'}
          </button>
        </div>

        {/* Validate Format */}
        <div className="border border-gray-200 rounded-md p-4">
          <h3 className="font-semibold text-gray-900 mb-2">✅ Validate coach_packet Format</h3>
          <p className="text-sm text-gray-600 mb-4">
            Verify coach packet structure against JSON schema
          </p>
          <button
            onClick={handleValidatePacket}
            disabled={running}
            className="w-full px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-sm font-medium"
          >
            {running ? 'Validating...' : 'Validate Packet'}
          </button>
        </div>
      </div>

      {/* Validation Input */}
      <div className="border border-gray-200 rounded-md p-4">
        <label className="block text-sm font-medium text-gray-900 mb-2">
          Coach Packet JSON (for validation)
        </label>
        <textarea
          value={validationInput}
          onChange={(e) => setValidationInput(e.target.value)}
          placeholder='{"coach_id": "example", "turn_count": 1, "messages": [...]}'
          className="w-full h-32 p-3 border border-gray-300 rounded-md font-mono text-xs"
        />
        <div className="text-xs text-gray-500 mt-2">
          Paste a coach_packet JSON to validate. Leave empty for minimal test.
        </div>
      </div>

      {/* Test Results */}
      {validationResult && (
        <div className="border border-gray-200 rounded-md p-4 bg-gray-50">
          <h3 className="font-semibold text-gray-900 mb-3">
            📊 Test Results - {validationResult.mode}
          </h3>
          {validationResult.mode === 'sanity' && (
            <div className="space-y-3">
              <div className="text-sm">
                <span className="font-medium">Status:</span>{' '}
                <span className={validationResult.status === 'passed' ? 'text-green-600' : 'text-red-600'}>
                  {validationResult.status}
                </span>
              </div>
              {validationResult.output && (
                <div>
                  <div className="text-sm font-medium mb-1">Output:</div>
                  <div className="bg-white p-3 rounded border border-gray-200 text-sm">
                    {validationResult.output}
                  </div>
                </div>
              )}
              {validationResult.coach_packet && (
                <div>
                  <div className="text-sm font-medium mb-1">Coach Packet:</div>
                  <pre className="bg-white p-3 rounded border border-gray-200 text-xs overflow-x-auto">
                    {JSON.stringify(validationResult.coach_packet, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
          {validationResult.mode === 'validate_packet' && (
            <div className="space-y-3">
              <div className="text-sm">
                <span className="font-medium">Valid:</span>{' '}
                <span className={validationResult.valid ? 'text-green-600' : 'text-red-600'}>
                  {validationResult.valid ? '✓ Yes' : '✗ No'}
                </span>
              </div>
              {validationResult.errors && validationResult.errors.length > 0 && (
                <div>
                  <div className="text-sm font-medium mb-1">Errors:</div>
                  <ul className="bg-white p-3 rounded border border-red-200 text-sm text-red-700 space-y-1">
                    {validationResult.errors.map((err: string, idx: number) => (
                      <li key={idx}>• {err}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Last Test Run */}
      <div className="border border-gray-200 rounded-md p-4">
        <h3 className="font-semibold text-gray-900 mb-3">📋 Last Test Run</h3>
        {loading ? (
          <div className="text-sm text-gray-500">Loading test data...</div>
        ) : lastTest ? (
          <div className="space-y-2">
            <div className="text-sm">
              <span className="font-medium text-gray-700">Status:</span>{' '}
              <span className={lastTest.status === 'none' ? 'text-gray-500' : 'text-green-600'}>
                {lastTest.status === 'none' ? 'No tests run' : lastTest.status}
              </span>
            </div>
            {lastTest.message && (
              <div className="text-sm text-gray-600 bg-gray-50 p-3 rounded">
                {lastTest.message}
              </div>
            )}
          </div>
        ) : (
          <div className="text-sm text-gray-500">No test data available</div>
        )}
      </div>

      {/* Info Banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
        <div className="flex items-start space-x-2">
          <span className="text-blue-600 text-lg">ℹ️</span>
          <div>
            <div className="text-sm font-medium text-blue-900">Test Framework</div>
            <div className="text-xs text-blue-700 mt-1">
              • <strong>Sanity Test:</strong> Returns a stubbed conversation to verify basic functionality
              <br />
              • <strong>Packet Validation:</strong> Validates JSON structure against coach_packet.json schema
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
