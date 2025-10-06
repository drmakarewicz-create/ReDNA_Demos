import { NextResponse } from 'next/server';

const DEFAULT_PERSONA = {
  key: 'head_coach',
  label: 'Head Coach (Orchestrator)',
};

export async function GET(request: Request) {
  const url = new URL(request.url);
  const overlayOk = url.searchParams.get('ui_debug') === '1';

  return NextResponse.json({
    composer_rendered: true,
    active_persona: DEFAULT_PERSONA,
    unabridged_anchor_ok: true,
    asks_panel_visible: true,
    overlay_ok: overlayOk,
  });
}
