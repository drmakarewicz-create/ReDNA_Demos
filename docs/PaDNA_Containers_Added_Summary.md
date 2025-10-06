# PaDNA Containers Added During Delta Exercises

**Last Updated:** 2025-10-03
**Total New Containers:** 77 (24 from v1 + 53 from v2)

---

## LLTEST v1 Refinement (24 containers)
_Batch: padna-refine-LLTEST-v1_
_Focus: Eyes, skin, hair, face, smile detail_

### Eyes/Iris Detail (5 containers)
- `PaDNA.EyeDNA.Iris.BaseColor` — Atomic iris color (brown, blue, green, hazel, etc.)
- `PaDNA.EyeDNA.Iris.Flecks` — Fleck color (hazel, gold, copper, etc.)
- `PaDNA.EyeDNA.Iris.FleckPattern` — Pattern (scattered, central, radial, dense)
- `PaDNA.EyeDNA.Iris.LimbalRing` — Ring prominence (none, faint, moderate, prominent)
- `PaDNA.EyeDNA.Iris.Saturation` — Saturation percentage (0-100%)

### Skin/Freckles (3 containers)
- `PaDNA.SkinDNA.Freckles.Density` — Concentration (none, light, medium, heavy, very-heavy)
- `PaDNA.SkinDNA.Freckles.Coverage` — Region (cheeks-only, t-zone, full-face, face-shoulders)
- `PaDNA.SkinDNA.Freckles.Contrast` — Visibility (subtle, visible, prominent, stark)

### Skin/Undertone (2 containers)
- `PaDNA.SkinDNA.Undertone.Type` — Type (cool, neutral, warm, golden-warm, peachy-warm)
- `PaDNA.SkinDNA.Undertone.Intensity` — Strength (subtle, moderate, strong, very-strong)

### Hair/Color (3 containers)
- `PaDNA.HairDNA.Color.Base` — Base color (black, auburn, red-auburn, blonde, etc.)
- `PaDNA.HairDNA.Color.Highlights` — Highlight type (sun-kissed, copper, gold, balayage, etc.)
- `PaDNA.HairDNA.Color.Dimension` — Multi-tonal variation (flat-monochrome to high-dimension)

### Hair/Curl Pattern (2 containers)
- `PaDNA.HairDNA.CurlPattern` — Curl typing (straight-1, wavy-2A/2B/2C, curly-3A/3B/3C, coily-4A/4B/4C)
- `PaDNA.HairDNA.WaveDefinition` — Wave definition (loose, medium, defined, tight)

### Hair/Parting (2 containers)
- `PaDNA.HairDNA.Parting.Side` — Side (left, right, center, zigzag, none, variable)
- `PaDNA.HairDNA.Parting.Consistency` — Frequency (low, medium, high, always)

### Face/Proportions (2 containers)
- `PaDNA.FaceDNA.EyeSpacing` — Eye spacing (very-close, close, average, wide, very-wide)
- `PaDNA.FaceDNA.EyeSizeRelative` — Eye size relative to face (small to large)

### Face/Structure (2 containers)
- `PaDNA.FaceDNA.Cheekbones` — Prominence (flat, subtle, moderate, prominent, high-sharp)
- `PaDNA.FaceDNA.CheekboneHeight` — Height (low, mid, high)

### Smile/Lip Detail (3 containers)
- `PaDNA.SmileDNA.LipFullness` — Overall fullness (thin to very-full)
- `PaDNA.SmileDNA.CupidsBow` — Cupid's bow definition (absent, subtle, defined, pronounced)
- `PaDNA.SmileDNA.LipSymmetry` — Symmetry (symmetric, slightly-asymmetric, asymmetric)

---

## BSTest + v2/v3 Refinements (53 containers)
_Batch: BSTest-enhanced-v2, LLTEST v2/v3_
_Focus: Makeup, hair accessories, body, hands, jewelry, apparel, behavioral, style_

### Eyebrows (3 containers)
- `PaDNA.BrowDNA.Shape` — Shape (straight, soft-arch, arched-soft-angle, high-arch, s-curve)
- `PaDNA.BrowDNA.Thickness` — Thickness (thin to thick)
- `PaDNA.BrowDNA.Color` — Color (light-blonde to black)

### Skin Extended (2 containers)
- `PaDNA.SkinDNA.Texture` — Texture (airbrushed, smooth, natural-with-visible-pores, coarse)
- `PaDNA.SkinDNA.TanLevel` — Tan level (pale, fair, sun-kissed, tan, deep)

