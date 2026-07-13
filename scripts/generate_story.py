# generate_story.py
# Generates a short viral kids' moral story with 10 scenes using Google Gemini API.
# Output: output/story.json  ->  { "title": ..., "description": ..., "tags": [...], "scenes": [...] }

import os
import json
import re
import sys
import time
import google.generativeai as genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "output", "story.json")

# Fast pacing ke liye default ko 10 scenes kar diya hai
NUM_SCENES = int(os.environ.get("NUM_SCENES", "10"))

# Google keeps retiring / restricting Gemini models per-account (1.0, 1.5, 2.0 are
# dead; 2.5-flash is "no longer available to new users" on some keys). A model
# showing up in ListModels does NOT guarantee generateContent will actually work
# for this specific key. So: don't hardcode one model — build a ranked list of
# candidates and fall through to the next one the instant any model 404s.

# If you want to force a specific model, set GEMINI_MODEL env var — it will be
# tried first, but we still fall through to others if it fails.
MANUAL_OVERRIDE = os.environ.get("GEMINI_MODEL", "").strip()

# Static fallback order used only if ListModels itself fails (e.g. network issue).
STATIC_FALLBACK_ORDER = [
    "gemini-flash-latest",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-pro-latest",
    "gemini-2.5-pro",
    "gemini-1.5-flash",
]

# Known-dead or known-restricted model name fragments — deprioritize these even
# if ListModels still lists them, since they tend to 404 on many keys.
DEPRIORITIZE_HINTS = ["1.0", "vision", "tuning", "embedding", "aqa"]

PROMPT_TEMPLATE = """You are an expert viral YouTube Shorts creator specializing in 2D animated kids' moral stories.

Write ONE highly engaging, original short animal moral story for children.

Structure & Algorithm Optimization Requirements:
- Total narration length should be fast-paced and fit within Shorts timing.
- Split the story into EXACTLY {num_scenes} short scenes to maintain rapid visual pacing.
- Scene 1's narration MUST open with a massive surprise, high-energy question, or sound effect hook line in its very first sentence (e.g., "BOOM! What did the little bear just find?!").
- The FINAL scene's narration must end with a sentence that loops seamlessly back into scene 1's opening line/theme, so the video can loop infinitely without a visible hard restart (Retention Hack).
- The FINAL scene's narration must also end with a short, natural call-to-action to hit the Like button (e.g., "...and if you loved this adventure, tap that like button!").

Per-scene Image Prompt Requirements:
- "narration": The story text for that scene (1-2 simple, high-impact sentences for kids).
- "image_prompt": A highly descriptive comma-separated prompt for SDXL-Turbo image generation. 
  * Always include: "vibrant colors, highly saturated cartoon style, 2D Disney animation aesthetic, cute expressive eyes, bright studio lighting, detailed background".
  * Keep character outfits, fur colors, and traits strictly CONSISTENT across all scenes.
  * For SCENE 1 ONLY: Add a prominent mystery/curiosity visual element (e.g., a glowing locked chest, a giant golden floating key, a mysterious shining door) to act as a high-CTR automatic thumbnail.

Metadata requirements:
- "title": Highly catchy, curiosity-driven, emotional YouTube Shorts title (under 50 characters) with 1-2 relevant emojis. (e.g., The Magic Honey Secret! 🍯🐻).
- "description": 2-3 lines, SEO-optimized, naturally incorporating keywords from tags.
- "tags": 8-10 trending tags mixing broad ("kids cartoon", "moral stories", "shorts", "bedtime stories") and specific keywords.

Return ONLY valid JSON in exactly this shape:
{{
  "title": "string",
  "description": "string",
  "tags": ["tag1", "tag2"],
  "scenes": [
    {{"narration": "string", "image_prompt": "string"}}
  ]
}}
"""


def extract_json(text: str) -> dict:
    """Fallback parser in case text has markdown fences."""
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text.strip())
    text = re.sub(r"```$", "", text.strip())
    text = text.strip()
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        text = text[start:end + 1]
    return json.loads(text)


