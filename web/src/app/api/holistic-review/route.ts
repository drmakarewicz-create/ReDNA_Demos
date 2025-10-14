/**
 * Holistic Review API v1
 *
 * Initiates a comprehensive Core + UCN/RR analysis to review all stored data
 * for a user and identify patterns, inferences, and relationships to improve
 * DNA/trait accuracy and refine RR scores.
 */

import { NextRequest, NextResponse } from 'next/server';

const CORE_FALLBACK_BASE = 'http://127.0.0.1:8015';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { userId } = body;

    if (!userId) {
      return NextResponse.json(
        { error: 'Missing userId in request body' },
        { status: 400 }
      );
    }

    const base = (process.env.NEXT_PUBLIC_CORE_API_BASE ?? CORE_FALLBACK_BASE).trim() || CORE_FALLBACK_BASE;

    // Call Core API to initiate holistic review
    const response = await fetch(
      `${base}/ui/holistic/review`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId }),
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
    console.error('Holistic review error:', error);
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      },
      { status: 500 }
    );
  }
}
