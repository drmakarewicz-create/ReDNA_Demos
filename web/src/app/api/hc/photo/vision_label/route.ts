import { NextRequest, NextResponse } from 'next/server';

const CORE_API_URL = process.env.CORE_API_URL || 'http://localhost:8001';

export async function POST(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const userId = searchParams.get('userId');
    const batchId = searchParams.get('batchId');
    const image = searchParams.get('image');

    if (!userId || !batchId) {
      return NextResponse.json({ error: 'userId and batchId required' }, { status: 400 });
    }

    const params = new URLSearchParams({
      user_id: userId,
      batch_id: batchId,
    });

    if (image) {
      params.append('image', image);
    }

    const response = await fetch(`${CORE_API_URL}/photo/vision/label?${params}`, {
      method: 'POST',
    });

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json({ error }, { status: response.status });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Photo vision label error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}
