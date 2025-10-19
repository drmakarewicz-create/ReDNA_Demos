import { NextResponse } from 'next/server';

const CORE_FALLBACK_BASE = 'http://127.0.0.1:8004';

export async function GET() {
  const base = (process.env.NEXT_PUBLIC_CORE_API_BASE ?? CORE_FALLBACK_BASE).trim() || CORE_FALLBACK_BASE;
  let coreOk = false;
  let coreStatus = 0;
  let coreErr: string | null = null;

  try {
    const response = await fetch(`${base}/docs`, { method: 'GET', cache: 'no-store' });
    coreStatus = response.status;
    coreOk = response.ok;
  } catch (error) {
    coreErr = error instanceof Error ? error.message : 'fetch-failed';
  }

  return NextResponse.json(
    {
      react: true,
      core: coreOk,
      coreStatus,
      coreErr,
      base,
      ts: new Date().toISOString(),
    },
    { status: 200 }
  );
}
