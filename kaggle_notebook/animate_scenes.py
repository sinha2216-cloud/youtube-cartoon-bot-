# kaggle_animate.py
# Orchestrates the Kaggle GPU execution from GitHub Actions.
# Extracts prompts from story.json, pushes them to Kaggle GPU, and pulls back animated clips + images.

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
    # 1. Kaggle Authentication Setup
    username = os.environ.get("KAGGLE_USERNAME")
    key = os.environ.get("KAGGLE_KEY")
    
    if not username or not key:
        print("ERROR: KAGGLE_USERNAME or KAGGLE_KEY environment variables not set. Cannot use Kaggle GPU.")
        sys.exit(1)

    home_dir = os.path.expanduser("~")
    os.makedirs(os.path.join(home_dir, ".kaggle"), exist_ok=True)
    with open(os.path.join(home_dir, ".kaggle", "kaggle.json"), "w") as f:
        json.dump({"username": username, "key": key}, f)
    os.chmod(os.path.join(home_dir, ".kaggle", "kaggle.json"), 0o600)

    # 2. Extract Prompts from Mistral Story
    if not os.path.exists(STORY_JSON):
        print(f"ERROR: story.json not found at {STORY_JSON}. Run generate_story.py first.")
        sys.exit(1)

    print("Reading viral prompts from story.json...")
    with open(STORY_JSON, "r", encoding="utf-8") as f:
        story_data = json.load(f)

    prompts = [scene["image_prompt"] for scene in story_data.get("scenes", [])]
    print(f"🚀 Successfully extracted {len(prompts)} prompts for Kaggle GPU Processing.")

    # 3. Build Kaggle Core Script dynamically with hardcoded prompts
    os.makedirs(KAGGLE_WORKSPACE, exist_ok=True)
    
    kaggle_script_content = f"""
import torch
import gc
import os
import subprocess
from PIL import Image

# Force update diffusers for seamless SVD execution
subprocess.run(["pip", "install", "-q", "--upgrade", "diffusers", "transformers", "accelerate"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

from diffusers import AutoPipelineForText2Image, StableVideoDiffusionPipeline
from diffusers.utils import export_to_video

prompts = {json.dumps(prompts, ensure_ascii=False)}

print(f"Total scenes to generate: {{len(prompts)}}")
os.makedirs("output_scenes", exist_ok=True)
generated_images = []

# PHASE 1: IMAGE GENERATION
print("Loading SDXL-Turbo for Image Generation...")
image_pipe = AutoPipelineForText2Image.from_pretrained(
    "stabilityai/sdxl-turbo", 
    torch_dtype=torch.float16, 
    variant="fp16"
)
image_pipe.to("cuda")

for i, prompt in enumerate(prompts):
    print(f"Generating Image {{i+1}}...")
    img = image_pipe(prompt=prompt, num_inference_steps=2, guidance_scale=0.0).images[0]
    img = img.resize((1024, 576)) 
    img_path = f"output_scenes/image_{{i}}.png"
    img.save(img_path)
    generated_images.append(img_path)

print("Flushing Image Model from Memory...")
del image_pipe
gc.collect()
torch.cuda.empty_cache()

# PHASE 2: VIDEO ANIMATION
print("Loading SVD for Animation...")
video_pipe = StableVideoDiffusionPipeline.from_pretrained(
    "stabilityai/stable-video-diffusion-img2vid-xt", 
    torch_dtype=torch.float16, 
    variant="fp16"
)
video_pipe.to("cuda")
video_pipe.enable_model_cpu_offload() 

for i, img_path in enumerate(generated_images):
    print(f"Animating Scene {{i+1}}...")
    img = Image.open(img_path)
    frames = video_pipe(img, decode_chunk_size=4, generator=torch.manual_seed(42)).frames[0]
    
    raw_vid = f"output_scenes/raw_scene_{{i}}.mp4"
    export_to_video(frames, raw_vid, fps=7)
    
    # PHASE 3: SATURATION BOOST
    print(f"Applying Saturation Boost to Scene {{i+1}}...")
    final_vid = f"output_scenes/final_scene_{{i}}.mp4"
    
    cmd = [
        "ffmpeg", "-y", "-i", raw_vid, 
        "-vf", "eq=saturation=1.5:contrast=1.1", 
        "-c:v", "libx264", "-crf", "18", final_vid
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(raw_vid):
        os.remove(raw_vid)

print("✅ Kaggle Processing Completed Successfully!")
"""

    with open(os.path.join(KAGGLE_WORKSPACE, "main.py"), "w", encoding="utf-8") as f:
        f.write(kaggle_script_content)

    # 4. Set Static Kaggle Metadata
    kernel_slug = "kids-cartoon-automation-hd"
    metadata = {
        "id": f"{username}/{kernel_slug}",
        "title": "Kids Cartoon Automation HD",
        "code_file": "main.py",
        "language": "python",
        "kernel_type": "script",
        "is_gpu": True,
        "enable_internet": True,
        "dataset_slugs": [],
        "container_slug": None,
        "competition_slugs": [],
        "kernel_slugs": []
    }

    with open(os.path.join(KAGGLE_WORKSPACE, "kernel-metadata.json"), "w") as f:
        json.dump(metadata, f)

    # 5. Push to Kaggle
    print("Pushing script payload to Kaggle GPU Cluster...")
    subprocess.run(["kaggle", "kernels", "push", "-p", KAGGLE_WORKSPACE], check=True)

    # 6. Monitor execution
    kernel_id = f"{username}/{kernel_slug}"
    print(f"Monitoring Kaggle Kernel: {kernel_id}")
    
    while True:
        status_res = subprocess.run(["kaggle", "kernels", "status", kernel_id], capture_output=True, text=True)
        status = status_res.stdout.lower()
        print(f"Current Kaggle Status -> {status_res.stdout.strip()}")
        
        if "complete" in status:
            print("🎉 Kaggle successfully generated all assets!")
            break
        elif "error" in status or "failed" in status:
            print("❌ Kaggle workflow failed with an internal GPU error.")
            sys.exit(1)
            
        time.sleep(30)

    # 7. Pull and Normalize Assets for Video Renderer
    print("Downloading processed assets back to GitHub local runner...")
    subprocess.run(["kaggle", "kernels", "output", kernel_id, "-p", OUTPUT_DIR], check=True)

    # Map down everything into output/images so render_video_animated.py gets everything it wants
    kaggle_out_dir = os.path.join(OUTPUT_DIR, "output_scenes")
    target_images_dir = os.path.join(OUTPUT_DIR, "images")
    os.makedirs(target_images_dir, exist_ok=True)

    if os.path.exists(kaggle_out_dir):
        for file_name in os.listdir(kaggle_out_dir):
            src_path = os.path.join(kaggle_out_dir, file_name)
            
            # Map Images (image_0.png -> scene_0.png)
            if file_name.startswith("image_") and file_name.endswith(".png"):
                idx = file_name.split("_")[-1].split(".")[0]
                shutil.copy(src_path, os.path.join(target_images_dir, f"scene_{idx}.png"))
            
            # Map Videos (final_scene_0.mp4 -> scene_0.mp4)
            elif file_name.startswith("final_scene_") and file_name.endswith(".mp4"):
                idx = file_name.split("_")[-1].split(".")[0]
                shutil.copy(src_path, os.path.join(target_images_dir, f"scene_{idx}.mp4"))
                shutil.copy(src_path, os.path.join(OUTPUT_DIR, f"scene_{idx}.mp4"))
                
        print("✅ Assets mapped and structured perfectly for rendering!")
    else:
        print("ERROR: Kaggle outputs not found in the expected directory structure.")
        sys.exit(1)

if __name__ == "__main__":
    main()
