# FlowCore AI Automation MVP

AI-powered daily short-form content automation for Instagram Reels and Facebook Pages.

## What This MVP Does

- Generates a daily topic, hook, pain point, CTA, script, caption, hashtags, and video prompts.
- Renders a vertical MP4 reel from generated scenes and subtitles.
- Uploads the MP4 to Cloudinary or stores it locally for development.
- Publishes to Instagram Reels through Meta Graph API when enabled.
- Publishes to Facebook Pages when page credentials are provided.
- Logs every run, failure, retry, and published media ID in the database.
- Exposes a webhook endpoint that n8n can trigger daily.

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

Open:

- API health: `http://localhost:8000/health`
- Swagger docs: `http://localhost:8000/docs`

## First Test

Keep `DRY_RUN_PUBLISH=true` in `.env` first.

```bash
curl -X POST http://localhost:8000/api/v1/runs/daily ^
  -H "Content-Type: application/json" ^
  -d "{\"niche\":\"AI automation for local businesses\",\"target_audience\":\"salon and clinic owners\"}"
```

The generated video will appear in `uploads/`.

## Real Instagram Publishing

For real publishing, set:

- `STORAGE_PROVIDER=cloudinary`
- Cloudinary credentials
- `META_ACCESS_TOKEN`
- `INSTAGRAM_ACCOUNT_ID`
- `AUTO_PUBLISH_INSTAGRAM=true`
- `DRY_RUN_PUBLISH=false`

Meta requires a public `video_url`, so local storage is only for development.

## n8n

Import `n8n-workflows/daily-instagram-reel.json`, then update the HTTP Request node URL to your deployed backend:

`https://your-domain.com/api/v1/runs/daily`

## Imgflip Meme Mode

For restaurant meme reels, create a normal Imgflip account and paste the username/password into `.env`:

```env
MEME_TEMPLATE_PROVIDER=imgflip
ENABLE_IMGFLIP_MEMES=true
IMGFLIP_USERNAME=
IMGFLIP_PASSWORD=
```

Imgflip does not use a separate API key for captioning. Keep this password unique to Imgflip.
