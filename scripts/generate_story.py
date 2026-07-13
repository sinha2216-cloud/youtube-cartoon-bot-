"""
generate_story.py
Generates a short kids' moral story broken into scenes using Google Gemini API (free tier).
Output: output/story.json  ->  { "title": ..., "scenes": [ {"narration": ..., "image_prompt": ...}, ... ] }
"""

import os
import json
import re
import sys
import time
import google.generativeai as genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "output", "story.json")

NUM_SCENES = int(os.environ.get("NUM_SCENES", "5"))

PROMPT_TEMPLATE = """You are a children's story writer for a YouTube Kids Shorts channel.

Write ONE short, original, wholesome moral story for children aged 3-8.

Structure requirements:
- Total narration length should be readable in about 90-150 seconds.
- Split the story into exactly {num_scenes} scenes.
- Scene 1's narration MUST open with a high-energy, suspenseful hook line or
  question in its very first sentence (e.g. a surprising question or an
  exclamation that makes a viewer curious what happens next). Avoid slow,
  scene-setting openers.
- The FINAL scene's narration must end with a sentence that flows naturally
  back into scene 1's opening line/theme, so the video can loop seamlessly
  when it repeats (the viewer shouldn't notice a hard restart).
- The FINAL scene's narration must also end with a short, natural
  call-to-action encouraging the viewer to press the Like button (e.g.
  "...and if you liked this story, tap that like button!") -- blend it into
  the story's wrap-up tone, don't make it feel like an ad.

Per-scene requirements:
- "narration": the story text for that scene (simple words, warm tone, 2-4 sentences).
- "image_prompt": a short visual description (in English, comma separated keywords) of what
  should be drawn for this scene, in a colorful 2D cartoon / children's book illustration style.
  Keep character descriptions CONSISTENT across all scenes (same character names, colors, outfits).
  For SCENE 1 ONLY: the image_prompt must also include one small curiosity/mystery visual
  element (e.g. a glowing box, a mysterious closed door, a wrapped gift) so the very first
  frame of the video sparks curiosity when used as an auto-thumbnail.

Metadata requirements:
- "title": catchy, includes 1-2 relevant emojis, under 60 characters, good for a YouTube title.
- "description": 2-3 lines, SEO-friendly, naturally reusing 2-3 of the tags as keywords.
- "tags": 5-8 comma-separated keywords (no # symbol) mixing broad terms (e.g. "kids stories",
  "moral stories for kids", "bedtime stories") with specific ones from this story (character
  names, theme).

Return ONLY valid JSON, no markdown fences, no extra text, in exactly this shape:
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
    """Gemini sometimes wraps JSON in markdown fences - strip those before parsing."""
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text.strip())
    text = re.sub(r"```$", "", text.strip())
    text = text.strip()
    # Fallback: find first { ... last }
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        text = text[start:end + 1]
    return json.loads(text)


def main():
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-flash-lite-latest")

    prompt = PROMPT_TEMPLATE.format(num_scenes=NUM_SCENES)

    last_err = None
    for attempt in range(3):
        try:
            response = model.generate_content(prompt)
            data = extract_json(response.text)
            if "scenes" not in data or not data["scenes"]:
                raise ValueError("No scenes returned by model.")
            os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Story generated successfully -> {OUTPUT_PATH}")
            print(f"Title: {data.get('title')}")
            print(f"Scenes: {len(data['scenes'])}")
            return
        except Exception as e:
            last_err = e
            print(f"Attempt {attempt + 1} failed: {e}", file=sys.stderr)
            wait_seconds = 20 * (attempt + 1)  # 20s, then 40s, then 60s
            print(f"Waiting {wait_seconds}s before retrying (rate limit backoff)...", file=sys.stderr)
            time.sleep(wait_seconds)

    print(f"ERROR: Story generation failed after retries: {last_err}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
