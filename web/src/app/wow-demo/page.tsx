'use client';

import { useState } from 'react';
import { WowFactorDashboard } from '../../components/wow-factor';

export default function WowDemoPage() {
  const [userId, setUserId] = useState('USER_DEMO1');
  const [demoMode, setDemoMode] = useState(true);

  return (
    <div className="min-h-screen bg-slate-950">
      {/* User Selector (for testing) */}
      <div className="fixed left-4 top-4 z-50 rounded-lg border border-slate-800 bg-slate-900/95 p-3 shadow-xl backdrop-blur">
        <label className="mb-2 block text-xs font-medium text-slate-400">
          Test User
        </label>
        <select
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          className="w-48 rounded border border-slate-700 bg-slate-800 px-2 py-1 text-sm text-slate-300"
        >
          <option value="USER_DEMO1">USER_DEMO1</option>
          <option value="USER_DEMO2">USER_DEMO2</option>
          <option value="USER_DEMO3">USER_DEMO3</option>
          <option value="TEST">TEST</option>
        </select>
        <div className="mt-2 flex items-center gap-2">
          <input
            type="checkbox"
            id="demo-mode"
            checked={demoMode}
            onChange={(e) => setDemoMode(e.target.checked)}
            className="rounded border-slate-700"
          />
          <label htmlFor="demo-mode" className="text-xs text-slate-400">
            Demo Mode
          </label>
        </div>
      </div>

      <WowFactorDashboard userId={userId} demoMode={demoMode} />
    </div>
  );
}
