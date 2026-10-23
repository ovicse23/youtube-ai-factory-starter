#!/usr/bin/env python3
"""Sync Local Engine state (.local/factory.db + episodes/* + settings.json)
with the deployed Cloudflare Control Center Worker (/api/sync).

Zero paid AI or video API calls are triggered during sync.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hybrid_store import HybridStore

DEFAULT_REMOTE_URL = "https://youtube-ai-factory.ovi-cse23.workers.dev"


def sync_with_cloudflare(mode: str = "push", remote_url: str = DEFAULT_REMOTE_URL, store: HybridStore | None = None) -> dict:
    active_store = store or HybridStore()
    endpoint = remote_url.rstrip("/") + "/api/sync"

    if mode == "push":
        bundle = active_store.export_sync_bundle()
        payload = json.dumps(bundle, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Origin": remote_url.rstrip("/"),
                "User-Agent": "YouTube-AI-Factory-Local-Engine/2.0",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))

    if mode == "pull":
        req = urllib.request.Request(
            endpoint,
            method="GET",
            headers={"User-Agent": "YouTube-AI-Factory-Local-Engine/2.0"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            remote_state = json.loads(resp.read().decode("utf-8"))
        snap = active_store.import_sync_bundle(remote_state)
        return {
            "ok": True,
            "mode": "pull",
            "channels": len(snap["channels"]),
            "ideas": len(snap["ideas"]),
            "videos": len(snap["videos"]),
            "jobs": len(snap["jobs"]),
        }

    raise ValueError("mode must be 'push' or 'pull'")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=["push", "pull"], default="push", help="push local -> Cloudflare or pull Cloudflare -> local")
    p.add_argument("--remote", default=DEFAULT_REMOTE_URL, help="Cloudflare Control Center base URL")
    args = p.parse_args()
    try:
        res = sync_with_cloudflare(mode=args.mode, remote_url=args.remote)
        print(json.dumps(res, indent=2, ensure_ascii=False))
    except urllib.error.URLError as err:
        raise SystemExit(f"ERROR syncing with {args.remote}: {err}")


if __name__ == "__main__":
    main()
