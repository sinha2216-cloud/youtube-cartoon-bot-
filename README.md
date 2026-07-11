# Automated Kids Cartoon YouTube Bot 🎬🧒

100% free, fully automated pipeline: **Gemini (story) → Edge-TTS (voice) → Hugging Face (images) → MoviePy (video) → YouTube API (upload)**, running daily on **GitHub Actions** — no server, no hosting cost.

---

## 📁 Project Structure

```
youtube-cartoon-bot/
├── .github/workflows/daily-upload.yml   # Cron automation (GitHub Actions)
├── scripts/
│   ├── generate_story.py                # Gemini API -> story.json
│   ├── generate_audio.py                # Edge-TTS -> audio/scene_*.mp3
│   ├── generate_images.py               # Hugging Face -> images/scene_*.png
│   ├── render_video.py                  # MoviePy -> final_video.mp4
│   ├── upload_youtube.py                # Uploads final_video.mp4 to YouTube
│   └── get_refresh_token.py             # ONE-TIME local OAuth setup helper
├── assets/
│   └── background_music.mp3             # (optional, you add this)
├── main.py                              # Runs the entire pipeline in order
├── requirements.txt
├── .gitignore
└── README.md
```

---

## ✅ Step-by-Step Setup (do this once)

### 1. Create the GitHub repository
Push this entire folder to a new GitHub repo (public repo = unlimited free Actions minutes).

### 2. Get your Gemini API Key (free)
1. Go to https://aistudio.google.com/app/apikey
2. Click **Create API Key** → copy it.

### 3. Get your Hugging Face Token (free)
1. Go to https://huggingface.co/settings/tokens
2. Create a new token with **"Read"** access → copy it.

### 4. Set up YouTube Data API v3 + OAuth (one-time)
1. Go to https://console.cloud.google.com/ → create a new project.
2. In **APIs & Services → Library**, search **YouTube Data API v3** → click **Enable**.
3. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
   - Application type: **Desktop app**
   - Give it any name → Create.
4. Download the JSON → rename it to `client_secret.json` → place it in the **root** of this project folder (same level as `main.py`).
5. **On your own computer** (not GitHub), run:
   ```bash
   pip install -r requirements.txt
   python scripts/get_refresh_token.py
   ```
6. A browser window opens → log in with the Google account that owns your YouTube channel → allow access.
7. The terminal prints 3 values:
   ```
   YOUTUBE_CLIENT_ID = ...
   YOUTUBE_CLIENT_SECRET = ...
   YOUTUBE_REFRESH_TOKEN = ...
   ```
   Keep this terminal window open / copy these — you need them in the next step.

   > ⚠️ Do this only once. This refresh token lets uploads run headless forever afterward — no browser/login needed in GitHub Actions.

### 5. Add GitHub Secrets
In your GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**. Add each of these one by one:

| Secret Name | Value |
|---|---|
| `GEMINI_API_KEY` | from Step 2 |
| `HF_TOKEN` | from Step 3 |
| `YOUTUBE_CLIENT_ID` | from Step 4.7 |
| `YOUTUBE_CLIENT_SECRET` | from Step 4.7 |
| `YOUTUBE_REFRESH_TOKEN` | from Step 4.7 |

### 6. (Optional) Add background music
Drop any royalty-free mp3 into `assets/background_music.mp3`. Good free sources: YouTube Audio Library, Pixabay Music, or Free Music Archive. If this file is absent, the bot simply skips background music — no error.

### 7. Test it
- Go to your repo's **Actions** tab → select **"Daily Kids Cartoon Video Generator & Uploader"** → click **Run workflow** to trigger it manually the first time.
- Recommended for your **first run**: temporarily change `YOUTUBE_PRIVACY_STATUS: "public"` to `"private"` inside `.github/workflows/daily-upload.yml`, so you can review the video privately before making the channel go fully live. Switch back to `"public"` once you're happy with quality.

### 8. Done!
It now runs automatically every day at the cron time set in `daily-upload.yml` (default 9:00 AM UTC). Change the `cron:` line to whatever schedule you like ([crontab.guru](https://crontab.guru) helps build the expression).

---

## 🖥️ Running locally (optional, for testing)

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your_key
export HF_TOKEN=your_token
export YOUTUBE_CLIENT_ID=your_id
export YOUTUBE_CLIENT_SECRET=your_secret
export YOUTUBE_REFRESH_TOKEN=your_refresh_token
export SKIP_UPLOAD=true   # set to false/remove once you want to actually upload

python main.py
```

The final video is saved to `output/final_video.mp4` — check it before letting it upload for real.

---

## ⚙️ Configuration knobs (env vars, all optional)

| Variable | Default | Purpose |
|---|---|---|
| `NUM_SCENES` | `5` | Number of scenes/images per video |
| `TTS_VOICE` | `en-US-AnaNeural` | Edge-TTS voice (see `edge-tts --list-voices` for more kid-friendly options) |
| `VIDEO_ORIENTATION` | `vertical` | `vertical` (1080x1920, for Shorts) or `landscape` (1920x1080) |
| `YOUTUBE_PRIVACY_STATUS` | `public` | `public`, `unlisted`, or `private` |
| `HF_MODEL` | `black-forest-labs/FLUX.1-schnell` | Primary Hugging Face image model (auto-falls back to alternates if busy) |
| `SKIP_UPLOAD` | `false` | Set `true` to render locally without uploading (testing) |

---

## ⚠️ Known Limitations (read before relying on this)

1. **Hugging Face free inference can be slow/unreliable** — cold starts (20-60s) and occasional rate limits are normal. The script retries automatically and falls back to alternate models, but on a bad day image generation may still fail. Check the Actions log if a run fails.
2. **YouTube API daily quota = 10,000 units.** One upload costs ~1,600 units, so you can safely upload up to ~6 videos/day on the free tier — one per day (this bot's default) is well within limits.
3. **GitHub Actions free tier**: unlimited minutes on public repos; 2,000 min/month free on private repos. This pipeline typically takes 5-10 minutes per run.
4. **YouTube Kids / COPPA policy**: this bot sets `selfDeclaredMadeForKids: True` honestly. Fully-automated "low-effort" content can face stricter monetization review — subtitles, unique art, and original scripts (all included here) help, but approval/monetization is still YouTube's discretion, not something automation can guarantee.
5. **First-run OAuth is manual** — `get_refresh_token.py` must be run once on your own machine (needs a browser). Everything after that is 100% headless.

---

## 🔧 Troubleshooting

- **"HF_TOKEN environment variable not set"** → check the GitHub Secret name matches exactly (case-sensitive).
- **Upload fails with 401/invalid_grant** → your refresh token may have been revoked (e.g., you changed your Google account password). Re-run `get_refresh_token.py` and update the `YOUTUBE_REFRESH_TOKEN` secret.
- **Video has no subtitles / font error** → make sure the workflow's `fonts-dejavu-core` install step ran successfully (it's included by default).
- **Images look inconsistent between scenes** → tweak the story prompt in `generate_story.py` to enforce more consistent character descriptions across scenes.
