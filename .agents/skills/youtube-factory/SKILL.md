---
name: youtube-factory
description: Orchestrate evidence-based YouTube niche research, top-tier country upload timing research, hooks, original scripts, visual prompts, credit-aware Digen-only production, local rendering, and private upload preparation for the YouTube AI Factory project.
---

# YouTube AI Factory (orchestrator)

When invoked, open the workspace `README.md`, `MASTER_PROMPT.md`, and episode schema in `examples/sample-episode.json`. Always check the state of prior episodes before creating new ideas. Default to **research-only** if invoked by an automation. Use the other local skills (`research-router`, `niche-scout`, `hook-script`, `production-bridge`, `quality-publish`) as appropriate.

1. **Research.** ALWAYS read `settings.json` and execute the `research-router` skill; Gemini-only mode must not call vidIQ. Browse current publicly available YouTube/search sources to compare niches for original English-language content aimed at top-tier markets (`US`, `UK`, `CA`, `AU`); record source links and exact observation dates. Do not fabricate search volumes, RPM, competitor retention or trends.
2. **Top-Tier Upload Timing Research.** Run `python3 factory.py upload-plan --aspect 9:16` (and `--aspect 16:9` when planning long-form) and validate current audience-overlap windows for `US`, `UK`, `CA`, and `AU`, converting into UTC and `publishing.creator_timezone`. Account for the 1–2h (Shorts) / 2–3h (Long-form) **PRIVATE upload indexing & HD processing buffer**, and document that YouTube Studio's *"When your viewers are on YouTube"* heatmap overrides baseline studies once ~28 days of channel data exist.
3. **Plan.** Propose 3–5 original topics, choose one after owner approval (or mark it clearly as a provisional pilot), create 3 hook variants and assess hook credibility.
4. **Write.** Build a coherent script, character/style bible, pacing and numbered shot list with clear `9:16` or `16:9` aspect ratio. Prepare valid episode JSON following sample schema; additionally set `made_for_kids` after owner's classification, and `contains_synthetic_media`.
5. **Package.** Run `python3 factory.py new <slug> --title "..." --niche "..."` if needed. Edit the JSON with the actual research-backed idea. Run `python3 factory.py pack <slug>`; all shots become separate Digen prompts and `upload-schedule.txt` + `seo-package.txt` receive the DST-aware Top-Tier upload plan.
6. **Produce.** Primary: use connected official Digen MCP (`https://api.digen.ai/v2/gateway/agent/openapi/mcp`), after confirming credit usage and budget; generate **Scene 1 first** to verify style and credit cost before generating remaining scenes. Place scenes in `episodes/<slug>/clips/scene-01.mp4`, etc. Never scrape or bypass credit/payment controls. Confirm adequate licensing for footage/audio.
7. **Render.** Once all clips exist, run `python3 factory.py render <slug>` (requires `ffmpeg` + `ffprobe`); optionally add `narration.wav` first. Inspect and request human review.
8. **Publish.** Only after explicit owner approval, use `scripts/youtube_upload.py` (Google OAuth) to upload **PRIVATELY** during the pre-peak buffer window so checks complete before the owner manually schedules public release in YouTube Studio. Do not automate public publication.
9. **Learn.** Summarize actual authorized YouTube Analytics data (including *"When your viewers are on YouTube"* and *Viewed vs. Swiped Away*) after a video publishes; adapt future hooks and upload slots based on real channel evidence.

Mandatory: report exactly which stages are complete and which are blocked by authentication, credits or human verification. Never promise viral results. Never embed API keys in source files. Do not auto-launch paid generations from the scheduled research automation.
