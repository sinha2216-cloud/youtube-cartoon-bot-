"""
scripts/kaggle_animate.py
OPTIONAL pipeline step: uploads this run's scene images (from output/images/)
to a Kaggle Dataset, triggers the pre-configured Kaggle Notebook (free GPU)
that runs kaggle_notebook/animate_scenes.py on them, waits for it to finish,
and pulls the resulting short animated clips back into
output/animated/scene_N_anim.mp4.

This step is designed to NEVER fail the pipeline:
  - Missing Kaggle credentials, network issues, quota exhausted, timeout,
    or the notebook erroring out all just print a warning and return.
  - render_video_animated.py checks output/animated/ first, then falls back
    to Ken Burns -- so any failure here just means a slightly-less-animated
    video, never a broken pipeline.

Required GitHub Secrets (only if you want this step to do anything --
otherwise it's a silent no-op and the rest of the pipeline is unaffected):
  KAGGLE_USERNAME
  KAGGLE_KEY

One-time setup:
  1. Free Kaggle account at kaggle.com. Verify your phone number under
     Settings -- this is required to enable GPU + internet on kernels.
  2. Settings -> API -> "Create New Token" -> downloads kaggle.json.
     Take the "username" and "key" values from it.
  3. Add them as GitHub Secrets: KAGGLE_USERNAME, KAGGLE_KEY.
  4. That's it -- the dataset and kernel are auto-created on first push,
     no manual Kaggle-side setup needed.

Test locally:
  export KAGGLE_USERNAME=your_username
  export KAGGLE_KEY=your_key
  python scripts/kaggle_animate.py
  ls output/animated/     # should contain scene_0_anim.mp4 etc. if it worked
"""

import json
import os
import shutil
import subprocess
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES_DIR = os.path.join(BASE_DIR, "output", "images")
ANIMATED_DIR = os.path.join(BASE_DIR, "output", "animated")
KERNEL_SRC_DIR = os.path.join(BASE_DIR, "kaggle_notebook")

DATASET_SLUG = "cartoon-bot-scenes"
KERNEL_SLUG = "cartoon-bot-animator"
MAX_WAIT_SEC = int(os.environ.get("KAGGLE_MAX_WAIT_SEC", "1500"))  # 25 min ceiling
POLL_EVERY_SEC = 20


def run(cmd):
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout.strip():
        print(result.stdout.strip())
    return result


def ensure_credentials():
    username = os.environ.get("KAGGLE_USERNAME")
    key = os.environ.get("KAGGLE_KEY")
    if not username or not key:
        print(
            "KAGGLE_USERNAME / KAGGLE_KEY not set -> skipping Kaggle animation step. "
            "(This is fine -- the pipeline will fall back to Ken Burns.)"
        )
        return None

    kaggle_dir = os.path.expanduser("~/.kaggle")
    os.makedirs(kaggle_dir, exist_ok=True)
    cred_path = os.path.join(kaggle_dir, "kaggle.json")
    with open(cred_path, "w") as f:
        json.dump({"username": username, "key": key}, f)
    os.chmod(cred_path, 0o600)
    return username


def upload_dataset(username: str) -> bool:
    staging = os.path.join(BASE_DIR, "_kaggle_dataset_staging")
    if os.path.exists(staging):
        shutil.rmtree(staging)
    os.makedirs(staging)

    if not os.path.isdir(IMAGES_DIR):
        print(f"No images directory found at {IMAGES_DIR} -> nothing to animate, skipping.")
        return False

    scene_images = sorted(f for f in os.listdir(IMAGES_DIR) if f.startswith("scene_") and f.endswith(".png"))
    if not scene_images:
        print("No scene_*.png found -> nothing to animate, skipping.")
        return False

    for f in scene_images:
        shutil.copy(os.path.join(IMAGES_DIR, f), os.path.join(staging, f))

    metadata = {
        "title": DATASET_SLUG,
        "id": f"{username}/{DATASET_SLUG}",
        "licenses": [{"name": "CC0-1.0"}],
    }
    with open(os.path.join(staging, "dataset-metadata.json"), "w") as f:
        json.dump(metadata, f)

    # Try to version an existing dataset first; if it doesn't exist yet, create it.
    result = run(["kaggle", "datasets", "version", "-p", staging, "-m", "pipeline update", "--dir-mode", "zip"])
    if result.returncode != 0:
        print("Version failed (likely first run) -> creating dataset...")
        result = run(["kaggle", "datasets", "create", "-p", staging, "--dir-mode", "zip"])
        if result.returncode != 0:
            print(f"Could not create/update Kaggle dataset:\n{result.stderr.strip()}")
            return False

    print(f"Uploaded {len(scene_images)} scene image(s) to Kaggle dataset '{username}/{DATASET_SLUG}'.")
    return True


def push_kernel(username: str) -> str:
    push_dir = os.path.join(BASE_DIR, "_kaggle_kernel_staging")
    if os.path.exists(push_dir):
        shutil.rmtree(push_dir)
    shutil.copytree(KERNEL_SRC_DIR, push_dir)

    kernel_id = f"{username}/{KERNEL_SLUG}"
    metadata = {
        "id": kernel_id,
        "title": KERNEL_SLUG,
        "code_file": "animate_scenes.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": True,
        "dataset_sources": [f"{username}/{DATASET_SLUG}"],
        "competition_sources": [],
        "kernel_sources": [],
    }
    with open(os.path.join(push_dir, "kernel-metadata.json"), "w") as f:
        json.dump(metadata, f)

    result = run(["kaggle", "kernels", "push", "-p", push_dir])
    if result.returncode != 0:
        print(f"Kernel push failed:\n{result.stderr.strip()}")
        return ""
    print(f"Kernel '{kernel_id}' pushed and running on Kaggle GPU.")
    return kernel_id


def wait_for_completion(kernel_id: str) -> bool:
    waited = 0
    while waited < MAX_WAIT_SEC:
        result = run(["kaggle", "kernels", "status", kernel_id])
        status_line = (result.stdout or result.stderr or "").strip().lower()
        if "complete" in status_line:
            return True
        if "error" in status_line or "cancel" in status_line:
            print("Kernel run failed or was cancelled on Kaggle's side.")
            return False
        time.sleep(POLL_EVERY_SEC)
        waited += POLL_EVERY_SEC
    print(f"Timed out after {MAX_WAIT_SEC}s waiting for Kaggle -> giving up for this run.")
    return False


def download_outputs(kernel_id: str):
    os.makedirs(ANIMATED_DIR, exist_ok=True)
    result = run(["kaggle", "kernels", "output", kernel_id, "-p", ANIMATED_DIR])
    if result.returncode != 0:
        print(f"Could not download outputs:\n{result.stderr.strip()}")
        return
    found = [f for f in os.listdir(ANIMATED_DIR) if f.endswith("_anim.mp4")]
    print(f"Downloaded {len(found)} animated clip(s): {found}")


def main():
    try:
        username = ensure_credentials()
        if not username:
            return

        if not upload_dataset(username):
            return

        kernel_id = push_kernel(username)
        if not kernel_id:
            return

        print("Waiting for Kaggle kernel to finish (free-tier GPU queue can take a few minutes)...")
        if wait_for_completion(kernel_id):
            download_outputs(kernel_id)
        else:
            print("Skipping download -> render step will fall back automatically.")

    except Exception as e:
        # Last-resort catch-all: this optional step must never break the pipeline.
        print(f"kaggle_animate.py hit an unexpected error, skipping this step entirely: {e}")


if __name__ == "__main__":
    main()
