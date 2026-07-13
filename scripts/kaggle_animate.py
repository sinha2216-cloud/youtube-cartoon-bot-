# kaggle_animate.py
import os, json, sys, time, subprocess

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KAGGLE_WORKSPACE = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "kaggle_run"))
OUTPUT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "output"))
STORY_JSON = os.path.join(OUTPUT_DIR, "story.json")

def main():
    username = os.environ.get("KAGGLE_USERNAME")
    key = os.environ.get("KAGGLE_KEY")
    kernel_id = f"{username}/kids-cartoon-automation-hd"
    
    with open(STORY_JSON, "r", encoding="utf-8") as f:
        story_data = json.load(f)
    prompts = [scene["image_prompt"] for scene in story_data.get("scenes", [])]

    os.makedirs(KAGGLE_WORKSPACE, exist_ok=True)
    
    # 1. Write main.py
    with open(os.path.join(KAGGLE_WORKSPACE, "main.py"), "w", encoding="utf-8") as f:
        f.write(f"""
import subprocess, os, json, torch
# FIXED: Updated transformers to 4.43.0 to support EncoderDecoderCache and satisfy peft
subprocess.run(['pip', 'install', '-q', 'diffusers==0.29.2', 'transformers==4.43.0', 'accelerate', 'peft'], check=True)

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
torch.cuda.empty_cache()

# Video Gen
svd = StableVideoDiffusionPipeline.from_pretrained("stabilityai/stable-video-diffusion-img2vid-xt", torch_dtype=torch.float16).to("cuda")
for i in range(len(prompts)):
    img = Image.open(f"output_scenes/image_{{i}}.png")
    frames = svd(img, decode_chunk_size=2, generator=torch.manual_seed(42)).frames[0]
    export_to_video(frames, f"output_scenes/final_scene_{{i}}.mp4", fps=7)
print("COMPLETED_SUCCESSFULLY")
""")

    # 2. Metadata
    with open(os.path.join(KAGGLE_WORKSPACE, "kernel-metadata.json"), "w") as f:
        json.dump({"id": kernel_id, "title": "Kids Cartoon Automation HD", "code_file": "main.py", "language": "python", "kernel_type": "script", "is_gpu": True, "enable_internet": True}, f)

    # 3. Push and WAIT
    print("Pushing to Kaggle...")
    subprocess.run(["kaggle", "kernels", "push", "-p", KAGGLE_WORKSPACE], check=True)

    print("Waiting for Kaggle to finish processing...")
    while True:
        time.sleep(60) 
        result = subprocess.run(["kaggle", "kernels", "status", kernel_id], capture_output=True, text=True)
        status = result.stdout.lower()
        print(f"Current Status: {status.strip()}")
        
        if "complete" in status:
            print("Kaggle Kernel Finished!")
            break
        elif "error" in status or "failed" in status:
            print("Kaggle Kernel Failed! Fetching logs...")
            # DUMP LOGS
            log_res = subprocess.run(["kaggle", "kernels", "output", kernel_id, "-p", OUTPUT_DIR], capture_output=True, text=True)
            print(log_res.stdout)
            sys.exit(1)

    # 4. Download
    print("Downloading assets...")
    subprocess.run(["kaggle", "kernels", "output", kernel_id, "-p", OUTPUT_DIR], check=True)
    print("Assets downloaded successfully.")

if __name__ == "__main__":
    main()