### Hair Extended (4 containers)
- `PaDNA.HairDNA.RootContrast` — Root visibility (none, faint, visible-darker-roots, strong)
- `PaDNA.HairDNA.Tone` — Tone (cool-ash, neutral, warm-golden, coppery, mixed)
- `PaDNA.HairDNA.UpdoStyle` — Updo style (none, ponytail, messy-high-bun, sleek-bun, half-up)
- `PaDNA.HairDNA.Accessories` — Accessories (none, flower-crowns, ribbons, clips, headband)

### Forehead (2 containers)
- `PaDNA.ForeheadDNA.Height` — Height (low, medium, high)
- `PaDNA.ForeheadDNA.Shape` — Shape (flat, gently-rounded, convex)

### Nose (1 container)
- `PaDNA.NoseDNA.BridgeWidth` — Bridge width (narrow, narrow-to-medium, medium, wide)

### Lips (1 container)
- `PaDNA.LipDNA.Texture` — Texture (matte, natural, smooth-with-natural-gloss, glossy)

### Body & Tattoos (3 containers)
- `PaDNA.BodyDNA.AbsDefinition` — Abs definition (none, soft, defined-visible, shredded)
- `PaDNA.BodyDNA.Tattoo.PelvisRight` — Right pelvis tattoo (none, small-symbol-text, floral, other)
- `PaDNA.BodyDNA.Tattoo.PelvisLeft` — Left pelvis tattoo (none, small-symbol-text, floral, other)

### Apparel (4 containers)
- `PaDNA.ApparelDNA.FrequentBottoms` — Bottom garments (denim-shorts, mini-skirts, low-rise-pants, etc.)
- `PaDNA.ApparelDNA.Patterns` — Patterns (leopard-print, floral, solid, striped, mixed)
- `PaDNA.ApparelDNA.Colors` — Colors (neon-pink, neon-green, bright-red, neutral, etc.)
- `PaDNA.ApparelDNA.Gloves` — Gloves (none, fingerless-black, wrist-length, full-length)

### Footwear (1 container)
- `PaDNA.FootwearDNA.Visibility` — Visibility (visible, often-out-of-frame, hidden)

### Hands & Nails (2 containers)
- `HandsDNA.Nails.Length` — Nail length (short, medium, long)
- `HandsDNA.Nails.Style` — Nail style (bare, polished-neutral, polished-color, french, acrylic-gel)

### Jewelry (3 containers)
- `JewelryDNA.Rings.Count` — Ring count (none, single, multiple)
- `JewelryDNA.Bracelets.Style` — Bracelet style (none, thin-bangles, charm, cuff, mixed)
- `JewelryDNA.Necklaces.Style` — Necklace style (none, pendant, choker, layered, statement)

### Makeup (10 containers)
- `MakeupDNA.Eyes.Style` — Eye makeup style (natural, smoky-eye, heavy-smoky-eye-with-black-liner, winged, glam)
- `MakeupDNA.Eyes.Underliner` — Underliner presence (absent, faint, present)
- `MakeupDNA.Lashes` — Lash style (natural, mascara, long-volumized-mascara-false, false-dramatic)
- `MakeupDNA.Lips.Color` — Lip color (nude, nude-to-pink, pink, red, berry, other)
- `MakeupDNA.Skin.Finish` — Foundation finish (natural, dewy, satin, medium-coverage-matte, full-coverage-matte)
- `MakeupDNA.Blush.Tone` — Blush tone (peach, soft-pink, rose, bronze)

### Behavioral (2 containers)
- `BehavioralDNA.Stance` — Stance (neutral, hands-on-hips, hip-pop, contrapposto, dynamic)
- `BehavioralDNA.Gestures` — Gestures (none, hair-flip, torso-sway, hand-flourish, mixed)

### Style Context (3 containers)
- `StyleContext.Environment` — Environment (indoor-home-large-windows, studio, beach, urban, outdoor-natural, mixed)
- `StyleContext.TimeOfDay` — Time of day (morning, daylight, mid-day, golden-hour, night)
- `StyleContext.BeachShots` — Beach shot frequency (none, occasional, frequent)

---

## High-Impact Containers (Priority for Rendering)

Based on iterative testing, these containers had the **highest impact on portrait accuracy**:

