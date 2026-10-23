# Paste this into Google Antigravity

> **Tip:** For the full end-to-end hybrid production prompt, see `MASTER_PROMPT.md`.

Open the entire folder `youtube-ai-factory-starter` as your Antigravity workspace. Preserve working files, schemas, and tests. Operate the **YouTube AI Factory** using our **Local-First Hybrid Architecture**:
- **Local Engine (Phase 1 MVP):** Antigravity + `.agents/skills/` + switchable **vidIQ / Gemini** research + **Digen-only** video generation + local **FFmpeg** rendering + local OAuth `PRIVATE` upload.
- **Cloudflare Control Center (Phase 2 & 3):** Online 6-module dashboard (`Channels • Research Provider • Ideas • Videos • Approvals • Analytics`), `cloudflare/schema.sql` (D1 / SQLite), R2 bucket (`youtube-ai-factory-assets`), and Production Job Queue, synced via `python3 factory.py sync`.

## Non-negotiable decisions

1. ALWAYS read `settings.json` before research and invoke `.agents/skills/research-router/SKILL.md` to honor provider (`auto`, `vidiq`, `gemini`), depth, target countries (`US`, `UK`, `CA`, `AU`), creator timezone (`Asia/Dhaka`), and fallback rules.
2. **Subscription Guardrail:** Gemini Pro and vidIQ subscriptions do not automatically grant unlimited custom cloud API calls. Run live MCP/agent research locally in Antigravity first. In `gemini` mode, **never call vidIQ MCP**.
3. **Top-Tier Upload Timing:** Run `python3 factory.py upload-plan --aspect 9:16` (or `16:9`) on every cycle to compute DST-aware `US`/`UK`/`CA`/`AU` `PRIVATE` upload buffer + `PUBLIC` release slots, and override with YouTube Studio's 28-day *"When your viewers are on YouTube"* heatmap once available.
4. **Digen-Only & Credit Gate:** Use `https://api.digen.ai/v2/gateway/agent/openapi/mcp` (or `digen-mcp` / `scripts/digen_request.py`) exclusively for video generation. Never add Google Flow. Never spend credits or auto-retry paid jobs without my explicit approval; generate **Scene 1 first**.
5. **Local FFmpeg & Private Upload:** Keep heavy FFmpeg rendering strictly on the Local Engine (`python3 factory.py render <slug>`), upload to YouTube as `PRIVATE` only (`scripts/youtube_upload.py`), and sync workspace state with Cloudflare using `python3 factory.py sync --mode push|pull`.
