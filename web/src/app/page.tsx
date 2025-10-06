import dynamic from 'next/dynamic';

const PageClient = dynamic(() => import('./page-client'), {
  ssr: false,
  loading: () => (
    <div className="flex min-h-screen items-center justify-center bg-slate-950">
      <div className="text-center">
        <div className="mb-4 inline-block h-12 w-12 animate-spin rounded-full border-4 border-slate-700 border-t-cyan-400"></div>
        <p className="text-slate-400">Loading Head Coach...</p>
      </div>
    </div>
  ),
});

export default function Page() {
  return <PageClient />;
}
