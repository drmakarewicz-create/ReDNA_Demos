/**
 * Trait-to-Prompt Converter v2.1
 *
 * Converts structured PaDNA trait data into optimized prompts for image generation.
 * TypeScript port of PhotoRefinementCoach/src/trait_to_prompt.py
 *
 * v2.1 Enhancements:
 * - Priority weighting for high-impact containers (freckles, iris, texture, makeup)
 * - Composite descriptors for iris detail and freckles
 * - Enhanced makeup and accessory mappings
 * - Anti-airbrushing negative prompts
 */

export interface Trait {
  resolved_value: any;
  ucn?: number;
  rr?: number;
  [key: string]: any;
}

export type TraitDict = Record<string, Trait>;

export type PromptStyle = 'photorealistic' | 'portrait' | 'cinematic' | 'artistic';

interface TraitDescription {
  [category: string]: string[];
}

// v2.1: Priority weighting for critical realism containers
const PRIORITY_WEIGHTS: Record<string, 'high' | 'med' | 'std'> = {
  'PaDNA.SkinDNA.Texture': 'high',
  'PaDNA.SkinDNA.Freckles.Density': 'high',
  'PaDNA.SkinDNA.Freckles.Coverage': 'high',
  'PaDNA.SkinDNA.Freckles.Contrast': 'high',
  'PaDNA.EyeDNA.Iris.BaseColor': 'high',
  'PaDNA.EyeDNA.Iris.Flecks': 'high',
  'PaDNA.EyeDNA.Iris.FleckPattern': 'high',
  'PaDNA.EyeDNA.Iris.LimbalRing': 'high',
  'MakeupDNA.Eyes.Style': 'med',
  'MakeupDNA.Lips.Finish': 'med',
};

const WEIGHT_VALUES = { high: 2.0, med: 1.5, std: 1.0 };

const STYLE_PREFIXES: Record<PromptStyle, string> = {
  photorealistic: 'Professional high-quality portrait photograph, photorealistic, 8k, detailed,',
  portrait: 'Studio portrait, professional lighting, detailed features,',
  cinematic: 'Cinematic portrait, film quality, dramatic lighting, detailed,',
  artistic: 'Artistic portrait, elegant composition, refined details,',
};

const TRAIT_ORDER = [
  // Core appearance (highest priority)
  'PaDNA.EyeDNA.Color',
  'PaDNA.EyeDNA.Shape',
  'PaDNA.HairDNA.Color',
  'PaDNA.HairDNA.Length',
  'PaDNA.HairDNA.Texture',
  'PaDNA.SkinDNA.Tone',
  'PaDNA.SkinDNA.Freckles',
  // Facial features
  'PaDNA.SmileDNA.SmileShape',
  'PaDNA.SmileDNA.Teeth',
  'PaDNA.EyeDNA.Lashes',
  'PaDNA.HairDNA.Parting',
  'PaDNA.HairDNA.Volume',
  // Expression
  'PaDNA.ExpressionDNA.TypicalExpression',
  'PaDNA.ExpressionDNA.EyeContact',
  // Body
  'PaDNA.BodyDNA.Build',
  'PaDNA.BodyDNA.WaistHipRatio',
  'PaDNA.BodyDNA.Legs',
  'PaDNA.BodyDNA.Arms',
  // Details
  'PaDNA.BodyDNA.Navel',
  'PaDNA.ApparelDNA.Jewelry.Necklace',
  'PaDNA.ApparelDNA.Jewelry.Earrings',
];

function categorizeTraitPath(path: string): string {
  if (path.includes('.EyeDNA.')) return 'eyes';
  if (path.includes('.HairDNA.')) return 'hair';
  if (path.includes('.SkinDNA.')) return 'skin';
  if (path.includes('.SmileDNA.') || path.includes('.FacialDNA.')) return 'face';
  if (path.includes('.ExpressionDNA.')) return 'expression';
  if (path.includes('.BodyDNA.')) return 'body';
  if (path.includes('.FitnessDNA.')) return 'fitness';
  if (path.includes('.ApparelDNA.') || path.includes('.Accessories.')) return 'apparel';
  if (path.includes('MakeupDNA')) return 'makeup';
  return 'other';
}

/**
 * v2.1: Composite descriptor for freckles (combines density + coverage + contrast)
 */
