import torch
import gc
import os
import json
import subprocess
from PIL import Image
from diffusers import AutoPipelineForText2Image, StableVideoDiffusionPipeline
from diffusers.utils import export_to_video

# 1. Inputs: Yeh prompts tumhare local system se aayenge
with open('input.json', 'r') as f:
    data = json.load(f)
prompts = data.get('prompts', [])

print(f"Total scenes to generate: {len(prompts)}")
os.makedirs("output_scenes", exist_ok=True)
generated_images = []

# ==========================================
# PHASE 1: IMAGE GENERATION (SDXL-Turbo - Free)
# ==========================================
print("Loading SDXL-Turbo for Image Generation...")
image_pipe = AutoPipelineForText2Image.from_pretrained(
    "stabilityai/sdxl-turbo", 
    torch_dtype=torch.float16, 
    variant="fp16"
)
image_pipe.to("cuda")

for i, prompt in enumerate(prompts):
    print(f"Generating Image {i+1}...")
    img = image_pipe(prompt=prompt, num_inference_steps=2, guidance_scale=0.0).images[0]
    img = img.resize((1024, 576)) 
    img_path = f"output_scenes/image_{i}.png"
    img.save(img_path)
    generated_images.append(img_path)

# 🛑 GPU Memory Khali karo taaki Animation model crash na ho
print("Flushing Image Model from Memory...")
del image_pipe
gc.collect()
torch.cuda.empty_cache()

# ==========================================
# PHASE 2: VIDEO ANIMATION (SVD)
# ==========================================
print("Loading SVD for Animation...")
video_pipe = StableVideoDiffusionPipeline.from_pretrained(
    "stabilityai/stable-video-diffusion-img2vid-xt", 
    torch_dtype=torch.float16, 
    variant="fp16"
)
video_pipe.to("cuda")
video_pipe.enable_model_cpu_offload() 

for i, img_path in enumerate(generated_images):
    print(f"Animating Scene {i+1}...")
    img = Image.open(img_path)
    frames = video_pipe(img, decode_chunk_size=4, generator=torch.manual_seed(42)).frames[0]
    
    raw_vid = f"output_scenes/raw_scene_{i}.mp4"
    export_to_video(frames, raw_vid, fps=7)
    
    # ==========================================
    # PHASE 3: VIRAL SATURATION HACK (Color Pop)
    # ==========================================
    print(f"Applying Saturation Boost to Scene {i+1}...")
    final_vid = f"output_scenes/final_scene_{i}.mp4"
    
    cmd = [
        "ffmpeg", "-y", "-i", raw_vid, 
        "-vf", "eq=saturation=1.5:contrast=1.1", 
        "-c:v", "libx264", "-crf", "18", final_vid
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.remove(raw_vid)

print("✅ All Scenes Generated, Animated, and Enhanced Successfully!")
