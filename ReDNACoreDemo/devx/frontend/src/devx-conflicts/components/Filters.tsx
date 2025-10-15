interface FiltersProps {
  status: string
  kind: string
  userId: string
  onStatusChange: (value: string) => void
  onKindChange: (value: string) => void
  onUserChange: (value: string) => void
}

export function ConflictFilters({ status, kind, userId, onStatusChange, onKindChange, onUserChange }: FiltersProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 text-sm">
      <label className="flex items-center gap-2">
        <span className="text-slate-500">Status</span>
        <select
          value={status}
          onChange={(event) => onStatusChange(event.target.value)}
          className="rounded border border-slate-300 bg-white px-2 py-1"
        >
          <option value="">All</option>
          <option value="open">Open</option>
          <option value="auto_resolved">Auto Resolved</option>
          <option value="resolved">Resolved</option>
          <option value="denied">Denied</option>
          <option value="escalated">Escalated</option>
        </select>
      </label>

      <label className="flex items-center gap-2">
        <span className="text-slate-500">Kind</span>
        <select
          value={kind}
          onChange={(event) => onKindChange(event.target.value)}
          className="rounded border border-slate-300 bg-white px-2 py-1"
        >
          <option value="">All</option>
          <option value="trait">Trait</option>
          <option value="interpretation">Interpretation</option>
          <option value="policy">Policy</option>
          <option value="permission">Permission</option>
          <option value="system">System</option>
        </select>
      </label>

      <label className="flex items-center gap-2">
        <span className="text-slate-500">User</span>
        <input
          value={userId}
          onChange={(event) => onUserChange(event.target.value)}
          placeholder="TEST"
          className="w-32 rounded border border-slate-300 px-2 py-1"
        />
      </label>
    </div>
  )
}
