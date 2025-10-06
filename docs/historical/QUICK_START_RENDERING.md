# 🎨 Quick Start: Local Portrait Rendering

Generate photorealistic portraits from PaDNA traits in 4 steps.

## Prerequisites
- Mac with Apple Silicon (M1/M2/M3)
- 16GB+ RAM recommended
- 50GB free disk space

## Setup (One-Time, ~30 minutes)

```bash
# 1. Install ComfyUI
cd ~/Documents/ReDNA_Demos
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
pip3 install -r requirements.txt

# 2. Download Model (choose one)
# Quick option: RealVisXL (6.5GB, 30-45sec generation)
wget https://huggingface.co/SG161222/RealVisXL_V4.0/resolve/main/RealVisXL_V4.0.safetensors \
  -O models/checkpoints/RealVisXL_V4.0.safetensors

# OR Best quality: FLUX.1-schnell (23GB, 60-90sec generation)
pip3 install huggingface_hub
huggingface-cli download black-forest-labs/FLUX.1-schnell \
  --local-dir models/checkpoints/FLUX.1-schnell
```

## Daily Usage (2 steps)

```bash
# Terminal 1: Start ComfyUI (keep running)
cd ~/Documents/ReDNA_Demos/ComfyUI
python3 main.py --force-fp16

# Terminal 2: Generate portrait
cd ~/Documents/ReDNA_Demos
.venv/bin/python PhotoRefinementCoach/scripts/generate_portrait.py \
  data/users/LLTEST/resolved.json
```

✅ **Image saved to:** `portraits/LLTEST.png`

## Common Commands

```bash
# Just see the prompt (no rendering)
.venv/bin/python PhotoRefinementCoach/scripts/generate_portrait.py \
  data/users/LLTEST/resolved.json --prompt-only

# Different style
.venv/bin/python PhotoRefinementCoach/scripts/generate_portrait.py \
  data/users/LLTEST/resolved.json --style cinematic

# Custom output
.venv/bin/python PhotoRefinementCoach/scripts/generate_portrait.py \
  data/users/LLTEST/resolved.json -o myportrait.png

# Generate for all users
for user_dir in data/users/*/; do
    user_id=$(basename "$user_dir")
    [ -f "$user_dir/resolved.json" ] && \
    .venv/bin/python PhotoRefinementCoach/scripts/generate_portrait.py \
        "$user_dir/resolved.json" -o "portraits/$user_id.png"
done
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| ComfyUI won't start | `pip3 install torch torchvision` |
| "No models available" | Check models are in `ComfyUI/models/checkpoints/` |
| Out of memory | Use `--lowvram` flag or smaller model |
| Connection refused | Start ComfyUI server first |
| Poor quality | Try FLUX model, increase steps to 30-40 |

## Generation Times
- **RealVisXL:** 30-45 seconds
- **FLUX:** 60-90 seconds
- **First generation:** +30 seconds (loading model)

## Files Created

- **ComfyUI client:** `PhotoRefinementCoach/src/comfyui_client.py`
- **Trait-to-prompt:** `PhotoRefinementCoach/src/trait_to_prompt.py`
- **CLI tool:** `PhotoRefinementCoach/scripts/generate_portrait.py`
- **Full docs:** `PhotoRefinementCoach/docs/LOCAL_RENDERING_SETUP.md`

## Next Steps

1. ✅ Test with LLTEST: `data/users/LLTEST/resolved.json`
2. Try different styles: `--style cinematic`
3. Experiment with models
4. Integrate into PaDNA Coach UI
5. Set up batch processing

## Support

Full documentation: [LOCAL_RENDERING_SETUP.md](PhotoRefinementCoach/docs/LOCAL_RENDERING_SETUP.md)