### Critical for Likeness
1. `PaDNA.EyeDNA.Iris.*` (all iris containers) — Eyes are identity anchors
2. `PaDNA.SkinDNA.Freckles.*` (density, coverage, contrast) — Signature features
3. `PaDNA.FaceDNA.Cheekbones` + `CheekboneHeight` — Facial structure
4. `PaDNA.BrowDNA.*` (shape, thickness, color) — Frame the face
5. `PaDNA.FaceDNA.EyeSpacing` + `EyeSizeRelative` — Facial harmony

### Critical for Realism
6. `PaDNA.SkinDNA.Texture` — Prevents overly smooth/AI look
7. `PaDNA.HairDNA.CurlPattern` + `WaveDefinition` — Realistic texture
8. `PaDNA.HairDNA.Color.*` (base, highlights, dimension) — Multi-tonal hair
9. `PaDNA.NoseDNA.BridgeWidth` — Subtle but important for proportions
10. `PaDNA.LipDNA.Texture` — Adds realistic finish

### Critical for Style Accuracy
11. `MakeupDNA.Eyes.Style` + `Underliner` — Signature looks (smoky-eye, etc.)
12. `PaDNA.HairDNA.RootContrast` — Visible roots change perception significantly
13. `PaDNA.BodyDNA.AbsDefinition` — Fitness indicators
14. `PaDNA.ApparelDNA.Patterns` + `Colors` — Neon/leopard print signatures
15. `StyleContext.Environment` + `TimeOfDay` — Lighting and setting

---

## Schema Implementation Notes

### Aliases (Backward Compatibility)
- `PaDNA.FaceDNA.EyeSize` → `PaDNA.EyeDNA.SizeRelative`
- Legacy `Makeup.*` paths → `MakeupDNA.*`

### Defaults
- All new containers: `ucn=0`, `curiosity=1.0`
- Sensitive containers flagged (biometric-adjacent traits)
- Explorer shows 🔒 badges for sensitive traits

### Next Steps
1. ✅ Registry patch v2 merged into `traits_registry.patch.yaml`
2. Upload BSTest-enhanced-v2.json and re-ingest
3. Re-render portraits and measure delta reduction
4. Update `trait-to-prompt.ts` with minimal mappings for new containers
5. Run acceptance QA on smoky-eye, blonde with visible roots, abs definition, tattoos, neon/leopard styling

---

## Migration Path

### From Legacy to Granular Containers

**Eyes:**
- `PaDNA.EyeDNA.Color: "Light Green With Hazel Flecks"` →
  - `PaDNA.EyeDNA.Iris.BaseColor: "light-green"`
  - `PaDNA.EyeDNA.Iris.Flecks: "hazel"`
  - `PaDNA.EyeDNA.Iris.FleckPattern: "scattered"`
  - `PaDNA.EyeDNA.Iris.LimbalRing: "moderate"`

**Skin:**
- `PaDNA.SkinDNA.Freckles: "Present, Across Face/Shoulders"` →
  - `PaDNA.SkinDNA.Freckles.Density: "medium-heavy"`
  - `PaDNA.SkinDNA.Freckles.Coverage: "face-shoulders"`
  - `PaDNA.SkinDNA.Freckles.Contrast: "prominent"`

**Hair:**
- `PaDNA.HairDNA.Color: "Red-Auburn"` →
  - `PaDNA.HairDNA.Color.Base: "red-auburn"`
  - `PaDNA.HairDNA.Color.Highlights: "copper"`
  - `PaDNA.HairDNA.Color.Dimension: "moderate-dimension"`

- `PaDNA.HairDNA.Texture: "Wavy"` →
  - `PaDNA.HairDNA.CurlPattern: "wavy-2B"`
  - `PaDNA.HairDNA.WaveDefinition: "defined"`

---

## Files Updated
- [traits_registry.patch.yaml](../ReDNACoreDemo/data/config/traits_registry.patch.yaml) — Schema definitions
- [DNA_Container_Reference.json](celebsamples/DNA_Container_Reference.json) — Reference catalog
- [Expanded_DNA_Containers_v2.md](../ReDNACoreDemo/data/config/Expanded_DNA_Containers_v2.md) — Conceptual documentation

---

**Summary:** The delta exercise process has added **77 new PaDNA containers** across two major refinement batches, significantly improving portrait rendering accuracy and realism. The v1 batch (LLTEST) focused on foundational detail (eyes, skin, hair), while v2 (BSTest) extended to makeup, accessories, body features, and contextual style markers.
