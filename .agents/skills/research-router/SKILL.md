---
name: research-router
description: Read workspace settings.json and route YouTube niche, keyword, competitor, top-tier upload timing, and hook research to vidIQ MCP or Gemini in Antigravity, with explicit fallback rules and truthful metrics.
---

# Research Router — mandatory before niche research

This is a WORKSPACE SKILL, not a Gemini or vidIQ API and not an implicit paid connection.

1. Read `settings.json` from the project root before any research. Run `python3 factory.py research-plan --topic "..."` and `python3 factory.py upload-plan` to load enforceable routing and upload-timing instructions. Do not silently override the user's provider choice.
2. Modes:
   - `gemini`: Use the currently signed-in Gemini model in Antigravity, its authorized web/search/browser tools and skills under `.agents/skills`. **Do not invoke any vidIQ tools or spend vidIQ credits.** Gemini is the reasoning/scripting model; external fresh evidence still needs cited web/YouTube data. Gemini AI Pro consumer subscription does not grant automatic Gemini API quotas to external apps.
   - `vidiq`: Use connected official vidIQ MCP (`https://mcp.vidiq.com/mcp`) keyword_research, outliers, trending_videos, channel_search or equivalent supported tools for research. Before expensive/batch research, check credits if available. When MCP is unavailable or plan limits prevent it, fall back only if `fallback_to_gemini` is true; otherwise stop and report.
   - `auto`: Check actual vidIQ MCP connection and credit availability; if usable choose vidIQ for measurements and Antigravity/Gemini for interpretation and writing. When unavailable, use Gemini only if the fallback toggle is true. If live availability cannot be checked, do not *pretend* vidIQ was queried: ask for authentication or fall back with an explicit caveat.
3. Regardless of provider, source research from real, dated, linked observations. Label vidIQ estimates as vidIQ estimates and avoid fake volume, growth, CTR and RPM numbers in Gemini-only mode. No automatic cross-platform subscription reuse.
4. **Top-Tier Country Upload Timing Requirement**: Every full research pass MUST include upload-window recommendations for `research.target_countries` (default `US`, `UK`, `CA`, `AU`) converted to UTC and `publishing.creator_timezone` via `python3 factory.py upload-plan`. Distinguish `9:16` Shorts from `16:9` Long-Form, include the 1–2h / 2–3h `private` upload processing buffer, and state that YouTube Studio's *"When your viewers are on YouTube"* report supersedes generic benchmarks once channel data accumulates.
5. Include in each research report: provider requested, provider actually used, source URLs, observation dates, top-tier upload schedule, unverified assumptions, titles/hooks, and decision rubric.
6. Always route scripts/storyboarding via `hook-script`. Digen (`https://api.digen.ai/v2/gateway/agent/openapi/mcp`) is the ONLY video-generation provider in this project; honor its credit-approval gate and the human approval gate on publication.
7. On periodic scheduled jobs, research and save proposals only. **No Digen generation or public publishing without approval.**

## Official MCP Connections

- **vidIQ MCP**: `https://mcp.vidiq.com/mcp` — Add in Antigravity via **Settings / Additional Options (...) → MCP Servers** (OAuth login recommended, or read-only API key via `Authorization: Bearer ...` in `~/.gemini/config/mcp_config.json`).
- **Digen MCP**: `https://api.digen.ai/v2/gateway/agent/openapi/mcp` — Official Streamable HTTP MCP endpoint authenticated via `Authorization: Bearer <DIGEN_API_KEY>` in `~/.gemini/config/mcp_config.json` (never commit keys to Git).

## Research output format

Store dated `.md` research files in `research/`. For each item provide concept, original angle, 3 hook options, recommended top-tier upload slot, sources, type of research (`vidIQ` or `Gemini`), and limitations. Avoid copied scripts, thumbnails or falsely verified facts.
