"""
generate_images.py
Generates one cartoon-style image per scene using Hugging Face Inference API.
Includes retry + model cold-start handling, since the free inference API can be slow/unreliable.
Output: output/images/scene_0.png, scene_1.png, ...
"""

import os
import json
import sys
import time
import requests

STORY_PATH = os.path.join(os.path.dirname(__file__), "..", "output", "story.json")
IMAGES_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "images")

HF_TOKEN = os.environ.get("HF_TOKEN")

# Fallback list of models in case the primary one is unavailable / rate-limited.
MODEL_CANDIDATES = [
    os.environ.get("HF_MODEL", "black-forest-labs/FLUX.1-schnell"),
    "stabilityai/stable-diffusion-2",
    "stabilityai/stable-diffusion-2-1",
]

STYLE_SUFFIX = (
    ", vibrant colors, 2D cartoon style, children's book illustration, "
    "clean line art, cute, high quality, no text, no watermark"
)

NEGATIVE_PROMPT = "scary, dark, violent, blurry, deformed, extra limbs, text, watermark, signature"


def query_hf(model: str, prompt: str, retries: int = 4, wait: int = 20) -> bytes:
    url = f"https://router.huggingface.co/hf-inference/models/{model}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": prompt, "options": {"wait_for_model": True}}
    if "stable-diffusion" in model:
        payload["parameters"] = {"negative_prompt": NEGATIVE_PROMPT}

    for attempt in range(retries):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"):
                return resp.content
            # Model loading - wait and retry
            if resp.status_code == 503:
                print(f"    model loading, waiting {wait}s...")
                time.sleep(wait)
                continue
            print(f"    HF error {resp.status_code}: {resp.text[:200]}")
        except requests.exceptions.RequestException as e:
            print(f"    request failed: {e}")
        time.sleep(wait)

    raise RuntimeError(f"Failed to generate image with model {model} after {retries} retries.")


def main():
    if not HF_TOKEN:
        print("ERROR: HF_TOKEN environment variable not set.", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(STORY_PATH):
        print(f"ERROR: {STORY_PATH} not found. Run generate_story.py first.", file=sys.stderr)
        sys.exit(1)

    with open(STORY_PATH, "r", encoding="utf-8") as f:
        story = json.load(f)

    os.makedirs(IMAGES_DIR, exist_ok=True)

    for i, scene in enumerate(story["scenes"]):
        prompt = scene["image_prompt"] + STYLE_SUFFIX
        out_path = os.path.join(IMAGES_DIR, f"scene_{i}.png")
        print(f"Generating image for scene {i}: {prompt[:80]}...")

        image_bytes = None
        last_err = None
        for model in MODEL_CANDIDATES:
            try:
                image_bytes = query_hf(model, prompt)
                print(f"  success using model: {model}")
                break
            except Exception as e:
                last_err = e
                print(f"  model {model} failed: {e}")

        if image_bytes is None:
            print(f"ERROR: All models failed for scene {i}: {last_err}", file=sys.stderr)
            sys.exit(1)

        with open(out_path, "wb") as f:
            f.write(image_bytes)
        print(f"  saved {out_path}")

    print("All images generated successfully.")


if __name__ == "__main__":
    main()
