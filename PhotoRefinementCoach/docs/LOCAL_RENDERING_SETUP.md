# Local Image Rendering Setup Guide

Complete guide to generating photorealistic portraits from PaDNA traits using local ComfyUI.

## Quick Start (TL;DR)

```bash
# 1. Install ComfyUI
cd ~/Documents/ReDNA_Demos
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
pip3 install -r requirements.txt

# 2. Download a model (choose one)
# FLUX.1-schnell (23GB, best quality, slower)
huggingface-cli download black-forest-labs/FLUX.1-schnell \
  --local-dir models/checkpoints/FLUX.1-schnell

# OR RealVisXL (6.5GB, good quality, faster)
wget https://huggingface.co/SG161222/RealVisXL_V4.0/resolve/main/RealVisXL_V4.0.safetensors \
  -O models/checkpoints/RealVisXL_V4.0.safetensors

# 3. Start ComfyUI
python3 main.py --force-fp16

# 4. In another terminal, generate portrait
cd ~/Documents/ReDNA_Demos
.venv/bin/python PhotoRefinementCoach/scripts/generate_portrait.py \
  data/users/LLTEST/resolved.json
```

---

## Detailed Setup

### Step 1: Install ComfyUI

ComfyUI is a node-based interface for Stable Diffusion that runs locally on your Mac.

```bash
# Navigate to project directory
cd ~/Documents/ReDNA_Demos

# Clone ComfyUI
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI

# Install dependencies
pip3 install torch torchvision torchaudio
pip3 install -r requirements.txt

# For Apple Silicon optimization
pip3 install --pre torch torchvision torchaudio \
  --extra-index-url https://download.pytorch.org/whl/nightly/cpu
```

**Expected time:** 5-10 minutes

### Step 2: Download AI Models

You need at least one checkpoint model. Choose based on your needs:

#### Option A: FLUX.1-schnell (Recommended for Quality)

**Pros:** Best photorealism, excellent detail
**Cons:** Large (23GB), slower generation (60-90s)
**Hardware:** Needs 16GB+ RAM

```bash
# Install huggingface CLI
pip3 install huggingface_hub

# Download FLUX
cd ~/Documents/ReDNA_Demos/ComfyUI
huggingface-cli download black-forest-labs/FLUX.1-schnell \
  --local-dir models/checkpoints/FLUX.1-schnell
```

#### Option B: RealVisXL V4 (Recommended for Speed)

**Pros:** Great photorealism, fast (30-45s), smaller (6.5GB)
**Cons:** Slightly less detail than FLUX
**Hardware:** Works on 8GB+ RAM

```bash
cd ~/Documents/ReDNA_Demos/ComfyUI
wget https://huggingface.co/SG161222/RealVisXL_V4.0/resolve/main/RealVisXL_V4.0.safetensors \
  -O models/checkpoints/RealVisXL_V4.0.safetensors
```

#### Option C: DreamshaperXL (Good All-Rounder)

**Pros:** Versatile, good portraits, fast
**Cons:** Slightly stylized
**Hardware:** Works on 8GB+ RAM

```bash
cd ~/Documents/ReDNA_Demos/ComfyUI
wget https://huggingface.co/Lykon/dreamshaper-xl-1-0/resolve/main/DreamShaperXL_Turbo_v2_1.safetensors \
  -O models/checkpoints/DreamShaperXL_Turbo_v2_1.safetensors
```

**Expected time:** 20-60 minutes depending on internet speed

#### Directory Structure After Download

```
ComfyUI/
├── models/
│   └── checkpoints/
│       ├── FLUX.1-schnell/         (if downloaded)
│       ├── RealVisXL_V4.0.safetensors  (if downloaded)
│       └── DreamShaperXL_Turbo_v2_1.safetensors  (if downloaded)
├── output/                          (generated images go here)
└── ...
```

### Step 3: Start ComfyUI Server

