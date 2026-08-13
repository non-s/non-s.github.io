# Contributing To Liquid Wire

## Local Setup

```bash
pip install -r requirements-dev.txt
python -m pytest
python -m ruff check .
```

FFmpeg must be available on `PATH`.

## Generate A Test Video

```bash
python generate_liquid_wire_video.py --preset short --duration 10
```

## YouTube Setup

1. Create or reuse a Google Cloud project for Liquid Wire.
2. Enable YouTube Data API v3 and YouTube Analytics API v2.
3. Configure OAuth consent with app name `Liquid Wire`.
4. Generate a channel token with:

```bash
python utils/youtube_oauth.py
```

5. Save the resulting token as GitHub secret `YOUTUBE_TOKEN`.
6. Set GitHub variable `LIQUID_WIRE_ENABLED=1`.
7. Keep `YOUTUBE_PRIVACY=private` until private uploads pass Content ID.

Never commit `youtube_token.json`, `client_secret.json`, or any API key.
