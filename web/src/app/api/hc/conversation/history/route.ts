import { NextRequest, NextResponse } from 'next/server';

const CORE_API_URL = process.env.CORE_API_URL || 'http://localhost:8001';

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const userId = searchParams.get('userId');
    const date = searchParams.get('date');
    const limit = searchParams.get('limit') || '50';

    if (!userId) {
      return NextResponse.json({ error: 'userId required' }, { status: 400 });
    }

    let url = `${CORE_API_URL}/hc/conversation/history?user_id=${encodeURIComponent(userId)}&limit=${limit}`;
    if (date) {
      url += `&date=${encodeURIComponent(date)}`;
    }

    const response = await fetch(url);

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json({ error }, { status: response.status });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('HC conversation history error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}
