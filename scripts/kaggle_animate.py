# kaggle_animate.py
import os, json, sys, time, subprocess

# Paths - Updated to use Absolute Path to avoid reference errors
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

    with open(STORY_JSON, "r", encoding="utf-8") as f:
        story_data = json.load(f)
    prompts = [scene["image_prompt"] for scene in story_data.get("scenes", [])]

    os.makedirs(KAGGLE_WORKSPACE, exist_ok=True)
    
    # 1. Write main.py
    with open(os.path.join(KAGGLE_WORKSPACE, "main.py"), "w", encoding="utf-8") as f:
        f.write(f"""
import subprocess, sys, os
subprocess.run(['pip', 'install', '-q', 'diffusers==0.29.2', 'transformers==4.40.2', 'accelerate'])
import torch, json
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
""")

    # 2. Write kernel-metadata.json
    metadata = {
        "id": f"{username}/kids-cartoon-automation-hd",
        "title": "Kids Cartoon Automation HD",
        "code_file": "main.py",
        "language": "python",
        "kernel_type": "script",
        "is_gpu": True,
        "enable_internet": True
    }
    with open(os.path.join(KAGGLE_WORKSPACE, "kernel-metadata.json"), "w") as f:
        json.dump(metadata, f)

    # 3. VERIFICATION CHECK (Crucial fix)
    print(f"DEBUG: Checking {KAGGLE_WORKSPACE} for files...")
    files = os.listdir(KAGGLE_WORKSPACE)
    print(f"Files found: {files}")
    if "kernel-metadata.json" not in files:
        print("CRITICAL ERROR: kernel-metadata.json NOT FOUND in workspace!")
        sys.exit(1)

    # 4. Push
    print("Pushing to Kaggle...")
    subprocess.run(["kaggle", "kernels", "push", "-p", KAGGLE_WORKSPACE], check=True)
    print("Push successful!")

if __name__ == "__main__":
    main()
