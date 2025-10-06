# Portrait Rendering Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ReDNA Photo Coach                            │
│                                                                     │
│  User imports JSON → Import Pipeline → Trait Validation           │
│         ↓                                                           │
│    resolved.json (32+ PaDNA traits with UCN scores)               │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    Trait-to-Prompt Converter                        │
│                   (trait_to_prompt.py)                              │
│                                                                     │
│  • Hierarchical trait prioritization                               │
│  • UCN-weighted emphasis                                           │
│  • Natural language generation                                     │
│  • Style-specific formatting                                       │
│                                                                     │
│  Input: resolved.json                                              │
│  Output: Optimized prompt text                                     │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
         "Professional high-quality portrait photograph,
          photorealistic, 8k, detailed, a woman with
          light green with hazel flecks eyes, almond-shaped eyes,
          red-auburn hair, long hair, wavy hair..."
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      ComfyUI Client                                 │
│                    (comfyui_client.py)                              │
│                                                                     │
│  • Workflow generation                                             │
│  • Queue management                                                │
│  • Progress monitoring                                             │
│  • Image retrieval                                                 │
│                                                                     │
│  API: http://127.0.0.1:8188                                        │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                       ComfyUI Server                                │
│                    (Local Installation)                             │
│                                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │  Checkpoint │  │   Sampling   │  │     VAE      │             │
│  │   Loader    │→ │   (K-Sampler)│→ │   Decoder    │             │
│  └─────────────┘  └──────────────┘  └──────────────┘             │
│         ↓                ↓                   ↓                     │
│    [Load Model]    [Generate]         [Decode to Image]           │
│                                                                     │
│  Models: FLUX.1, RealVisXL, DreamshaperXL                         │
│  Hardware: Apple Silicon (MPS acceleration)                        │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
              Generated Image (PNG, 768x1024)
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        Output & Storage                             │
│                                                                     │
│  • Save to portraits/<user_id>.png                                 │
│  • Update user profile                                             │
│  • Display in PaDNA Coach UI                                       │
│  • Enable regeneration/variations                                  │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Trait Collection (Photo Coach)
```json
{
  "PaDNA.HairDNA.Color": {
    "resolved_value": "Red-Auburn",
    "ucn": 920.0
  },
  "PaDNA.EyeDNA.Color": {
    "resolved_value": "Light Green With Hazel Flecks",
    "ucn": 940.0
  },
  ...32 total traits
}
```

### 2. Prompt Generation
```python
PromptBuilder(style="photorealistic")
  .prioritize_by_ucn(threshold=800)
  .categorize(eyes, hair, skin, body...)
  .format_natural_language()
  → "Professional portrait photograph, a woman with..."
```

### 3. ComfyUI Workflow
```json
{
  "1": {"class_type": "CheckpointLoaderSimple"},
  "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt}},
  "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative}},
  "4": {"class_type": "EmptyLatentImage"},
  "5": {"class_type": "KSampler"},
  "6": {"class_type": "VAEDecode"},
  "7": {"class_type": "SaveImage"}
}
```

### 4. Generation Parameters
```python
{
  "width": 768,
  "height": 1024,
  "steps": 25,
  "cfg_scale": 7.5,
  "sampler": "euler",
  "scheduler": "normal",
  "seed": random()
}
```

## Component Interaction

```
CLI Tool (generate_portrait.py)
    ↓
┌────────────────────────────────┐
│  Load resolved.json            │
│  ↓                              │
│  Generate prompt               │
│  (trait_to_prompt.py)          │
│  ↓                              │
│  Create ComfyUI client         │
│  (comfyui_client.py)           │
│  ↓                              │
│  Check server availability     │
│  ↓                              │
│  Build workflow                │
│  ↓                              │
│  Queue for execution           │
│  ↓                              │
│  Poll for completion           │
│  ↓                              │
│  Download image                │
│  ↓                              │
│  Save to disk                  │
└────────────────────────────────┘
```

## Trait Prioritization Logic

```python
Priority 1 (Highest Impact):
  - Eyes (color, shape)
  - Hair (color, length, texture)
  - Skin (tone, freckles)

Priority 2 (Facial Features):
  - Smile (shape, teeth)
  - Expression (mood, eye contact)
  - Face shape

Priority 3 (Body):
  - Build, proportions
  - Height, fitness
  - Body features

Priority 4 (Details):
  - Jewelry, piercings
  - Style themes
  - Accessories
```

**UCN Filtering:**
- UCN ≥ 900: Very high confidence (emphasized)
- UCN ≥ 800: High confidence (included)
- UCN < 800: Lower confidence (optional, filtered if too many traits)

## Performance Characteristics

