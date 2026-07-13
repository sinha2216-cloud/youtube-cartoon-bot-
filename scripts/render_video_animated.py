"""
render_video_animated.py
Combines Kaggle AI-animated MP4 clips + voiceover audio into a final MP4,
loops the animation to match audio length, adds background music safely,
and burns-in PIL subtitles.
Output: output/final_video.mp4
"""

import os
import json
import sys
from PIL import Image, ImageDraw, ImageFont

# Compatibility shim for newer Pillow versions
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    CompositeVideoClip,
    CompositeAudioClip,
    concatenate_videoclips,
)
from moviepy.video.fx.all import loop
from moviepy.audio.fx.all import audio_loop

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
STORY_PATH = os.path.join(BASE_DIR, "output", "story.json")
IMAGES_DIR = os.path.join(BASE_DIR, "output", "images")  # Contains Kaggle mp4s too
AUDIO_DIR = os.path.join(BASE_DIR, "output", "audio")
MUSIC_PATH = os.path.join(BASE_DIR, "assets", "background_music.mp3")
OUTPUT_PATH = os.path.join(BASE_DIR, "output", "final_video.mp4")

# Default to Vertical (Shorts/Reels)
ORIENTATION = os.environ.get("VIDEO_ORIENTATION", "vertical")
if ORIENTATION == "vertical":
    W, H = 1080, 1920
else:
    W, H = 1920, 1080

FPS = 30
MUSIC_VOLUME = 0.08

def process_animated_clip(video_path: str, target_duration: float):
    """Loads Kaggle AI video, loops it to match narration duration, and fits WxH."""
    clip = VideoFileClip(video_path)
    
    # Loop the short SVD video if narration is longer, else trim it
    if clip.duration < target_duration:
        clip = loop(clip, duration=target_duration)
    else:
        clip = clip.subclip(0, target_duration)
        
    # Smart Aspect Ratio Cover (Crop & Resize to fit WxH seamlessly)
    scale = max(W / clip.w, H / clip.h)
    clip = clip.resize(scale)
    
    # Center crop into the destination resolution
    composite = CompositeVideoClip([clip.set_position(("center", "center"))], size=(W, H))
    return composite.set_duration(target_duration)

def _wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width or not current:
            current = test
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines

def make_subtitle_clip(text: str, duration: float):
    """Pure PIL burned-in subtitle generator (No ImageMagick dependency)."""
    font_size = int(H * 0.035)
    max_width = int(W * 0.85)

    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()

    # Create dummy to measure text wrap
    from PIL import ImageClip as PILImageClip
    import numpy as np
    
    dummy = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    lines = _wrap_text(dummy, text, font, max_width)

    line_height = int(font_size * 1.3)
    canvas_height = line_height * len(lines) + 20
    canvas = Image.new("RGBA", (W, canvas_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        line_width = bbox[2] - bbox[0]
        x = (W - line_width) // 2
        y = i * line_height + 10
        draw.text((x, y), line, font=font, fill="white", stroke_width=3, stroke_fill="black")

    frame = np.array(canvas)
    from moviepy.editor import ImageClip as MoviepyImageClip
    txt_clip = MoviepyImageClip(frame).set_duration(duration).set_position(("center", int(H * 0.75)))
    return txt_clip

def main():
    if not os.path.exists(STORY_PATH):
        print(f"❌ ERROR: {STORY_PATH} not found.", file=sys.stderr)
        sys.exit(1)

    with open(STORY_PATH, "r", encoding="utf-8") as f:
        story = json.load(f)

    scene_clips = []

    for i, scene in enumerate(story["scenes"]):
        # 🔄 FIX: Targeted the Kaggle generated MP4 instead of static PNG
        video_clip_path = os.path.join(IMAGES_DIR, f"scene_{i}.mp4")
        audio_path = os.path.join(AUDIO_DIR, f"scene_{i}.mp3")

        if not os.path.exists(video_clip_path) or not os.path.exists(audio_path):
            print(f"❌ ERROR: Missing AI assets for scene {i} ({video_clip_path} / {audio_path})", file=sys.stderr)
            sys.exit(1)

        narration_audio = AudioFileClip(audio_path)
        duration = narration_audio.duration + 0.3  # tight clean buffer

        # Process the real AI video animation clip
        visual = process_animated_clip(video_clip_path, duration)
        subtitle = make_subtitle_clip(scene["narration"], duration)

        scene_video = CompositeVideoClip([visual, subtitle], size=(W, H)).set_duration(duration)
        scene_video = scene_video.set_audio(narration_audio)
        scene_clips.append(scene_video)

    print("🎬 Stitching all AI animated scenes together...", flush=True)
    final_video = concatenate_videoclips(scene_clips, method="compose")

    # 🔄 FIX: Safe Background Music Audio Loop Mixing
    if os.path.exists(MUSIC_PATH):
        try:
            print("🎵 Mixing background music loop...", flush=True)
            music = AudioFileClip(MUSIC_PATH).volumex(MUSIC_VOLUME)
            music = audio_loop(music, duration=final_video.duration)
            mixed_audio = CompositeAudioClip([final_video.audio, music])
            final_video = final_video.set_audio(mixed_audio)
        except Exception as e:
            print(f"⚠️ WARNING: Could not mix background music: {e}")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    
    print(f"⚡ Rendering Final MP4 Video ({W}x{H}) with 4 Threads...", flush=True)
    final_video.write_videofile(
        OUTPUT_PATH,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="medium",
        logger=None # Suppress massive messy logs in GitHub actions
    )

    print(f"🎉 SUCCESS: Video rendered perfectly -> {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
