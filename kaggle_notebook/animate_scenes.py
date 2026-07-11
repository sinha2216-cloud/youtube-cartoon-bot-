"""
kaggle_notebook/animate_scenes.py
Runs INSIDE a Kaggle Notebook (GPU-enabled, internet-enabled) -- this file
does NOT run in GitHub Actions directly. It gets pushed to Kaggle and
triggered remotely by scripts/kaggle_animate.py via the official Kaggle API.

What it does:
  - Reads scene_*.png from the attached Kaggle Dataset
    (mounted read-only at /kaggle/input/<dataset-slug>/)
  - Runs each image through Stable Video Diffusion (open-weights, free,
    via Hugging Face's diffusers library -- same ecosystem as the rest of
    the pipeline, just running on Kaggle's GPU instead of a serverless
    endpoint)
  - Writes short animated clips to /kaggle/working/, which
    scripts/kaggle_animate.py then downloads via `kaggle kernels output`

One scene failing does NOT stop the others -- a missing output file for a
given scene just means the local pipeline falls back to Ken Burns for it.

Note on licensing: stable-video-diffusion-img2vid-xt is released under
Stability AI's Community License (free for individuals/small revenue).
Worth a quick check on stability.ai's license page if this channel starts
earning meaningfully.
"""

import glob
import os
import subprocess
import sys

# Kaggle's base image usually has torch preinstalled; pin diffusers/etc. explicitly
# since Kaggle's default versions drift and SVD needs a fairly recent diffusers.
subprocess.run(
    [
        sys.executable, "-m", "pip", "install", "-q",
        "diffusers==0.30.0", "accelerate==0.33.0",
        "imageio==2.34.2", "imageio-ffmpeg==0.5.1",
    ],
    check=True,
)

import torch  # noqa: E402
from diffusers import StableVideoDiffusionPipeline  # noqa: E402
from diffusers.utils import export_to_video, load_image  # noqa: E402
from PIL import Image  # noqa: E402

OUTPUT_DIR = "/kaggle/working"
NUM_FRAMES = 14
FPS = 7
# SVD-XT was trained at 1024x576. We keep that native size for quality and let
# the local MoviePy step (fit_clip_to_frame in render_video_animated.py)
# scale/crop into the final vertical or landscape canvas.
LANDSCAPE_SIZE = (1024, 576)
PORTRAIT_SIZE = (576, 1024)


def find_input_dir() -> str:
    candidates = glob.glob("/kaggle/input/*/")
    if not candidates:
        raise FileNotFoundError(
            "No dataset mounted under /kaggle/input/ -- check that "
            "kernel-metadata.json's dataset_sources points at the right dataset."
        )
    return candidates[0]


def target_size_for(image: Image.Image):
    return PORTRAIT_SIZE if image.height >= image.width else LANDSCAPE_SIZE


def main():
    input_dir = find_input_dir()
    print(f"Reading scene images from: {input_dir}")

    scene_paths = sorted(glob.glob(os.path.join(input_dir, "scene_*.png")))
    print(f"Found {len(scene_paths)} scene image(s).")
    if not scene_paths:
        print("Nothing to animate -- exiting cleanly.")
        return

    print("Loading Stable Video Diffusion (this takes a minute on first run)...")
    pipe = StableVideoDiffusionPipeline.from_pretrained(
        "stabilityai/stable-video-diffusion-img2vid-xt",
        torch_dtype=torch.float16,
        variant="fp16",
    )
    pipe.enable_model_cpu_offload()

    for path in scene_paths:
        scene_name = os.path.splitext(os.path.basename(path))[0]  # e.g. "scene_0"
        out_path = os.path.join(OUTPUT_DIR, f"{scene_name}_anim.mp4")
        try:
            print(f"Animating {scene_name}...")
            image = load_image(path)
            image = image.resize(target_size_for(image))

            frames = pipe(
                image,
                num_frames=NUM_FRAMES,
                decode_chunk_size=4,
                motion_bucket_id=60,     # lower = subtler motion; gentle for story scenes
                noise_aug_strength=0.02,
            ).frames[0]

            export_to_video(frames, out_path, fps=FPS)
            print(f"  -> saved {out_path}")
        except Exception as e:
            # Never let one bad scene kill the whole kernel run.
            print(f"  FAILED on {scene_name}: {e} -> skipping, local pipeline will fall back.")

    print("Kaggle animation pass complete.")


if __name__ == "__main__":
    main()
