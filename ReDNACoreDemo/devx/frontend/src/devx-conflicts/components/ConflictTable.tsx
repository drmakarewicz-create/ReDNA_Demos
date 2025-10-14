import React from 'react'

export interface ConflictRow {
  conflict_id: string
  user_id: string
  kind: string
  status: string
  path?: string | null
  severity?: string
  created_at?: string
  resolver?: string | null
}

interface ConflictTableProps {
  conflicts: ConflictRow[]
  onSelect: (conflictId: string) => void
}

export function ConflictTable({ conflicts, onSelect }: ConflictTableProps) {
  if (!conflicts.length) {
    return (
      <div className="rounded border border-slate-200 bg-white p-6 text-center text-sm text-slate-500">
        No conflicts captured yet.
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded border border-slate-200 bg-white">
      <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-3 py-2">ID</th>
            <th className="px-3 py-2">User</th>
            <th className="px-3 py-2">Kind</th>
            <th className="px-3 py-2">Severity</th>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2">Path</th>
            <th className="px-3 py-2">Resolver</th>
            <th className="px-3 py-2">Created</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200 bg-white">
          {conflicts.map((conflict) => (
            <tr
              key={conflict.conflict_id}
              className="cursor-pointer hover:bg-slate-50"
              onClick={() => onSelect(conflict.conflict_id)}
            >
              <td className="px-3 py-2 font-mono text-xs text-slate-600">{conflict.conflict_id.slice(0, 8)}</td>
              <td className="px-3 py-2">{conflict.user_id}</td>
              <td className="px-3 py-2 capitalize">{conflict.kind}</td>
              <td className="px-3 py-2 capitalize">{conflict.severity ?? '—'}</td>
              <td className="px-3 py-2 capitalize">{conflict.status}</td>
              <td className="px-3 py-2 text-xs text-slate-600">{conflict.path ?? '—'}</td>
              <td className="px-3 py-2 text-xs capitalize text-slate-600">{conflict.resolver ?? '—'}</td>
              <td className="px-3 py-2 text-xs text-slate-500">{conflict.created_at ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

