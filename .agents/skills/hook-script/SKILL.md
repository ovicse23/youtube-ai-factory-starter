---
name: hook-script
description: Create memorable honest hooks, original scripts, storyboards, visual consistency guides, SEO briefs, and top-tier upload schedules for 30-90 second Shorts or longer videos.
---

# Hook and script writer

First consult `settings.json` and `.agents/skills/research-router/SKILL.md` for provenance rules. Given the selected original niche and a research source pack:
1. Develop 3 distinct openings of 1–3 seconds (surprise/contrast/problem) that honestly match the payoff; do not copy competitors.
2. Pick the strongest using an explained internal rubric: clarity, immediate visual question, distinctiveness, truthful payoff.
3. Write a beginning, escalation, reveal and satisfying ending; use a visual change or meaningful beat roughly every 3–6 seconds (not arbitrary cuts).
4. Split script into coherent 6–10-second visual shot prompts (or user-selected durations), with character identity bible, dialogue attribution, camera actions, ambient sound and emotional progression.
5. Save an episode JSON in the format of `examples/sample-episode.json` and run `python3 factory.py pack <slug>` so prompts, `seo-package.txt`, and `upload-schedule.txt` (DST-aware `US`/`UK`/`CA`/`AU` timing) are generated automatically. Script length must fit generated scene durations after narration read-through.
6. Create authentic channel-specific SEO and a distinct, mobile-readable thumbnail concept.
7. Explicitly identify claims requiring external fact-checking. Mark fictional content as fictional; do not impersonate real people.
