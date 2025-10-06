/**
 * PaDNA Portrait Generation API Route
 *
 * Server-side endpoint for generating portraits from PaDNA traits using local ComfyUI.
 */

import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';
import { comfyGenerate, isComfyAvailable } from '../../../../server/comfy';
import { buildPromptFromTraits, getDefaultNegativePrompt, type PromptStyle, type TraitDict } from '../../../../server/trait-to-prompt';

const DATA_DIR = path.join(process.cwd(), '..', 'data');
const PUBLIC_DIR = path.join(process.cwd(), 'public');
const PORTRAITS_DIR = path.join(PUBLIC_DIR, 'portraits');

interface GeneratePortraitRequest {
  userId: string;
  style?: PromptStyle;
  seed?: number;
  width?: number;
  height?: number;
  steps?: number;
}

/**
 * POST /api/padna/portrait
 *
 * Generate a portrait from user's PaDNA traits
 */
export async function POST(request: NextRequest) {
  try {
    // Parse request body
    const body: GeneratePortraitRequest = await request.json();
    const { userId, style = 'photorealistic', seed, width = 768, height = 1024, steps = 25 } = body;

    if (!userId || typeof userId !== 'string') {
      return NextResponse.json(
        { ok: false, error: 'userId is required and must be a string' },
        { status: 400 }
      );
    }

    // Health check: is ComfyUI running?
    const comfyAvailable = await isComfyAvailable();
    if (!comfyAvailable) {
      return NextResponse.json(
        {
          ok: false,
          error: 'ComfyUI is not running',
          help: 'Start ComfyUI with: cd ~/Documents/ReDNA_Demos/ComfyUI && python3 main.py --force-fp16',
        },
        { status: 503 }
      );
    }

    // Load user's resolved.json
    const resolvedPath = path.join(DATA_DIR, 'users', userId, 'resolved.json');

    let traits: TraitDict;
    try {
      const resolvedData = await fs.readFile(resolvedPath, 'utf-8');
      traits = JSON.parse(resolvedData);
    } catch (error) {
      return NextResponse.json(
        {
          ok: false,
          error: `Failed to load traits for user ${userId}`,
          details: error instanceof Error ? error.message : 'Unknown error',
        },
        { status: 404 }
      );
    }

    // Validate traits
    if (!traits || typeof traits !== 'object' || Object.keys(traits).length === 0) {
      return NextResponse.json(
        { ok: false, error: `No traits found for user ${userId}` },
        { status: 400 }
      );
    }

    // Generate prompt from traits
    const prompt = buildPromptFromTraits(traits, style);
    const negativePrompt = getDefaultNegativePrompt();

    console.log(`[PaDNA Portrait] Generating for user ${userId}`);
    console.log(`[PaDNA Portrait] Prompt: ${prompt.substring(0, 100)}...`);

    // Generate image with ComfyUI
    const imageBuffer = await comfyGenerate({
      prompt,
      negativePrompt,
      width,
      height,
      steps,
      cfg: 7.5,
      seed,
      modelName: null, // Auto-detect
      samplerName: 'euler',
      scheduler: 'normal',
    });

    if (!imageBuffer) {
      return NextResponse.json(
        {
          ok: false,
          error: 'Image generation failed',
          details: 'ComfyUI did not return an image. Check ComfyUI console for errors.',
        },
        { status: 500 }
      );
    }

    // Ensure portraits directory exists
    try {
      await fs.mkdir(PORTRAITS_DIR, { recursive: true });
    } catch (error) {
      // Directory might already exist
    }

    const timestamp = new Date().toISOString();
    const timestampForFilename = timestamp.replace(/:/g, '-').replace(/\..+/, ''); // 2025-10-04T15-10-23

    // Save latest render to public/portraits/<userId>.png (always current)
    const latestFilename = `${userId}.png`;
    const latestPath = path.join(PORTRAITS_DIR, latestFilename);
    await fs.writeFile(latestPath, imageBuffer);

    // ALSO save timestamped version to public/portraits/<userId>_<timestamp>.png (for history)
    const timestampedFilename = `${userId}_${timestampForFilename}.png`;
    const timestampedPath = path.join(PORTRAITS_DIR, timestampedFilename);
    await fs.writeFile(timestampedPath, imageBuffer);

    const imageUrl = `/portraits/${latestFilename}`;
    const timestampedUrl = `/portraits/${timestampedFilename}`;

    console.log(`[PaDNA Portrait] Saved latest to ${latestPath}`);
    console.log(`[PaDNA Portrait] Saved history to ${timestampedPath}`);

    return NextResponse.json({
      ok: true,
      url: imageUrl,
      timestampedUrl,
      path: latestPath,
      timestampedPath,
      timestamp,
      prompt: prompt.substring(0, 200), // Return truncated prompt for debugging
    });
  } catch (error) {
    console.error('[PaDNA Portrait] Error:', error);

    return NextResponse.json(
      {
        ok: false,
        error: 'Internal server error',
        details: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}

/**
 * GET /api/padna/portrait?userId=<id>
 *
 * Check if a portrait exists for a user
 */
export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const userId = searchParams.get('userId');

  if (!userId) {
    return NextResponse.json(
      { ok: false, error: 'userId parameter is required' },
      { status: 400 }
    );
  }

  const filename = `${userId}.png`;
  const portraitPath = path.join(PORTRAITS_DIR, filename);

  try {
    await fs.access(portraitPath);
    const stats = await fs.stat(portraitPath);

    return NextResponse.json({
      ok: true,
      exists: true,
      url: `/portraits/${filename}`,
      size: stats.size,
      modified: stats.mtime.toISOString(),
    });
  } catch {
    return NextResponse.json({
      ok: true,
      exists: false,
    });
  }
}
