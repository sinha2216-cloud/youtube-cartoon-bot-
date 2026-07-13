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


def main():
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    genai.configure(api_key=GEMINI_API_KEY)
    
    # Using the standard stable gemini-1.5-flash model for reliable structure matching
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = PROMPT_TEMPLATE.format(num_scenes=NUM_SCENES)

    last_err = None
    for attempt in range(3):
        try:
            # Force target JSON format via model configuration
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            data = extract_json(response.text)
            
            if "scenes" not in data or not data["scenes"]:
                raise ValueError("No scenes returned by model.")
            
            # Direct validation check to ensure it matched the requested scene length
            if len(data["scenes"]) != NUM_SCENES:
                print(f"Warning: Model generated {len(data['scenes'])} scenes instead of {NUM_SCENES}.", file=sys.stderr)

            os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            print(f"✅ Viral Story generated successfully -> {OUTPUT_PATH}")
            print(f"Title: {data.get('title')}")
            print(f"Scenes Configured: {len(data['scenes'])}")
            return
            
        except Exception as e:
            last_err = e
            print(f"Attempt {attempt + 1} failed: {e}", file=sys.stderr)
            wait_seconds = 20 * (attempt + 1)
            print(f"Waiting {wait_seconds}s before retrying...", file=sys.stderr)
            time.sleep(wait_seconds)

    print(f"ERROR: Story generation failed after retries: {last_err}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