```bash
cd ~/Documents/ReDNA_Demos/ComfyUI

# Start server (use fp16 for faster inference on Mac)
python3 main.py --force-fp16

# Optional flags:
# --listen 0.0.0.0  # Allow network access
# --port 8188       # Custom port (default is 8188)
# --lowvram         # If you have limited RAM
```

You should see:
```
Starting server...
Total VRAM 16384 MB, total RAM 16384 MB
pytorch version: 2.1.0
Set vram state to: NORMAL_VRAM
Device: mps
VAE dtype: torch.float32

To see the GUI go to: http://127.0.0.1:8188
```

✅ **ComfyUI is now running!**

Open http://127.0.0.1:8188 in your browser to see the node-based interface.

**Keep this terminal open** - ComfyUI needs to stay running for image generation.

### Step 4: Test Basic Generation

Before integrating with ReDNA, test that ComfyUI works:

1. Open http://127.0.0.1:8188
2. You'll see a workflow with connected nodes
3. Find the **"CLIP Text Encode (Prompt)"** node
4. Enter a simple prompt: `"a beautiful woman with red hair and green eyes, photorealistic"`
5. Click **"Queue Prompt"** (or press Ctrl+Enter)
6. Wait 30-90 seconds
7. Image appears in the preview panel!

If this works, you're ready for ReDNA integration ✅

---

## ReDNA Integration

### Generate Portrait from User Traits

Now you can generate portraits directly from resolved.json files:

```bash
# Navigate to ReDNA project
cd ~/Documents/ReDNA_Demos

# Generate portrait for LLTEST user
.venv/bin/python PhotoRefinementCoach/scripts/generate_portrait.py \
  data/users/LLTEST/resolved.json

# Output will be saved to: portraits/LLTEST.png
```

### Advanced Usage

```bash
# Custom output location
.venv/bin/python PhotoRefinementCoach/scripts/generate_portrait.py \
  data/users/LLTEST/resolved.json \
  -o custom/path/portrait.png

# Different style
.venv/bin/python PhotoRefinementCoach/scripts/generate_portrait.py \
  data/users/LLTEST/resolved.json \
  --style cinematic

# Just see the prompt without rendering
.venv/bin/python PhotoRefinementCoach/scripts/generate_portrait.py \
  data/users/LLTEST/resolved.json \
  --prompt-only

# Use remote ComfyUI server
.venv/bin/python PhotoRefinementCoach/scripts/generate_portrait.py \
  data/users/LLTEST/resolved.json \
  --server http://192.168.1.100:8188
```

### Styles Available

- `photorealistic` - Professional portrait photograph (default)
- `portrait` - Studio portrait with professional lighting
- `cinematic` - Film-quality with dramatic lighting
- `artistic` - Artistic interpretation with refined details

---

## Programmatic Usage

Use the Python API directly in your code:

```python
from pathlib import Path
from PhotoRefinementCoach.src.comfyui_client import ComfyUIClient, generate_portrait_from_traits
from PhotoRefinementCoach.src.trait_to_prompt import generate_prompt_from_traits
import json

# Load traits
with open("data/users/LLTEST/resolved.json") as f:
    traits = json.load(f)

# Option 1: Quick generation
success, error = generate_portrait_from_traits(
    traits=traits,
    output_path=Path("output/portrait.png"),
    style="photorealistic"
)

if success:
    print("✅ Portrait generated!")
else:
    print(f"❌ Error: {error}")

# Option 2: Advanced control
client = ComfyUIClient()

# Generate prompt
prompt = generate_prompt_from_traits(traits, style="photorealistic")

# Generate with custom parameters
image = client.generate_image(
    prompt=prompt,
    width=768,
    height=1024,
    steps=30,
    cfg_scale=7.5,
    seed=42,  # Use specific seed for reproducibility
)

if image:
    image.save("output/custom_portrait.png")
```

---

## Performance Tips

### Speed Optimization

