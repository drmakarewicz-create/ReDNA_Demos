import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  agentApi,
  AgentSummary,
  AgentDetail,
  AutonomyLevel,
  ConfigurableAutonomy,
  CapabilityResponse,
  MailboxEntry,
} from '../../lib/agentApi';
import { userOpsHC } from '../../lib/routes';
import { Link } from 'react-router-dom';

const RUN_SCOPE = 'core.agent.run';
const CONFIG_SCOPE = 'core.agent.config';

type LoadingState = 'idle' | 'loading' | 'success' | 'error';

const statusPalette: Record<string, string> = {
  enabled: 'bg-emerald-100 text-emerald-700',
  disabled: 'bg-gray-200 text-gray-600',
};

function useAsyncAction<Args extends unknown[], T>(
  action: (...args: Args) => Promise<T>,
  deps: unknown[] = []
) {
  const [state, setState] = useState<LoadingState>('idle');
  const [error, setError] = useState<string | null>(null);

  const wrapped = useCallback(async (...args: Args) => {
    setState('loading');
    setError(null);
    try {
      const result = await action(...args);
      setState('success');
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      setState('error');
      throw err;
    }
  }, deps);

  return { run: wrapped, state, error };
}

function formatIso(ts?: string | null): string {
  if (!ts) return '—';
  try {
    const date = new Date(ts);
    if (Number.isNaN(date.getTime())) return ts;
    return date.toLocaleString();
  } catch {
    return ts;
  }
}

function capabilityValid(cap?: CapabilityResponse | null): boolean {
  if (!cap) return false;
  const exp = new Date(cap.payload.exp);
  return exp.getTime() - Date.now() > 30_000; // require at least 30s remaining
}

function StatusDot({ state }: { state: string }) {
  const palette =
    state === 'enabled' ? 'bg-green-500' : state === 'disabled' ? 'bg-gray-400' : 'bg-yellow-500';
  return <span className={`inline-block h-2.5 w-2.5 rounded-full ${palette}`} />;
}

function JsonPreview({ payload }: { payload: Record<string, any> }) {
  return (
    <pre className="bg-gray-900 text-emerald-100 text-xs rounded-md px-3 py-2 overflow-x-auto max-h-40 leading-relaxed">
      {JSON.stringify(payload, null, 2)}
    </pre>
  );
}

