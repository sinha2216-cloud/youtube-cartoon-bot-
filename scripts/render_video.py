"""
render_video.py
Combines images + audio into a final MP4 with a Ken Burns (slow zoom/pan) effect,
background music (optional), and burned-in subtitles.
Output: output/final_video.mp4
"""

import os
import json
import sys
import random
import numpy as np

# Compatibility shim: newer Pillow versions removed Image.ANTIALIAS,
# but moviepy 1.0.3 still references it internally.
from PIL import Image, ImageDraw, ImageFont
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

from moviepy.editor import (
    ImageClip,
    AudioFileClip,
    CompositeVideoClip,
    CompositeAudioClip,
    concatenate_videoclips,
)

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
STORY_PATH = os.path.join(BASE_DIR, "output", "story.json")
IMAGES_DIR = os.path.join(BASE_DIR, "output", "images")
AUDIO_DIR = os.path.join(BASE_DIR, "output", "audio")
MUSIC_PATH = os.path.join(BASE_DIR, "assets", "background_music.mp3")
OUTPUT_PATH = os.path.join(BASE_DIR, "output", "final_video.mp4")

# Vertical (Shorts) by default. Set VIDEO_ORIENTATION=landscape for 16:9.
ORIENTATION = os.environ.get("VIDEO_ORIENTATION", "vertical")
if ORIENTATION == "vertical":
    W, H = 1080, 1920
else:
    W, H = 1920, 1080

FPS = 30
MUSIC_VOLUME = 0.08  # keep music quiet under narration


def ken_burns_clip(image_path: str, duration: float, zoom_in: bool):
    """Apply a slow zoom (Ken Burns effect) to a still image, cropped/resized to fill W x H."""
    clip = ImageClip(image_path)

    # Resize so the image covers the full frame (cover, not contain)
    scale = max(W / clip.w, H / clip.h) * 1.15  # extra 15% for zoom headroom
    clip = clip.resize(scale)

    start_zoom, end_zoom = (1.0, 1.12) if zoom_in else (1.12, 1.0)

    def make_frame_size(t):
        progress = t / duration if duration > 0 else 0
        z = start_zoom + (end_zoom - start_zoom) * progress
        return z

    def resize_func(t):
        return make_frame_size(t)

    zoomed = clip.resize(resize_func).set_duration(duration)
    zoomed = zoomed.set_position(("center", "center"))

    # Center-crop each frame to exact WxH
    composite = CompositeVideoClip([zoomed], size=(W, H)).set_duration(duration)
    return composite


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
    """Burned-in subtitle drawn directly with PIL (no ImageMagick dependency,
    since GitHub Actions runners don't have it installed by default)."""
    font_size = int(H * 0.035)
    max_width = int(W * 0.85)

    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()

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
        draw.text((x, y), line, font=font, fill="white", stroke_width=2, stroke_fill="black")

    frame = np.array(canvas)
    txt_clip = ImageClip(frame).set_duration(duration).set_position(("center", int(H * 0.75)))
    return txt_clip


def main():
    if not os.path.exists(STORY_PATH):
        print(f"ERROR: {STORY_PATH} not found.", file=sys.stderr)
        sys.exit(1)

    with open(STORY_PATH, "r", encoding="utf-8") as f:
        story = json.load(f)

    scene_clips = []

    for i, scene in enumerate(story["scenes"]):
        img_path = os.path.join(IMAGES_DIR, f"scene_{i}.png")
        audio_path = os.path.join(AUDIO_DIR, f"scene_{i}.mp3")

        if not os.path.exists(img_path) or not os.path.exists(audio_path):
            print(f"ERROR: Missing asset for scene {i} ({img_path} / {audio_path})", file=sys.stderr)
            sys.exit(1)

        narration_audio = AudioFileClip(audio_path)
        duration = narration_audio.duration + 0.4  # small buffer

        visual = ken_burns_clip(img_path, duration, zoom_in=random.choice([True, False]))
        subtitle = make_subtitle_clip(scene["narration"], duration)

        scene_video = CompositeVideoClip([visual, subtitle], size=(W, H)).set_duration(duration)
        scene_video = scene_video.set_audio(narration_audio)
        scene_clips.append(scene_video)

    final_video = concatenate_videoclips(scene_clips, method="compose")

    # Optional background music, mixed quietly under narration
    if os.path.exists(MUSIC_PATH):
        try:
            music = AudioFileClip(MUSIC_PATH).volumex(MUSIC_VOLUME)
            loops_needed = int(final_video.duration // music.duration) + 1
            music = concatenate_videoclips([music] * loops_needed) if loops_needed > 1 else music
            music = music.set_duration(final_video.duration)
            mixed_audio = CompositeAudioClip([final_video.audio, music])
            final_video = final_video.set_audio(mixed_audio)
        except Exception as e:
            print(f"WARNING: could not mix background music: {e}")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    final_video.write_videofile(
        OUTPUT_PATH,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="medium",
    )

    print(f"Video rendered successfully -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
