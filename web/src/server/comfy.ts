/**
 * ComfyUI Server Client
 *
 * Node.js implementation of ComfyUI API client for local image generation.
 * Replicates the workflow from Python's comfyui_client.py.
 */

const COMFY_BASE_URL = 'http://127.0.0.1:8188';
const GENERATION_TIMEOUT_MS = 180000; // 3 minutes
const POLL_INTERVAL_MS = 2000;

export interface ComfyGenerateParams {
  prompt: string;
  negativePrompt?: string;
  width?: number;
  height?: number;
  steps?: number;
  cfg?: number;
  seed?: number | null;
  modelName?: string | null;
  samplerName?: string;
  scheduler?: string;
}

export interface ComfySystemStats {
  system: {
    os: string;
    python_version: string;
    embedded_python: boolean;
  };
  devices: Array<{
    name: string;
    type: string;
    vram_total: number;
    vram_free: number;
  }>;
}

/**
 * Check if ComfyUI server is available
 */
export async function isComfyAvailable(): Promise<boolean> {
  try {
    const response = await fetch(`${COMFY_BASE_URL}/system_stats`, {
      signal: AbortSignal.timeout(5000),
    });
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Get ComfyUI system statistics
 */
export async function getSystemStats(): Promise<ComfySystemStats | null> {
  try {
    const response = await fetch(`${COMFY_BASE_URL}/system_stats`, {
      signal: AbortSignal.timeout(5000),
    });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

/**
 * Get list of available checkpoint models
 */
export async function getAvailableModels(): Promise<string[]> {
  try {
    const response = await fetch(`${COMFY_BASE_URL}/object_info`, {
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) return [];

    const data = await response.json();
    const ckptLoader = data['CheckpointLoaderSimple'];
    const modelNames = ckptLoader?.input?.required?.ckpt_name?.[0];

    return Array.isArray(modelNames) ? modelNames : [];
  } catch (error) {
    console.error('Failed to fetch models:', error);
    return [];
  }
}

/**
 * Build ComfyUI workflow JSON
 */
function buildWorkflow(params: ComfyGenerateParams & { modelName: string }): Record<string, any> {
  const {
    prompt,
    negativePrompt = '',
    width = 768,
    height = 1024,
    steps = 25,
    cfg = 7.5,
    seed = null,
    modelName,
    samplerName = 'euler',
    scheduler = 'normal',
  } = params;

  const actualSeed = seed ?? Math.floor(Math.random() * 4294967295);

  return {
    '1': {
      class_type: 'CheckpointLoaderSimple',
      inputs: { ckpt_name: modelName },
    },
    '2': {
      class_type: 'CLIPTextEncode',
      inputs: {
        text: prompt,
        clip: ['1', 1],
      },
    },
    '3': {
      class_type: 'CLIPTextEncode',
      inputs: {
        text: negativePrompt,
        clip: ['1', 1],
      },
    },
    '4': {
      class_type: 'EmptyLatentImage',
      inputs: {
        width,
        height,
        batch_size: 1,
      },
    },
    '5': {
      class_type: 'KSampler',
      inputs: {
        seed: actualSeed,
        steps,
        cfg,
        sampler_name: samplerName,
        scheduler,
        denoise: 1.0,
        model: ['1', 0],
        positive: ['2', 0],
        negative: ['3', 0],
        latent_image: ['4', 0],
      },
    },
    '6': {
      class_type: 'VAEDecode',
      inputs: {
        samples: ['5', 0],
        vae: ['1', 2],
      },
    },
    '7': {
      class_type: 'SaveImage',
      inputs: {
        filename_prefix: 'padna_portrait',
        images: ['6', 0],
      },
    },
  };
}

/**
 * Queue a workflow for execution
 */
async function queuePrompt(workflow: Record<string, any>, clientId: string): Promise<string | null> {
  try {
    const response = await fetch(`${COMFY_BASE_URL}/prompt`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: workflow,
        client_id: clientId,
      }),
      signal: AbortSignal.timeout(10000),
    });

    if (!response.ok) {
      const text = await response.text();
      console.error('Failed to queue prompt:', text);
      return null;
    }

    const data = await response.json();
    return data.prompt_id;
  } catch (error) {
    console.error('Error queuing prompt:', error);
    return null;
  }
}

/**
 * Wait for workflow completion and retrieve image
 */
async function waitForCompletion(promptId: string): Promise<Buffer | null> {
  const startTime = Date.now();

  while (Date.now() - startTime < GENERATION_TIMEOUT_MS) {
    try {
      // Check history
      const historyResponse = await fetch(`${COMFY_BASE_URL}/history/${promptId}`, {
        signal: AbortSignal.timeout(10000),
      });

      if (historyResponse.ok) {
        const history = await historyResponse.json();

        if (promptId in history) {
          const outputs = history[promptId]?.outputs || {};

          // Look for saved images in output nodes
          for (const nodeId of Object.keys(outputs)) {
            const output = outputs[nodeId];
            const images = output?.images;

            if (images && images.length > 0) {
              const imageInfo = images[0];
              const filename = imageInfo.filename;
              const subfolder = imageInfo.subfolder || '';
              const folderType = imageInfo.type || 'output';

              // Download the image
              const imageData = await downloadImage(filename, subfolder, folderType);
              if (imageData) {
                console.log(`Retrieved image: ${filename}`);
                return imageData;
              }
            }
          }
        }
      }

      // Wait before polling again
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
    } catch (error) {
      console.warn('Error checking status:', error);
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
    }
  }

  console.error(`Timeout waiting for prompt ${promptId}`);
  return null;
}

/**
 * Download generated image from ComfyUI
 */
async function downloadImage(
  filename: string,
  subfolder: string = '',
  folderType: string = 'output'
): Promise<Buffer | null> {
  try {
    const params = new URLSearchParams({
      filename,
      type: folderType,
    });
    if (subfolder) {
      params.set('subfolder', subfolder);
    }

    const response = await fetch(`${COMFY_BASE_URL}/view?${params.toString()}`, {
      signal: AbortSignal.timeout(30000),
    });

    if (response.ok) {
      const arrayBuffer = await response.arrayBuffer();
      return Buffer.from(arrayBuffer);
    } else {
      console.error('Failed to download image:', await response.text());
      return null;
    }
  } catch (error) {
    console.error('Error downloading image:', error);
    return null;
  }
}

/**
 * Generate an image using ComfyUI
 *
 * @param params Generation parameters
 * @returns Image buffer or null if failed
 */
export async function comfyGenerate(params: ComfyGenerateParams): Promise<Buffer | null> {
  // Auto-detect model if not specified
  let modelName = params.modelName;
  if (!modelName) {
    const models = await getAvailableModels();
    if (models.length === 0) {
      console.error('No models available in ComfyUI');
      return null;
    }
    modelName = models[0];
    console.log(`Auto-selected model: ${modelName}`);
  }

  // Build workflow
  const workflow = buildWorkflow({ ...params, modelName });

  // Generate client ID
  const clientId = `padna_${Date.now()}_${Math.random().toString(36).substring(7)}`;

  // Queue the workflow
  const promptId = await queuePrompt(workflow, clientId);
  if (!promptId) {
    return null;
  }

  console.log(`Queued workflow: ${promptId}`);

  // Wait for completion and get image
  const imageData = await waitForCompletion(promptId);
  return imageData;
}
