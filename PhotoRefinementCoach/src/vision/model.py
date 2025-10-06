from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Tuple
import os, base64, hashlib, json, requests, io
from PIL import Image

# ------------------------
# Recency tag
# ------------------------
class RecencyTag(str, Enum):
    RECENT = "RECENT"
    OLD    = "OLD"
    RETRO  = "RETRO"

# ------------------------
# Observation (per photo)
# ------------------------
@dataclass
class VisionObservation:
    image_id: str
    recency: RecencyTag
    model_name: str
    model_version: str
    tokens: Dict[str, Dict[str, Any]]  # dna_path -> {"value": token, "confidence": float, "details": {...}}

# ------------------------
# Base class
# ------------------------
class VisionModel:
    name: str = "mock-vision"
    version: str = "1.0"

    @staticmethod
    def from_name(name: str) -> "VisionModel":
        if name.startswith("llama3-vision"):
            return Llama3VisionAdapter()
        return MockVision()

    def analyze(self, image_bytes: bytes, recency: RecencyTag) -> VisionObservation:
        raise NotImplementedError

# ------------------------
# Helpers
# ------------------------
def _prep_image(image_bytes: bytes, max_px: int = 1024, quality: int = 90) -> Tuple[bytes, str]:
    """
    Downscale & JPEG-encode to keep payloads small and predictable for the VLM.
    Returns (jpeg_bytes, sha1_hex).
    """
    im = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = im.size
    if max(w, h) > max_px:
        scale = max_px / float(max(w, h))
        im = im.resize((int(w*scale), int(h*scale)))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", optimize=True, quality=quality)
    jb = buf.getvalue()
    hsh = hashlib.sha1(jb).hexdigest()
    return jb, hsh

# ------------------------
# Deterministic mock
# ------------------------
class MockVision(VisionModel):
    name, version = "mock-vision", "1.0"
    def analyze(self, image_bytes: bytes, recency: RecencyTag) -> VisionObservation:
        h = hashlib.sha1(image_bytes).hexdigest()
        seed = int(h[:8], 16)
        def pick(seq): return seq[seed % len(seq)]
        def conf(a=0.72, b=0.22): return max(0.55, min(0.95, a + ((seed % 1000)/1000 - 0.5)*b))
        tokens = {
            "PaDNA.HairDNA.Color":   {"value": pick(["blonde","light-blonde","brown","dark-brown","red","auburn"]), "confidence": conf()},
            "PaDNA.HairDNA.Length":  {"value": pick(["medium","long","very-long"]), "confidence": conf()},
            "PaDNA.HairDNA.Texture": {"value": pick(["straight","wavy","curly"]), "confidence": conf()},
            "PaDNA.HairDNA.Style":   {"value": pick(["loose","bangs","styled-wave"]), "confidence": conf()},
            "PaDNA.HairDNA.Part":    {"value": pick(["center","slight-left","slight-right","none"]), "confidence": conf()},
            "PaDNA.EyeDNA.Color":    {"value": pick(["blue","green","gray","brown"]), "confidence": conf()},
            "PaDNA.EyeDNA.Shape":    {"value": pick(["almond","round"]), "confidence": conf()},
            "PaDNA.EyeDNA.Lashes.Length": {"value": pick(["short","medium","long"]), "confidence": conf()},
            "PaDNA.SkinDNA.Tone":    {"value": pick(["light","light-medium","medium"]), "confidence": conf()},
            "PaDNA.SkinDNA.Undertone": {"value": pick(["cool","warm","neutral"]), "confidence": conf()},
            "PaDNA.FaceDNA.Shape":   {"value": pick(["oval","heart","round","square"]), "confidence": conf()},
            "PaDNA.LipDNA.Fullness": {"value": pick(["thin","medium","full"]), "confidence": conf()},
            "PaDNA.GlassesDNA":      {"value": pick(["none","occasional"]), "confidence": conf()},
            "PaDNA.DistinguishingMarksDNA.Tattoos":  {"value": pick(["none","present"]), "confidence": conf()},
            "PaDNA.DistinguishingMarksDNA.Tattoos.Location": {"value": pick(["arm","wrist","ankle","shoulder"]), "confidence": conf()},
            "PaDNA.DistinguishingMarksDNA.Piercings":{"value": pick(["earlobes","none"]), "confidence": conf()},
            "PaDNA.Accessories.Earrings": {"value": pick(["studs","hoops","none"]), "confidence": conf()},
            "PaDNA.PostureDNA":      {"value": pick(["neutral","slight-tilt-right","slight-tilt-left"]), "confidence": conf()},
            "PaDNA.ApparelDNA.Style":{"value": pick(["glam","boho","classic"]), "confidence": conf()},
            "PaDNA.ApparelDNA.Fit":  {"value": pick(["fitted","tailored","regular"]), "confidence": conf()},
            "PaDNA.ApparelDNA.Palette":{"value": pick(["warm-metallic","cool","warm","neutral"]), "confidence": conf()},
        }
        return VisionObservation(h[:10], recency, self.name, self.version, tokens)

