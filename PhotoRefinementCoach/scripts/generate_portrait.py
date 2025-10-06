#!/usr/bin/env python3
"""
Generate Portrait from PaDNA Traits

Reads a user's resolved.json and generates a photorealistic portrait
using local ComfyUI installation.
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.comfyui_client import ComfyUIClient, generate_portrait_from_traits
from src.trait_to_prompt import generate_prompt_from_traits


def main():
    parser = argparse.ArgumentParser(
        description="Generate photorealistic portrait from PaDNA traits",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate from user's resolved.json
  python generate_portrait.py data/users/LLTEST/resolved.json

  # Specify output location
  python generate_portrait.py data/users/LLTEST/resolved.json -o portraits/LLTEST.png

  # Use different style
  python generate_portrait.py data/users/LLTEST/resolved.json --style cinematic

  # Just show the prompt without generating
  python generate_portrait.py data/users/LLTEST/resolved.json --prompt-only

  # Specify ComfyUI server
  python generate_portrait.py data/users/LLTEST/resolved.json --server http://localhost:8188
        """
    )

    parser.add_argument(
        "resolved_json",
        help="Path to resolved.json file"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output image path (default: portraits/<user_id>.png)"
    )
    parser.add_argument(
        "--style",
        choices=["photorealistic", "portrait", "cinematic", "artistic"],
        default="photorealistic",
        help="Rendering style"
    )
    parser.add_argument(
        "--server",
        default="http://127.0.0.1:8188",
        help="ComfyUI server URL"
    )
    parser.add_argument(
        "--prompt-only",
        action="store_true",
        help="Only show the generated prompt, don't render"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    # Load traits
    resolved_path = Path(args.resolved_json)
    if not resolved_path.exists():
        print(f"❌ Error: File not found: {resolved_path}")
        return 1

    try:
        with resolved_path.open("r") as f:
            traits = json.load(f)
    except Exception as exc:
        print(f"❌ Error loading traits: {exc}")
        return 1

    # Generate prompt
    try:
        prompt = generate_prompt_from_traits(traits, style=args.style)
    except Exception as exc:
        print(f"❌ Error generating prompt: {exc}")
        return 1

    print("=" * 80)
    print("GENERATED PROMPT")
    print("=" * 80)
    print()
    print(prompt)
    print()
    print(f"Style: {args.style}")
    print(f"Traits used: {len(traits)}")
    print()

    if args.prompt_only:
        print("✅ Prompt generated successfully (use without --prompt-only to render)")
        return 0

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        # Extract user_id from path or use filename
        user_id = resolved_path.parent.name
        output_path = Path("portraits") / f"{user_id}.png"

    print("=" * 80)
    print("GENERATING IMAGE")
    print("=" * 80)
    print()
    print(f"Output: {output_path}")
    print(f"Server: {args.server}")
    print()

    # Create client
    client = ComfyUIClient(base_url=args.server)

    # Check if server is running
    if not client.is_available():
        print("❌ Error: ComfyUI server is not running")
        print()
        print("Start ComfyUI with:")
        print("  cd ~/Documents/ReDNA_Demos/ComfyUI")
        print("  python3 main.py --force-fp16")
        print()
        print("Then open http://127.0.0.1:8188 in your browser")
        return 1

    # Get available models
    models = client.get_models()
    if models:
        print(f"Available models: {', '.join(models[:3])}")
        if len(models) > 3:
            print(f"  ... and {len(models) - 3} more")
    else:
        print("⚠️  Warning: No models detected. Make sure models are in ComfyUI/models/checkpoints/")

    print()
    print("🎨 Generating portrait (this may take 30-90 seconds)...")
    print()

    # Generate!
    success, error = generate_portrait_from_traits(
        traits=traits,
        output_path=output_path,
        client=client,
        style=args.style
    )

    print()
    if success:
        print("=" * 80)
        print("✅ SUCCESS!")
        print("=" * 80)
        print()
        print(f"Portrait saved to: {output_path}")
        print(f"File size: {output_path.stat().st_size / 1024 / 1024:.1f} MB")
        print()
        print("Open the image:")
        print(f"  open {output_path}")
        return 0
    else:
        print("=" * 80)
        print("❌ FAILED")
        print("=" * 80)
        print()
        print(f"Error: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
