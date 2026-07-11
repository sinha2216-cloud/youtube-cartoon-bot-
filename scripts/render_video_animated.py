"""
scripts/render_video_animated.py
Drop-in replacement for render_video.py. For each scene, tries a REAL
animated clip first, then falls back to the reliable Ken Burns effect:

  1. output/animated/scene_N_anim.mp4 -- produced by the optional Kaggle
     GPU step (kaggle_animate.py). Real motion, needs one-time Kaggle setup.
  2. Ken Burns pan/zoom on the static image (from render_video.py) --
     always works, no network, no external account needed.

If you never set up Kaggle (no KAGGLE_USERNAME/KAGGLE_KEY secrets), this
behaves identically to render_video.py -- every scene just falls back to
Ken Burns. So swapping this in for render_video.py in main.py is safe
either way.
"""

import json
import os
import random

from moviepy.editor import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    VideoFileClip,
    concatenate_videoclips,
)
from moviepy.video.fx.crop import crop

# Reuse everything that's already tested and working -- same constants,
# same Ken Burns effect, same PIL-based subtitle rendering.
from render_video import (
    W, H, FPS, MUSIC_VOLUME,
    STORY_PATH, IMAGES_DIR, AUDIO_DIR, MUSIC_PATH, OUTPUT_PATH,
    ken_burns_clip, make_subtitle_clip,
)

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
ANIMATED_DIR = os.path.join(BASE_DIR, "output", "animated")  # populated by kaggle_animate.py, if used


def fit_clip_to_frame(clip):
    """Scale to cover the WxH frame (like CSS object-fit: cover), then center-crop.
    Prevents a Kaggle clip's aspect ratio from stretching/squashing into the
    final vertical/landscape canvas."""
    scale = max(W / clip.w, H / clip.h)
    resized = clip.resize(scale)
    return crop(resized, width=W, height=H, x_center=resized.w / 2, y_center=resized.h / 2)


def loop_or_trim(clip, duration: float):
    if clip.duration < duration:
        loops = int(duration // clip.duration) + 1
        clip = concatenate_videoclips([clip] * loops)
    return clip.subclip(0, duration).set_duration(duration)


def load_kaggle_clip(index: int, duration: float):
    """A clip already rendered by the Kaggle GPU step, if present."""
    path = os.path.join(ANIMATED_DIR, f"scene_{index}_anim.mp4")
    if not os.path.exists(path):
        return None
    try:
        clip = VideoFileClip(path)
        clip = loop_or_trim(clip, duration)
        return fit_clip_to_frame(clip)
    except Exception as e:
        print(f"  Kaggle clip for scene_{index} exists but failed to load ({e}) -> falling back to Ken Burns.")
        return None


def main():
    if not os.path.exists(STORY_PATH):
        print(f"ERROR: {STORY_PATH} not found.")
        raise SystemExit(1)

    with open(STORY_PATH, "r", encoding="utf-8") as f:
        story = json.load(f)

    scene_clips = []

    for i, scene in enumerate(story["scenes"]):
        img_path = os.path.join(IMAGES_DIR, f"scene_{i}.png")
        audio_path = os.path.join(AUDIO_DIR, f"scene_{i}.mp3")

        if not os.path.exists(img_path) or not os.path.exists(audio_path):
            print(f"ERROR: Missing asset for scene {i} ({img_path} / {audio_path})")
            raise SystemExit(1)

        narration_audio = AudioFileClip(audio_path)
        duration = narration_audio.duration + 0.4

        visual = load_kaggle_clip(i, duration)
        source = "Kaggle GPU (real animation)"
        if visual is None:
            visual = ken_burns_clip(img_path, duration, zoom_in=random.choice([True, False]))
            source = "Ken Burns (fallback)"
        print(f"  Scene {i} visual source: {source}")

        subtitle = make_subtitle_clip(scene["narration"], duration)
        scene_video = CompositeVideoClip([visual, subtitle], size=(W, H)).set_duration(duration)
        scene_video = scene_video.set_audio(narration_audio)
        scene_clips.append(scene_video)

    final_video = concatenate_videoclips(scene_clips, method="compose")

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