function frecklesComposite(density?: string, coverage?: string, contrast?: string): string | null {
  if (!density || density === 'none') return null;

  const densityMap: Record<string, string> = {
    'light': 'light freckles',
    'medium': 'medium density freckles',
    'heavy': 'heavy freckles',
    'very-heavy': 'very heavy freckles',
  };

  const coverageMap: Record<string, string> = {
    'cheeks-only': 'on cheeks',
    't-zone': 'across nose bridge and t-zone',
    'full-face': 'covering the face',
    'face-shoulders': 'across face, neck and shoulders',
    'face-neck-shoulders': 'across face, neck and shoulders',
  };

  const contrastMap: Record<string, string> = {
    'subtle': 'subtle',
    'visible': 'visible',
    'prominent': 'prominent',
    'stark': 'high-contrast',
  };

  const d = densityMap[density] || `${density} freckles`;
  const cvr = coverage ? coverageMap[coverage] : '';
  const ctr = contrast ? contrastMap[contrast] : '';

  // Build: "prominent medium density freckles across face, neck and shoulders"
  const parts = [ctr, d, cvr].filter(Boolean);
  return parts.join(' ').trim();
}

/**
 * v2.1: Composite descriptor for iris (combines base color + flecks + pattern + limbal ring)
 */
function irisComposite(base?: string, flecks?: string, pattern?: string, ring?: string): string | null {
  if (!base) return null;

  const baseColorMap: Record<string, string> = {
    'light-green': 'striking light green eyes',
    'hazel': 'hazel eyes',
    'amber': 'warm amber eyes',
    'light-blue': 'bright light blue eyes',
    'gray': 'cool gray eyes',
  };

  const patternMap: Record<string, string> = {
    'scattered': ' scattered throughout the iris',
    'central': ' concentrated near the pupil',
    'radial': ' radiating from the pupil',
    'dense': ' densely distributed across the iris',
  };

  const ringMap: Record<string, string> = {
    'faint': ', subtle limbal ring',
    'moderate': ', moderate limbal ring adding depth',
    'prominent': ', prominent limbal ring',
    'dark-prominent': ', dark prominent limbal ring for striking eyes',
  };

  const baseText = baseColorMap[base.toLowerCase()] || `${base.replace(/-/g, ' ')} eyes`;
  const fleckText = (flecks && flecks !== 'none') ? ` with ${flecks} flecks` : '';
  const patternText = (pattern && pattern !== 'none') ? (patternMap[pattern] || '') : '';
  const ringText = (ring && ring !== 'none') ? (ringMap[ring] || '') : '';

  return `${baseText}${fleckText}${patternText}${ringText}`.trim();
}

