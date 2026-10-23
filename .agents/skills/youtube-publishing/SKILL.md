---
name: youtube-publishing
description: Manage official YouTube Data API OAuth connections, execute private-first uploads, enforce human QA sign-off, and schedule public releases.
---

# YouTube Publishing Skill

Handles channel authentication, private uploads, and scheduled public releases via the official YouTube Data API.

## Mandatory Publishing Protocol

1. **Private Upload First**:
   - Every video must be uploaded with privacy status `private`.
   - Never publish directly to `public` without explicit human review and sign-off.

2. **Scheduled Release Timing**:
   - Set `status.publishAt` in RFC 3339 format (e.g. `2026-10-24T16:00:00Z`).
   - Align with the calculated Top-Tier audience window (12:00–14:00 US Eastern / 22:00–00:00 Asia/Dhaka).

3. **Human Quality Gate Sign-Off**:
   - Verify the 5-point QA checklist:
     1. Visual continuity inspected.
     2. Audio mix normalized (no clipping).
     3. Opening hook delivered under 3 seconds.
     4. Synthetic media disclosure tagged.
     5. Top-Tier country scheduled release window confirmed.

4. **Idempotent Job Execution**:
   - Prevent duplicate uploads by checking existing video records and YouTube upload IDs.