**Mac M1/M2/M3:**
- Use `--force-fp16` flag (2x faster)
- Enable Metal acceleration (automatic)
- Use RealVisXL or DreamshaperXL for faster generation
- Reduce steps: 20-25 steps usually sufficient
- Use smaller dimensions: 512x768 instead of 768x1024

**Expected Generation Times:**
- FLUX.1-schnell: 60-90 seconds (M1/M2), 40-60 seconds (M3)
- RealVisXL: 30-45 seconds (M1/M2), 20-30 seconds (M3)
- DreamshaperXL Turbo: 20-30 seconds (M1/M2), 10-20 seconds (M3)

### Quality Optimization

**For Best Results:**
- Use FLUX.1-schnell model
- Higher steps: 30-40
- CFG scale: 7-9
- Full resolution: 768x1024 or 1024x1024
- Enable upscaling (if available in workflow)

**Prompt Optimization:**
- Use high UCN threshold (850+) for only the most confident traits
- Add style keywords: "professional photography", "8k", "detailed"
- Use negative prompts to avoid common issues

---

## Troubleshooting

### ComfyUI Won't Start

**Error:** `ImportError: No module named 'torch'`
**Fix:** Install PyTorch: `pip3 install torch torchvision torchaudio`

**Error:** `CUDA not available`
**Fix:** This is normal on Mac. Use MPS (Metal) instead.

**Error:** `Out of memory`
**Fix:**
- Use `--lowvram` flag
- Reduce image dimensions
- Close other applications
- Use a smaller model (RealVisXL instead of FLUX)

### Generation Fails

**Error:** `No models available`
**Fix:** Ensure models are in `ComfyUI/models/checkpoints/` directory

**Error:** `Connection refused`
**Fix:** Make sure ComfyUI server is running on http://127.0.0.1:8188

**Error:** `Timeout waiting for prompt`
**Fix:**
- First generation is slow (loading model into memory)
- Increase timeout in code
- Check ComfyUI console for errors

### Poor Image Quality

**Issue:** Blurry or distorted images
**Fix:**
- Increase steps (30-40)
- Use better model (FLUX or RealVisXL)
- Adjust CFG scale (7-9)
- Add more detailed prompt keywords

**Issue:** Wrong features
**Fix:**
- Check trait UCN values (low UCN = less confident)
- Increase emphasis_threshold to use only high-confidence traits
- Add specific keywords to prompt
- Try different random seeds

---

## Workflow Integration

### Batch Generation

Generate portraits for all users:

```bash
for user_dir in data/users/*/; do
    user_id=$(basename "$user_dir")
    if [ -f "$user_dir/resolved.json" ]; then
        echo "Generating portrait for $user_id..."
        .venv/bin/python PhotoRefinementCoach/scripts/generate_portrait.py \
            "$user_dir/resolved.json" \
            -o "portraits/$user_id.png"
    fi
done
```

### Auto-Generation on Import

Add to your import pipeline to automatically generate portraits when traits are imported.

### UI Integration

The PaDNA Coach UI can be extended to:
1. Show "Generate Portrait" button
2. Display generation progress
3. Show generated images in user profile
4. Allow regeneration with different styles/seeds

---

## Next Steps

1. **Test the setup** with your LLTEST user
2. **Try different models** to find your preferred quality/speed balance
3. **Experiment with styles** (photorealistic, cinematic, etc.)
4. **Integrate into UI** for seamless user experience
5. **Set up batch processing** for existing users

---

## Resources

- **ComfyUI Documentation:** https://github.com/comfyanonymous/ComfyUI
- **Model Hub:** https://huggingface.co/models?pipeline_tag=text-to-image
- **Prompt Engineering:** https://platform.stability.ai/docs/features/text-to-image
- **ReDNA Trait Docs:** `docs/TRAIT_DEFINITIONS.md`

---

## Support

If you encounter issues:
1. Check ComfyUI console output for errors
2. Verify model files are downloaded correctly
3. Test basic generation in ComfyUI web interface first
4. Check system resources (RAM, disk space)
5. Review trait data quality (UCN values, completeness)