# ------------------------
# Llama-3-Vision via local Ollama
# ------------------------
class Llama3VisionAdapter(VisionModel):
    """
    Calls local Ollama with a vision-capable model (e.g., 'llama3.2-vision').
    Configure via env:
      OLLAMA_HOST  (default http://127.0.0.1:11434)
      OLLAMA_MODEL (default llama3.2-vision)
    """
    name, version = "llama3-vision", "ollama-0.3"

    def __init__(self):
        self.host  = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        self.model = os.getenv("OLLAMA_MODEL", "llama3.2-vision")
        self.timeout = (30, 240)  # longer read timeout for first-load

    def _check_model(self):
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=(5,10))
            r.raise_for_status()
            tags = [m.get("name", "") for m in r.json().get("models", [])]
            normalized = {name.split(":", 1)[0] for name in tags}
            if self.model not in normalized:
                # Not fatal, but helpful to surface early
                raise RuntimeError(f"Model '{self.model}' not found in Ollama tags: {tags}")
        except Exception as e:
            raise RuntimeError(f"Ollama not reachable at {self.host} ({e})")

    def _chat(self, image_b64: str) -> Dict[str, Any]:
        enums = {
            "PaDNA.HairDNA.Color": ["black","dark-brown","brown","light-brown","auburn","red","strawberry-blonde","blonde","light-blonde","gray","white","dyed-vivid","dyed-pastel"],
            "PaDNA.HairDNA.Intensity": ["natural","dyed","highlighted","unknown"],
            "PaDNA.HairDNA.Length":["buzzed","short","medium","long","very-long"],
            "PaDNA.HairDNA.Texture":["straight","wavy","curly","coily"],
            "PaDNA.HairDNA.Pattern":["full","thinning","receding","partial-balding","bald","unknown"],
            "PaDNA.HairDNA.Style":["loose","ponytail","bun","braids","bangs","layered","undercut","styled-wave","afro","pixie"],
            "PaDNA.HairDNA.Part":["center","slight-left","slight-right","zigzag","none"],
            "PaDNA.EyeDNA.Color":["brown","hazel","amber","green","gray","blue"],
            "PaDNA.EyeDNA.Shape":["round","almond","upturned","downturned","monolid","hooded"],
            "PaDNA.EyeDNA.Lid":["single","double","hooded","none"],
            "PaDNA.EyeDNA.Lashes.Length":["short","medium","long"],
            "PaDNA.BrowDNA.Shape":["straight","arched","rounded","angled","unknown"],
            "PaDNA.BrowDNA.Density":["sparse","medium","full","unknown"],
            "PaDNA.FaceDNA.Shape":["oval","heart","round","square","diamond","oblong"],
            "PaDNA.FaceDNA.Cheekbones":["prominent","soft","neutral"],
            "PaDNA.FaceDNA.Freckles":["present","none","faint"],
            "PaDNA.SkinDNA.Tone":["very-light","light","light-medium","medium","medium-deep","deep"],
            "PaDNA.SkinDNA.Undertone":["cool","warm","neutral","olive"],
            "PaDNA.SkinDNA.Clarity":["clear","freckles","moles","blemishes","unknown"],
            "PaDNA.LipDNA.Fullness":["thin","medium","full","very-full"],
            "PaDNA.LipDNA.Coloration":["natural","bold","glossy","matte"],
            "PaDNA.GlassesDNA":["none","occasional","regular","sunglasses"],
            "PaDNA.DistinguishingMarksDNA.Freckles":["present","none","faint"],
            "PaDNA.DistinguishingMarksDNA.Moles":["visible","none","faint"],
            "PaDNA.DistinguishingMarksDNA.Tattoos":["none","present"],
            "PaDNA.DistinguishingMarksDNA.Tattoos.Location":["arm","wrist","ankle","shoulder","back","leg","chest","other"],
            "PaDNA.DistinguishingMarksDNA.Piercings":["none","earlobes","multiple","nose","lip","other"],
            "PaDNA.Accessories.Earrings":["none","studs","hoops","statement","multiple"],
            "PaDNA.Accessories.Necklace":["present","none"],
            "PaDNA.Accessories.Bracelet":["present","none"],
            "PaDNA.Accessories.Watch":["present","none"],
            "PaDNA.FacialHairDNA.Style":["none","stubble","short-beard","full-beard","mustache","goatee"],
            "PaDNA.FaceDNA.Smile":["neutral","closed-smile","open-smile","smirk"],
            "PaDNA.FaceDNA.TeethVisibility":["none","partial","full"],
            "PaDNA.PostureDNA.HeadTilt":["left","right","neutral"],
            "PaDNA.PostureDNA.BodyLean":["forward","back","neutral"],
            "PaDNA.ApparelDNA.Top.Color":["white","black","gray","blue","green","red","pink","orange","yellow","brown","multicolor","unknown"],
            "PaDNA.ApparelDNA.Top.Style":["tank","tee","blouse","button","sweater","hoodie","dress","jacket","strapless"],
            "PaDNA.ApparelDNA.Top.Pattern":["solid","striped","plaid","floral","graphic","textured","lace","animal"],
            "PaDNA.ApparelDNA.Bottom.Visible":["present","not-visible"],
            "PaDNA.ApparelDNA.Accessories":["belt","scarf","hat","tie","none"],
            "PaDNA.ApparelDNA.Palette":["cool","warm","neutral","monochrome","warm-metallic","cool-metallic"],
            "PaDNA.ApparelDNA.Fit":["relaxed","regular","tailored","fitted"],
            "PaDNA.ApparelDNA.Style":["casual","classic","formal","athletic","boho","glam","street","business"],
        }
        example_payload = {
            "traits": {
                "PaDNA.HairDNA.Color": "red",
                "PaDNA.SkinDNA.Tone": "light-medium",
                "PaDNA.GlassesDNA": False
            },
            "confidence": {
                "PaDNA.HairDNA.Color": 0.86,
                "PaDNA.SkinDNA.Tone": 0.71,
                "PaDNA.GlassesDNA": 0.95
            },
            "evidence": {
                "PaDNA.HairDNA.Color": ["hair appears copper red under indoor lighting"],
                "PaDNA.SkinDNA.Tone": ["complexion between light and medium"],
                "PaDNA.GlassesDNA": ["no eyewear visible"]
            }
        }
        instruction = (
            "You are the PaDNA vision inspector. Analyse ONLY the provided image and respond with JSON that adheres to the schema below. "
            "Every trait must map to a single canonical token from the allowed enums. If you are unsure, omit the trait. "
            "Confidence must be a float between 0 and 1. Evidence is a list of short literal phrases describing what you see.\n\n"
            "Schema example (do not copy values, just follow the structure):\n"
            + json.dumps(example_payload, indent=2)
            + "\n\nRespond with JSON only — no markdown, prose, or extra keys."
            + " Traits must use the exact enum values.\n\nAllowed enums:\n"
            + json.dumps(enums)
        )
        url = f"{self.host}/api/chat"
        payload = {
            "model": self.model,
            "messages": [{"role":"user","content":instruction,"images":[image_b64]}],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.0},
        }
        r = requests.post(url, json=payload, timeout=self.timeout)
        r.raise_for_status()
        content = r.json().get("message", {}).get("content","").strip()
        try:
            return json.loads(content)
        except Exception:
            start, end = content.find("{"), content.rfind("}")
            if start != -1 and end != -1:
                snippet = content[start : end + 1]
                try:
                    return json.loads(snippet)
                except Exception:
                    pass
            raise ValueError(f"Model did not return JSON content: {content[:200]}...")

    def analyze(self, image_bytes: bytes, recency: RecencyTag) -> VisionObservation:
        # Preprocess image (downscale & JPEG)
        jpeg, hsh = _prep_image(image_bytes)
        image_b64 = base64.b64encode(jpeg).decode("utf-8")
        image_id  = hsh[:10]

        try:
            self._check_model()
            raw = self._chat(image_b64)
            tokens: Dict[str, Dict[str, Any]] = {}

            trait_block = raw.get("traits") if isinstance(raw, dict) else None
            confidence_block = raw.get("confidence") if isinstance(raw, dict) else {}
            evidence_block = raw.get("evidence") if isinstance(raw, dict) else {}

            if isinstance(trait_block, dict) and trait_block:
                for path, value in trait_block.items():
                    if value in (None, "", "Unknown"):
                        continue
                    conf = float(confidence_block.get(path, 0.6) or 0.6)
                    evidence = evidence_block.get(path) or []
                    tokens[path] = {
                        "value": value,
                        "confidence": conf,
                        "details": {"evidence": evidence},
                    }

            if not tokens:
                raise ValueError("Empty token set from model.")
            return VisionObservation(image_id, recency, self.name, f"{self.version}:{self.model}", tokens)
        except Exception as e:
            # Surface a gentle notice by embedding a debug token; pipeline keeps running.
            tokens = {
                "PaDNA.Debug.ModelFallback": {
                    "value": f"fallback: {type(e).__name__}",
                    "confidence": 0.2,
                    "details": {"error": str(e)}
                }
            }
            return VisionObservation(image_id, recency, f"{self.name}-fallback", f"{self.version}:{self.model}", tokens)
