---
name: quality-publish
description: Perform final video technical and editorial quality checks, verify top-tier country upload timing, prepare metadata, and optionally upload a reviewed video privately to YouTube using OAuth.
---

# Quality and publishing

Before publishing:
1. Verify scene completeness, `output/final.mp4` opens and plays cleanly, speech/music licensed, text/narration accuracy, audio levels, visual consistency, originality, no misleading title or thumbnail, AI/synthetic media disclosure (`contains_synthetic_media`), and explicit `made_for_kids` classification (`true` or `false`).
2. Verify **Top-Tier Country Upload Timing**: check `episodes/<slug>/upload-schedule.txt` (or run `python3 factory.py upload-plan --aspect <9:16|16:9>`) so the **PRIVATE** upload happens at least **1–2 hours** (Shorts) or **2–3 hours** (Long-Form) ahead of the target `US`/`UK`/`CA`/`AU` overlap window in `publishing.creator_timezone`.
3. Export QA checklist to `episodes/<slug>/qa.md`.
4. Ensure human reviewer explicitly approves the finished video and record that by setting `status` in `episode.json` to `approved-for-upload`.
5. Run `python3 scripts/youtube_upload.py <slug>` (dry-run first, then `--confirm-private-upload` after owner sign-off). The uploader ALWAYS sets privacy to `private`; it never publishes publicly or bypasses account verification. OAuth credentials (`client_secrets.json`, `youtube_token.json`) stay strictly inside gitignored `.secrets/`.
6. After `private` upload completes and HD/copyright checks pass in YouTube Studio, the owner manually schedules public release for the chosen Top-Tier window (and transitions to YouTube Studio's *"When your viewers are on YouTube"* heatmap once 28+ days of audience analytics exist).
