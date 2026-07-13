import os
import json
import sys
import time
import subprocess
import shutil

# Paths
STORY_JSON = os.path.join(os.path.dirname(__file__), "..", "output", "story.json")
KAGGLE_WORKSPACE = os.path.join(os.path.dirname(__file__), "..", "kaggle_run")
OUTPUT_IMAGES_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "images")

def main():
    print("🚀 INIT: Kaggle GPU Orchestrator (Version: P100 Stable - Strict Tracking)", flush=True)

    # 1. Setup Credentials
    username = os.environ.get("KAGGLE_USERNAME")
    key = os.environ.get("KAGGLE_KEY")
    
    if not username or not key:
        print("❌ FATAL: KAGGLE_USERNAME or KAGGLE_KEY missing in Secrets!", file=sys.stderr)
        sys.exit(1)

    home_dir = os.path.expanduser("~")
    os.makedirs(os.path.join(home_dir, ".kaggle"), exist_ok=True)
    with open(os.path.join(home_dir, ".kaggle", "kaggle.json"), "w") as f:
        json.dump({"username": username, "key": key}, f)
    os.chmod(os.path.join(home_dir, ".kaggle", "kaggle.json"), 0o600)

    # 2. Extract Prompts
    if not os.path.exists(STORY_JSON):
        print(f"❌ FATAL: story.json not found! Run generate_story.py first.", file=sys.stderr)
        sys.exit(1)

    with open(STORY_JSON, "r", encoding="utf-8") as f:
        story_data = json.load(f)

    prompts = [scene.get("image_prompt", "") for scene in story_data.get("scenes", [])]
    if not prompts:
        print("❌ FATAL: No prompts found in story.json!", file=sys.stderr)
        sys.exit(1)
        
    print(f"✅ Loaded {len(prompts)} prompts for Kaggle generation.", flush=True)

    # 3. Build Kaggle Core Script
    os.makedirs(KAGGLE_WORKSPACE, exist_ok=True)
    os.makedirs(OUTPUT_IMAGES_DIR, exist_ok=True)
    
    kaggle_script_content = f"""
import sys
import subprocess
import os

print("🛠️ Checking & Synchronizing Environment...", flush=True)
subprocess.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "torch==2.4.1", "torchvision==0.19.1", "torchaudio==2.4.1", "--index-url", "https://download.pytorch.org/whl/cu121"])
subprocess.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "diffusers", "transformers", "accelerate", "peft", "pillow"])
print("✅ Environment Synced!", flush=True)

import torch
import gc
from PIL import Image
from diffusers import AutoPipelineForText2Image, StableVideoDiffusionPipeline
from diffusers.utils import export_to_video
import json

prompts = {json.dumps(prompts, ensure_ascii=False)}

print(f"Total scenes to process: {{len(prompts)}}", flush=True)
generated_images = []

# PHASE 1: IMAGE GENERATION
print("Loading SDXL-Turbo...", flush=True)
image_pipe = AutoPipelineForText2Image.from_pretrained("stabilityai/sdxl-turbo", torch_dtype=torch.float16, variant="fp16")
image_pipe.to("cuda")

for i, prompt in enumerate(prompts):
    print(f"Generating Image {{i}}...", flush=True)
    img = image_pipe(prompt=prompt, num_inference_steps=2, guidance_scale=0.0).images[0]
    img = img.resize((1024, 576)) 
    img_path = f"scene_{{i}}.png"
    img.save(img_path)
    generated_images.append(img_path)

del image_pipe
gc.collect()
torch.cuda.empty_cache()

# PHASE 2: VIDEO ANIMATION
print("Loading SVD...", flush=True)
video_pipe = StableVideoDiffusionPipeline.from_pretrained("stabilityai/stable-video-diffusion-img2vid-xt", torch_dtype=torch.float16, variant="fp16")
video_pipe.to("cuda")
video_pipe.enable_model_cpu_offload() 

for i, img_path in enumerate(generated_images):
    print(f"Animating Scene {{i}}...", flush=True)
    img = Image.open(img_path)
    frames = video_pipe(img, decode_chunk_size=4, generator=torch.manual_seed(42)).frames[0]
    
    raw_vid = f"raw_scene_{{i}}.mp4"
    final_vid = f"scene_{{i}}.mp4"
    export_to_video(frames, raw_vid, fps=7)
    
    # Saturation Boost
    subprocess.run(["ffmpeg", "-y", "-i", raw_vid, "-vf", "eq=saturation=1.5:contrast=1.1", "-c:v", "libx264", "-crf", "18", final_vid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(raw_vid):
        os.remove(raw_vid)

print("✅ Kaggle Generation Complete!", flush=True)
"""
    with open(os.path.join(KAGGLE_WORKSPACE, "main.py"), "w", encoding="utf-8") as f:
        f.write(kaggle_script_content)

    # 4. Kernel Metadata
    unique_id = int(time.time())
    kernel_slug = f"kids-cartoon-auto-{unique_id}"
    metadata = {
        "id": f"{username}/{kernel_slug}",
        "title": f"Kids Cartoon Auto {unique_id}",
        "code_file": "main.py",
        "language": "python",
        "kernel_type": "script",
        "enable_gpu": True,
        "enable_internet": True
    }

    with open(os.path.join(KAGGLE_WORKSPACE, "kernel-metadata.json"), "w") as f:
        json.dump(metadata, f)

    # 5. Push to Kaggle
    print(f"📤 Pushing to Kaggle GPU (Slug: {kernel_slug})...", flush=True)
    subprocess.run(["kaggle", "kernels", "push", "-p", KAGGLE_WORKSPACE], check=True)

    # 6. Monitor (Strict & Verbose)
    kernel_id = f"{username}/{kernel_slug}"
    print("⏳ Waiting for Kaggle GPU...", flush=True)
    
    while True:
        status_res = subprocess.run(["kaggle", "kernels", "status", kernel_id], capture_output=True, text=True)
        raw_status = status_res.stdout.strip()
        print(f"📊 Kaggle Status Log: {raw_status}", flush=True)  # Live log for GitHub Actions
        
        status = raw_status.lower()
        
        # Strict checking for completion string
        if "has status \"complete\"" in status or status.endswith('"complete"'):
            print("🎉 Kaggle Run Completed Successfully!", flush=True)
            break
        elif "failed" in status or "error" in status or "has status \"error\"" in status:
            print(f"❌ FATAL: Kaggle GPU execution failed! Check your Kaggle dashboard.", file=sys.stderr)
            sys.exit(1)
            
        time.sleep(30)

    # 7. Pull Assets & Verify
    print(f"📥 Downloading assets to {OUTPUT_IMAGES_DIR}...", flush=True)
    subprocess.run(["kaggle", "kernels", "output", kernel_id, "-p", OUTPUT_IMAGES_DIR], check=True)
    
    # Check if files actually downloaded
    downloaded_files = os.listdir(OUTPUT_IMAGES_DIR)
    print(f"📁 Files downloaded in output/images: {downloaded_files}", flush=True)
    
    if not downloaded_files:
        print("❌ FATAL: Kaggle step marked success but NO files were downloaded!", file=sys.stderr)
        sys.exit(1)
        
    print("✅ Assets ready for Video Renderer.", flush=True)

if __name__ == "__main__":
    main()
