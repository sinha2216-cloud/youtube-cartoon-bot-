import os
import sys
import subprocess

def run_step(script_name, description):
    print(f"\n{'='*70}")
    print(f"🚀 {description}")
    print(f"{'='*70}", flush=True)
    
    script_path = os.path.join("scripts", script_name)
    if not os.path.exists(script_path):
        print(f"❌ ERROR: Script {script_path} not found! Check your folder structure.", file=sys.stderr)
        sys.exit(1)
        
    # Run the script and halt everything if it fails
    result = subprocess.run([sys.executable, script_path])
    if result.returncode != 0:
        print(f"❌ FATAL ERROR: {script_name} crashed with exit code {result.returncode}. Stopping pipeline.", file=sys.stderr)
        sys.exit(1)

def main():
    # 1. OUT OF THE BOX FIX: Create all required directories BEFORE doing anything!
    print("🛠️ Setting up workspace directories...", flush=True)
    os.makedirs("output", exist_ok=True)
    os.makedirs("output/audio", exist_ok=True)
    os.makedirs("output/images", exist_ok=True) 
    os.makedirs("kaggle_run", exist_ok=True)

    # 2. Run the full automation pipeline sequentially
    run_step("generate_story.py", "Step 1: Generating Viral Script (Mistral AI)...")
    run_step("generate_audio.py", "Step 2: Generating Voiceovers (Edge TTS)...")
    run_step("kaggle_animate.py", "Step 3: Generating & Animating on Kaggle GPU...")
    run_step("render_video_animated.py", "Step 4: Rendering Final Video with Subtitles...")
    
    # 🔄 FIX: Added the automated YouTube upload step right here
    run_step("upload_to_youtube.py", "Step 5: Uploading Final Video to YouTube...")
    
    print("\n🎉 BOOM! Full pipeline completed successfully! Video is live on YouTube!", flush=True)

if __name__ == "__main__":
    main()
