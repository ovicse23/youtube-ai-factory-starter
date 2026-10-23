# Top-Tier Country (`US`, `UK`, `CA`, `AU`) YouTube Upload Best-Time Research

- **Observation Date:** `2026-10-23`
- **Provider Requested (`settings.json`):** `auto` (`fallback_to_gemini: true`)
- **Provider Actually Used:** `gemini` (Antigravity + live web research; `vidiq` MCP `https://mcp.vidiq.com/mcp` not yet authenticated)
- **Target Markets:** United States (`US`), United Kingdom (`UK`), Canada (`CA`), Australia (`AU`)
- **Creator Timezone (`settings.json`):** `Asia/Dhaka` (`UTC+06:00`)

---

## 1. Key Findings from Multi-Platform Studies & YouTube Guidance

1. **Shorts (`9:16`) and Long-Form (`16:9`) Peak at Different Hours**:
   - **Buffer's 2026 study (1.8M+ YouTube posts)** and **Sprout Social / vidIQ** analyses show that **YouTube Shorts** peak in late afternoon and evening mobile-scrolling windows (**16:00–21:00 local audience time**, strongest **Wednesday–Saturday**, with **Friday 16:00 local** ranking #1 overall in Buffer's dataset).
   - **Long-Form (`16:9`)** performs best when published **2–3 hours ahead** of North American/UK evening lean-back & Connected TV (CTV) peaks (**13:00–16:00 local weekday**) or during **weekend morning leisure** (**09:00–11:00 local Saturday/Sunday**, with **Sunday 10:00** ranking #1 overall for long-form in Buffer's study).

2. **Cross-Atlantic Overlap Math (`US` + `UK` + `CA`)**:
   - Because `Europe/London` is **5 hours ahead** of `America/New_York` / `America/Toronto` (4 hours during brief spring/autumn DST transition weeks), publishing at **12:00–14:00 US Eastern** simultaneously hits:
     - **UK (`17:00–19:00`):** Post-work / post-school evening prime mobile & desktop viewing.
     - **US & Canada East (`12:00–14:00`):** Midday lunch & early afternoon mobile scroll.
     - **US & Canada West (`09:00–11:00`):** Morning active window.

3. **Handling Australia (`AU`) Without Hurting `US` / `UK` Velocity**:
   - `Australia/Sydney` (`UTC+10` / `UTC+11` AEDT) is **15 hours ahead** of `America/New_York` on `2026-10-23`.
   - A secondary slot at **16:00–18:00 US Eastern** hits **US/CA late afternoon**, **US Pacific 13:00–15:00**, and **Sydney 07:00–09:00 (+1d)** morning commute—ideal for Friday/Saturday Shorts rotation.

4. **Mandatory `PRIVATE` Upload Indexing & QA Buffer**:
   - Always upload via `scripts/youtube_upload.py` as **`private`** **1–2 hours** (Shorts) or **2–3 hours** (Long-Form) *before* scheduled public release. This ensures 1080p/4K transcoding, automated copyright checks, and synthetic-media metadata settle before first impressions go out.

5. **YouTube's Official Algorithmic Caveat & 28-Day Override Rule**:
   - Per YouTube Creator Liaison & YouTube Help, upload clock-time does **not** cap long-term algorithmic reach; it optimizes **initial 24–48h subscriber and seed-audience velocity**.
   - Once your channel accumulates ~28 days of traffic, **YouTube Studio → Analytics → Audience → "When your viewers are on YouTube"** supersedes generic industry studies: schedule public release **1–2 hours before** your darkest purple heatmap bar.

---

## 2. DST-Aware Schedule Conversion Table (Reference Date: `2026-10-23`)

> Recompute anytime for winter/summer DST shifts using:
> `python3 factory.py upload-plan --aspect 9:16 --date YYYY-MM-DD`

### A. YouTube Shorts (`9:16`)

| Slot | Best Days | Action | `Asia/Dhaka` (`+06`) | `UTC` | `US/CA Eastern` (`EDT`) | `UK` (`BST`) | `AU Sydney` (`AEDT`) |
|:--|:--|:--|:--|:--|:--|:--|:--|
| **1. Primary US+UK+CA Overlap** | Wed, Thu, Fri (Tue) | Upload `PRIVATE` | **20:00–22:00** | 14:00–16:00 | 10:00–12:00 | 15:00–17:00 | 01:00–03:00 (+1d) |
| **1. Primary US+UK+CA Overlap** | Wed, Thu, Fri (Tue) | Schedule `PUBLIC` | **22:00–00:00 (+1d)** | 16:00–18:00 | **12:00–14:00** | **17:00–19:00** | 03:00–05:00 (+1d) |
| **2. Secondary US Peak + AU Morning** | Fri, Thu, Sat | Upload `PRIVATE` | **00:00–02:00 (+1d)** | 18:00–20:00 | 14:00–16:00 | 19:00–21:00 | 05:00–07:00 (+1d) |
| **2. Secondary US Peak + AU Morning** | Fri, Thu, Sat | Schedule `PUBLIC` | **02:00–04:00 (+1d)** | 20:00–22:00 | **16:00–18:00** | 21:00–23:00 | **07:00–09:00 (+1d)** |

*(Note: After US clocks fall back to `EST` in November while `Asia/Dhaka` stays `UTC+06`, `12:00–14:00 EST` becomes `23:00–01:00 (+1d)` in `Asia/Dhaka`. Always run `python3 factory.py upload-plan` on upload day.)*

### B. Long-Form Videos (`16:9`)

| Slot | Best Days | Action | `Asia/Dhaka` (`+06`) | `UTC` | `US/CA Eastern` (`EDT`) | `UK` (`BST`) | `AU Sydney` (`AEDT`) |
|:--|:--|:--|:--|:--|:--|:--|:--|
| **1. Weekday US+UK+CA Pre-Peak** | Wed, Thu, Fri | Upload `PRIVATE` | **20:00–22:00** | 14:00–16:00 | 10:00–12:00 | 15:00–17:00 | 01:00–03:00 (+1d) |
| **1. Weekday US+UK+CA Pre-Peak** | Wed, Thu, Fri | Schedule `PUBLIC` | **23:00–01:00 (+1d)** | 17:00–19:00 | **13:00–15:00** | **18:00–20:00** | 04:00–06:00 (+1d) |
| **2. Weekend Leisure Peak** | Sun, Sat | Upload `PRIVATE` | **17:00–18:30** | 11:00–12:30 | 07:00–08:30 | 12:00–13:30 | 22:00–23:30 |
| **2. Weekend Leisure Peak** | Sun, Sat | Schedule `PUBLIC` | **19:00–21:00** | 13:00–15:00 | **09:00–11:00** | **14:00–16:00** | 00:00–02:00 (+1d) |

---

## 3. Dated Verifiable Sources (`Observed: 2026-10-23`)

1. **Buffer — Best Time to Post on YouTube (1.8M+ YouTube videos/Shorts study):** `https://buffer.com/resources/best-time-to-post-on-youtube/`
2. **Sprout Social — Best Times to Post on YouTube:** `https://sproutsocial.com/insights/best-times-to-post-on-youtube/`
3. **vidIQ — Best Time to Post YouTube Videos & Shorts:** `https://vidiq.com/blog/post/best-time-to-post-youtube-videos/`
4. **Google / YouTube Help — When your viewers are on YouTube (Audience tab):** `https://support.google.com/youtube/answer/10343433`
