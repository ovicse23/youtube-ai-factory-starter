#!/usr/bin/env python3
"""Local Hybrid Control Center HTTP server for YouTube AI Factory.

Serves the full 6-module frontend (Channels, Research Provider, Ideas, Videos,
Approvals, Analytics) backed by HybridStore (.local/factory.db + workspace files).
No external requests or paid AI calls are initiated automatically.
"""
from __future__ import annotations

import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from hybrid_store import HybridStore
from research_router import research_instructions
from upload_timing import compute_upload_windows

ROOT = Path(__file__).resolve().parent
DASHBOARD_DIR = ROOT / "dashboard"

CSP_POLICY = (
    "default-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; "
    "connect-src 'self'; "
    "media-src 'self' blob:; "
    "img-src 'self' data: blob: https://*.googleusercontent.com https://*.ytimg.com https://www.youtube.com; "
    "base-uri 'none'; "
    "frame-ancestors 'none'"
)

STATIC_ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/data.js": ("data.js", "text/javascript; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/dashboard/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/dashboard/data.js": ("data.js", "text/javascript; charset=utf-8"),
    "/dashboard/app.js": ("app.js", "text/javascript; charset=utf-8"),
}

SAFE_MEDIA_RE = re.compile(r"^/api/media/([a-z0-9-]{1,64})/([a-zA-Z0-9._-]{1,80})$")


def get_env_var(key: str, default: str = "") -> str:
    val = os.environ.get(key)
    if val:
        return val
    env_file = ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return default