function traitToDescription(path: string, value: any): string | null {
  // Handle list values
  if (Array.isArray(value)) {
    if (value.length === 0) return null;
    if (value.length === 1) {
      value = String(value[0]);
    } else {
      value = value.slice(0, 3).join(', ');
    }
  }

  // Convert to string
  const valueStr = String(value).toLowerCase();
  const valueDisplay = String(value);

  // Skip certain values
  const skipValues = ['absent', 'none', 'n/a', 'unknown'];
  if (skipValues.includes(valueStr)) {
    return null;
  }

  // Map trait paths to natural descriptions
  const descriptions: Record<string, string | null> = {
    // Eyes
    'PaDNA.EyeDNA.Color': `${valueDisplay} eyes`,
    'PaDNA.EyeDNA.Shape': `${valueStr}-shaped eyes`,
    'PaDNA.EyeDNA.Lashes': `${valueStr} eyelashes`,
    // Eyes - Enhanced (Note: iris components handled by composite in extractDescriptions)
    'PaDNA.EyeDNA.Spacing': `${valueStr} eye spacing`,
    // Hair
    'PaDNA.HairDNA.Color': `${valueStr} hair`,
    'PaDNA.HairDNA.Length': `${valueStr} hair`,
    'PaDNA.HairDNA.Texture': `${valueStr} hair`,
    'PaDNA.HairDNA.Volume': `${valueStr} voluminous hair`,
    'PaDNA.HairDNA.Parting': `hair with ${valueStr}`,
    'PaDNA.HairDNA.Color.Base': `${valueStr} hair`,
    'PaDNA.HairDNA.Color.Highlights': `hair with ${valueStr} highlights`,
    'PaDNA.HairDNA.CurlPattern': `${valueStr.replace(/-/g, ' ')} curl pattern`,
    'PaDNA.HairDNA.Parting.Side': `${valueStr} side part`,
    // Hair - v2.1 Headpiece
    'PaDNA.HairDNA.Accessories.Headpiece': (() => {
      const headpieceMap: Record<string, string> = {
        'crown': 'wearing ornate crown',
        'tiara': 'wearing elegant tiara',
        'flower-crown': 'wearing flower crown',
        'headband': 'wearing headband',
        'veil': 'wearing veil',
        'fascinator': 'wearing fascinator',
      };
      return headpieceMap[valueStr] || null;
    })(),
    // Skin
    'PaDNA.SkinDNA.Tone': `${valueStr} skin`,
    'PaDNA.SkinDNA.Freckles': valueStr.includes('present') ? `${valueStr} freckles` : null,
    // Skin - v2.1 Texture (HIGH PRIORITY)
    'PaDNA.SkinDNA.Texture': (() => {
      const textureMap: Record<string, string> = {
        'natural-with-visible-pores': 'natural skin texture, visible pores, realistic skin detail',
        'smooth': 'smooth skin with subtle natural texture',
        'airbrushed': 'perfectly smooth skin',
        'coarse': 'textured skin with visible pores',
      };
      return textureMap[valueStr] || valueStr;
    })(),
    // Skin - Freckles (Note: individual components skipped if composite used)
    'PaDNA.SkinDNA.Undertone.Type': `${valueStr.replace(/-/g, ' ')} undertones`,
    // Face/Smile
    'PaDNA.SmileDNA.SmileShape': valueStr,
    'PaDNA.SmileDNA.Teeth': `${valueStr} teeth`,
    'PaDNA.SmileDNA.Dimples': valueStr.includes('present') ? 'dimples' : null,
    'PaDNA.SmileDNA.LipFullness': `${valueStr.replace(/-/g, ' ')} lips`,
    'PaDNA.SmileDNA.CupidsBow': `${valueStr} cupid's bow`,
    'PaDNA.FaceDNA.Cheekbones': `${valueStr} cheekbones`,
    // Expression
    'PaDNA.ExpressionDNA.TypicalExpression': valueStr,
    'PaDNA.ExpressionDNA.EyeContact': valueStr,
    // Body
    'PaDNA.BodyDNA.Build': `${valueStr} build`,
    'PaDNA.BodyDNA.WaistHipRatio': `${valueStr} figure`,
    'PaDNA.BodyDNA.Legs': `${valueStr} legs`,
    'PaDNA.BodyDNA.Arms': `${valueStr} arms`,
    'PaDNA.BodyDNA.Bust': `${valueStr} bust`,
    'PaDNA.BodyDNA.Navel': valueStr.includes('pierced') ? 'navel piercing' : null,
    // Fitness
    'PaDNA.FitnessDNA.Indicators': valueStr,
    // Apparel/Jewelry
    'PaDNA.ApparelDNA.Jewelry.Necklace': `wearing ${valueStr}`,
    'PaDNA.ApparelDNA.Jewelry.Earrings': `wearing ${valueStr}`,
    // Apparel - v2.1 Themes
    'PaDNA.ApparelDNA.Themes': (() => {
      if (!Array.isArray(value) || value.length === 0) return null;
      const themeMap: Record<string, string> = {
        'pageant': 'pageant photography style',
        'glamour': 'glamour photography',
        'beachwear': 'beach setting, casual beachwear',
        'casual': 'casual style',
        'athletic': 'athletic wear, fitness setting',
        'evening-wear': 'elegant evening wear',
        'performance': 'performance outfit',
        'editorial': 'editorial fashion photography',
      };
      return value.slice(0, 2).map((t: string) => themeMap[t] || t).join(', ');
    })(),
    // Makeup - v2.1 (MEDIUM-HIGH PRIORITY)
    'MakeupDNA.Eyes.Style': (() => {
      const styleMap: Record<string, string> = {
        'natural': 'natural eye makeup',
        'smoky-eye': 'smoky eye makeup',
        'heavy-smoky-eye-with-black-liner': 'heavy dramatic smoky eye with thick black eyeliner, intense eye makeup',
        'winged': 'winged eyeliner',
        'glam': 'glamorous eye makeup',
      };
      return styleMap[valueStr] || valueStr;
    })(),
    'MakeupDNA.Eyes.Underliner': valueStr === 'present' ? 'lower eyelid liner' : null,
    'MakeupDNA.Lashes': (() => {
      const lashMap: Record<string, string> = {
        'natural': 'natural lashes',
        'mascara': 'mascara-enhanced lashes',
        'long-volumized-mascara-false': 'long volumized lashes with dramatic mascara or false lashes',
        'false-dramatic': 'dramatic false eyelashes',
      };
      return lashMap[valueStr] || valueStr;
    })(),
    'MakeupDNA.Lips.Color': (() => {
      const colorMap: Record<string, string> = {
        'nude': 'nude lips',
        'nude-to-pink': 'nude pink lips',
        'pink': 'pink lips',
        'red': 'red lips',
        'berry': 'berry-toned lips',
      };
      return colorMap[valueStr] || `${valueStr} lips`;
    })(),
    'MakeupDNA.Lips.Finish': (() => {
      const finishMap: Record<string, string> = {
        'matte': 'matte lip finish',
        'natural': 'natural lip finish',
        'gloss': 'glossy lips, shiny finish',
        'shimmer': 'shimmery lips',
        'metallic': 'metallic lip finish',
      };
      return finishMap[valueStr] || valueStr;
    })(),
    'MakeupDNA.Skin.Finish': (() => {
      const finishMap: Record<string, string> = {
        'natural': 'natural skin finish',
        'dewy': 'dewy skin finish',
        'satin': 'satin skin finish',
        'medium-coverage-matte': 'medium-coverage matte foundation',
        'full-coverage-matte': 'full-coverage matte foundation',
      };
      return finishMap[valueStr] || valueStr;
    })(),
    'MakeupDNA.Blush.Tone': `${valueStr} blush`,
  };

  const desc = descriptions[path];

  // Fallback: use value directly
  if (desc === undefined && value) {
    return valueStr;
  }

  return desc ?? null;
}

