#!/usr/bin/env python3
"""Opt-in Digen Agent REST fallback helper.

Primary integration is the official Digen Streamable HTTP MCP endpoint:
  https://api.digen.ai/v2/gateway/agent/openapi/mcp

This script provides a direct REST fallback if needed. It reads DIGEN_API_KEY
from the environment, local .env, or ~/.env without ever printing the secret.
Never automatically retries paid tasks or assumes a returned message is an MP4.
"""
import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://api.digen.ai/v2/gateway/agent/openapi/v1"
MCP_ENDPOINT = "https://api.digen.ai/v2/gateway/agent/openapi/mcp"
ROOT = Path(__file__).resolve().parents[1]


def _load_key() -> str | None:
    env_val = os.environ.get("DIGEN_API_KEY", "").strip()
    if env_val:
        return env_val
    for candidate in (ROOT / ".env", Path.home() / ".env"):
        if candidate.is_file():
            for raw_line in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == "DIGEN_API_KEY":
                    cleaned = v.strip().strip('"').strip("'")
                    if cleaned:
                        return cleaned
    return None


def request(url, key, payload=None, stream=False):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Authorization": f"Bearer {key}", "Accept": "text/event-stream" if stream else "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    return urllib.request.urlopen(req, timeout=1200 if stream else 30)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("slug", help="Existing episode slug")
    parser.add_argument("--scene", type=int, default=1)
    parser.add_argument("--confirm-spend", action="store_true", help="Explicitly permit a credit-using Digen request")
    args = parser.parse_args()
    epdir = ROOT / "episodes" / args.slug
    promptfile = epdir / "prompts" / f"scene-{args.scene:02d}.txt"
    if not promptfile.exists():
        raise SystemExit("Run: python3 factory.py pack <slug> first")
    task = ("Using your supported video-generation skill, create ONE scene only. "
            "Keep the given visual identity and aspect ratio. Output a playable asset or an asset link. "
            "Do not start additional scenes or retry generations automatically.\n\n" + promptfile.read_text(encoding="utf-8"))
    if not args.confirm_spend:
        print(f"DRY RUN (Digen MCP endpoint: {MCP_ENDPOINT}).")
        print("This is the prompt which would be sent to Digen:\n\n" + task)
        print("\nNo credits used. Prefer Digen MCP in Antigravity, or set DIGEN_API_KEY and pass --confirm-spend.")
        return
    key = _load_key()
    if not key:
        raise SystemExit("DIGEN_API_KEY missing; add it to ~/.env or .env securely in your terminal.")
    print("Submitting one scene to Digen. Credits may be charged; check your Digen account terms.")
    try:
        with request(BASE + "/conversations?workflow=skill_agent", key, {
                "client_env": {"language": "en-US", "timezone": "Asia/Dhaka"}}) as resp:
            convo = json.load(resp)
        data = convo.get("data", convo)
        conv_id = data.get("conversation_id") or data.get("id")
        if not conv_id:
            raise ValueError(f"Could not find conversation ID: {str(convo)[:600]}")
        output = {"conversation_id": conv_id, "events": [], "messages": None, "note": "Check result and download asset manually if needed"}
        with request(BASE + "/chat", key, {"conversation_id": conv_id, "workflow": "skill_agent",
                  "blocks": [{"type": "text", "content": task}]}, stream=True) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if line.startswith("data:"):
                    payload = line[5:].strip()
                    try:
                        output["events"].append(json.loads(payload))
                    except json.JSONDecodeError:
                        output["events"].append({"raw": payload})
        with request(BASE + f"/conversations/{conv_id}/messages?limit=30", key) as resp:
            output["messages"] = json.load(resp)
        target = epdir / f"digen-scene-{args.scene:02d}-response.json"
        target.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Saved Digen response: {target}")
        print("Review returned assets, then place downloaded video in clips/scene-XX.mp4.")
    except urllib.error.HTTPError as err:
        raise SystemExit(f"Digen HTTP {err.code}: {err.read().decode(errors='replace')[:600]}")


if __name__ == '__main__':
    main()
