---
name: niche-scout
description: Research original YouTube channel niches, competitor patterns, underserved audiences, top-tier country upload windows, and idea opportunities with source links and uncertainty.
---

# Niche scout

First run the `research-router` skill and honor the research provider in `settings.json`; never use vidIQ when Gemini-only mode is selected.

1. Investigate 5 candidate original-video niches aimed primarily at top-tier English-speaking audiences (`US`, `UK`, `CA`, `AU`).
2. For each niche, record a representative competitor/topic list with accessible public URLs, observation dates, content quality, audience promise, saturation evidence, evergreen potential, production cost, and best format (`9:16` Shorts vs `16:9` Long-Form).
3. Pair each niche with its optimal **Top-Tier Country Upload Window** using `python3 factory.py upload-plan` (accounting for US/CA Eastern + UK evening overlap, Australia morning secondary slot, creator local timezone, and the 1–2h / 2–3h `private` upload indexing buffer).
4. Avoid assuming a high RPM or promising a viral outcome. Prioritize feasible concepts with original character/world ownership and coherent scene count (less credit intensive).
5. Rank using clearly labeled internal scoring: curiosity (20), distinction (20), production feasibility (25), evergreen potential (20), serial potential (15).
6. Save `research/niches-YYYY-MM-DD.md`, `research/ideas-YYYY-MM-DD.md`, and (if not yet present for the current cycle) `research/upload-timing-top-tier-YYYY-MM-DD.md`.
7. Never use scraped private competitor stats or made-up figures. Include a section on what could disprove your recommendations.
