# Paste this into Google Antigravity

> **Tip:** For the full end-to-end production prompt, see `MASTER_PROMPT.md`.

Open the entire folder `youtube-ai-factory-starter` as the Antigravity project. Preserve working files and existing scripts. You are building a **Digen-only YouTube AI Factory**, with **switchable vidIQ/Gemini research**, **Top-Tier Country (`US`, `UK`, `CA`, `AU`) upload best-time scheduling**, and explicit credit/publishing safeguards.

## Non-negotiable decisions

1. ALWAYS read `settings.json` before research and invoke `.agents/skills/research-router/SKILL.md` to honor its provider, depth, target countries, creator timezone, and fallback configuration.
2. Gemini-only = Gemini in Antigravity + web research + local YouTube Skills. **Never call vidIQ MCP in this mode**. My Google AI Pro subscription does not fund an independent Gemini API in this app; do not use unapproved paid APIs.
3. vidIQ mode = use official vidIQ MCP (`https://mcp.vidiq.com/mcp`) research and identify metrics as vidIQ-sourced. On failure, use Gemini only if fallback toggle is enabled; otherwise stop and explain.
4. Auto = check live vidIQ MCP access and available credits, use vidIQ where possible, fall back to Gemini if enabled. When connection is unknown, do not claim vidIQ data was obtained.
5. **Top-Tier Upload Timing**: Always run `python3 factory.py upload-plan` to pair every episode with DST-aware `US`/`UK`/`CA`/`AU` upload and scheduled-publish windows in `publishing.creator_timezone` (including the 1–2h Shorts / 2–3h Long-Form `private` upload processing buffer and YouTube Studio audience heatmap override rule).
6. Digen is the ONLY video-generation service, using its official remote MCP endpoint `https://api.digen.ai/v2/gateway/agent/openapi/mcp` (or documented REST fallback `scripts/digen_request.py`). Do not add Google Flow. Do not spend credits, automatically retry a paid video job, or upload publicly without my explicit approval.
7. Only create original, high-quality content and verifiable research. Do not fabricate keyword search-volume, competitor retention, CTR or revenue/RPM numbers in Gemini-only research.

## Tasks

1. Verify: `python3 -m unittest discover -s tests -v`, `python3 factory.py settings`, `python3 factory.py upload-plan --aspect 9:16`, `python3 factory.py research-plan --topic "Find 5 original English-language YouTube niches for US/UK/Canada/Australia"`, and optionally `python3 dashboard.py` (`http://127.0.0.1:8787`).
2. Confirm actual Gemini model availability in Antigravity and connect official vidIQ MCP (`https://mcp.vidiq.com/mcp`) and Digen MCP (`https://api.digen.ai/v2/gateway/agent/openapi/mcp`) only with my authorization. Never ask me to paste secret keys into chat.
3. Follow provider settings and perform dated, sourced niche + top-tier upload timing research using `/niche-scout` and `/hook-script`. Save reports under `research/` with provider name, dates, source URLs, upload windows, original ideas and 3 hooks each.
4. Create ONE coherent Digen-ready pilot with `episode.json`, visual consistency guide, numbered prompts, SEO and Top-Tier upload schedule using `python3 factory.py new ...` / `python3 factory.py pack ...`.
5. Connect Digen official MCP (`https://api.digen.ai/v2/gateway/agent/openapi/mcp`) or REST only after I authenticate and approve credit usage. Generate **Scene 1 first** to confirm video result, consistency and charge before requesting the rest.
6. Once clips are exported/available, render them using `python3 factory.py render <slug>`, inspect `final.mp4`, write `qa.md`, and prepare the thumbnail/title/schedule package.
7. Install the provided research-only Antigravity automation (`automation/sidecar.json`) only with my authorization. It must check `settings.json` each time and never spend Digen credits by default.
8. After I approve the exact channel/video and final metadata, optional YouTube OAuth upload (`scripts/youtube_upload.py`) sets `PRIVATE` visibility only during the pre-peak buffer so I can schedule public release myself in YouTube Studio.
