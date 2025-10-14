import { UserSummary } from '@/lib/userOpsApi'

interface ProfileTabProps {
  userId: string
  loading: boolean
  summary: UserSummary | null
}

export default function ProfileTab({ userId, loading, summary }: ProfileTabProps) {
  if (loading) {
    return <div className="text-sm text-gray-500">Loading profile data…</div>
  }

  if (!summary) {
    return (
      <div className="rounded-md border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-600">
        No summary information available for <span className="font-medium">{userId}</span>.
      </div>
    )
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-4">
        <section className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-900">Storage Overview</h3>
          <dl className="mt-3 grid grid-cols-2 gap-3 text-sm text-gray-600">
            <div>
              <dt className="text-xs uppercase tracking-wide text-gray-500">Total size</dt>
              <dd className="mt-1 font-medium text-gray-900">{formatBytes(summary.size_bytes)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-gray-500">Last updated</dt>
              <dd className="mt-1 font-medium text-gray-900">{formatDate(summary.last_updated)}</dd>
            </div>
          </dl>
        </section>
        <section className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-900">Counts</h3>
          <ul className="mt-3 space-y-2 text-sm text-gray-600">
            <li>
              <span className="font-medium text-gray-900">{summary.counts.evidence}</span> evidence
              items
            </li>
            <li>
              <span className="font-medium text-gray-900">{summary.counts.derived}</span> derived
              facts
            </li>
            <li>
              <span className="font-medium text-gray-900">{summary.counts.containers}</span>{' '}
              containers touched
            </li>
          </ul>
        </section>
      </div>
      <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-6 text-sm text-gray-500">
        Upcoming profile insights (Phase 5.B):
        <ul className="mt-3 list-disc pl-4">
          <li>Holistic trend chart (RR / curiosity / UCN)</li>
          <li>Recent capability events + consent changes</li>
          <li>Head Coach session summary timeline</li>
        </ul>
      </div>
    </div>
  )
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes)) return '—'
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const index = Math.floor(Math.log(bytes) / Math.log(1024))
  const value = bytes / Math.pow(1024, index)
  return `${value.toFixed(1)} ${units[index]}`
}

function formatDate(value?: string | null): string {
  if (!value) return '—'
  try {
    const date = new Date(value)
    return date.toLocaleString()
  } catch {
    return value
  }
}