### Generation Pipeline

| Stage | Time | Notes |
|-------|------|-------|
| Load traits | <1s | JSON parsing |
| Generate prompt | <1s | String manipulation |
| Queue workflow | <1s | HTTP POST |
| **Model inference** | **20-90s** | Depends on model/hardware |
| Download image | <1s | HTTP GET |
| Save to disk | <1s | File I/O |
| **Total** | **25-95s** | First run +30s for model load |

### Model Comparison

| Model | Size | Speed (M1) | Quality | Memory |
|-------|------|------------|---------|--------|
| FLUX.1-schnell | 23GB | 60-90s | ⭐⭐⭐⭐⭐ | 16GB+ |
| RealVisXL | 6.5GB | 30-45s | ⭐⭐⭐⭐ | 8GB+ |
| DreamshaperXL | 6.6GB | 20-30s | ⭐⭐⭐ | 8GB+ |

## Error Handling

```python
try:
    # 1. Check server availability
    if not client.is_available():
        return "ComfyUI not running"

    # 2. Validate models exist
    models = client.get_models()
    if not models:
        return "No models found"

    # 3. Generate with timeout
    image = client.generate_image(...)
    if image is None:
        return "Generation failed"

    # 4. Save with error checking
    image.save(output_path)

except Exception as exc:
    logger.error(f"Pipeline error: {exc}")
    return error_message
```

## Integration Points

### Current Integration
- ✅ CLI tool for manual generation
- ✅ Python API for programmatic use
- ✅ Trait-to-prompt conversion
- ✅ ComfyUI client library

### Future Integration
- [ ] PaDNA Coach UI button
- [ ] Automatic generation on import
- [ ] Batch processing endpoint
- [ ] Real-time preview
- [ ] Style selection UI
- [ ] Regeneration with variations
- [ ] Image comparison view
- [ ] Export to user profile

## File Locations

```
ReDNA_Demos/
├── PhotoRefinementCoach/
│   ├── src/
│   │   ├── trait_to_prompt.py      # Prompt generation
│   │   └── comfyui_client.py        # API client
│   ├── scripts/
│   │   └── generate_portrait.py     # CLI tool
│   └── docs/
│       ├── LOCAL_RENDERING_SETUP.md # Full guide
│       └── RENDERING_ARCHITECTURE.md # This file
├── ComfyUI/                         # Local installation
│   ├── models/
│   │   └── checkpoints/             # AI models
│   ├── output/                      # Generated images
│   └── main.py                      # Server
├── data/
│   └── users/
│       └── <user_id>/
│           └── resolved.json        # Trait source
└── portraits/                       # Output directory
    └── <user_id>.png               # Generated portraits
```

## API Endpoints

### ComfyUI REST API

```
GET  /system_stats          # Server status
GET  /object_info           # Available nodes/models
POST /prompt                # Queue workflow
GET  /history/{prompt_id}   # Check status
GET  /queue                 # Current queue
GET  /view?filename=...     # Download image
```

### Python API (ReDNA)

```python
# High-level
from PhotoRefinementCoach.src.comfyui_client import generate_portrait_from_traits

success, error = generate_portrait_from_traits(
    traits=traits_dict,
    output_path=Path("portrait.png"),
    style="photorealistic"
)

# Low-level
from PhotoRefinementCoach.src.comfyui_client import ComfyUIClient

client = ComfyUIClient("http://127.0.0.1:8188")
image = client.generate_image(
    prompt="...",
    width=768,
    height=1024,
    steps=25
)
```

## Quality Assurance

### Prompt Quality Checks
- ✅ Trait count (30+ traits optimal)
- ✅ High UCN coverage (>80% above 800)
- ✅ Key features present (eyes, hair, skin)
- ✅ Prompt length (80-150 words optimal)
- ✅ Style keywords included

### Image Quality Checks
- Resolution verification (768x1024)
- File size validation (2-10MB)
- Format confirmation (PNG)
- Visual inspection (manual QA)

### Error Recovery
- Model auto-detection if not specified
- Retry with different seed on failure
- Fallback to smaller dimensions if OOM
- Graceful degradation (skip low-UCN traits)

## Scaling Considerations

### Single User
- Generation time: 30-90 seconds
- Disk space: ~5MB per image
- Model memory: 6-23GB (stays loaded)

### Batch Processing
- Sequential generation: N × 30-90s
- Parallel not recommended (memory limits)
- Queue system for multiple requests
- Estimated: ~50 images/hour (RealVisXL)

### Production Deployment
- Keep ComfyUI running as service
- Implement queue manager
- Add caching for repeated requests
- Monitor resource usage
- Set up backup/failover
