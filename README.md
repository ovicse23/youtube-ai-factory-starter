# YouTube AI Factory — Digen-only, vidIQ/Gemini-switchable + Top-Tier Upload Timing

**Status:** Local research settings/dashboard, DST-aware Top-Tier Country upload scheduler, and Digen video prompt / FFmpeg assembly toolkit. Live Gemini or vidIQ research is carried out by the connected **Antigravity agent and `.agents/skills/`**, not by `dashboard.py`. Real Digen video generation requires authentication, credits, and explicit approval.

## Key capabilities

- **Switchable research provider:** `vidiq`, `gemini`, or `auto` with explicit Gemini fallback toggle in `settings.json`.
- **Top-Tier Country (`US`, `UK`, `CA`, `AU`) upload timing engine (`upload_timing.py`):** Computes DST-aware private-upload buffer + public-release windows for both `9:16` YouTube Shorts and `16:9` Long-Form videos, converted into `UTC` and `publishing.creator_timezone` (e.g. `Asia/Dhaka`).
- **Digen-only video production:** Configured for Digen's official Streamable HTTP MCP endpoint (`https://api.digen.ai/v2/gateway/agent/openapi/mcp`) plus opt-in single-scene REST fallback (`scripts/digen_request.py`). No Google Flow dependency.
- **Master Prompt included:** Ready-to-paste `MASTER_PROMPT.md` (and quick-start `ANTIGRAVITY_START_PROMPT.md`) for full Antigravity orchestration.
- **Credit & publishing safeguards:** Zero paid Digen generation without explicit approval; Scene-1-first verification; automatic paid retries disabled; private-only OAuth YouTube upload (`scripts/youtube_upload.py`).

## 1. Start the local settings dashboard

Requires Python 3.10+ (zero third-party packages needed for core CLI & dashboard):

```bash
cd youtube-ai-factory-starter
python3 dashboard.py
```

Open **http://127.0.0.1:8787** on the same computer to configure research provider (`auto`, `vidiq`, `gemini`), depth (`quick`, `full`), and fallback, or preview generated Antigravity instructions. Endpoints also include `/api/settings`, `/api/research-plan`, and `/api/upload-plan?aspect=9:16`.

## 2. CLI reference

```bash
# View or update research & timezone settings
python3 factory.py settings
python3 factory.py set-research --provider auto --depth full --fallback on --countries US,UK,CA,AU --creator-tz Asia/Dhaka

# Compute DST-aware Top-Tier Country (US/UK/CA/AU) upload & publish schedule
python3 factory.py upload-plan --aspect 9:16
python3 factory.py upload-plan --aspect 16:9

# Generate provider-aware research instructions for Antigravity
python3 factory.py research-plan --topic "Find 5 US/UK/CA/AU original micro-story niches"
```

### Research routing matrix

| Setting | Action |
|:--|:--|
| `gemini` | Gemini inside Antigravity + `.agents/skills/` + web search. **Never calls vidIQ**. |
| `vidiq`, fallback off | vidIQ MCP (`https://mcp.vidiq.com/mcp`) only; stops if disconnected or out of credits. |
| `vidiq`, fallback on | Prefers vidIQ MCP, then falls back to Gemini + web with explicit caveat. |
| `auto`, fallback on (default) | Checks live vidIQ MCP access/credits; uses vidIQ if usable, otherwise Gemini + web. |
| `auto`, fallback off | Checks vidIQ MCP and stops if unavailable. |

## 3. Connect MCP servers in Antigravity

Antigravity reads global MCP servers from `~/.gemini/config/mcp_config.json` (or via **Settings / Additional Options (...) → MCP Servers**). See `.agents/mcp_config.example.json` for reference—**never commit bearer tokens or API keys to Git**.

### Official MCP endpoints

- **Digen MCP (Streamable HTTP):** `https://api.digen.ai/v2/gateway/agent/openapi/mcp`
  - Auth header: `Authorization: Bearer <DIGEN_API_KEY>`
- **vidIQ MCP (Streamable HTTP):** `https://mcp.vidiq.com/mcp`
  - Auth: OAuth browser login in Antigravity UI (recommended) or `Authorization: Bearer <VIDIQ_API_KEY>`

## 4. Top-Tier Country upload timing workflow

`upload_timing.py` synthesizes multi-million-post studies (Buffer, Sprout Social, vidIQ) with YouTube's official Audience Analytics guidance:

- **Shorts (`9:16`) Primary Overlap (`US` + `UK` + `CA`):** Schedule public release **12:00–14:00 US Eastern** (**17:00–19:00 UK**) on **Wed / Thu / Fri**; upload as `private` **1–2 hours earlier** (`10:00–12:00 ET`). Secondary `US Pacific` + `AU Morning` slot: **16:00–18:00 ET** (**Fri / Thu / Sat**).
- **Long-Form (`16:9`) Primary Slots:** Weekday pre-peak **13:00–15:00 US Eastern** (**Wed / Thu / Fri**) or Weekend leisure **09:00–11:00 US Eastern** (**Sun / Sat**); upload as `private` **2–3 hours earlier**.
- **Channel Data Override:** Once ~28 days of channel views accumulate, use **YouTube Studio → Analytics → Audience → "When your viewers are on YouTube"** and schedule 1–2 hours ahead of your darkest purple bar.

## 5. Episode creation, Digen generation & FFmpeg render

```bash
python3 factory.py new pilot-01 --title "The Clockmaker Inside Your Watch" --niche "Everyday Hidden Mechanics" --aspect 9:16
python3 factory.py pack pilot-01
python3 factory.py status pilot-01
```

`pack` generates:
- `episodes/pilot-01/prompts/scene-01.txt` ... `scene-NN.txt`
- `episodes/pilot-01/narration.txt`
- `episodes/pilot-01/seo-package.txt`
- `episodes/pilot-01/upload-schedule.txt`

Dry-run or single-scene opt-in REST submission (if not invoking Digen MCP directly):

```bash
python3 scripts/digen_request.py pilot-01 --scene 1                 # dry-run (0 credits)
python3 scripts/digen_request.py pilot-01 --scene 1 --confirm-spend # chargeable single scene (requires DIGEN_API_KEY)
```

Place exported clips at `episodes/pilot-01/clips/scene-01.mp4`, `scene-02.mp4`, etc. (plus optional `narration.wav`), install `ffmpeg` (`brew install ffmpeg`), and assemble:

```bash
python3 factory.py render pilot-01
```

## 6. Optional private YouTube OAuth upload

1. Install upload dependencies: `pip install -r requirements-upload.txt`
2. Save Google Cloud Desktop OAuth JSON at `.secrets/client_secrets.json` (gitignored).
3. Review `episodes/<slug>/output/final.mp4`, complete `qa.md`, set `"made_for_kids": false` (or `true` if directed at kids) and `"status": "approved-for-upload"` in `episode.json`.
4. Test dry-run, then upload **privately** during the pre-peak buffer window:

```bash
python3 scripts/youtube_upload.py pilot-01
python3 scripts/youtube_upload.py pilot-01 --confirm-private-upload
```

## 7. Run unit tests

```bash
python3 -m unittest discover -s tests -v
```
