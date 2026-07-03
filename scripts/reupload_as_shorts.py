"""
Re-upload an existing 16:9 video as a YouTube Short (9:16).

Steps:
1. Convert existing master to 9:16 blur-behind using ffmpeg
2. Set existing YouTube video to private
3. Upload the 9:16 version as a new Short
4. Update journal entry with new video_id

Usage:
    cd /Users/dasein/dev/slope-studio
    python3 scripts/reupload_as_shorts.py \
        --run-id j0039_abel_quintic \
        --old-video-id uo2RTUjVFiU \
        --channel pilot-channel
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def build_9x16(src: Path, dst: Path) -> None:
    """Convert 16:9 video to 9:16 using blur-behind fill."""
    print(f"Converting {src.name} → {dst.name} (9:16 blur-behind)...")
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-filter_complex",
        # bg: blur the video to fill 1080x1920
        "[0:v]scale=1080:1920,boxblur=20:5[bg];"
        # fg: scale original to fit within 1080x1920 (letterbox width)
        "[0:v]scale=w=1080:h=1920:force_original_aspect_ratio=decrease[fg];"
        # overlay fg centered on bg
        "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[v]",
        "-map", "[v]", "-map", "0:a",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k",
        str(dst),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("ffmpeg stderr:", result.stderr[-2000:])
        raise RuntimeError("ffmpeg conversion failed")
    print(f"Done. Output: {dst}")


def retire_video(video_id: str, channel: str, privacy: str) -> None:
    """Flip existing YouTube video to unlisted or private."""
    print(f"Setting {video_id} to {privacy}...")
    sys.path.insert(0, str(ROOT))
    from studio.providers.publish import set_privacy
    status = set_privacy(video_id, privacy=privacy, channel=channel)
    print(f"Video {video_id} is now: {status}")


def upload_video(run_dir: Path, shorts_mp4: Path, channel: str) -> str:
    """Upload the 9:16 video and return the new video ID."""
    print(f"Uploading {shorts_mp4.name} to YouTube ({channel})...")
    sys.path.insert(0, str(ROOT))
    from studio.providers.publish import publish

    meta_file = run_dir / "06_final.json"
    meta = json.loads(meta_file.read_text())
    tags = meta.get("tags") or [h.lstrip("#") for h in meta.get("hashtags", [])]
    title = meta.get("title", "")
    description = meta.get("description", "")

    thumb = run_dir / "02_visuals" / "thumbnail.png"

    result = publish(
        "youtube", shorts_mp4, title, description, tags,
        privacy="public", channel=channel,
        thumbnail=thumb if thumb.exists() else None,
    )
    print(f"Uploaded: {result.note}")
    vid_id = result.note.split("watch?v=")[1].split()[0]
    return vid_id


def update_journal(channel: str, old_video_id: str, new_video_id: str) -> None:
    """Update journal entry: swap video_id, clear metrics/snapshots."""
    journal_path = ROOT / "runs" / "_marketing" / channel / "journal.json"
    data = json.loads(journal_path.read_text())

    # Find the entries list
    entries_key = None
    for k, v in data.items():
        if isinstance(v, list) and any(
            isinstance(e, dict) and e.get("video_id") == old_video_id
            for e in v
        ):
            entries_key = k
            break

    if entries_key is None:
        print(f"WARNING: could not find journal entry for {old_video_id}")
        return

    for entry in data[entries_key]:
        if isinstance(entry, dict) and entry.get("video_id") == old_video_id:
            entry["video_id"] = new_video_id
            entry["video_url"] = f"https://youtube.com/watch?v={new_video_id}"
            entry["metrics"] = {}
            entry["snapshots"] = []
            entry["virality"] = None
            entry["outcome"] = None
            entry.setdefault("notes", []).append(
                f"Re-uploaded as Shorts (9:16). Old video_id: {old_video_id} retired (unlisted/private)."
            )
            print(f"Journal entry updated: {old_video_id} → {new_video_id}")
            break

    journal_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print("Journal saved.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-upload video as YouTube Short")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--old-video-id", required=True)
    parser.add_argument("--channel", required=True)
    parser.add_argument("--skip-convert", action="store_true", help="Skip ffmpeg if already converted")
    parser.add_argument("--old-privacy", choices=["unlisted", "private"], default="unlisted",
                        help="Privacy for the old video after reupload (default: unlisted)")
    parser.add_argument("--skip-private", action="store_true", help="Skip flipping old video privacy")
    parser.add_argument("--skip-upload", action="store_true", help="Dry run — skip upload")
    args = parser.parse_args()

    run_dir = ROOT / "runs" / args.run_id
    if not run_dir.exists():
        sys.exit(f"Run dir not found: {run_dir}")

    src_mp4 = run_dir / "06_final.mp4"
    dst_mp4 = run_dir / "06_final_shorts.mp4"

    if not args.skip_convert:
        build_9x16(src_mp4, dst_mp4)
    else:
        print(f"Skipping conversion, using existing: {dst_mp4}")

    if not dst_mp4.exists():
        sys.exit(f"Shorts video not found: {dst_mp4}")

    if not args.skip_private:
        retire_video(args.old_video_id, args.channel, args.old_privacy)

    if not args.skip_upload:
        new_id = upload_video(run_dir, dst_mp4, args.channel)
        update_journal(args.channel, args.old_video_id, new_id)
        print(f"\nDone. New Short: https://youtube.com/shorts/{new_id}")
    else:
        print("Dry run — skipping upload and journal update.")


if __name__ == "__main__":
    main()
