"""
main.py
Orchestrates the full pipeline in order:
1. Generate story  2. Generate audio  3. Generate images  4. Render video  5. Upload to YouTube

Run locally with:  python main.py
Runs automatically via GitHub Actions on schedule.
"""

import subprocess
import sys
import os

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "scripts")

STEPS = [
    ("Generating story...", "generate_story.py"),
    ("Generating audio...", "generate_audio.py"),
    ("Generating images...", "generate_images.py"),
    ("Animating scenes on Kaggle GPU (optional, safe no-op without secrets)...", "kaggle_animate.py"),
    ("Rendering video...", "render_video_animated.py"),
    ("Uploading to YouTube...", "upload_youtube.py"),
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

    print("\nPipeline completed successfully!")


if __name__ == "__main__":
    main()
