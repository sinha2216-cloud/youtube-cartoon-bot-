# kaggle_animate.py
import os, json, sys, time, subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KAGGLE_WORKSPACE = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "kaggle_run"))
OUTPUT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "output"))
STORY_JSON = os.path.join(OUTPUT_DIR, "story.json")

def main():
    username = os.environ.get("KAGGLE_USERNAME")
    key = os.environ.get("KAGGLE_KEY")
    if not username or not key:
        print("ERROR: KAGGLE_USERNAME or KAGGLE_KEY not set!")
        sys.exit(1)

    kernel_id = f"{username}/kids-cartoon-automation-hd"

    with open(STORY_JSON, "r", encoding="utf-8") as f:
        story_data = json.load(f)
    prompts = [scene["image_prompt"] for scene in story_data.get("scenes", [])]

    os.makedirs(KAGGLE_WORKSPACE, exist_ok=True)

    with open(os.path.join(KAGGLE_WORKSPACE, "main.py"), "w", encoding="utf-8") as f:
        f.write(f"""
import subprocess, os, json, sys

print("Installing PyTorch build compatible with older P100 GPUs (Pascal/sm_60)...")
subprocess.run([
    sys.executable, "-m", "pip", "install", "-q",
    "torch==2.5.0", "torchvision==0.20.0",
    "--index-url", "https://download.pytorch.org/whl/cu121"
], check=True)

subprocess.run([
    sys.executable, "-m", "pip", "install", "-q",
    "diffusers==0.29.2", "transformers==4.43.0", "accelerate", "peft"
], check=True)

import torch
print(f"CUDA Available: {{torch.cuda.is_available()}}")
print(f"Torch Version: {{torch.__version__}}")

from diffusers import AutoPipelineForText2Image, StableVideoDiffusionPipeline
from diffusers.utils import export_to_video
from PIL import Image

prompts = {json.dumps(prompts)}
os.makedirs("output_scenes", exist_ok=True)

# Cartoon-style suffix so SDXL-Turbo leans away from realistic/photographic output
STYLE_SUFFIX = ", flat 2D cartoon style, children's book illustration, vector art, clean bold outlines, vibrant colors, no photorealism"

# PORTRAIT size for vertical YouTube Shorts (was landscape before -- caused bad cropping)
TARGET_SIZE = (576, 1024)

pipe = AutoPipelineForText2Image.from_pretrained("stabilityai/sdxl-turbo", torch_dtype=torch.float16).to("cuda")
for i, p in enumerate(prompts):
    img = pipe(p + STYLE_SUFFIX, num_inference_steps=2, guidance_scale=0.0).images[0].resize(TARGET_SIZE)
    img.save(f"output_scenes/image_{{i}}.png")
del pipe
torch.cuda.empty_cache()

svd = StableVideoDiffusionPipeline.from_pretrained("stabilityai/stable-video-diffusion-img2vid-xt", torch_dtype=torch.float16).to("cuda")
for i in range(len(prompts)):
    img = Image.open(f"output_scenes/image_{{i}}.png")
    frames = svd(
        img,
        decode_chunk_size=2,
        num_inference_steps=15,        # was ~25 default -> ~40% faster per scene
        motion_bucket_id=130,          # was unset (defaults to subtle ~1-40) -> visibly more motion
        noise_aug_strength=0.03,
        generator=torch.manual_seed(42),
    ).frames[0]
    export_to_video(frames, f"output_scenes/final_scene_{{i}}.mp4", fps=7)
print("COMPLETED_SUCCESSFULLY")
""")

    with open(os.path.join(KAGGLE_WORKSPACE, "kernel-metadata.json"), "w") as f:
        json.dump({
            "id": kernel_id,
            "title": "Kids Cartoon Automation HD",
            "code_file": "main.py",
            "language": "python",
            "kernel_type": "script",
            "enable_gpu": True,
            "enable_internet": True
        }, f)

    print("Pushing to Kaggle...")
    subprocess.run(["kaggle", "kernels", "push", "-p", KAGGLE_WORKSPACE], check=True)

    print("Waiting for Kaggle to finish processing...")
    while True:
        time.sleep(60)
        result = subprocess.run(["kaggle", "kernels", "status", kernel_id], capture_output=True, text=True)
        status = result.stdout.lower()
        print(f"Current Status: {status.strip()}")

        if "complete" in status:
            break
        elif "error" in status or "failed" in status:
            print("Kaggle Kernel Failed! Fetching logs...")
            log_res = subprocess.run(["kaggle", "kernels", "output", kernel_id, "-p", OUTPUT_DIR], capture_output=True, text=True)
            print(log_res.stdout)
            sys.exit(1)

    print("Downloading assets...")
    subprocess.run(["kaggle", "kernels", "output", kernel_id, "-p", OUTPUT_DIR], check=True)

if __name__ == "__main__":
    main()
