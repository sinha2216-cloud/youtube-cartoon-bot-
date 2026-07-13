# main.py
# Orchestrates the full viral pipeline in order:
# 1. Generate story (Gemini JSON)  2. Generate audio  3. Generate Images + Animation (Kaggle GPU)  4. Render video  5. Upload to YouTube
# Run locally with:  python main.py

import subprocess
import sys
import os

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "scripts")

# UPDATED STEPS: 'generate_images.py' ko bypass karke direct Kaggle ko handle kiya hai
STEPS = [
    ("Generating viral story structure...", "generate_story.py"),
    ("Generating audio/voiceover...", "generate_audio.py"),
    # Kaggle script now automatically generates 10 Images (SDXL-Turbo) + Animates them (SVD)
    ("Generating Images & Animating scenes on Kaggle GPU...", "kaggle_animate.py"),
    ("Rendering final video with subtitles...", "render_video_animated.py"),
    ("Uploading viral content to YouTube...", "upload_youtube.py"),
]


def run_step(label: str, script: str):
    print(f"\n{'=' * 60}\n{label}\n{'=' * 60}")
    script_path = os.path.join(SCRIPTS_DIR, script)
    result = subprocess.run([sys.executable, script_path])
    if result.returncode != 0:
        print(f"\nFATAL: {script} failed with exit code {result.returncode}. Stopping pipeline.")
        sys.exit(result.returncode)


def main():
    skip_upload = os.environ.get("SKIP_UPLOAD", "false").lower() == "true"

    for label, script in STEPS:
        if script == "upload_youtube.py" and skip_upload:
            print("\nSKIP_UPLOAD=true -> skipping YouTube upload step.")
            continue
        run_step(label, script)

    print("\nPipeline completed successfully! Video is live! 🚀")


if __name__ == "__main__":
    main()
