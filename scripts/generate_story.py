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

PROMPT_TEMPLATE = """You are a children's story writer for a YouTube Kids channel.

Write ONE short, original, wholesome moral story for children aged 3-8.
Requirements:
- Total narration length should be readable in about 90-150 seconds.
- Split the story into exactly {num_scenes} scenes.
- Each scene needs:
  1. "narration": the story text for that scene (simple words, warm tone, 2-4 sentences).
  2. "image_prompt": a short visual description (in English, comma separated keywords) of what
     should be drawn for this scene, in a colorful 2D cartoon / children's book illustration style.
     Keep character descriptions CONSISTENT across all scenes (same character names, colors, outfits).
- Include a "title" for the story (catchy, under 60 characters, good for a YouTube title).
- Include a short "description" (2-3 lines) suitable for a YouTube video description, and
  5-8 "tags" (comma separated keywords, no # symbol) relevant for YouTube kids content.

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
