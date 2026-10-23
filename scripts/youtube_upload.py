#!/usr/bin/env python3
"""Official OAuth-based YouTube PRIVATE upload & Channel Integration.
Supports:
1. OAuth 2.0 flow for desktop / browser authorization.
2. Fetching real channel profile (title, handle, avatar, subscriber count).
3. Resumable chunked video upload (private-first policy).
4. Custom thumbnail upload via YouTube Data API v3.
5. Truthful SEO, Made For Kids, and Synthetic Media disclosures.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SECRETS_DIR = ROOT / ".secrets"
CLIENT_SECRETS_PATH = SECRETS_DIR / "client_secrets.json"
TOKEN_PATH = SECRETS_DIR / "youtube_token.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def ensure_secrets_dir() -> Path:
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    return SECRETS_DIR


def get_oauth_status() -> dict[str, Any]:
    """Check whether Google OAuth client secrets and user tokens exist and are valid."""
    ensure_secrets_dir()
    has_client = CLIENT_SECRETS_PATH.is_file()
    has_token = TOKEN_PATH.is_file()

    if not has_client:
        return {
            "configured": False,
            "authenticated": False,
            "channel": None,
            "hint": "Provide client_secrets.json (OAuth Client ID) from Google Cloud Console.",
        }

    if not has_token:
        return {
            "configured": True,
            "authenticated": False,
            "channel": None,
            "hint": "Client secrets found. Click 'Authorize with Google' to link your YouTube channel.",
        }

    try:
        creds = get_credentials(auto_auth=False)
        if not creds or not creds.valid:
            return {
                "configured": True,
                "authenticated": False,
                "channel": None,
                "hint": "Credentials expired or invalid. Re-authorization required.",
            }
        ch = get_authenticated_channel(creds)
        return {
            "configured": True,
            "authenticated": True,
            "channel": ch,
            "hint": f"Connected to {ch.get('title')} ({ch.get('handle')}).",
        }
    except Exception as err:
        return {
            "configured": True,
            "authenticated": False,
            "channel": None,
            "error": str(err),
            "hint": "Failed to verify YouTube authentication.",
        }


def save_client_secrets(data: dict[str, Any] | str) -> dict[str, Any]:
    """Save client secrets JSON to .secrets/client_secrets.json."""
    ensure_secrets_dir()
    if isinstance(data, str):
        data = json.loads(data)

    # Validate structure
    if "installed" not in data and "web" not in data:
        # Check if user passed client_id and client_secret directly
        cid = data.get("client_id")
        csec = data.get("client_secret")
        if cid and csec:
            data = {
                "installed": {
                    "client_id": cid.strip(),
                    "client_secret": csec.strip(),
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "redirect_uris": ["http://localhost", "http://127.0.0.1"],
                }
            }
        else:
            raise ValueError("Invalid client_secrets format. Must contain 'installed' or 'web' or client_id/client_secret.")

    CLIENT_SECRETS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(CLIENT_SECRETS_PATH)}


def get_credentials(auto_auth: bool = True):
    """Load or refresh credentials; optionally run local OAuth flow if interactive."""
    ensure_secrets_dir()
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if TOKEN_PATH.is_file():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        except Exception:
            creds = None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        except Exception:
            creds = None

    if (not creds or not creds.valid) and auto_auth:
        if not CLIENT_SECRETS_PATH.is_file():
            raise FileNotFoundError(f"Missing Google OAuth client secrets at {CLIENT_SECRETS_PATH}")
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS_PATH), SCOPES)
        creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return creds


def get_authenticated_channel(creds=None) -> dict[str, Any]:
    """Retrieve authenticated user's YouTube channel details."""
    if creds is None:
        creds = get_credentials(auto_auth=True)

    from googleapiclient.discovery import build

    yt = build("youtube", "v3", credentials=creds)
    res = yt.channels().list(mine=True, part="snippet,statistics,contentDetails").execute()
    items = res.get("items", [])
    if not items:
        raise ValueError("No YouTube channel found for the authenticated Google account.")

    item = items[0]
    snip = item.get("snippet", {})
    stats = item.get("statistics", {})

    # Extract best available avatar
    thumbs = snip.get("thumbnails", {})
    avatar_url = (
        thumbs.get("high", {}).get("url")
        or thumbs.get("medium", {}).get("url")
        or thumbs.get("default", {}).get("url")
        or ""
    )

    handle = snip.get("customUrl", "")
    if handle and not handle.startswith("@"):
        handle = f"@{handle}"
    if not handle:
        handle = f"@{snip.get('title', 'channel').lower().replace(' ', '')}"

    return {
        "id": item["id"],
        "title": snip.get("title", ""),
        "handle": handle,
        "description": snip.get("description", ""),
        "avatar_url": avatar_url,
        "subscriber_count": int(stats.get("subscriberCount", 0)),
        "video_count": int(stats.get("videoCount", 0)),
        "view_count": int(stats.get("viewCount", 0)),
        "country": snip.get("country", "US"),
    }


