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
- "tags": 5-8 comma-separated
