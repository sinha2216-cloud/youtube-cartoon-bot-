# kaggle_animate.py
import os, json, sys, time, subprocess

# Paths
STORY_JSON = os.path.join(os.path.dirname(__file__), "..", "output", "story.json")
KAGGLE_WORKSPACE = os.path.join(os.path.dirname(__file__), "..", "kaggle_run")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")

def main():
    username = os.environ.get("KAGGLE_USERNAME")
    key = os.environ.get("KAGGLE_KEY")
    
    with open(STORY_JSON, "r", encoding="utf-8") as f:
        story_data = json.load(f)
    prompts = [scene["image_prompt"] for scene in story_data.get("scenes", [])]

    os.makedirs(KAGGLE_WORKSPACE, exist_ok=True)
    
    # Kaggle main.py script
    kaggle_script = f"""
import os, subprocess, sys
# Debug: List installed packages so we see version clashes
subprocess.run(['pip', 'list'], capture_output=True, text=True)

try:
    print("Attempting Install...")
    subprocess.run(['pip', 'install', '-q', 'diffusers==0.29.2', 'transformers==4.40.2', 'accelerate'], check=True)
    
    import torch
    print(f"CUDA Available: {{torch.cuda.is_available()}}")
    
    from diffusers import AutoPipelineForText2Image
    print("Diffusers Imported successfully")
    
except Exception as e:
    print(f"CRITICAL ERROR: {{e}}")
    sys.exit(1)
"""

    with open(os.path.join(KAGGLE_WORKSPACE, "main.py"), "w", encoding="utf-8") as f:
        f.write(kaggle_script)

    # Push to Kaggle
    subprocess.run(["kaggle", "kernels", "push", "-p", KAGGLE_WORKSPACE], check=True)
    
    kernel_id = f"{username}/kids-cartoon-automation-hd"
    
    # Wait for result
    for i in range(10): # Max 10 checks
        time.sleep(30)
        res = subprocess.run(["kaggle", "kernels", "status", kernel_id], capture_output=True, text=True)
        print(f"Status: {res.stdout.strip()}")
        if "complete" in res.stdout.lower(): break
        if "error" in res.stdout.lower():
            # FETCH LOGS ON ERROR
            print("--- KAGGLE LOGS DUMP ---")
            log_res = subprocess.run(["kaggle", "kernels", "output", kernel_id, "-p", OUTPUT_DIR], capture_output=True, text=True)
            print(log_res.stdout)
            print(log_res.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()    
