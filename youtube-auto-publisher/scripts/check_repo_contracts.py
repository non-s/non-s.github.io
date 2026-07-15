from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()

REQUIRED_FILES = (
    ".env.example",
    ".gitignore",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "config.py",
    "main.py",
    "requirements.txt",
    "scripts/check_production_contracts.py",
    "scripts/check_workflows.py",
)

REQUIRED_ENV_EXAMPLE_KEYS = (
    "PEXELS_API_KEY",
    "PEXELS_TIMEOUT_SECONDS",
    "PEXELS_MAX_DOWNLOAD_MB",
    "GROQ_API_KEY",
    "GROQ_MODEL",
    "GROQ_TTS_MODEL",
    "GROQ_TTS_VOICE",
    "YOUTUBE_CLIENT_ID",
    "YOUTUBE_CLIENT_SECRET",
    "YOUTUBE_TOKEN_JSON",
    "VIDEO_PRIVACY_STATUS",
    "VIDEO_CATEGORY_ID",
    "VIDEO_WIDTH",
    "VIDEO_HEIGHT",
    "VIDEO_FPS",
    "VIDEO_DURATION",
    "VIDEO_NUM_CLIPS",
    "VIDEO_MIN_DURATION",
    "VIDEO_MAX_DURATION",
    "VIDEO_MAX_CLIPS",
    "AUDIO_SAMPLE_RATE",
    "AUDIO_CHANNELS",
    "AUDIO_VOICE_VOLUME",
    "AUDIO_MUSIC_VOLUME",
    "AUDIO_FADE_DURATION",
    "SUBTITLE_FONT",
    "SUBTITLE_FONT_SIZE",
    "SUBTITLE_COLOR",
    "SUBTITLE_STROKE_COLOR",
    "SUBTITLE_STROKE_WIDTH",
    "SUBTITLE_POSITION",
    "OUTPUT_DIR",
    "TEMP_DIR",
    "MUSIC_DIR",
    "FONTS_DIR",
    "DATABASE_URL",
    "PUBLISH_TIMES",
    "MAX_VIDEOS_PER_DAY",
    "ENABLE_AUTO_PUBLISH",
    "LOG_LEVEL",
    "LOG_FILE",
    "MAX_UPLOAD_RETRIES",
    "UPLOAD_RETRY_MAX_SLEEP_SECONDS",
    "HTTP_USER_AGENT",
)

REQUIRED_GITIGNORE_ENTRIES = (
    ".env",
    "token.json",
    "client_secrets.json",
    "credentials.json",
    "data/*.db",
    "output/",
    "temp/",
    "logs/",
)


def env_keys(text: str) -> set[str]:
    keys: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys.add(line.split("=", 1)[0].strip())
    return keys


def check_repo_contracts(root: Path = ROOT) -> list[str]:
    failures: list[str] = []

    for rel_path in REQUIRED_FILES:
        if not (root / rel_path).exists():
            failures.append(f"required file missing: {rel_path}")

    license_text = (
        (root / "LICENSE").read_text(encoding="utf-8")
        if (root / "LICENSE").exists()
        else ""
    )
    if "MIT License" not in license_text:
        failures.append("LICENSE must contain MIT License text referenced by README")

    readme_text = (
        (root / "README.md").read_text(encoding="utf-8")
        if (root / "README.md").exists()
        else ""
    )
    if "[LICENSE](LICENSE)" in readme_text and not (root / "LICENSE").exists():
        failures.append("README links to LICENSE, but LICENSE is missing")

    env_text = (
        (root / ".env.example").read_text(encoding="utf-8")
        if (root / ".env.example").exists()
        else ""
    )
    missing_env = sorted(set(REQUIRED_ENV_EXAMPLE_KEYS) - env_keys(env_text))
    for key in missing_env:
        failures.append(f".env.example is missing {key}")

    gitignore_text = (
        (root / ".gitignore").read_text(encoding="utf-8")
        if (root / ".gitignore").exists()
        else ""
    )
    for entry in REQUIRED_GITIGNORE_ENTRIES:
        if entry not in gitignore_text:
            failures.append(f".gitignore is missing {entry}")

    return failures


def main() -> int:
    failures = check_repo_contracts()
    if failures:
        print("REPO_CONTRACTS_FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("REPO_CONTRACTS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