function extractDescriptions(traits: TraitDict, emphasisThreshold: number): TraitDescription {
  const descriptions: TraitDescription = {};

  // v2.1: Track composite components
  const irisComponents = {
    base: traits['PaDNA.EyeDNA.Iris.BaseColor']?.resolved_value,
    flecks: traits['PaDNA.EyeDNA.Iris.Flecks']?.resolved_value,
    pattern: traits['PaDNA.EyeDNA.Iris.FleckPattern']?.resolved_value,
    ring: traits['PaDNA.EyeDNA.Iris.LimbalRing']?.resolved_value,
  };

  const frecklesComponents = {
    density: traits['PaDNA.SkinDNA.Freckles.Density']?.resolved_value,
    coverage: traits['PaDNA.SkinDNA.Freckles.Coverage']?.resolved_value,
    contrast: traits['PaDNA.SkinDNA.Freckles.Contrast']?.resolved_value,
  };

  // v2.1: Build sorted trait list by priority × UCN
  const sortedTraits = Object.entries(traits).map(([path, trait]) => {
    const priority = PRIORITY_WEIGHTS[path] || 'std';
    const ucn = trait?.ucn ?? 800;
    const weight = WEIGHT_VALUES[priority] * ucn;
    return { path, trait, weight };
  }).sort((a, b) => b.weight - a.weight);

  // v2.1: Add iris composite first if components exist
  if (irisComponents.base) {
    const irisDesc = irisComposite(
      irisComponents.base,
      irisComponents.flecks,
      irisComponents.pattern,
      irisComponents.ring
    );
    if (irisDesc) {
      if (!descriptions.eyes) descriptions.eyes = [];
      descriptions.eyes.push(irisDesc);
    }
  }

  // v2.1: Add freckles composite first if components exist
  if (frecklesComponents.density) {
    const frecklesDesc = frecklesComposite(
      frecklesComponents.density,
      frecklesComponents.coverage,
      frecklesComponents.contrast
    );
    if (frecklesDesc) {
      if (!descriptions.skin) descriptions.skin = [];
      descriptions.skin.push(frecklesDesc);
    }
  }

  // Skip individual iris/freckles components (handled by composites)
  const skipPaths = new Set([
    'PaDNA.EyeDNA.Iris.BaseColor',
    'PaDNA.EyeDNA.Iris.Flecks',
    'PaDNA.EyeDNA.Iris.FleckPattern',
    'PaDNA.EyeDNA.Iris.LimbalRing',
    'PaDNA.SkinDNA.Freckles.Density',
    'PaDNA.SkinDNA.Freckles.Coverage',
    'PaDNA.SkinDNA.Freckles.Contrast',
  ]);

  for (const { path, trait } of sortedTraits) {
    if (!trait || typeof trait !== 'object') continue;
    if (skipPaths.has(path)) continue;

    const value = trait.resolved_value;
    if (value === null || value === undefined) continue;

    const category = categorizeTraitPath(path);
    if (!descriptions[category]) {
      descriptions[category] = [];
    }

    const desc = traitToDescription(path, value);
    if (desc) {
      descriptions[category].push(desc);
    }
  }

  return descriptions;
}