def upload_episode_to_youtube(slug: str, confirm_private: bool = True, force: bool = False) -> dict[str, Any]:
    """Upload video file with SEO metadata and custom thumbnail to YouTube in private mode."""
    folder = ROOT / "episodes" / slug
    if not folder.is_dir():
        raise FileNotFoundError(f"Episode directory not found: {folder}")

    ep_file = folder / "episode.json"
    if not ep_file.is_file():
        raise FileNotFoundError(f"episode.json missing for {slug}")

    episode = json.loads(ep_file.read_text(encoding="utf-8"))
    video = folder / "output" / "final.mp4"
    if not video.is_file():
        raise FileNotFoundError(f"Video file missing: {video}. Render the video first with factory.py render.")

    # Status check
    if not force and episode.get("status") not in ("approved-for-upload", "rendered-review-required", "private-uploaded"):
        raise PermissionError(
            f"Approval required: episode status is '{episode.get('status')}'. Certify Gate 2 & Gate 3 in Publishing Queue first."
        )

    if not confirm_private:
        return {
            "dry_run": True,
            "slug": slug,
            "title": episode.get("title"),
            "video_path": str(video),
            "message": "Dry run complete. Set confirm_private=True to upload.",
        }

    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError

    creds = get_credentials(auto_auth=True)
    yt = build("youtube", "v3", credentials=creds)

    seo = episode.get("seo", {})
    title = seo.get("title") or episode.get("title") or "YouTube AI Factory Video"
    # Ensure title length conforms to YouTube max 100 characters
    if len(title) > 100:
        title = title[:97] + "..."

    description = seo.get("description") or f"{title}\n\nProduced with YouTube AI Factory."
    tags = seo.get("tags") or ["shorts", "educational", "3d"]
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    # Respect truthful AI disclosures and COPPA guidelines
    made_for_kids = bool(episode.get("made_for_kids", False))
    synthetic = bool(episode.get("contains_synthetic_media", True))

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags[:30],
            "categoryId": "27",  # Education
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": made_for_kids,
            "containsSyntheticMedia": synthetic,
        },
    }

    # Upload video file (8MB chunks)
    media_body = MediaFileUpload(str(video), mimetype="video/mp4", chunksize=1024 * 1024 * 8, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media_body)

    result = None
    while result is None:
        progress, result = req.next_chunk()
        if progress:
            pct = round(progress.progress() * 100)
            print(f"Uploading {slug}: {pct}%")

    video_id = result.get("id")
    if not video_id:
        raise RuntimeError("YouTube upload succeeded but no video ID was returned.")

    # Upload thumbnail if candidate exists
    thumb_uploaded = False
    thumb_candidates = [
        folder / "output" / "preview-thumbnail.jpg",
        folder / "thumbnail.png",
        folder / "cover.png",
        folder / "output" / "preview.jpg",
    ]
    thumb_path = next((p for p in thumb_candidates if p.is_file()), None)
    if thumb_path:
        try:
            mime = "image/jpeg" if thumb_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
            yt.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumb_path), mimetype=mime),
            ).execute()
            thumb_uploaded = True
            print(f"Thumbnail uploaded successfully from {thumb_path.name}")
        except Exception as t_err:
            print(f"Warning: Failed to set thumbnail for {video_id}: {t_err}")

    # Save upload record
    record = {
        "video_id": video_id,
        "url": f"https://youtu.be/{video_id}",
        "studio_url": f"https://studio.youtube.com/video/{video_id}/edit",
        "title": title,
        "privacy_status": "private",
        "thumbnail_uploaded": thumb_uploaded,
        "response": result,
    }
    (folder / "youtube-upload-result.json").write_text(json.dumps(record, indent=2), encoding="utf-8")

    # Update episode state
    episode["status"] = "private-uploaded"
    episode["youtube_video_id"] = video_id
    episode["youtube_url"] = f"https://youtu.be/{video_id}"
    episode["thumbnail_uploaded"] = thumb_uploaded
    ep_file.write_text(json.dumps(episode, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Sync back to hybrid sqlite store if running
    try:
        from hybrid_store import HybridStore
        store = HybridStore()
        store.upsert_video(episode)
    except Exception:
        pass

    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("slug", nargs="?", help="Episode slug to upload")
    p.add_argument("--confirm-private-upload", action="store_true", help="Authorize real private YouTube upload")
    p.add_argument("--status", action="store_true", help="Check OAuth connection status")
    p.add_argument("--connect", action="store_true", help="Run interactive OAuth authorization")
    p.add_argument("--force", action="store_true", help="Bypass episode status check")
    a = p.parse_args()

    if a.status:
        st = get_oauth_status()
        print(json.dumps(st, indent=2))
        return

    if a.connect:
        creds = get_credentials(auto_auth=True)
        ch = get_authenticated_channel(creds)
        print(f"Successfully connected to YouTube!\nChannel: {ch['title']} ({ch['handle']})\nSubscribers: {ch['subscriber_count']}")
        return

    if not a.slug:
        p.print_help()
        sys.exit(1)

    rec = upload_episode_to_youtube(a.slug, confirm_private=a.confirm_private_upload, force=a.force)
    print(json.dumps(rec, indent=2))


if __name__ == "__main__":
    main()
