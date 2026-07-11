"""
generate_audio.py
Converts each scene's narration into an mp3 using Edge-TTS (100% free, no API key needed).
Output: output/audio/scene_0.mp3, scene_1.mp3, ...  + output/audio_durations.json
"""

import os
import json
import asyncio
import sys
import edge_tts
from mutagen.mp3 import MP3

STORY_PATH = os.path.join(os.path.dirname(__file__), "..", "output", "story.json")
AUDIO_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "audio")
DURATIONS_PATH = os.path.join(os.path.dirname(__file__), "..", "output", "audio_durations.json")

# Good kid-friendly natural voices available for free in edge-tts.
# en-US-AnaNeural = child-like/young female voice, great for kids content.
VOICE = os.environ.get("TTS_VOICE", "en-US-AnaNeural")
RATE = os.environ.get("TTS_RATE", "+0%")


async def synthesize(text: str, out_path: str):
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE)
    await communicate.save(out_path)


def main():
    if not os.path.exists(STORY_PATH):
        print(f"ERROR: {STORY_PATH} not found. Run generate_story.py first.", file=sys.stderr)
        sys.exit(1)

    with open(STORY_PATH, "r", encoding="utf-8") as f:
        story = json.load(f)

    os.makedirs(AUDIO_DIR, exist_ok=True)
    durations = []

    for i, scene in enumerate(story["scenes"]):
        text = scene["narration"]
        out_path = os.path.join(AUDIO_DIR, f"scene_{i}.mp3")
        print(f"Generating audio for scene {i}...")

        last_err = None
        for attempt in range(3):
            try:
                asyncio.run(synthesize(text, out_path))
                break
            except Exception as e:
                last_err = e
                print(f"  attempt {attempt + 1} failed: {e}", file=sys.stderr)
        else:
            print(f"ERROR: Could not generate audio for scene {i}: {last_err}", file=sys.stderr)
            sys.exit(1)

        audio = MP3(out_path)
        durations.append(audio.info.length)
        print(f"  saved {out_path} ({audio.info.length:.2f}s)")

    with open(DURATIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(durations, f, indent=2)

    print(f"All audio generated. Durations saved -> {DURATIONS_PATH}")


if __name__ == "__main__":
    main()
