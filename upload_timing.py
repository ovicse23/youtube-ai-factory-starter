"""Evidence-grounded YouTube upload & scheduling planner for Tier-1 markets.

Computes DST-aware private-upload and scheduled-publish windows across top-tier
English-speaking countries (US, UK, CA, AU) and converts them into UTC and the
creator's local timezone using Python's standard-library zoneinfo.

No external API calls or paid credits are used by this module.
"""
from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

TIER1_ZONES: dict[str, tuple[str, str]] = {
    "US": ("US Eastern (ET)", "America/New_York"),
    "US_PT": ("US Pacific (PT)", "America/Los_Angeles"),
    "CA": ("Canada Eastern", "America/Toronto"),
    "UK": ("United Kingdom", "Europe/London"),
    "AU": ("Australia East", "Australia/Sydney"),
    "NZ": ("New Zealand", "Pacific/Auckland"),
    "IE": ("Ireland", "Europe/Dublin"),
}

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    ("Buffer YouTube Timing Study (1.8M+ posts)", "https://buffer.com/resources/best-time-to-post-on-youtube/"),
    ("Sprout Social YouTube Posting Times", "https://sproutsocial.com/insights/best-times-to-post-on-youtube/"),
    ("vidIQ Best Time to Post on YouTube", "https://vidiq.com/blog/post/best-time-to-post-youtube-videos/"),
    ("YouTube Help — When Your Viewers Are on YouTube", "https://support.google.com/youtube/answer/10343433"),
)


def validate_timezone(tz_name: str) -> str:
    if not isinstance(tz_name, str) or not tz_name.strip():
        raise ValueError("Timezone must be a non-empty IANA timezone string (e.g. 'Asia/Dhaka' or 'UTC')")
    clean = tz_name.strip()
    try:
        ZoneInfo(clean)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown IANA timezone: {clean}") from exc
    return clean


def _parse_ref_date(ref_date: str | None) -> date:
    if not ref_date:
        return datetime.now(ZoneInfo("UTC")).date()
    return date.fromisoformat(ref_date)


def _convert_window(
    day: date,
    start_hm: tuple[int, int],
    end_hm: tuple[int, int],
    anchor_tz: str,
    target_tz: str,
) -> str:
    src = ZoneInfo(anchor_tz)
    dst = ZoneInfo(target_tz)
    start_dt = datetime.combine(day, time(*start_hm), tzinfo=src).astimezone(dst)
    end_dt = datetime.combine(day, time(*end_hm), tzinfo=src).astimezone(dst)
    day_shift = (start_dt.date() - day).days
    end_shift = (end_dt.date() - start_dt.date()).days
    shift_note = " (+1d)" if day_shift > 0 else (" (-1d)" if day_shift < 0 else "")
    cross_midnight = " (+1d)" if end_shift > 0 and day_shift == 0 else ""
    tz_abbr = start_dt.tzname() or target_tz
    return f"{start_dt.strftime('%H:%M')}–{end_dt.strftime('%H:%M')}{cross_midnight} {tz_abbr}{shift_note}"


def _active_market_zones(target_countries: list[str]) -> list[tuple[str, str]]:
    normalized = [c.strip().upper() for c in target_countries if isinstance(c, str) and c.strip()]
    zones: list[tuple[str, str]] = [("UTC", "UTC")]
    seen: set[str] = {"UTC"}
    for code in normalized:
        if code == "US":
            for key in ("US", "US_PT"):
                label, tz = TIER1_ZONES[key]
                if tz not in seen:
                    zones.append((label, tz))
                    seen.add(tz)
        elif code in TIER1_ZONES:
            label, tz = TIER1_ZONES[code]
            if tz not in seen:
                zones.append((label, tz))
                seen.add(tz)
    return zones