def generate_or_render_episode(slug: str, store: HybridStore) -> dict[str, Any]:
    ep_dir = store.episodes_dir / slug
    ep_file = ep_dir / "episode.json"
    if not ep_file.is_file():
        raise FileNotFoundError(f"Episode {slug} not found")
    ep = json.loads(ep_file.read_text(encoding="utf-8"))

    clips_dir = ep_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    out_dir = ep_dir / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    scenes = ep.get("scenes", [])
    if not scenes:
        scenes = [
            {"duration_seconds": 6, "name": "Opening Hook", "prompt": ep.get("title", "Hook")},
            {"duration_seconds": 12, "name": "Core Revelation", "prompt": "Hidden mechanism revealed in high contrast 3D"},
            {"duration_seconds": 10, "name": "Resolution & CTA", "prompt": "Macro tilt-shift close-up conclusion"},
        ]
        ep["scenes"] = scenes

    aspect = ep.get("aspect", "9:16")
    w, h = (1080, 1920) if aspect == "9:16" else (1920, 1080)

    from factory import get_ffmpeg_bin, ffmpeg_run
    ff = get_ffmpeg_bin()

    real_footage_sample = active_store.episodes_dir / "pilot-01" / "clips" / "scene-01.mp4"
    for idx, sc in enumerate(scenes, 1):
        clip_path = clips_dir / f"scene-{idx:02d}.mp4"
        if not clip_path.is_file() or clip_path.stat().st_size < 1024:
            if real_footage_sample.is_file() and real_footage_sample.stat().st_size > 100 * 1024:
                shutil.copy2(real_footage_sample, clip_path)
            else:
                dur = int(sc.get("duration_seconds", 6))
                c = "0x0f291e"
                cmd = [
                    ff, "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", f"color=c={c}:s={w}x{h}:d={dur}",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={dur}",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k", "-shortest",
                    str(clip_path),
                ]
                ffmpeg_run(cmd)

    work = out_dir / "normalized"
    work.mkdir(parents=True, exist_ok=True)
    parts = []
    for idx, sc in enumerate(scenes, 1):
        clip_path = clips_dir / f"scene-{idx:02d}.mp4"
        part_path = work / f"part-{idx:02d}.mp4"
        cmd = [
            ff, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(clip_path),
            "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k",
            str(part_path),
        ]
        ffmpeg_run(cmd)
        parts.append(part_path)

    concat_txt = work / "concat.txt"
    concat_txt.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    final_mp4 = out_dir / "final.mp4"
    ffmpeg_run([ff, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", str(final_mp4)])

    thumb = out_dir / "preview-thumbnail.jpg"
    ffmpeg_run([ff, "-y", "-hide_banner", "-loglevel", "error", "-ss", "1", "-i", str(final_mp4), "-frames:v", "1", "-q:v", "2", str(thumb)])

    ep["status"] = "rendered-review-required"
    ep_file.write_text(json.dumps(ep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    store.upsert_video(ep)

    try:
        from scripts.automation_worker import sync_video_to_r2
        sync_video_to_r2(slug, out_dir)
    except Exception as exc:
        print(f"R2 background sync notice: {exc}")

    return {
        "ok": True,
        "slug": slug,
        "status": "rendered-review-required",
        "final_url": f"/api/media/{slug}/final.mp4",
        "preview_url": f"/api/media/{slug}/preview-thumbnail.jpg",
        "title": ep.get("title", slug),
    }


def make_handler(store: HybridStore | None = None):
    active_store = store or HybridStore()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            return

        def _reply(self, status: int, data: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", CSP_POLICY)
            self.end_headers()
            self.wfile.write(data)

        def _json(self, status: int, obj: object) -> None:
            self._reply(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _check_same_origin(self) -> bool:
            origin = self.headers.get("Origin")
            if origin and origin != f"http://{self.headers.get('Host', '')}":
                self._json(403, {"error": "Origin not allowed"})
                return False
            return True

        def _read_json_body(self, max_bytes: int = 262144) -> dict:
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                raise PermissionError("Send application/json")
            size = int(self.headers.get("Content-Length", "0"))
            if size < 2 or size > max_bytes:
                raise ValueError("Request body length invalid")
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object")
            return payload

        def do_GET(self) -> None:
            url = urlparse(self.path)
            path = url.path

            if path in STATIC_ASSETS:
                fname, ctype = STATIC_ASSETS[path]
                target = DASHBOARD_DIR / fname
                if not target.is_file():
                    return self._json(404, {"error": "Static file missing"})
                return self._reply(200, target.read_bytes(), ctype)

            if path == "/api/bootstrap":
                return self._json(200, active_store.bootstrap())

            if path == "/api/settings":
                return self._json(200, active_store.get_settings())

            if path == "/api/research-plan":
                qs = parse_qs(url.query)
                topic = qs.get("topic", ["Research 5 original YouTube niches"])[0][:400]
                text = research_instructions(active_store.get_settings(), topic)
                return self._reply(200, text.encode("utf-8"), "text/plain; charset=utf-8")

            if path == "/api/upload-plan":
                qs = parse_qs(url.query)
                aspect = qs.get("aspect", ["9:16"])[0]
                if aspect not in ("9:16", "16:9"):
                    return self._json(400, {"error": "aspect must be 9:16 or 16:9"})
                s = active_store.get_settings()
                countries_raw = qs.get("countries", [""])[0]
                countries = (
                    [c.strip().upper() for c in countries_raw.split(",") if c.strip()]
                    if countries_raw
                    else s["research"]["target_countries"]
                )
                tz = qs.get("tz", [s["publishing"]["creator_timezone"]])[0]
                ref_date = qs.get("date", [None])[0]
                try:
                    return self._json(
                        200,
                        compute_upload_windows(aspect=aspect, target_countries=countries, creator_tz=tz, ref_date=ref_date),
                    )
                except ValueError as err:
                    return self._json(400, {"error": str(err)})

            if path == "/api/channels/incubate":
                qs = parse_qs(url.query)
                topic = qs.get("topic", [""])[0][:200]
                tz = qs.get("tz", [""])[0]
                return self._json(200, active_store.incubate_channel(topic=topic, creator_tz=tz))

            if path == "/api/oauth/status":
                try:
                    from scripts.youtube_upload import get_oauth_status
                    st = get_oauth_status()
                except Exception as e:
                    st = {"configured": False, "authenticated": False, "channel": None, "error": str(e)}
                st["has_api_key"] = bool(get_env_var("YOUTUBE_API_KEY"))
                return self._json(200, st)

            if path == "/api/youtube/channel-lookup":
                qs = parse_qs(url.query)
                handle = qs.get("handle", [""])[0].strip()
                channel_id = qs.get("channel_id", [""])[0].strip()
                api_key = get_env_var("YOUTUBE_API_KEY")
                if not api_key:
                    return self._json(400, {"error": "YOUTUBE_API_KEY is not configured in .env"})
                if not handle and not channel_id:
                    return self._json(400, {"error": "Please provide 'handle' (e.g. @channel) or 'channel_id'"})
                try:
                    import urllib.request, urllib.parse
                    if channel_id:
                        api_url = f"https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics,brandingSettings&id={urllib.parse.quote(channel_id)}&key={api_key}"
                    else:
                        h_param = handle if handle.startswith("@") else f"@{handle}"
                        api_url = f"https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics,brandingSettings&forHandle={urllib.parse.quote(h_param)}&key={api_key}"
                    
                    req = urllib.request.Request(api_url, headers={"User-Agent": "YouTubeAIFactory/1.0"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        yt_data = json.loads(resp.read().decode("utf-8"))
                    
                    items = yt_data.get("items", [])
                    if not items and handle and not channel_id:
                        clean_h = handle.lstrip("@")
                        api_url2 = f"https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics,brandingSettings&forUsername={urllib.parse.quote(clean_h)}&key={api_key}"
                        with urllib.request.urlopen(urllib.request.Request(api_url2, headers={"User-Agent": "YouTubeAIFactory/1.0"}), timeout=10) as resp2:
                            yt_data2 = json.loads(resp2.read().decode("utf-8"))
                        items = yt_data2.get("items", [])

                    if not items:
                        return self._json(404, {"error": f"No YouTube channel found matching '{handle or channel_id}'"})
                    
                    item = items[0]
                    snip = item.get("snippet", {})
                    stats = item.get("statistics", {})
                    thumbs = snip.get("thumbnails", {})
                    avatar = thumbs.get("high", {}).get("url") or thumbs.get("medium", {}).get("url") or thumbs.get("default", {}).get("url") or ""
                    custom_handle = snip.get("customUrl", "") or handle
                    if custom_handle and not custom_handle.startswith("@"):
                        custom_handle = f"@{custom_handle}"
                    
                    res = {
                        "ok": True,
                        "channel": {
                            "youtube_channel_id": item["id"],
                            "title": snip.get("title", ""),
                            "handle": custom_handle,
                            "description": snip.get("description", ""),
                            "avatar_url": avatar,
                            "subscriber_count": int(stats.get("subscriberCount", 0)),
                            "video_count": int(stats.get("videoCount", 0)),
                            "view_count": int(stats.get("viewCount", 0)),
                            "country": snip.get("country", "US"),
                        }
                    }
                    return self._json(200, res)
                except Exception as err:
                    return self._json(500, {"error": f"YouTube API lookup failed: {err}"})

            if path == "/api/channels":
                return self._json(200, active_store.list_channels())
            if path == "/api/niches":
                return self._json(200, active_store.list_niches())
            if path == "/api/automations":
                return self._json(200, active_store.list_automations())
            if path == "/api/characters":
                return self._json(200, active_store.list_characters())
            if path == "/api/providers/usage":
                return self._json(200, active_store.list_provider_usage())
            if path == "/api/overview/kpis":
                return self._json(200, active_store.get_overview_kpis())
            if path == "/api/ideas":
                return self._json(200, active_store.list_ideas())
            if path == "/api/videos":
                return self._json(200, active_store.list_videos())
            if path == "/api/approvals":
                return self._json(200, active_store.list_approvals())
            if path == "/api/jobs":
                return self._json(200, active_store.list_jobs())
            if path == "/api/analytics":
                return self._json(200, active_store.list_analytics())
            if path == "/api/sync":
                return self._json(200, active_store.export_sync_bundle())

            media_match = SAFE_MEDIA_RE.match(path)
            if media_match:
                slug, fname = media_match.groups()
                ep_dir = active_store.episodes_dir / slug
                candidate = ep_dir / ("output" if fname.startswith(("final", "preview")) else "clips") / fname
                if not candidate.is_file():
                    return self._json(404, {"error": "Media asset not found locally"})
                ctype = "video/mp4" if fname.endswith(".mp4") else "image/jpeg" if fname.endswith((".jpg", ".jpeg")) else "application/octet-stream"
                return self._reply(200, candidate.read_bytes(), ctype)

            return self._json(404, {"error": "Not found"})

        def do_POST(self) -> None:
            if not self._check_same_origin():
                return
            path = urlparse(self.path).path
            try:
                body = self._read_json_body()
                if path == "/api/research-settings":
                    return self._json(200, active_store.update_settings(body))
                if path == "/api/channels/incubate":
                    package = body.get("package") or body
                    idx = int(body.get("concept_index", 0))
                    return self._json(200, active_store.adopt_incubated_channel(package, concept_index=idx))
                if path == "/api/channels":
                    return self._json(200, active_store.upsert_channel(body))
                if path == "/api/niches":
                    return self._json(200, active_store.upsert_niche(body))
                if path == "/api/automations":
                    return self._json(200, active_store.upsert_automation(body))
                if path == "/api/automations/toggle":
                    return self._json(200, active_store.toggle_automation(str(body.get("id")), bool(body.get("enabled"))))
                if path == "/api/automations/pause-all":
                    return self._json(200, active_store.pause_all_automations(bool(body.get("pause", True))))
                if path == "/api/automations/run":
                    return self._json(200, active_store.trigger_automation(str(body.get("id"))))
                if path == "/api/characters":
                    return self._json(200, active_store.upsert_character(body))
                if path == "/api/providers/usage":
                    return self._json(
                        200,
                        active_store.log_provider_usage(
                            str(body.get("provider", "vidiq")),
                            str(body.get("action", "query")),
                            float(body.get("credits_used", 0.0)),
                            body.get("metadata"),
                        ),
                    )
                if path == "/api/ideas":
                    return self._json(200, active_store.upsert_idea(body))
                if path == "/api/ideas/promote":
                    return self._json(200, active_store.promote_idea(str(body.get("idea_id", "")), str(body.get("slug", ""))))
                if path == "/api/videos":
                    return self._json(200, active_store.upsert_video(body))
                if path == "/api/approvals":
                    return self._json(200, active_store.upsert_approval(body))
                if path == "/api/jobs":
                    return self._json(200, active_store.enqueue_job(body))
                if path == "/api/jobs/complete":
                    return self._json(
                        200,
                        active_store.complete_job(
                            str(body.get("job_id", "")),
                            str(body.get("status", "completed")),
                            str(body.get("result_summary", "")),
                        ),
                    )
                if path == "/api/analytics":
                    return self._json(200, active_store.upsert_analytics(body))
                if path == "/api/sync":
                    return self._json(200, active_store.import_sync_bundle(body))
                if path == "/api/oauth/save-secrets":
                    from scripts.youtube_upload import save_client_secrets
                    res = save_client_secrets(body)
                    return self._json(200, res)
                if path == "/api/oauth/connect":
                    from scripts.youtube_upload import get_credentials, get_authenticated_channel
                    creds = get_credentials(auto_auth=True)
                    ch_info = get_authenticated_channel(creds)
                    ch_record = active_store.upsert_channel({
                        "name": ch_info["title"],
                        "handle": ch_info["handle"],
                        "description": ch_info["description"],
                        "niche": body.get("niche", "Connected Channel"),
                        "default_aspect": body.get("default_aspect", "9:16"),
                        "target_countries": body.get("target_countries", ["US", "UK", "CA", "AU"]),
                        "creator_timezone": body.get("creator_timezone", "Asia/Dhaka"),
                        "oauth_connected": 1,
                        "youtube_channel_id": ch_info["id"],
                        "avatar_url": ch_info["avatar_url"],
                        "subscriber_count": ch_info["subscriber_count"],
                        "video_count": ch_info["video_count"],
                        "status": "active",
                    })
                    return self._json(200, {"ok": True, "channel": ch_record, "authenticated": True})
                if path == "/api/channels/import-youtube":
                    ch_info = body.get("channel") or body
                    ch_record = active_store.upsert_channel({
                        "name": ch_info.get("title") or ch_info.get("name"),
                        "handle": ch_info["handle"],
                        "description": ch_info.get("description", ""),
                        "niche": body.get("niche") or ch_info.get("niche") or "YouTube Channel",
                        "default_aspect": body.get("default_aspect", "9:16"),
                        "target_countries": body.get("target_countries", ["US", "UK", "CA", "AU"]),
                        "creator_timezone": body.get("creator_timezone", "Asia/Dhaka"),
                        "oauth_connected": 1 if ch_info.get("oauth_connected") else 0,
                        "youtube_channel_id": ch_info.get("youtube_channel_id") or ch_info.get("id", ""),
                        "avatar_url": ch_info.get("avatar_url", ""),
                        "subscriber_count": int(ch_info.get("subscriber_count", 0)),
                        "video_count": int(ch_info.get("video_count", 0)),
                        "status": "active",
                    })
                    return self._json(200, ch_record)
                if path == "/api/videos/generate":
                    slug = str(body.get("slug", "")).strip()
                    if not slug:
                        return self._json(400, {"error": "Missing slug"})
                    res = generate_or_render_episode(slug, active_store)
                    return self._json(200, res)
                if path == "/api/publish/upload":
                    slug = str(body.get("slug", "")).strip()
                    if not slug:
                        return self._json(400, {"error": "Missing slug"})
                    confirm = bool(body.get("confirm_private_upload", True))
                    from scripts.youtube_upload import upload_episode_to_youtube
                    res = upload_episode_to_youtube(slug, confirm_private=confirm, force=bool(body.get("force", False)))
                    return self._json(200, res)
                if path == "/api/automate/full-pipeline":
                    from scripts.automation_worker import AutomationWorker
                    worker = AutomationWorker(active_store)
                    channel_id = str(body.get("channel_id") or "ch-hawthorn")
                    niche = str(body.get("niche") or "Cozy Miniature Folklore")
                    res = worker.run_full_autonomous_pipeline(channel_id, niche)
                    return self._json(200, res)
                if path == "/api/automate/process-job":
                    from scripts.automation_worker import AutomationWorker
                    worker = AutomationWorker(active_store)
                    job = worker.process_next_job()
                    return self._json(200, {"ok": True, "job": job})
                if path == "/api/channels/search-youtube":
                    from scripts.claude_youtube_bridge import fetch_channel_data
                    handle = str(body.get("handle") or body.get("query") or "")
                    if not handle:
                        return self._json(400, {"error": "Missing handle or channel identifier"})
                    res = fetch_channel_data(handle)
                    return self._json(200, res)
                if path == "/api/ideas/auto-generate":
                    import time
                    from scripts.claude_youtube_bridge import generate_ideas_package, search_competitor_videos
                    niche = str(body.get("niche") or "Cozy Miniature Folklore")
                    comps = search_competitor_videos(f"{niche} shorts", max_results=5)
                    ideas = generate_ideas_package(niche, competitor_data=comps)
                    channel_id = str(body.get("channel_id") or "ch-hawthorn")
                    saved = []
                    for idx, idea in enumerate(ideas, 1):
                        rec = active_store.upsert_idea({
                            "id": f"idea-gen-{int(time.time())}-{idx}",
                            "channel_id": channel_id,
                            "niche": niche,
                            "title": idea["title"],
                            "format": "Short (9:16)",
                            "estimated_views_tier": "100k-500k",
                            "virality_score": float(idea["composite_score"]),
                            "hook_angle": idea["hook_angle"],
                            "thumbnail_concept": idea["thumbnail_concept"],
                            "status": "ready-to-script",
                        })
                        saved.append(rec)
                    return self._json(200, {"ok": True, "ideas": saved})
                if path == "/api/hooks/generate":
                    from scripts.claude_youtube_bridge import generate_retention_hooks
                    topic = str(body.get("topic") or "Miniature Story")
                    niche = str(body.get("niche") or "Cozy Miniature Folklore")
                    res = generate_retention_hooks(topic, niche)
                    return self._json(200, res)
                return self._json(404, {"error": "Not found"})
            except PermissionError as err:
                return self._json(415, {"error": str(err)})
            except (json.JSONDecodeError, ValueError, KeyError) as err:
                return self._json(400, {"error": str(err)})
            except Exception as err:
                return self._json(500, {"error": str(err)})

        def do_PUT(self) -> None:
            if not self._check_same_origin():
                return
            path = urlparse(self.path).path
            media_match = SAFE_MEDIA_RE.match(path)
            if not media_match:
                return self._json(404, {"error": "Not found"})
            slug, fname = media_match.groups()
            if not fname.endswith((".mp4", ".jpg", ".jpeg", ".png")):
                return self._json(400, {"error": "Only .mp4, .jpg, or .png media files are accepted"})
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 80 * 1024 * 1024:
                return self._json(400, {"error": "Media upload must be between 1B and 80MB"})
            raw = self.rfile.read(size)
            subdir = "output" if fname.startswith(("final", "preview")) else "clips"
            dest = active_store.episodes_dir / slug / subdir / fname
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
            return self._json(200, {"ok": True, "url": f"/api/media/{slug}/{fname}", "bytes": len(raw)})

    return Handler


def serve(port: int = 8787) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler())
    print(f"YouTube AI Factory Local Control Center running at http://127.0.0.1:{port}/ (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, default=8787)
    serve(p.parse_args().port)