function MailboxTable({ title, entries }: { title: string; entries: MailboxEntry[] }) {
  return (
    <div className="bg-white rounded-lg shadow border border-gray-200">
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700">{title}</h3>
        <span className="text-xs text-gray-500">{entries.length} recent</span>
      </div>
      <div className="max-h-80 overflow-y-auto divide-y divide-gray-200">
        {entries.length === 0 ? (
          <div className="px-4 py-6 text-sm text-gray-500">No entries</div>
        ) : (
          entries.map((entry, idx) => (
            <div key={`${entry.job_id || idx}-${idx}`} className="px-4 py-3 space-y-2">
              <div className="flex items-center gap-2 text-sm text-gray-600">
                {entry.status && (
                  <span className="inline-flex items-center gap-2">
                    <StatusDot state={entry.status} />
                    <span className="uppercase text-xs tracking-wide font-semibold text-gray-700">
                      {entry.status}
                    </span>
                  </span>
                )}
                {entry.kind && <span className="text-xs text-blue-600">{entry.kind}</span>}
                {entry.source && <span className="text-xs text-gray-400">via {entry.source}</span>}
              </div>
              <JsonPreview payload={entry as Record<string, any>} />
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default function AgentControlPanel({
  focusUserId,
  embedded = false,
}: {
  focusUserId?: string;
  embedded?: boolean;
} = {}) {
  const [agentsList, setAgentsList] = useState<AgentSummary[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(focusUserId ?? null);
  const [detail, setDetail] = useState<AgentDetail | null>(null);
  const [runCapability, setRunCapability] = useState<CapabilityResponse | null>(null);
  const [configCapability, setConfigCapability] = useState<CapabilityResponse | null>(null);
  const [toast, setToast] = useState<{ kind: 'success' | 'error'; message: string } | null>(null);

  const loadAgents = useCallback(async () => {
    if (embedded && focusUserId) {
      // Embedded mode focuses on a single user; skip roster load.
      return;
    }
    const agents = await agentApi.listAgents();
    setAgentsList(agents);
    if (!selectedUserId && agents.length > 0) {
      setSelectedUserId(agents[0].user_id);
    }
  }, [embedded, focusUserId, selectedUserId]);

  const loadDetail = useCallback(
    async (userId: string) => {
      const payload = await agentApi.getAgent(userId);
      setDetail(payload);
    },
    [setDetail]
  );

  useEffect(() => {
    if (!embedded || !focusUserId) {
      loadAgents().catch((err) => setToast({ kind: 'error', message: err.message }));
    }
  }, [embedded, focusUserId, loadAgents]);

  useEffect(() => {
    if (focusUserId) {
      setSelectedUserId(focusUserId);
    }
  }, [focusUserId]);

  useEffect(() => {
    if (!selectedUserId) return;
    loadDetail(selectedUserId).catch((err) => setToast({ kind: 'error', message: err.message }));
  }, [selectedUserId, loadDetail]);

  const ensureCapability = useCallback(
    async (scope: string) => {
      const targetUser = selectedUserId;
      if (!targetUser) throw new Error('No agent selected');
      if (scope === RUN_SCOPE && capabilityValid(runCapability)) return runCapability!.token;
      if (scope === CONFIG_SCOPE && capabilityValid(configCapability)) return configCapability!.token;

      const issued = await agentApi.issueCapability(targetUser, scope, 600);
      if (scope === RUN_SCOPE) setRunCapability(issued);
      if (scope === CONFIG_SCOPE) setConfigCapability(issued);
      return issued.token;
    },
    [selectedUserId, runCapability, configCapability]
  );

  const runAction = useAsyncAction(
    async () => {
      if (!selectedUserId) throw new Error('Select an agent first');
      const token = await ensureCapability(RUN_SCOPE);
      const result = await agentApi.runAgent(selectedUserId, token);
      await loadDetail(selectedUserId);
      setToast({ kind: 'success', message: `Run completed: ${result.executed} jobs executed` });
    },
    [selectedUserId, ensureCapability, loadDetail]
  );

  const updateAutonomy = useAsyncAction(
    async (level: ConfigurableAutonomy) => {
      if (!selectedUserId) throw new Error('Select an agent first');
      const token = await ensureCapability(CONFIG_SCOPE);
      await agentApi.updateAutonomy(selectedUserId, level, token);
      await Promise.all([loadDetail(selectedUserId), loadAgents()]);
      setToast({ kind: 'success', message: `Autonomy set to ${level}` });
    },
    [selectedUserId, ensureCapability, loadDetail, loadAgents]
  );

  const toggleStatus = useAsyncAction(
    async () => {
      if (!selectedUserId || !detail) throw new Error('Select an agent first');
      const token = await ensureCapability(CONFIG_SCOPE);
      const nextStatus = detail.record.status === 'enabled' ? 'disabled' : 'enabled';
      await agentApi.setStatus(selectedUserId, nextStatus, token);
      await Promise.all([loadDetail(selectedUserId), loadAgents()]);
      setToast({ kind: 'success', message: `Agent ${nextStatus}` });
    },
    [selectedUserId, detail, ensureCapability, loadDetail, loadAgents]
  );

  const refreshMailbox = useAsyncAction(
    async () => {
      if (!selectedUserId) throw new Error('Select an agent first');
      const snapshot = await agentApi.getMailbox(selectedUserId, 40);
      setDetail((prev) =>
        prev
          ? {
              ...prev,
              mailbox: snapshot,
            }
          : prev
      );
    },
    [selectedUserId]
  );

  const selectedRecord = useMemo(() => {
    if (!detail) return null;
    return detail.record;
  }, [detail]);

  const pendingActive = useMemo(() => {
    if (!detail) return 0;
    return detail.state.pending_jobs.filter((job) => job.status !== 'completed').length;
  }, [detail]);

  const quotaInfo = useMemo(() => {
    if (!detail) return { quota: 0, remaining: 0 };
    const quota = detail.record.quotas?.jobs_per_day ?? 0;
    return { quota, remaining: detail.record.quota_remaining ?? quota };
  }, [detail]);

  const autonomyLevel = (detail?.policy.autonomy ?? detail?.record.autonomy ?? 'manual') as AutonomyLevel;

  return (
    <div className={embedded ? 'space-y-6' : 'max-w-7xl mx-auto px-6 py-6 space-y-6'}>
      <header className={`flex items-center justify-between gap-4 ${embedded ? '' : ''}`}>
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 flex items-center gap-3">
            🤖 Agent Control Center
          </h1>
          <p className="text-sm text-gray-600">
            Manage Head Coach background agents, autonomy mode, and job activity.
          </p>
        </div>
        {!embedded && (
          <button
            className="text-sm text-blue-600 hover:text-blue-700"
            onClick={() =>
              loadAgents().catch((err) =>
                setToast({ kind: 'error', message: err.message })
              )
            }
          >
            Refresh roster
          </button>
        )}
      </header>

      {toast && (
        <div
          className={`rounded-md px-4 py-3 text-sm ${
            toast.kind === 'success'
              ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
              : 'bg-red-100 text-red-700 border border-red-200'
          }`}
        >
          {toast.message}
        </div>
      )}

      <section className="grid grid-cols-12 gap-5">
        {!embedded && (
          <aside className="col-span-12 lg:col-span-3 bg-white border border-gray-200 rounded-lg shadow-sm">
            <div className="px-4 py-3 border-b border-gray-200">
              <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Agents</h2>
            </div>
            <ul className="divide-y divide-gray-100 max-h-[28rem] overflow-y-auto">
              {agentsList.map((agent) => {
                const isActive = agent.user_id === selectedUserId;
                return (
                  <li
                    key={agent.agent_id}
                    className={`px-4 py-3 cursor-pointer transition ${
                      isActive ? 'bg-blue-50 border-l-4 border-blue-500' : 'hover:bg-gray-50'
                    }`}
                    onClick={() => setSelectedUserId(agent.user_id)}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-sm font-medium text-gray-800">{agent.agent_id}</div>
                        <div className="text-xs text-gray-500">User: {agent.user_id}</div>
                      </div>
                      <div
                        className={`text-xs font-semibold px-2 py-1 rounded ${
                          statusPalette[agent.status] ?? 'bg-gray-100 text-gray-500'
                        }`}
                      >
                        {agent.status}
                      </div>
                    </div>
                    <div className="mt-2 flex items-center justify-between text-xs text-gray-500">
                      <span>Autonomy: {agent.autonomy}</span>
                      <span>
                        Jobs: {agent.executed_today}/{agent.quotas?.jobs_per_day ?? 0}
                      </span>
                    </div>
                  </li>
                );
              })}
              {agentsList.length === 0 && (
                <li className="px-4 py-6 text-sm text-gray-500 text-center">No agents registered</li>
              )}
            </ul>
          </aside>
        )}

        <main
          className={`col-span-12 space-y-5 ${
            embedded ? '' : 'lg:col-span-9'
          }`}
        >
          {!selectedRecord ? (
            <div className="bg-white border border-dashed border-gray-300 rounded-lg py-16 text-center text-gray-500">
              Select an agent to inspect details.
            </div>
          ) : (
            <>
              <section className="bg-white border border-gray-200 rounded-lg shadow-sm">
                <div className="px-5 py-4 border-b border-gray-200 flex flex-wrap items-center justify-between gap-4">
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center gap-3">
                      <StatusDot state={selectedRecord.status} />
                      <div>
                        <div className="text-lg font-semibold text-gray-900">{selectedRecord.agent_id}</div>
                        <div className="text-xs text-gray-500">User {selectedRecord.user_id}</div>
                      </div>
                    </div>
                    {selectedRecord.user_id && (
                      <Link
                        to={userOpsHC(selectedRecord.user_id)}
                        className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1 transition-colors"
                      >
                        <span>→</span> Open Head Coach settings for {selectedRecord.user_id}
                      </Link>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      className="px-3 py-2 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-60"
                      disabled={runAction.state === 'loading' || selectedRecord.status !== 'enabled'}
                      onClick={() =>
                        runAction
                          .run()
                          .catch((err) => setToast({ kind: 'error', message: err.message || 'Run failed' }))
                      }
                    >
                      {runAction.state === 'loading' ? 'Running…' : 'Run Now'}
                    </button>
                    <button
                      className="px-3 py-2 text-sm rounded-md border border-gray-300 text-gray-700 hover:bg-gray-100 disabled:opacity-60"
                      disabled={toggleStatus.state === 'loading'}
                      onClick={() =>
                        toggleStatus
                          .run()
                          .catch((err) => setToast({ kind: 'error', message: err.message || 'Update failed' }))
                      }
                    >
                      {detail?.record.status === 'enabled' ? 'Stop Agent' : 'Start Agent'}
                    </button>
                  </div>
                </div>

                <div className="px-5 py-4 grid grid-cols-1 md:grid-cols-3 gap-4 text-sm text-gray-700">
                  <div>
                    <div className="text-xs uppercase text-gray-500">Last Run</div>
                    <div className="font-medium">{formatIso(detail?.state.last_run)}</div>
                  </div>
                  <div>
                    <div className="text-xs uppercase text-gray-500">Next Run</div>
                    <div className="font-medium">{formatIso(detail?.state.next_run)}</div>
                  </div>
                  <div>
                    <div className="text-xs uppercase text-gray-500">Pending Jobs</div>
                    <div className="font-medium">
                      {pendingActive} active / {detail?.state.pending_jobs.length ?? 0} total
                    </div>
                  </div>
                </div>

                <div className="px-5 pb-5 grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                  <div className="bg-emerald-50 rounded-md px-4 py-3">
                    <div className="text-xs uppercase text-emerald-600 font-semibold">Quota</div>
                    <div className="text-emerald-800">
                      {quotaInfo.remaining} remaining of {quotaInfo.quota} today
                    </div>
                  </div>
                  <div className="bg-blue-50 rounded-md px-4 py-3">
                    <div className="text-xs uppercase text-blue-600 font-semibold">Run Count</div>
                    <div className="text-blue-800">{detail?.state.run_count ?? 0} total runs</div>
                  </div>
                </div>
              </section>

              <section className="bg-white border border-gray-200 rounded-lg shadow-sm px-5 py-5 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-semibold text-gray-800 uppercase tracking-wide">Autonomy</h3>
                    <p className="text-xs text-gray-500">
                      Toggle autonomy mode to govern automatic execution scope.
                    </p>
                  </div>
                  <select
                    className="border border-gray-300 rounded-md px-3 py-2 text-sm"
                    value={autonomyLevel}
                    onChange={(event) =>
                      updateAutonomy
                        .run(event.target.value as ConfigurableAutonomy)
                        .catch((err) => setToast({ kind: 'error', message: err.message || 'Failed to update autonomy' }))
                    }
                    disabled={updateAutonomy.state === 'loading'}
                  >
                    <option value="propose">Propose (notify only)</option>
                    <option value="semi">Semi (execute nudges/refinements)</option>
                    <option value="auto">Auto (full autonomy)</option>
                  </select>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-gray-600">
                  <div>
                    <div className="text-xs uppercase text-gray-500">Namespaces</div>
                    <div className="flex flex-wrap gap-2 mt-1">
                      {detail?.policy.permissions.namespaces.map((ns) => (
                        <span key={ns} className="px-2 py-1 text-xs bg-gray-100 text-gray-700 rounded">
                          {ns}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs uppercase text-gray-500">Sensitive Scopes</div>
                    <div className="flex flex-wrap gap-2 mt-1">
                      {detail?.policy.permissions.sensitive.map((scope) => (
                        <span key={scope} className="px-2 py-1 text-xs bg-rose-100 text-rose-700 rounded">
                          {scope}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </section>

              <section className="grid grid-cols-1 xl:grid-cols-2 gap-5">
                <MailboxTable title="Inbox" entries={detail?.mailbox.inbox ?? []} />
                <MailboxTable title="Outbox" entries={detail?.mailbox.outbox ?? []} />
              </section>

              <div className="flex items-center justify-end gap-3">
                <button
                  className="px-3 py-2 text-sm rounded-md border border-gray-300 text-gray-700 hover:bg-gray-100 disabled:opacity-60"
                  onClick={() =>
                    refreshMailbox
                      .run()
                      .catch((err) => setToast({ kind: 'error', message: err.message || 'Mailbox refresh failed' }))
                  }
                  disabled={refreshMailbox.state === 'loading'}
                >
                  Refresh Mailbox
                </button>
                <button
                  className="px-3 py-2 text-sm rounded-md border border-gray-300 text-gray-700 hover:bg-gray-100"
                  onClick={() => selectedUserId && loadDetail(selectedUserId)}
                >
                  Reload Details
                </button>
              </div>
            </>
          )}
        </main>
      </section>
    </div>
  );
}
