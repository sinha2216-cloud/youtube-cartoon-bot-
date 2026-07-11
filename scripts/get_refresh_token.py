"""
get_refresh_token.py
RUN THIS ONLY ONCE, ON YOUR OWN COMPUTER (NOT in GitHub Actions).

It opens a browser login screen for YOUR YouTube channel, then prints a
refresh token. Copy that refresh token into your GitHub Secrets as
YOUTUBE_REFRESH_TOKEN. After this one-time step, uploads run headless
forever with no login screen.

Prerequisites:
1. Go to https://console.cloud.google.com/
2. Create a project -> Enable "YouTube Data API v3"
3. Create OAuth Client ID credentials (type: Desktop App)
4. Download the JSON and save it as client_secret.json in this folder
"""

import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET_FILE = os.path.join(os.path.dirname(__file__), "..", "client_secret.json")


def main():
    if not os.path.exists(CLIENT_SECRET_FILE):
        print(f"ERROR: {CLIENT_SECRET_FILE} not found.")
        print("Download it from Google Cloud Console (OAuth Client ID -> Desktop app) first.")
        return

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    credentials = flow.run_local_server(port=0)

    print("\n=========== SUCCESS ===========")
    print("Add these as GitHub Secrets in your repo (Settings -> Secrets and variables -> Actions):\n")
    print(f"YOUTUBE_CLIENT_ID = {credentials.client_id}")
    print(f"YOUTUBE_CLIENT_SECRET = {credentials.client_secret}")
    print(f"YOUTUBE_REFRESH_TOKEN = {credentials.refresh_token}")
    print("================================\n")

    # Also save locally for convenience/reference (do NOT commit this file)
    with open(os.path.join(os.path.dirname(__file__), "..", "youtube_token_backup.json"), "w") as f:
        json.dump(
            {
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "refresh_token": credentials.refresh_token,
            },
            f,
            indent=2,
        )
    print("Backup also saved to youtube_token_backup.json (keep this file private, never commit it!)")


if __name__ == "__main__":
    main()
