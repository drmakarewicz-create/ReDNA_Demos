/**
 * HC State API v1
 *
 * Returns current HC state for UI rendering:
 * - goals, open tasks, curiosity hotspots
 * - recent decisions, checkpoints
 * - relationship preferences
 */

import { NextRequest, NextResponse } from 'next/server';

const CORE_FALLBACK_BASE = 'http://127.0.0.1:8015';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const userId = searchParams.get('userId');

  if (!userId) {
    return NextResponse.json(
      { error: 'Missing userId parameter' },
      { status: 400 }
    );
  }

  const base = (process.env.NEXT_PUBLIC_CORE_API_BASE ?? CORE_FALLBACK_BASE).trim() || CORE_FALLBACK_BASE;

  try {
    // Call Core API to get HC state
    const response = await fetch(
      `${base}/hc/state?user_id=${encodeURIComponent(userId)}`,
      {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
        cache: 'no-store'
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      return NextResponse.json(
        { error: `Core API error: ${response.status} ${errorText}` },
        { status: response.status }
      );
    }

    const data = await response.json();

    return NextResponse.json(data, { status: 200 });
  } catch (error) {
    console.error('HC state fetch error:', error);
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : 'Unknown error',
        userId,
        timestamp: new Date().toISOString()
      },
      { status: 500 }
    );
  }
}
