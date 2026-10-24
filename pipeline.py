"""
pipeline.py  (Person 1)

compare_photos(before_path, after_path) -> list[dict]

Sends a move-in (BEFORE) photo and a move-out (AFTER) photo to Gemma 4 through
the Gemini API and returns a list of POSSIBLE differences. Each item looks like:

    {"description": "Dark scuff mark on wall left of door",
     "location":    "Left wall near door",
     "category":    "damage",      # damage | stain | missing_item | cleanliness | other
     "severity":    "minor",       # minor | moderate | major
     "confidence":  "high"}        # low | medium | high

Quick tests from the terminal:
    python pipeline.py --ping                      # check key + model work (text only)
    python pipeline.py before.jpg after.jpg        # compare one pair
    python pipeline.py before.jpg after.jpg --raw  # also print the raw model text
    python pipeline.py before.jpg after.jpg --no-cache
    python pipeline.py before.jpg after.jpg --sensitivity=5   # 1 (low) to 5 (high), default 3

Environment (.env file, never committed):
    GEMINI_API_KEY=your_key_here
    GEMMA_MODEL=gemma-4-31b-it        # optional; or gemma-4-26b-a4b-it
    USE_FAKE=1                        # optional; return fake data, no API call
"""
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageOps

load_dotenv()

MODEL = os.environ.get("GEMMA_MODEL", "gemma-4-31b-it")
PROMPT_VERSION = "v1"          # bump this when you change PROMPT so old cache is ignored
CACHE_DIR = Path("cache")
MAX_SIDE = int(os.environ.get("IMAGE_MAX_SIDE", "1280"))   # shrink big phone photos: faster, fewer errors

CATEGORIES = {"damage", "stain", "missing_item", "cleanliness", "other"}
SEVERITIES = {"minor", "moderate", "major"}
CONFIDENCES = {"low", "medium", "high"}

PROMPT = """You are helping a tenant document the condition of a rental unit.
You are given two photos of the same area. The FIRST image is the BEFORE photo
(move-in). The SECOND image is the AFTER photo (move-out).

List visible differences that could affect a security deposit, such as new
damage, stains, missing items, or cleanliness problems. Ignore differences
caused only by lighting, camera angle, shadows, or items that were simply moved,
unless they hide damage. Only report what you can clearly see. If you are not
sure, set confidence to "low". Do not guess about anything outside the photos.

Return ONLY valid JSON: a list of objects with keys description, location,
category (damage, stain, missing_item, cleanliness, other), severity (minor,
moderate, major), confidence (low, medium, high). If there are no meaningful
differences, return [].
"""

# Added to the prompt so the app's "AI Sensitivity" slider (1-5) really changes the model's behavior.
SENSITIVITY_TEXT = {
    1: "Sensitivity 1 of 5 (low): report only clear, significant problems. Ignore minor scuffs, small marks, and normal wear and tear.",
    2: "Sensitivity 2 of 5: report clear problems. Mention minor marks only if they are plainly visible.",
    3: "Sensitivity 3 of 5 (default): report clear differences, including minor ones you can see plainly.",
    4: "Sensitivity 4 of 5: also report small marks, scuffs, and light staining when you can see them.",
    5: "Sensitivity 5 of 5 (high): report even small or subtle differences you can see, marking uncertain ones with low confidence.",
}

FAKE_RESULT = [{
    "description": "Example: scuff mark on wall",
    "location": "Left wall",
    "category": "damage",
    "severity": "minor",
    "confidence": "high",
}]

LAST_RAW = ""   # the most recent raw model text, handy for debugging


class PipelineError(Exception):
    """Raised with a message that is safe to show to the user."""


# --------------------------------------------------------------------------- client
_client = None


def _get_client():
    global _client
    if _client is None:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise PipelineError("Missing GEMINI_API_KEY. Add it to your .env file.")
        from google import genai   # imported here so fake mode works without the package
        _client = genai.Client(api_key=key)
    return _client


def _friendly(e):
    code = getattr(e, "code", None)
    text = str(e)
    if code == 429:
        return "Rate limit reached. Wait a minute and try again."
    if code in (401, 403):
        return "The API key was rejected. Check GEMINI_API_KEY in your .env file."
    if code in (500, 503, 504):
        return ("The model service had a temporary error. Try again in a minute, or set "
                "GEMMA_MODEL=gemma-4-26b-a4b-it in .env, or use smaller photos.")
    if code == 404 or "not found" in text.lower():
        return f"Model '{MODEL}' was not found. Check the exact name in Google AI Studio."
    return "Model call failed: " + text[:300]


