#!/usr/bin/env python3
"""Local Hybrid Control Center HTTP server for YouTube AI Factory.

Serves the full 6-module frontend (Channels, Research Provider, Ideas, Videos,
Approvals, Analytics) backed by HybridStore (.local/factory.db + workspace files).
No external requests or paid AI calls are initiated automatically.
"""
from __future__ import annotations

import json
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
    "img-src 'self' data: blob:; "
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

            if path == "/api/channels":
                return self._json(200, active_store.list_channels())
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
                if path == "/api/channels":
                    return self._json(200, active_store.upsert_channel(body))
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
                return self._json(404, {"error": "Not found"})
            except PermissionError as err:
                return self._json(415, {"error": str(err)})
            except (json.JSONDecodeError, ValueError, KeyError) as err:
                return self._json(400, {"error": str(err)})

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
