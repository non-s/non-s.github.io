# YouTube OAuth Setup For Liquid Wire

This step must be done with the Google account that owns `@LiquidWireStudio`.

## 1. Google Cloud

1. Open <https://console.cloud.google.com/>.
2. Create or select a project named `Liquid Wire`.
3. Enable:
   - YouTube Data API v3
   - YouTube Analytics API v2
4. Configure OAuth consent:
   - App name: `Liquid Wire`
   - User type: External is fine for a personal project
   - Add your own Google account as a test user if the app is in testing
5. Create OAuth Client ID:
   - Application type: Desktop app
   - Name: `Liquid Wire Local Uploader`
6. Download the JSON as `client_secret.json`.

## 2. Local Token

Place `client_secret.json` at the repository root, then run:

```bash
python utils/youtube_oauth.py
```

Choose the Google account that owns the new Liquid Wire channel and approve the
requested YouTube scopes.

The script writes `youtube_token.json`.

## 3. GitHub Secret

Upload the token to GitHub Actions:

```bash
gh secret set YOUTUBE_TOKEN < youtube_token.json
```

Then verify:

```bash
python scripts/healthcheck.py --mode all
gh workflow run "Liquid Wire - Generate and Upload" --ref main -f preset=short -f duration=15
```

Keep `YOUTUBE_PRIVACY=private` until the private upload shows no Content ID
claim in YouTube Studio.

## Never Commit

These files must remain local only:

- `client_secret.json`
- `youtube_token.json`
