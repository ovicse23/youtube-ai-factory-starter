---
name: production-bridge
description: Turn episode scripts into structured Digen prompts, connect the official Digen MCP endpoint, track credits, and collect generated clips for local FFmpeg assembly.
---

# Digen production bridge

Run `python3 factory.py pack <slug>` first. Verify output prompts for separate scenes in `episodes/<slug>/prompts/`.

## Production modes (Digen ONLY — no Google Flow)

- **Primary — Official Digen Remote MCP (`https://api.digen.ai/v2/gateway/agent/openapi/mcp`):**
  1. Confirm the `digen` MCP server is active in Antigravity (`~/.gemini/config/mcp_config.json` or **Additional Options (...) → MCP Servers**) with `Authorization: Bearer <DIGEN_API_KEY>`. See `.agents/mcp_config.example.json` for schema; **never** commit API keys to Git or ask the user to paste keys in chat.
  2. Inspect available Digen MCP tools/workflows (e.g., `skill_agent`) and check credit balance/cost if exposed.
  3. **Explicit Credit Gate:** Ask the owner for explicit approval before any chargeable call. Generate **Scene 1 only** first to verify visual continuity, aspect ratio, and actual credit deduction before generating Scenes 2..N. Never auto-retry failed paid jobs.
  4. Download/export approved MP4 clips to `episodes/<slug>/clips/scene-01.mp4`, `scene-02.mp4`, etc.

- **Fallback — Opt-in Digen REST Script:**
  - Dry-run (0 credits): `python3 scripts/digen_request.py <slug> --scene 1`
  - Chargeable single-scene submit (after storing `DIGEN_API_KEY` in `~/.env` or `.env` and owner approval): `python3 scripts/digen_request.py <slug> --scene 1 --confirm-spend`

Never assume web-app Digen credits equal Digen Agent OpenAPI/MCP credits; verify plan and charges first. Once all clips are in `clips/`, run `python3 factory.py render <slug>` (requires `ffmpeg` and `ffprobe`). Respect copyrights and synthetic-media labels.