def compute_upload_windows(
    aspect: str = "9:16",
    target_countries: list[str] | None = None,
    creator_tz: str = "Asia/Dhaka",
    ref_date: str | None = None,
) -> dict:
    if aspect not in ("9:16", "16:9"):
        raise ValueError("aspect must be '9:16' (Shorts) or '16:9' (Long-form)")
    creator_tz = validate_timezone(creator_tz)
    countries = target_countries or ["US", "UK", "CA", "AU"]
    day = _parse_ref_date(ref_date)
    anchor = "America/New_York"

    if aspect == "9:16":
        format_label = "YouTube Shorts (9:16)"
        raw_slots = [
            {
                "id": "shorts_transatlantic_primary",
                "name": "Primary US + UK + CA Overlap Slot",
                "best_days": ["Wednesday", "Thursday", "Friday", "Tuesday"],
                "private_upload_et": ((10, 0), (12, 0)),
                "public_publish_et": ((12, 0), (14, 0)),
                "rationale": (
                    "Hits UK 17:00–19:00 prime post-work/school scroll simultaneously with "
                    "US/Canada Eastern 12:00–14:00 lunch/early-afternoon mobile break."
                ),
            },
            {
                "id": "shorts_na_pacific_au_secondary",
                "name": "Secondary US Afternoon/Evening + AU Morning Slot",
                "best_days": ["Friday", "Thursday", "Saturday"],
                "private_upload_et": ((14, 0), (16, 0)),
                "public_publish_et": ((16, 0), (18, 0)),
                "rationale": (
                    "Aligns with Buffer's top Friday 16:00 local Shorts slot, US Pacific afternoon, "
                    "and Australia East morning commute."
                ),
            },
        ]
    else:
        format_label = "Long-Form Video (16:9)"
        raw_slots = [
            {
                "id": "longform_weekday_overlap",
                "name": "Primary Weekday US + UK + CA Pre-Peak Slot",
                "best_days": ["Wednesday", "Thursday", "Friday"],
                "private_upload_et": ((10, 0), (12, 0)),
                "public_publish_et": ((13, 0), (15, 0)),
                "rationale": (
                    "Publishes 2–3 hours ahead of North American 17:00–21:00 CTV/lean-back peak "
                    "for indexing while landing directly in UK 18:00–20:00 evening viewing."
                ),
            },
            {
                "id": "longform_weekend_morning",
                "name": "Weekend Leisure Peak Slot",
                "best_days": ["Sunday", "Saturday"],
                "private_upload_et": ((7, 0), (8, 30)),
                "public_publish_et": ((9, 0), (11, 0)),
                "rationale": (
                    "Captures Sunday/Saturday 09:00–11:00 ET relaxed morning viewing (Buffer's #1 "
                    "overall long-form slot is Sunday 10:00) plus UK 14:00–16:00 afternoon."
                ),
            },
        ]

    market_zones = _active_market_zones(countries)
    slots_out = []
    for slot in raw_slots:
        u_start, u_end = slot["private_upload_et"]
        p_start, p_end = slot["public_publish_et"]
        conversions = {}
        for label, tz in market_zones:
            conversions[label] = {
                "timezone": tz,
                "private_upload": _convert_window(day, u_start, u_end, anchor, tz),
                "public_publish": _convert_window(day, p_start, p_end, anchor, tz),
            }
        creator_conv = {
            "timezone": creator_tz,
            "private_upload": _convert_window(day, u_start, u_end, anchor, creator_tz),
            "public_publish": _convert_window(day, p_start, p_end, anchor, creator_tz),
        }
        slots_out.append({
            "id": slot["id"],
            "name": slot["name"],
            "best_days": slot["best_days"],
            "rationale": slot["rationale"],
            "creator_local": creator_conv,
            "markets": conversions,
        })

    return {
        "reference_date": day.isoformat(),
        "aspect": aspect,
        "format": format_label,
        "target_countries": [c.strip().upper() for c in countries if isinstance(c, str) and c.strip()],
        "creator_timezone": creator_tz,
        "slots": slots_out,
        "workflow_rules": [
            "Upload via scripts/youtube_upload.py as PRIVATE at least 1–2 hours (Shorts) or 2–3 hours (Long-form) before target public release so HD/4K processing, copyright checks, and synthetic-media labels settle.",
            "Schedule the PRIVATE -> PUBLIC transition manually inside YouTube Studio after human review.",
            "Upload timing optimizes initial 24–48h velocity only; hook retention, Viewed-vs-Swiped-Away %, and CTR govern long-term reach.",
            "Once your channel has ~28 days of audience data, override generic windows with YouTube Studio -> Analytics -> Audience -> 'When your viewers are on YouTube' (publish 1–2 hours before your darkest purple bar).",
        ],
        "sources": [{"title": title, "url": url} for title, url in RESEARCH_SOURCES],
    }


def format_upload_plan(
    aspect: str = "9:16",
    target_countries: list[str] | None = None,
    creator_tz: str = "Asia/Dhaka",
    ref_date: str | None = None,
) -> str:
    plan = compute_upload_windows(
        aspect=aspect,
        target_countries=target_countries,
        creator_tz=creator_tz,
        ref_date=ref_date,
    )
    lines = [
        f"TOP-TIER COUNTRY UPLOAD & SCHEDULE PLAN — {plan['format']}",
        f"Reference date (DST-aware): {plan['reference_date']} | Markets: {', '.join(plan['target_countries'])} | Creator TZ: {plan['creator_timezone']}",
        "",
    ]
    for idx, slot in enumerate(plan["slots"], 1):
        lines.append(f"{idx}. {slot['name']}")
        lines.append(f"   Best days: {', '.join(slot['best_days'])}")
        lines.append(
            f"   Creator local ({slot['creator_local']['timezone']}): "
            f"Upload PRIVATE {slot['creator_local']['private_upload']} -> Schedule PUBLIC {slot['creator_local']['public_publish']}"
        )
        for label, conv in slot["markets"].items():
            lines.append(
                f"   - {label} ({conv['timezone']}): "
                f"Private {conv['private_upload']} | Public {conv['public_publish']}"
            )
        lines.append(f"   Why: {slot['rationale']}")
        lines.append("")

    lines.append("PUBLISHING & ANALYTICS SAFEGUARDS:")
    for rule in plan["workflow_rules"]:
        lines.append(f"- {rule}")
    lines.append("")
    lines.append("EVIDENCE SOURCES:")
    for src in plan["sources"]:
        lines.append(f"- {src['title']}: {src['url']}")
    return "\n".join(lines)
