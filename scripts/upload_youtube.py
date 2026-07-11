"""
upload_youtube.py
Uploads output/final_video.mp4 to YouTube using a stored OAuth refresh token
(no browser/login screen needed - fully headless, works in GitHub Actions).
"""

import os
import sys
import json
import time
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
STORY_PATH = os.path.join(BASE_DIR, "output", "story.json")
VIDEO_PATH = os.path.join(BASE_DIR, "output", "final_video.mp4")

CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET")
REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN")

# "public", "private", or "unlisted". Use "private" first to test before going live.
PRIVACY_STATUS = os.environ.get("YOUTUBE_PRIVACY_STATUS", "public")
CATEGORY_ID = "1"  # "Film & Animation" - reasonable default for cartoon content


def get_authenticated_service():
    if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
        print("ERROR: Missing YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN.", file=sys.stderr)
        sys.exit(1)

    creds = Credentials(
        token=None,
        refresh_token=REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def main():
    if not os.path.exists(VIDEO_PATH):
        print(f"ERROR: {VIDEO_PATH} not found. Run render_video.py first.", file=sys.stderr)
        sys.exit(1)

    with open(STORY_PATH, "r", encoding="utf-8") as f:
        story = json.load(f)

    title = story.get("title", "Kids Cartoon Story")[:95]  # YouTube title limit ~100 chars
    description = story.get("description", "A fun animated story for kids.")
    tags = story.get("tags", ["kids", "cartoon", "story", "moral story"])

    youtube = get_authenticated_service()

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": CATEGORY_ID,
        },
        "status": {
            "privacyStatus": PRIVACY_STATUS,
            "selfDeclaredMadeForKids": True,  # REQUIRED: mark honestly as kids content
        },
    }

    media = MediaFileUpload(VIDEO_PATH, chunksize=-1, resumable=True, mimetype="video/mp4")

    print(f"Uploading '{title}' to YouTube...")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    retries = 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"  upload progress: {int(status.progress() * 100)}%")
        except HttpError as e:
            retries += 1
            if retries > 5:
                print(f"ERROR: upload failed after retries: {e}", file=sys.stderr)
                sys.exit(1)
            wait = 2 ** retries
            print(f"  upload error, retrying in {wait}s... ({e})")
            time.sleep(wait)

    print("\n=========== UPLOAD SUCCESSFUL ===========")
    print(f"Video ID: {response['id']}")
    print(f"URL: https://youtu.be/{response['id']}")
    print("==========================================")


if __name__ == "__main__":
    main()
