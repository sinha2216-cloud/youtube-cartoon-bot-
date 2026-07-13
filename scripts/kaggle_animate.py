# kaggle_animate.py
# Orchestrates the Kaggle GPU execution from GitHub Actions.

import os
import json
import sys
import time
import subprocess
import shutil

# Paths
STORY_JSON = os.path.join(os.path.dirname(__file__), "..", "output", "story.json")
KAGGLE_WORKSPACE = os.path.join(os.path.dirname(__file__), "..", "kaggle_run")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")

def main():
    username = os.environ.get("KAGGLE_USERNAME")
    key = os.environ.get("KAGGLE_KEY")
    if not username or not key:
        sys.exit(1)

    with open(STORY_JSON, "r", encoding="utf-8") as f:
        story_data = json.load(f)
    prompts = [scene["image_prompt"] for scene in story_data.get("scenes", [])]

    os.makedirs(KAGGLE_WORKSPACE, exist_ok=True)
    
    # Kaggle main.py script
    kaggle_script = f"""
import os
os.system('pip install -q diffusers==0.29.2 transformers==4.40.2 accelerate==0.30.1')

import torch
from diffusers import AutoPipelineForText2Image, StableVideoDiffusionPipeline
from diffusers.utils import export_to_video
from PIL import Image

prompts = {json.dumps(prompts)}
os.makedirs("output_scenes", exist_ok=True)

# Image Gen
pipe = AutoPipelineForText2Image.from_pretrained("stabilityai/sdxl-turbo", torch_dtype=torch.float16).to("cuda")
for i, p in enumerate(prompts):
    img = pipe(p, num_inference_steps=2, guidance_scale=0.0).images[0].resize((1024, 576))
    img.save(f"output_scenes/image_{{i}}.png")
del pipe

# Video Gen
svd = StableVideoDiffusionPipeline.from_pretrained("stabilityai/stable-video-diffusion-img2vid-xt", torch_dtype=torch.float16).to("cuda")
for i in range(len(prompts)):
    img = Image.open(f"output_scenes/image_{{i}}.png")
    frames = svd(img, decode_chunk_size=2, generator=torch.manual_seed(42)).frames[0]
    export_to_video(frames, f"output_scenes/final_scene_{{i}}.mp4", fps=7)
"""

    with open(os.path.join(KAGGLE_WORKSPACE, "main.py"), "w") as f:
        f.write(kaggle_script)

    # Metadata
    with open(os.path.join(KAGGLE_WORKSPACE, "kernel-metadata.json"), "w") as f:
        json.dump({
            "id": f"{username}/kids-cartoon-automation-hd",
            "title": "Kids Cartoon Automation HD",
            "code_file": "main.py",
            "language": "python",
            "kernel_type": "script",
            "is_gpu": True,
            "enable_internet": True
        }, f)

    subprocess.run(["kaggle", "kernels", "push", "-p", KAGGLE_WORKSPACE], check=True)
    
    # Wait for completion
    kernel_id = f"{username}/kids-cartoon-automation-hd"
    while True:
        res = subprocess.run(["kaggle", "kernels", "status", kernel_id], capture_output=True, text=True)
        if "complete" in res.stdout.lower(): break
        if "error" in res.stdout.lower(): sys.exit(1)
        time.sleep(40)

    subprocess.run(["kaggle", "kernels", "output", kernel_id, "-p", OUTPUT_DIR], check=True)
    print("✅ Done.")

if __name__ == "__main__":
    main()
