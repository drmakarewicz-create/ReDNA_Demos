import StackStatus from '@/components/StackStatus'

export default function StackStatusPage() {
  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-3xl font-bold text-slate-900">ReDNA Stack Status</h1>
        <p className="mt-2 text-sm text-slate-600">
          Monitor service health, restart options, and run diagnostics without leaving the browser.
        </p>
      </div>
      <StackStatus />
    </div>
  )
}
