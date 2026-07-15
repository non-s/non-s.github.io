import argparse
import os
import sys
import tempfile
from pathlib import Path

try:
    from tiktok_uploader.upload import upload_video
except ImportError:
    print("Error: tiktok-uploader is not installed.")
    sys.exit(1)

def write_netscape_cookies(session_id: str, path: str):
    # Domain, IncludeSubdomains, Path, Secure, Expiry, Name, Value
    content = f".tiktok.com\tTRUE\t/\tTRUE\t2145916800\tsessionid\t{session_id}\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n")
        f.write(content)

def main():
    parser = argparse.ArgumentParser(description="Upload video to TikTok via Playwright.")
    parser.add_argument("--video", required=True, help="Path to the video file")
    parser.add_argument("--desc", required=True, help="Description/caption for the video")
    args = parser.parse_args()

    session_id = os.environ.get("TIKTOK_SESSION_ID")
    if not session_id:
        print("Error: TIKTOK_SESSION_ID environment variable not set.")
        sys.exit(1)

    video_path = Path(args.video).resolve()
    if not video_path.exists():
        print(f"Error: Video file {video_path} not found.")
        sys.exit(1)

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tf:
        cookie_path = tf.name

    try:
        write_netscape_cookies(session_id, cookie_path)
        print(f"Uploading {video_path.name} to TikTok...")
        # tiktok-uploader utilizes headless Playwright to perform the upload
        upload_video(
            filename=str(video_path),
            description=args.desc,
            cookies=cookie_path,
            headless=True
        )
        print("TikTok upload sequence finished.")
    except Exception as e:
        print(f"TikTok upload failed with exception: {e}")
        sys.exit(1)
    finally:
        if os.path.exists(cookie_path):
            os.remove(cookie_path)

if __name__ == "__main__":
    main()
