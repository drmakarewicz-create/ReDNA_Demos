"""
ComfyUI Client for Local Image Generation

Integrates with locally-running ComfyUI instance to generate photorealistic
portraits from PaDNA traits.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import random
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from PIL import Image

logger = logging.getLogger(__name__)


class ComfyUIClient:
    """Client for interacting with ComfyUI API."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8188",
        timeout: int = 300
    ):
        """
        Initialize ComfyUI client.

        Args:
            base_url: ComfyUI server URL
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client_id = str(uuid.uuid4())

    def is_available(self) -> bool:
        """Check if ComfyUI server is running."""
        try:
            response = requests.get(f"{self.base_url}/system_stats", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def get_models(self) -> List[str]:
        """Get list of available checkpoint models."""
        try:
            response = requests.get(f"{self.base_url}/object_info", timeout=10)
            if response.ok:
                data = response.json()
                # Extract checkpoint models from object_info
                ckpt_loader = data.get("CheckpointLoaderSimple", {})
                ckpt_names = ckpt_loader.get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
                return ckpt_names
        except Exception as exc:
            logger.error(f"Failed to get models: {exc}")
        return []

    def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        model_name: Optional[str] = None,
        width: int = 768,
        height: int = 1024,
        steps: int = 20,
        cfg_scale: float = 7.0,
        seed: Optional[int] = None,
        sampler_name: str = "euler",
        scheduler: str = "normal",
    ) -> Optional[Image.Image]:
        """
        Generate an image using ComfyUI.

        Args:
            prompt: Text prompt
            negative_prompt: Negative prompt
            model_name: Checkpoint model name (auto-detect if None)
            width: Image width
            height: Image height
            steps: Sampling steps
            cfg_scale: CFG scale
            seed: Random seed (random if None)
            sampler_name: Sampler algorithm
            scheduler: Scheduler type

        Returns:
            PIL Image or None if failed
        """
        # Auto-detect model if not specified
        if model_name is None:
            models = self.get_models()
            if not models:
                logger.error("No models available in ComfyUI")
                return None
            model_name = models[0]
            logger.info(f"Auto-selected model: {model_name}")

        # Generate random seed if not provided
        if seed is None:
            seed = random.randint(0, 2**32 - 1)

        # Build workflow
        workflow = self._build_workflow(
            prompt=prompt,
            negative_prompt=negative_prompt,
            model_name=model_name,
            width=width,
            height=height,
            steps=steps,
            cfg_scale=cfg_scale,
            seed=seed,
            sampler_name=sampler_name,
            scheduler=scheduler,
        )

        # Queue the workflow
        try:
            prompt_id = self._queue_prompt(workflow)
            if not prompt_id:
                return None

            # Wait for completion and get image
            image_data = self._wait_for_completion(prompt_id)
            if not image_data:
                return None

            # Convert to PIL Image
            image = Image.open(io.BytesIO(image_data))
            return image

        except Exception as exc:
            logger.error(f"Failed to generate image: {exc}")
            return None

    def _build_workflow(
        self,
        prompt: str,
        negative_prompt: str,
        model_name: str,
        width: int,
        height: int,
        steps: int,
        cfg_scale: float,
        seed: int,
        sampler_name: str,
        scheduler: str,
    ) -> Dict[str, Any]:
        """Build ComfyUI workflow JSON."""
        # This is a basic SDXL workflow
        # Adjust node IDs and structure based on your ComfyUI version
        workflow = {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": model_name}
            },
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": prompt,
                    "clip": ["1", 1]
                }
            },
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": negative_prompt,
                    "clip": ["1", 1]
                }
            },
            "4": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": width,
                    "height": height,
                    "batch_size": 1
                }
            },
            "5": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg_scale,
                    "sampler_name": sampler_name,
                    "scheduler": scheduler,
                    "denoise": 1.0,
                    "model": ["1", 0],
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "latent_image": ["4", 0]
                }
            },
            "6": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["5", 0],
                    "vae": ["1", 2]
                }
            },
            "7": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "padna_portrait",
                    "images": ["6", 0]
                }
            }
        }
        return workflow

    def _queue_prompt(self, workflow: Dict[str, Any]) -> Optional[str]:
        """Queue a workflow for execution."""
        payload = {
            "prompt": workflow,
            "client_id": self.client_id
        }

        try:
            response = requests.post(
                f"{self.base_url}/prompt",
                json=payload,
                timeout=10
            )

            if response.ok:
                data = response.json()
                prompt_id = data.get("prompt_id")
                logger.info(f"Queued workflow: {prompt_id}")
                return prompt_id
            else:
                logger.error(f"Failed to queue prompt: {response.text}")
                return None

        except Exception as exc:
            logger.error(f"Error queuing prompt: {exc}")
            return None

    def _wait_for_completion(self, prompt_id: str, poll_interval: float = 2.0) -> Optional[bytes]:
        """Wait for workflow completion and retrieve image."""
        start_time = time.time()
        last_progress = None

        while time.time() - start_time < self.timeout:
            try:
                # Check history
                response = requests.get(
                    f"{self.base_url}/history/{prompt_id}",
                    timeout=10
                )

                if response.ok:
                    history = response.json()

                    if prompt_id in history:
                        outputs = history[prompt_id].get("outputs", {})

                        # Look for saved images in output nodes
                        for node_id, output in outputs.items():
                            images = output.get("images", [])
                            if images:
                                # Get the first image
                                image_info = images[0]
                                filename = image_info.get("filename")
                                subfolder = image_info.get("subfolder", "")
                                folder_type = image_info.get("type", "output")

                                # Download the image
                                image_data = self._download_image(filename, subfolder, folder_type)
                                if image_data:
                                    logger.info(f"Retrieved image: {filename}")
                                    return image_data

                # Check queue status for progress
                queue_response = requests.get(f"{self.base_url}/queue", timeout=5)
                if queue_response.ok:
                    queue_data = queue_response.json()
                    running = queue_data.get("queue_running", [])

                    for item in running:
                        if item[1] == prompt_id:
                            # Extract progress if available
                            progress = item[2] if len(item) > 2 else None
                            if progress != last_progress:
                                logger.info(f"Generation progress: {progress}")
                                last_progress = progress

            except Exception as exc:
                logger.warning(f"Error checking status: {exc}")

            time.sleep(poll_interval)

        logger.error(f"Timeout waiting for prompt {prompt_id}")
        return None

    def _download_image(
        self,
        filename: str,
        subfolder: str = "",
        folder_type: str = "output"
    ) -> Optional[bytes]:
        """Download generated image from ComfyUI."""
        try:
            params = {
                "filename": filename,
                "type": folder_type,
            }
            if subfolder:
                params["subfolder"] = subfolder

            response = requests.get(
                f"{self.base_url}/view",
                params=params,
                timeout=30
            )

            if response.ok:
                return response.content
            else:
                logger.error(f"Failed to download image: {response.text}")
                return None

        except Exception as exc:
            logger.error(f"Error downloading image: {exc}")
            return None

    def get_system_stats(self) -> Dict[str, Any]:
        """Get ComfyUI system statistics."""
        try:
            response = requests.get(f"{self.base_url}/system_stats", timeout=5)
            if response.ok:
                return response.json()
        except Exception as exc:
            logger.error(f"Failed to get system stats: {exc}")
        return {}


def generate_portrait_from_traits(
    traits: Dict[str, Dict[str, Any]],
    output_path: Path,
    client: Optional[ComfyUIClient] = None,
    style: str = "photorealistic",
) -> Tuple[bool, Optional[str]]:
    """
    Generate a portrait image from PaDNA traits.

    Args:
        traits: Trait dictionary from resolved.json
        output_path: Where to save the generated image
        client: ComfyUI client (creates new if None)
        style: Rendering style

    Returns:
        Tuple of (success, error_message)
    """
    # Create client if not provided
    if client is None:
        client = ComfyUIClient()

    # Check if ComfyUI is running
    if not client.is_available():
        return False, "ComfyUI is not running. Start it with: cd ComfyUI && python3 main.py"

    # Generate prompt
    from .trait_to_prompt import generate_prompt_from_traits
    prompt = generate_prompt_from_traits(traits, style=style)

    logger.info(f"Generating portrait with prompt: {prompt[:100]}...")

    # Generate image
    image = client.generate_image(
        prompt=prompt,
        negative_prompt=(
            "blurry, low quality, distorted, deformed, ugly, bad anatomy, "
            "bad proportions, extra limbs, mutated, disfigured, "
            "watermark, text, signature, multiple heads"
        ),
        width=768,
        height=1024,
        steps=25,
        cfg_scale=7.5,
    )

    if image is None:
        return False, "Image generation failed. Check ComfyUI logs."

    # Save image
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, format="PNG", quality=95)
        logger.info(f"Saved portrait to: {output_path}")
        return True, None
    except Exception as exc:
        return False, f"Failed to save image: {exc}"