def _generate(contents):
    """One model call with a short retry on rate limits. Returns the response text."""
    try:
        from google.genai import types
    except ImportError as e:
        raise PipelineError("Package missing. Run: pip install google-genai") from e
    client = _get_client()
    for attempt in range(4):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=types.GenerateContentConfig(temperature=0),
            )
            return response.text or ""
        except Exception as e:                      # noqa: BLE001
            code = getattr(e, "code", None)
            if code in (429, 500, 503, 504) and attempt < 3:
                wait = 15 if code == 429 else 5 * (attempt + 1)   # temporary: wait, then retry
                print(f"(model busy, error {code}; retrying in {wait}s...)", file=sys.stderr)
                time.sleep(wait)
                continue
            raise PipelineError(_friendly(e)) from e
    return ""


# --------------------------------------------------------------------------- images
def _load_image(path):
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)     # phone photos are often stored rotated
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    return img


# --------------------------------------------------------------------------- parsing
def _extract_json(text):
    """Pull a JSON list out of the model text, even if it added fences or chatter."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.IGNORECASE).strip()
    try:
        data = json.loads(t)
    except json.JSONDecodeError:
        start, end = t.find("["), t.rfind("]")
        if start == -1 or end <= start:
            raise ValueError("no JSON list found in model output")
        data = json.loads(t[start:end + 1])
    if isinstance(data, dict):                       # e.g. {"differences": [...]}
        lists = [v for v in data.values() if isinstance(v, list)]
        if not lists:
            raise ValueError("JSON object had no list inside")
        data = lists[0]
    if not isinstance(data, list):
        raise ValueError("JSON was not a list")
    return data


def _normalize(items):
    """Keep only well-formed items and force the fields into the agreed values."""
    clean = []
    for it in items:
        if not isinstance(it, dict):
            continue
        desc = str(it.get("description", "")).strip()
        if not desc:
            continue
        category = str(it.get("category", "other")).strip().lower()
        severity = str(it.get("severity", "minor")).strip().lower()
        confidence = str(it.get("confidence", "low")).strip().lower()
        clean.append({
            "description": desc,
            "location": str(it.get("location", "")).strip(),
            "category": category if category in CATEGORIES else "other",
            "severity": severity if severity in SEVERITIES else "minor",
            "confidence": confidence if confidence in CONFIDENCES else "low",   # unsure -> low
        })
    return clean


# --------------------------------------------------------------------------- cache
def _cache_path(before_path, after_path, sensitivity=3):
    h = hashlib.sha256()
    for p in (before_path, after_path):
        h.update(Path(p).read_bytes())
    h.update(f"{MODEL}|{PROMPT_VERSION}|{sensitivity}".encode())
    return CACHE_DIR / f"{h.hexdigest()[:24]}.json"


# --------------------------------------------------------------------------- main function
def compare_photos(before_path, after_path, use_cache=True, sensitivity=3):
    """Return a list of possible differences between two photos (see module docstring).
    sensitivity: 1 (report only clear, significant problems) to 5 (report subtle ones too)."""
    global LAST_RAW

    if os.environ.get("USE_FAKE") == "1":
        return [dict(x) for x in FAKE_RESULT]

    try:
        sensitivity = min(5, max(1, int(sensitivity)))
    except (TypeError, ValueError):
        sensitivity = 3

    cache_file = _cache_path(before_path, after_path, sensitivity)
    if use_cache and cache_file.exists():
        return json.loads(cache_file.read_text())

    before, after = _load_image(before_path), _load_image(after_path)
    prompt = PROMPT + "\n" + SENSITIVITY_TEXT[sensitivity] + "\nNever report anything you cannot clearly see."

    items, last_error = None, None
    for _ in range(2):                                  # one retry if the JSON is bad
        LAST_RAW = _generate([before, after, prompt])
        try:
            items = _normalize(_extract_json(LAST_RAW))
            break
        except ValueError as e:
            last_error = e
    if items is None:
        raise PipelineError(f"The model's answer could not be read ({last_error}). Try again.")

    CACHE_DIR.mkdir(exist_ok=True)
    cache_file.write_text(json.dumps(items, indent=2))
    return items


# --------------------------------------------------------------------------- command line
if __name__ == "__main__":
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    try:
        if "--ping" in flags:
            print(f"Model: {MODEL}")
            print("Reply:", _generate(["Reply with the single word OK."]).strip())
        elif len(args) == 2:
            t0 = time.time()
            sens = 3
            for fl in flags:
                if fl.startswith("--sensitivity="):
                    sens = fl.split("=", 1)[1]
            result = compare_photos(args[0], args[1], use_cache="--no-cache" not in flags, sensitivity=sens)
            print(json.dumps(result, indent=2))
            print(f"\n{len(result)} possible difference(s) in {time.time() - t0:.1f}s using {MODEL}")
            if "--raw" in flags:
                print("\nRAW MODEL TEXT:\n" + LAST_RAW)
        else:
            print(__doc__)
            sys.exit(1)
    except PipelineError as e:
        print("ERROR:", e)
        if "--raw" in flags and LAST_RAW:
            print("\nRAW MODEL TEXT:\n" + LAST_RAW)
        sys.exit(1)