def _rank_key(name: str):
    """Lower rank = tried first. Prefer 'latest' aliases, then flash, then pro,
    deprioritize anything matching DEPRIORITIZE_HINTS."""
    lname = name.lower()
    if any(h in lname for h in DEPRIORITIZE_HINTS):
        return (9, name)
    if "latest" in lname and "flash" in lname:
        return (0, name)
    if "flash" in lname:
        return (1, name)
    if "latest" in lname:
        return (2, name)
    if "pro" in lname:
        return (3, name)
    return (5, name)


def get_model_candidates() -> list:
    """Return an ordered list of model names to try, manual override first."""
    candidates = []

    try:
        available = []
        for m in genai.list_models():
            methods = getattr(m, "supported_generation_methods", [])
            if "generateContent" in methods:
                available.append(m.name.replace("models/", ""))

        available = sorted(set(available), key=_rank_key)
        candidates.extend(available)
    except Exception as e:
        print(f"Warning: ListModels failed ({e}); using static fallback list.", file=sys.stderr)
        candidates.extend(STATIC_FALLBACK_ORDER)

    # Make sure the static fallbacks are present too, in case ListModels
    # returned an incomplete/odd list for this key.
    for name in STATIC_FALLBACK_ORDER:
        if name not in candidates:
            candidates.append(name)

    # Manual override always goes first.
    if MANUAL_OVERRIDE:
        candidates = [MANUAL_OVERRIDE] + [c for c in candidates if c != MANUAL_OVERRIDE]

    return candidates


def is_model_unavailable_error(err: Exception) -> bool:
    msg = str(err).lower()
    return (
        "404" in msg
        or "not found" in msg
        or "no longer available" in msg
        or "not supported" in msg
    )


def main():
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    genai.configure(api_key=GEMINI_API_KEY)

    prompt = PROMPT_TEMPLATE.format(num_scenes=NUM_SCENES)
    candidates = get_model_candidates()
    print(f"Model candidates to try, in order: {candidates}", file=sys.stderr)

    last_err = None
    tried_models = []

    for model_name in candidates:
        tried_models.append(model_name)
        print(f"\n--- Trying model: {model_name} ---", file=sys.stderr)

        try:
            model = genai.GenerativeModel(model_name)
        except Exception as e:
            print(f"Could not initialize model {model_name}: {e}", file=sys.stderr)
            last_err = e
            continue

        # Up to 2 quick retries per model (for transient errors), then move on.
        for attempt in range(2):
            try:
                response = model.generate_content(
                    prompt,
                    generation_config={"response_mime_type": "application/json"}
                )
                data = extract_json(response.text)

                if "scenes" not in data or not data["scenes"]:
                    raise ValueError("No scenes returned by model.")

                if len(data["scenes"]) != NUM_SCENES:
                    print(f"Warning: Model generated {len(data['scenes'])} scenes instead of {NUM_SCENES}.", file=sys.stderr)

                os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
                with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                print(f"✅ Viral Story generated successfully -> {OUTPUT_PATH}")
                print(f"Model used: {model_name}")
                print(f"Title: {data.get('title')}")
                print(f"Scenes Configured: {len(data['scenes'])}")
                return

            except Exception as e:
                last_err = e
                print(f"Model {model_name}, attempt {attempt + 1} failed: {e}", file=sys.stderr)

                if is_model_unavailable_error(e):
                    print(f"Model {model_name} seems unavailable for this API key. Moving to next candidate immediately.", file=sys.stderr)
                    break  # stop retrying this model, go to next candidate

                # Transient/non-availability error (rate limit, network, etc.) - brief wait then retry same model.
                wait_seconds = 15 * (attempt + 1)
                print(f"Waiting {wait_seconds}s before retrying same model...", file=sys.stderr)
                time.sleep(wait_seconds)

    print(f"\nERROR: Story generation failed. Tried models: {tried_models}", file=sys.stderr)
    print(f"Last error: {last_err}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
