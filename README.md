# YouTube AI Factory — Local-First Hybrid Architecture (Antigravity + Digen + vidIQ/Gemini + Cloudflare Control Center)

An evidence-grounded, cost-minimizing **Local-First Hybrid YouTube Automation System** combining **Google Antigravity** locally (for zero-overage MCP research, Digen generation, and FFmpeg video rendering) with a **Cloudflare Control Center** online (for multi-channel management, D1/SQLite records, R2 video storage, human approval gates, and production job queuing).

---

## 1. Hybrid Architecture Overview

```text
Cloudflare Control Center Dashboard (Online Anywhere & Local 127.0.0.1:8787)
   Channels • Research Provider • Ideas • Videos • Approvals • Analytics
                     │                                 │
          ┌──────────┴──────────┐           ┌──────────┴──────────┐
          ▼                     │           │                     ▼
     LOCAL ENGINE (Phase 1)     │◄── sync ──►│    CLOUD ENGINE (Phase 2 & 3)
 • Antigravity + YouTube Skills │           │ • Cloudflare Workers API + Cron
 • Gemini / vidIQ MCP Research  │           │ • D1 SQLite Schema (schema.sql)
 • Digen CLI / Remote MCP       │           │ • R2 Video Storage (MEDIA_BUCKET)
 • Local FFmpeg Video Rendering │           │ • Production Job Queue
          └──────────┬──────────┘           └──────────┬──────────┘
                     └───────────────┬─────────────────┘
                                     ▼
                    YouTube Publishing + Analytics Loop
         Private OAuth Upload → Review → Top-Tier Scheduled Release → Heatmap Feedback
```

### Why Local-First Hybrid?
1. **Protects Your Existing Subscriptions:** Gemini Pro and vidIQ Max subscriptions work through supported local interfaces and MCP servers (`https://mcp.vidiq.com/mcp`) without introducing surprise third-party cloud API charges.
2. **Avoids Workers CPU Limits:** Heavy 1080p FFmpeg H.264/AAC video normalization and audio mixing run natively on your Mac (`python3 factory.py render <slug>`), never hitting Cloudflare Workers Free CPU caps.
3. **24/7 Control Center Anywhere:** Cloudflare Workers + Static Assets + R2 (`youtube-ai-factory-assets`) + D1 schema (`cloudflare/schema.sql`) keep your channels, ideas, scripts, approval gates, and analytics accessible online from any device.

---

## 2. Quick Start — Phase 1 Local MVP

Requires Python 3.9+ (zero third-party packages required for core CLI, SQLite store, and local Control Center):

```bash
cd youtube-ai-factory-starter

# 1. Run the full unit test suite
python3 -m unittest discover -s tests -v

# 2. Launch the full 6-module Control Center locally at http://127.0.0.1:8787
python3 dashboard.py
```

### Core CLI Commands (`factory.py`)

```bash
# Inspect or switch Research Provider (auto | vidiq | gemini) & target countries
python3 factory.py settings
python3 factory.py set-research --provider auto --depth full --fallback on --countries US,UK,CA,AU --creator-tz Asia/Dhaka

# Compute DST-aware Top-Tier Country (US, UK, CA, AU) upload & release windows
python3 factory.py upload-plan --aspect 9:16
python3 factory.py upload-plan --aspect 16:9

# Generate provider-routed Antigravity instructions
python3 factory.py research-plan --topic "Find 5 underserved US/UK/CA/AU Shorts ideas"

# Create, pack prompts, check status & render an episode locally with FFmpeg
python3 factory.py new pilot-02 --title "Why Airplane Windows Have That Tiny Hole" --niche "Everyday Hidden Mechanics" --aspect 9:16
python3 factory.py pack pilot-01
python3 factory.py status pilot-01
python3 factory.py render pilot-01   # Requires: brew install ffmpeg

# Sync Local Engine (.local/factory.db + episodes/*) <-> Cloudflare Control Center
python3 factory.py sync --mode pull --remote https://youtube-ai-factory.ovi-cse23.workers.dev
python3 factory.py sync --mode push --remote https://youtube-ai-factory.ovi-cse23.workers.dev
```

