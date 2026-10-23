# Quality & Publishing Checklist — `pilot-01` (*The Lantern Beneath Hawthorn Hollow*)

- **Episode Slug:** `pilot-01`
- **Format / Duration:** `9:16` YouTube Short (4 scenes × 8s = 32s target)
- **Research Backing:** `research/niches-2026-10-23.md`, `research/ideas-2026-10-23.md`, `research/upload-timing-top-tier-2026-10-23.md`

## Pre-Production Checks (Completed)
- [x] `episode.json` schema validated (`slug`, `title`, `niche`, `aspect`, `target_audience`, `script`, `scenes`, `seo`)
- [x] Fictional folklore framing explicitly disclosed in description (`contains_synthetic_media: true`)
- [x] `made_for_kids` explicitly set (`false` — general US/UK/CA/AU cozy folklore audience; confirm before final upload)
- [x] Visual continuity bible locks non-human character geometry ("Wick", russet leaf cloak, mossy bell-cap, hexagonal brass lantern)
- [x] Top-Tier (`US`, `UK`, `CA`, `AU`) upload schedule generated in `upload-schedule.txt`

## Production & Render Gate (Pending Owner Auth & Credit Approval)
- [ ] Authenticate Digen MCP (`https://api.digen.ai/v2/gateway/agent/openapi/mcp`) or `DIGEN_API_KEY`
- [ ] Approve Scene-01 credit spend and inspect `clips/scene-01.mp4` before generating Scenes 02–04
- [ ] Export `scene-01.mp4` .. `scene-04.mp4` (and optional `narration.wav`)
- [ ] Install `ffmpeg` (`brew install ffmpeg`) and run `python3 factory.py render pilot-01`
- [ ] Human review of `output/final.mp4` (audio balance, transitions, zero unwanted text)
- [ ] Set `status` in `episode.json` to `"approved-for-upload"`
- [ ] Upload as `PRIVATE` via `python3 scripts/youtube_upload.py pilot-01 --confirm-private-upload` during `20:00–22:00 Asia/Dhaka` (`10:00–12:00 EDT`), then schedule `PUBLIC` release in YouTube Studio for `22:00–00:00 Asia/Dhaka` (`12:00–14:00 EDT` / `17:00–19:00 BST` on Thu/Fri)
