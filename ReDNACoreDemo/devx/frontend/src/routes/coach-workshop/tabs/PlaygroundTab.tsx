import { useState } from 'react'

interface PlaygroundTabProps {
  coachId: string
  coachLabel: string
}

export default function PlaygroundTab({ coachId, coachLabel }: PlaygroundTabProps) {
  const [sandboxMode, setSandboxMode] = useState<'user' | 'developer'>('user')

  return (
    <div className="space-y-6">
      {/* Coach Header */}
      <div className="pb-3 border-b border-gray-200">
        <h2 className="text-xl font-bold text-gray-900">{coachLabel}</h2>
        <p className="text-sm text-gray-500 mt-1">Test coach behavior in a safe sandbox environment</p>
      </div>

      {/* Sandbox Mode Toggle */}
      <div className="flex items-center space-x-2">
        <button
          onClick={() => setSandboxMode('user')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            sandboxMode === 'user'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          👤 User Sandbox
        </button>
        <button
          onClick={() => setSandboxMode('developer')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            sandboxMode === 'developer'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          🛠️ Developer Mode
        </button>
      </div>

      {/* Banner */}
      <div className="bg-amber-50 border border-amber-200 rounded-md p-4">
        <div className="flex items-start space-x-2">
          <span className="text-amber-600 text-lg">⚠️</span>
          <div className="flex-1">
            <div className="text-sm font-medium text-amber-900">Local LLM Sandbox Not Configured</div>
            <div className="text-xs text-amber-700 mt-1">
              The playground requires a local LLM instance for safe testing. Configuration and setup instructions
              coming soon.
            </div>
          </div>
        </div>
      </div>

      {/* Current Configuration */}
      <div className="border border-gray-200 rounded-md p-4">
        <h3 className="font-semibold text-gray-900 mb-3">📦 Active Configuration</h3>
        <div className="space-y-2 text-sm">
          <div className="flex items-start">
            <span className="font-medium text-gray-700 w-32">Prompt File:</span>
            <span className="font-mono text-gray-600 bg-gray-100 px-2 py-0.5 rounded">
              prompts/{coachId}_ai.md
            </span>
          </div>
          <div className="flex items-start">
            <span className="font-medium text-gray-700 w-32">Features JSON:</span>
            <span className="font-mono text-gray-600 bg-gray-100 px-2 py-0.5 rounded">
              prompts/features/{coachId}_features.json
            </span>
          </div>
          <div className="flex items-start">
            <span className="font-medium text-gray-700 w-32">File Hash:</span>
            <span className="font-mono text-gray-500 text-xs">Coming soon - will show SHA256 of active files</span>
          </div>
        </div>
      </div>

      {/* Disabled Chat Area */}
      <div className="border border-gray-300 rounded-md bg-gray-50 p-6 relative">
        <div className="absolute inset-0 bg-gray-100 bg-opacity-60 flex items-center justify-center rounded-md">
          <div className="text-center">
            <div className="text-gray-400 text-3xl mb-2">🔒</div>
            <div className="text-sm font-medium text-gray-700">Sandbox Unavailable</div>
            <div className="text-xs text-gray-500 mt-1">Configure local LLM to enable testing</div>
          </div>
        </div>

        {/* Placeholder UI */}
        <div className="space-y-3 opacity-30">
          <div className="flex items-start space-x-3">
            <div className="w-8 h-8 rounded-full bg-gray-300"></div>
            <div className="flex-1 bg-white border border-gray-200 rounded-lg p-3">
              <div className="h-4 bg-gray-200 rounded w-3/4"></div>
            </div>
          </div>
          <div className="flex items-start space-x-3 justify-end">
            <div className="flex-1 bg-blue-50 border border-blue-200 rounded-lg p-3">
              <div className="h-4 bg-blue-200 rounded w-2/3 ml-auto"></div>
            </div>
            <div className="w-8 h-8 rounded-full bg-blue-300"></div>
          </div>
        </div>

        {/* Input Area */}
        <div className="mt-4 opacity-30">
          <div className="flex items-center space-x-2">
            <input
              type="text"
              disabled
              placeholder="Type a message..."
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md bg-white"
            />
            <button disabled className="px-4 py-2 bg-blue-600 text-white rounded-md">
              Send
            </button>
          </div>
        </div>
      </div>

      {/* Mode Explanation */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="border border-gray-200 rounded-md p-4">
          <h4 className="font-semibold text-gray-900 mb-2">👤 User Sandbox</h4>
          <p className="text-sm text-gray-600">
            Test as a regular user would experience the coach. Uses actual prompt file and features config with
            simulated user data.
          </p>
        </div>

        <div className="border border-gray-200 rounded-md p-4">
          <h4 className="font-semibold text-gray-900 mb-2">🛠️ Developer Mode</h4>
          <p className="text-sm text-gray-600">
            Advanced testing with raw LLM output, token counts, and step-by-step reasoning. Includes prompt injection
            testing.
          </p>
        </div>
      </div>
    </div>
  )
}