---

## 3. Connect Official MCP Endpoints Locally

Register MCP servers in `~/.gemini/config/mcp_config.json` (see `.agents/mcp_config.example.json`—**never commit tokens or keys to Git**):

- **Digen MCP (Sole Video Generator):** `https://api.digen.ai/v2/gateway/agent/openapi/mcp` (or local `digen-mcp` CLI)
- **vidIQ MCP (Switchable Keyword/Outlier Intelligence):** `https://mcp.vidiq.com/mcp`

Single-scene Digen dry-run & opt-in REST helper:

```bash
python3 scripts/digen_request.py pilot-01 --scene 1                 # 0-credit dry-run preview
python3 scripts/digen_request.py pilot-01 --scene 1 --confirm-spend # Chargeable Scene 1 ONLY after human approval
```

---

## 4. Top-Tier Country (`US`, `UK`, `CA`, `AU`) Upload Timing

`upload_timing.py` synthesizes multi-million-post datasets (Buffer, Sprout Social, vidIQ) with YouTube Audience Analytics:

- **Shorts (`9:16`) Primary Cross-Atlantic Overlap (`US` + `UK` + `CA`):** Schedule public release **12:00–14:00 US Eastern** (**17:00–19:00 UK**, **22:00–00:00 Asia/Dhaka**) on **Wed / Thu / Fri**; upload as `private` **1–2 hours earlier** (`20:00–22:00 Asia/Dhaka`).
- **Shorts (`9:16`) Secondary `US Pacific` + `AU Morning` Slot:** **16:00–18:00 US Eastern** (**Fri / Thu / Sat**).
- **Long-Form (`16:9`) Primary Slots:** Weekday pre-peak **13:00–15:00 US Eastern** (**Wed / Thu / Fri**) or Weekend leisure **09:00–11:00 US Eastern** (**Sun / Sat**); upload as `private` **2–3 hours earlier**.
- **28-Day Studio Override:** Once ~28 days of channel views accumulate, log your darkest purple bar from *YouTube Studio → Analytics → Audience → "When your viewers are on YouTube"* in the **Analytics** tab to override generic benchmarks.

---

## 5. Phase 2 & 3 Cloudflare Control Center Deployment

`wrangler.jsonc` configures Cloudflare Workers + Static Assets (`./public`) + R2 (`MEDIA_BUCKET` → `youtube-ai-factory-assets`) + `cloudflare/schema.sql` (D1 SQLite):

```bash
# Deploy Worker + Frontend Control Center + R2 Media Binding
XDG_CONFIG_HOME="$HOME/.wrangler" wrangler deploy

# Optional: When attaching a dedicated Cloudflare D1 database slot:
XDG_CONFIG_HOME="$HOME/.wrangler" wrangler d1 create youtube-ai-factory-db
XDG_CONFIG_HOME="$HOME/.wrangler" wrangler d1 execute youtube-ai-factory-db --remote --file=cloudflare/schema.sql
```

When `env.DB` (D1) is bound, `cloudflare/worker.js` executes relational SQL against `yaf_*` tables; when `env.DB` is unbound (e.g., on accounts at the 10-DB Free tier limit), `cloudflare/worker.js` automatically persists state durably inside `env.MEDIA_BUCKET` (`youtube-ai-factory-assets`) alongside binary MP4/thumbnail previews.

---

## 6. Optional Private YouTube OAuth Upload

1. Install upload dependencies: `pip install -r requirements-upload.txt`
2. Place Desktop OAuth client JSON at `.secrets/client_secrets.json` (gitignored).
3. Approve Gates 1–3 in the **Approvals** tab (sets `"status": "approved-for-upload"` and verifies `made_for_kids` + `contains_synthetic_media`).
4. Dry-run and upload **privately** during the pre-peak buffer:

```bash
python3 scripts/youtube_upload.py pilot-01
python3 scripts/youtube_upload.py pilot-01 --confirm-private-upload
```
