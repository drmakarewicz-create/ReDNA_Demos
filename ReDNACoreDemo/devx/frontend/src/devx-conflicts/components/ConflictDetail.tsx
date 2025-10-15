interface ConflictDetailProps {
  conflict?: Record<string, any> | null
}

export function ConflictDetail({ conflict }: ConflictDetailProps) {
  if (!conflict) {
    return (
      <div className="rounded border border-slate-200 bg-white p-6 text-center text-sm text-slate-500">
        Select a conflict from the table to inspect evidence.
      </div>
    )
  }

  const evidence = Array.isArray(conflict.evidence) ? conflict.evidence : []

  return (
    <div className="space-y-4">
      <section className="rounded border border-slate-200 bg-white p-4 text-sm text-slate-600">
        <h3 className="mb-2 text-sm font-semibold text-slate-800">Summary</h3>
        <dl className="grid grid-cols-2 gap-2">
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-400">Conflict ID</dt>
            <dd>{conflict.conflict_id}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-400">User</dt>
            <dd>{conflict.user_id}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-400">Kind</dt>
            <dd className="capitalize">{conflict.kind}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-400">Status</dt>
            <dd className="capitalize">{conflict.status}</dd>
          </div>
          <div className="col-span-2">
            <dt className="text-xs uppercase tracking-wide text-slate-400">Path</dt>
            <dd>{conflict.path ?? '—'}</dd>
          </div>
        </dl>
      </section>

      <section className="rounded border border-slate-200 bg-white p-4 text-sm text-slate-600">
        <h3 className="mb-2 text-sm font-semibold text-slate-800">Evidence</h3>
        <div className="space-y-3">
          {evidence.map((item: any) => (
            <div key={item.evidence_id} className="rounded border border-slate-100 bg-slate-50 p-3">
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span>{item.source_type}</span>
                <span>{item.timestamp}</span>
              </div>
              <div className="mt-2 text-slate-700">
                <strong>{item.module ?? 'Value'}:</strong> <span>{String(item.value)}</span>
              </div>
              {item.weight !== undefined && (
                <div className="mt-1 text-xs text-slate-500">Weight: {item.weight.toFixed ? item.weight.toFixed(2) : item.weight}</div>
              )}
            </div>
          ))}
        </div>
      </section>

      {conflict.outcome && (
        <section className="rounded border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
          <h3 className="mb-2 text-sm font-semibold text-emerald-800">Outcome</h3>
          <p><strong>Resolver:</strong> {conflict.outcome.resolver}</p>
          {conflict.outcome.resolved_value !== undefined && (
            <p><strong>Value:</strong> {String(conflict.outcome.resolved_value)}</p>
          )}
          {conflict.outcome.reason && <p className="mt-1 text-xs text-emerald-700">{conflict.outcome.reason}</p>}
        </section>
      )}
    </div>
  )
}