/**
 * Build an optimized prompt from PaDNA traits
 */
export function buildPromptFromTraits(
  traits: TraitDict,
  style: PromptStyle = 'photorealistic',
  emphasisThreshold: number = 800.0,
  maxTokens: number = 200
): string {
  const segments: string[] = [];

  // Style prefix
  segments.push(STYLE_PREFIXES[style]);

  // Build descriptions by category
  const descriptions = extractDescriptions(traits, emphasisThreshold);

  // Collect face parts
  const faceParts: string[] = [];

  // Eyes
  if (descriptions.eyes) {
    faceParts.push(...descriptions.eyes);
  }

  // Hair
  if (descriptions.hair) {
    faceParts.push(...descriptions.hair);
  }

  // Skin
  if (descriptions.skin) {
    faceParts.push(...descriptions.skin);
  }

  // Face features and smile
  if (descriptions.smile) {
    faceParts.push(...descriptions.smile);
  }
  if (descriptions.face) {
    faceParts.push(...descriptions.face);
  }

  // Core subject with face features
  if (faceParts.length > 0) {
    segments.push(`a woman with ${faceParts.join(', ')}.`);
  } else {
    segments.push('a woman.');
  }

  // v2.1: Makeup (medium-high priority)
  if (descriptions.makeup && descriptions.makeup.length > 0) {
    segments.push(descriptions.makeup.join(', ') + '.');
  }

  // Expression
  if (descriptions.expression && descriptions.expression.length > 0) {
    segments.push(`Expression: ${descriptions.expression.slice(0, 2).join(', ')}.`);
  }

  // Body and fitness
  const bodyParts: string[] = [];
  if (descriptions.body) {
    bodyParts.push(...descriptions.body.slice(0, 4));
  }
  if (descriptions.fitness) {
    bodyParts.push(...descriptions.fitness.slice(0, 2));
  }

  if (bodyParts.length > 0) {
    segments.push(`Body: ${bodyParts.join(', ')}.`);
  }

  // Details (jewelry, apparel)
  if (descriptions.apparel && descriptions.apparel.length > 0) {
    const details = descriptions.apparel.slice(0, 3);
    segments.push(`Wearing: ${details.join(', ')}.`);
  }

  // Join segments
  let prompt = segments.join(' ');

  // Add quality keywords
  prompt += ', sharp focus, high detail, natural lighting';

  // Truncate if too long
  const words = prompt.split(/\s+/);
  if (words.length > maxTokens) {
    prompt = words.slice(0, maxTokens).join(' ') + '...';
  }

  return prompt;
}

/**
 * Get default negative prompt (v2.1 enhanced)
 */
export function getDefaultNegativePrompt(traits?: TraitDict): string {
  let negativePrompt =
    'blurry, low quality, distorted, deformed, ugly, bad anatomy, ' +
    'bad proportions, extra limbs, mutated, disfigured, ' +
    'watermark, text, signature, logo, multiple heads, duplicate, ' +
    'cartoon, anime, painting, illustration';

  // v2.1: Add anti-airbrushing when natural texture is specified
  if (traits) {
    const skinTexture = traits['PaDNA.SkinDNA.Texture']?.resolved_value;
    if (skinTexture === 'natural-with-visible-pores') {
      negativePrompt += ', NOT airbrushed, NOT overly smooth skin, NOT plastic-looking';
    }
  }

  return negativePrompt;
}
