# generate_story.py
# Generates a highly engaging, well-researched kids' moral story using Mistral API.
# Output: output/story.json  ->  { "title": ..., "description": ..., "tags": [...], "scenes": [...] }

import os
import json
import re
import sys
import time
# 🔄 FIX: Naye Mistral SDK ke mutabiq import path sahi kiya hai
from mistralai.client import Mistral

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "output", "story.json")

NUM_SCENES = int(os.environ.get("NUM_SCENES", "10"))

# UPGRADED VIRAL PROMPT: Focuses on well-researched themes, high retention, and fast pacing.
PROMPT_TEMPLATE = """You are an expert YouTube Shorts strategist and a master storyteller for children's content. 
Your goal is to write ONE highly engaging, well-researched, and original animal moral story that guarantees high viewer retention and instant engagement.

Research & Psychology Requirements:
- The theme must revolve around highly searched, parent-approved educational topics (e.g., emotional intelligence, sharing, overcoming fear, or problem-solving) disguised as a fun, fast-paced adventure.
- Total narration length must fit perfectly within a 45-60 second Short (fast-paced).
- Split the story into EXACTLY {num_scenes} short scenes to maintain rapid visual pacing.

Algorithmic Hooks & Loops:
- SCENE 1: The opening sentence MUST be a massive auditory/visual hook. Start with an urgent question, a shocking discovery, or a high-energy sound word (e.g., "WAIT! Why is the tiny fox glowing?!").
- FINAL SCENE: The ending sentence MUST loop seamlessly back into Scene 1's opening line so the video repeats infinitely without the viewer noticing a hard cut (The Infinite Retention Hack).
- FINAL SCENE CTA: Blend a very quick call-to-action seamlessly into the last sentence (e.g., "...and if you want more magical secrets, hit subscribe!").

Image Generation Prompts (SDXL-Turbo):
- "narration": The voiceover text (1-2 punchy sentences).
- "image_prompt": A highly detailed comma-separated visual prompt. 
  * ALWAYS include: "vibrant eye-catching colors, extremely saturated cartoon style, 2D modern Disney animation aesthetic, cute oversized expressive eyes, bright magical lighting, hyper-detailed background".
  * Keep character outfits, fur colors, and sizes strictly CONSISTENT.
  * For SCENE 1 ONLY: Include a prominent, highly clickable visual mystery (e.g., a glowing floating locked chest, a giant mysterious egg) to serve as a high-CTR auto-thumbnail.

Metadata Optimization:
- "title": A high-CTR, curiosity-driven title under 50 characters with 1-2 emojis. Must evoke emotion (e.g., The Secret of the Glowing Egg! 🦊✨).
- "description": SEO-optimized, engaging 2-3 lines including the moral lesson.
- "tags": 10 trending tags mixing broad ("kids animation", "moral stories", "shorts") and highly specific long-tail keywords.

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
    if not MISTRAL_API_KEY:
        print("ERROR: MISTRAL_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    # Initialize Mistral Client
    client = Mistral(api_key=MISTRAL_API_KEY)
    prompt = PROMPT_TEMPLATE.format(num_scenes=NUM_SCENES)
    
    model_name = "mistral-large-latest"
    print(f"--- Generating Viral Script using Mistral AI ({model_name}) ---", file=sys.stderr)

    last_err = None
    for attempt in range(3):
        try:
            # Enforce JSON output strictly
            response = client.chat.complete(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            data = extract_json(response.choices[0].message.content)

            if "scenes" not in data or not data["scenes"]:
                raise ValueError("No scenes returned by model.")

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
            wait_seconds = 10 * (attempt + 1)
            print(f"Waiting {wait_seconds}s before retrying...", file=sys.stderr)
            time.sleep(wait_seconds)

    print(f"\nERROR: Story generation failed after 3 attempts.", file=sys.stderr)
    print(f"Last error: {last_err}", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    main()
