#!/usr/bin/env python3
"""Local SQLite + workspace file store implementing cloudflare/schema.sql.

Bridges the Local Engine (Antigravity + MCP + FFmpeg + episodes/*) with the
Cloudflare Control Center (Workers + D1 + R2 + Production Job Queue).
"""
from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_router import load_settings, save_settings, validate
from upload_timing import compute_upload_windows, format_upload_plan

ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT / "cloudflare" / "schema.sql"
DEFAULT_DB_PATH = ROOT / ".local" / "factory.db"

VIDIQ_LEDGER = {
    "planName": "Max",
    "totalCredits": 6142,
    "maxRenewableCredits": 6000,
    "addOnCredits": 200,
    "metricsAsOf": "2026-10-22T09:42:31Z",
    "digenWorkflow": "skill_agent (v21 active)",
    "digenMcpEndpoint": "https://api.digen.ai/v2/gateway/agent/openapi/mcp",
    "vidiqMcpEndpoint": "https://mcp.vidiq.com/mcp",
}

VIDIQ_KEYWORDS = [
    {
        "keyword": "miniature diorama",
        "overall": 67.5,
        "competition": 26.8,
        "competitionLabel": "Low",
        "monthlySearches": "18,555",
        "usVolume": "unknown (null)",
        "growth30d": "+118.7%",
        "topOpportunity": "diy diorama / satisfying video (88.4K US)",
    },
    {
        "keyword": "animated short film",
        "overall": 66.9,
        "competition": 56.0,
        "competitionLabel": "Medium",
        "monthlySearches": "323,517",
        "usVolume": "32,105",
        "growth30d": "+126.6%",
        "topOpportunity": "short film (69.4 overall, 141.9K US)",
    },
    {
        "keyword": "how things work",
        "overall": 65.3,
        "competition": 54.0,
        "competitionLabel": "Medium",
        "monthlySearches": "173,105",
        "usVolume": "18,933",
        "growth30d": "+25.5%",
        "topOpportunity": "everything professor (70.4 overall)",
    },
    {
        "keyword": "deep sea creatures",
        "overall": 64.8,
        "competition": 59.0,
        "competitionLabel": "Medium",
        "monthlySearches": "254,959",
        "usVolume": "17,847",
        "growth30d": "-21.6%",
        "topOpportunity": "deep sea mysteries (69.4 overall, 37.7 comp)",
    },
    {
        "keyword": "forgotten history",
        "overall": 62.6,
        "competition": 63.0,
        "competitionLabel": "Med-High",
        "monthlySearches": "215,889",
        "usVolume": "15,606",
        "growth30d": "-14.4%",
        "topOpportunity": "world war 2 (67.6 overall, 58.5 comp)",
    },
]

SEED_CHANNELS = [
    {
        "id": "ch-hawthorn",
        "name": "Hawthorn Hollow Miniatures",
        "handle": "@hawthornhollow",
        "niche": "Cozy Miniature Diorama Folklore",
        "default_aspect": "9:16",
        "target_countries": ["US", "UK", "CA", "AU"],
        "creator_timezone": "Asia/Dhaka",
        "studio_heatmap_override": "",
        "status": "active",
    },
    {
        "id": "ch-mechanics",
        "name": "Everyday Hidden Mechanics 3D",
        "handle": "@hiddenmechanics3d",
        "niche": "Everyday Hidden Mechanics",
        "default_aspect": "9:16",
        "target_countries": ["US", "UK", "CA", "AU"],
        "creator_timezone": "Asia/Dhaka",
        "studio_heatmap_override": "",
        "status": "pilot-ready",
    },
]

SEED_IDEAS = [
    {
        "id": "idea-miniature-folklore",
        "channel_id": "ch-hawthorn",
        "title": "The Lantern Beneath Hawthorn Hollow",
        "niche": "Cozy Miniature Diorama Folklore",
        "score": 91,
        "rubric": "Curiosity 18/20 · Distinction 19/20 · Digen 23/25 · Evergreen 17/20 · Serial 14/15",
        "aspect": "9:16",
        "vidiq_summary": "67.5/100 overall · 26.8 Low competition · +118.7% 30d search growth",
        "promise": "Tilt-shift moss-and-brass miniature dioramas bringing 32-second UK & North American woodland micro-myths to life with recurring non-human sprite Wick.",
        "upload_slot": "Thu/Fri 12:00–14:00 ET (22:00–00:00 BDT)",
        "hooks": [
            "Every autumn in the British hills, hikers spot tiny brass lanterns glowing beneath hawthorn roots.",
            "When frost hits the hollow, one acorn-sized keeper has eight seconds before the last ember dies.",
            "Look closely inside this mossy oak root—someone left the porch light on.",
        ],
        "sources": [
            {"label": "PBS Storied / Monstrum", "url": "https://www.youtube.com/@pbsstoried"},
            {"label": "YouTube Miniature Diorama", "url": "https://www.youtube.com/results?search_query=miniature+folklore+diorama"},
        ],
        "status": "in-production",
    },
    {
        "id": "idea-airplane-window",
        "channel_id": "ch-mechanics",
        "title": "Why Airplane Windows Have That Tiny Hole",
        "niche": "Everyday Hidden Mechanics",
        "score": 89,
        "rubric": "Curiosity 19/20 · Distinction 17/20 · Digen 21/25 · Evergreen 19/20 · Serial 13/15",
        "aspect": "9:16",
        "vidiq_summary": "65.3/100 overall · 173,105/mo searches (+25.5% 30d) · 18,933 US volume",
        "promise": "Stylized 3D cutaway micro-documentary showing how a 1mm bleed hole balances cabin air pressure across three acrylic panes at 35,000 feet.",
        "upload_slot": "Wed/Thu/Fri 12:00–14:00 ET (22:00–00:00 BDT)",
        "hooks": [
            "There is an intentional hole drilled right through your airplane window—and it keeps the cabin pane from shattering.",
            "At 35,000 feet, three thin layers hold back freezing air thanks to a one-millimeter bleed hole.",
            "Slice an airliner window in half and you'll spot a tiny tunnel doing a life-saving job.",
        ],
        "sources": [
            {"label": "How Things Work", "url": "https://www.youtube.com/@YoutubeHowThingsWork"},
            {"label": "Practical Engineering", "url": "https://www.youtube.com/@PracticalEngineeringChannel"},
        ],
        "status": "shortlisted",
    },
    {
        "id": "idea-tiny-rover",
        "channel_id": "ch-hawthorn",
        "title": "Unit Bramble and the Last Lunar Dandelion",
        "niche": "Tiny Rover Chronicles (Cozy Sci-Fi)",
        "score": 86,
        "rubric": "Curiosity 17/20 · Distinction 18/20 · Digen 23/25 · Evergreen 15/20 · Serial 13/15",
        "aspect": "9:16",
        "vidiq_summary": "66.9/100 overall · 323,517/mo (+126.6% 30d) · 32,105 US volume",
        "promise": "Isometric macro dispatch following palm-sized repair rover 'Unit Bramble' tending forgotten terrarium domes across quiet moons.",
        "upload_slot": "Fri/Sat 16:00–18:00 ET (02:00–04:00 BDT +1d)",
        "hooks": [
            "Sixty years after humans left Outpost Nine, the smallest rover found something impossible growing in the dust.",
            "Sunset on this moon lasts two freezing weeks—and Unit Bramble just found one flower outside the dome.",
            "His battery hit four percent right when his botanical scanner turned green for the first time in a century.",
        ],
        "sources": [{"label": "DUST Sci-Fi Shorts", "url": "https://www.youtube.com/@watchdust"}],
        "status": "shortlisted",
    },
    {
        "id": "idea-abyssal-squid",
        "channel_id": "ch-mechanics",
        "title": "How Deep-Sea Squid Use Light to Disappear",
        "niche": "Abyssal & Microscopic Mysteries",
        "score": 82,
        "rubric": "Curiosity 18/20 · Distinction 16/20 · Digen 19/25 · Evergreen 17/20 · Serial 12/15",
        "aspect": "9:16",
        "vidiq_summary": "'deep sea mysteries' sub-niche: 69.4/100 overall · 37.7 Low-Med competition",
        "promise": "Clearly labeled 3D scientific visualization unpacking real deep-sea counter-illumination and bioluminescent defense mechanisms.",
        "upload_slot": "Thu/Fri 12:00–14:00 ET (22:00–00:00 BDT)",
        "hooks": [
            "Half a mile beneath the ocean surface, this creature turns on belly headlights to become completely invisible.",
            "In pitch-black water, flashing bright blue is actually how tiny shrimp escape giant predators.",
            "What looks like glowing stardust in ocean waves is a microscopic burglar alarm.",
        ],
        "sources": [
            {"label": "MBARI", "url": "https://www.youtube.com/@MBARIvideo"},
            {"label": "EV Nautilus", "url": "https://www.youtube.com/@EVNautilus"},
        ],
        "status": "shortlisted",
    },
    {
        "id": "idea-clockwork-hat",
        "channel_id": "ch-mechanics",
        "title": "The Self-Tipping Clockwork Hat of 1896",
        "niche": "Forgotten Industrial Oddities",
        "score": 79,
        "rubric": "Curiosity 19/20 · Distinction 15/20 · Digen 17/25 · Evergreen 17/20 · Serial 11/15",
        "aspect": "9:16",
        "vidiq_summary": "62.6/100 overall · 63.0 competition · requires ultra-specific patent angles",
        "promise": "Dry-witted animated micro-history about US Patent No. 556,248—an 1896 bowler hat that tipped itself politely via clockwork gears.",
        "upload_slot": "Tue/Wed/Thu 12:00–14:00 ET (22:00–00:00 BDT)",
        "hooks": [
            "In 1896, inventors patented a hat that tipped itself politely—using clockwork gears strapped to your forehead.",
            "Before electronic alarms, British factory towns paid a worker with a twelve-foot pea-shooter to tap upstairs windows.",
            "Victorian parlor catalogs briefly sold cast-iron mechanical rocking chairs that fanned your face while you read.",
        ],
        "sources": [
            {"label": "Simple History", "url": "https://www.youtube.com/@Simplehistory"},
            {"label": "Weird History", "url": "https://www.youtube.com/@WeirdHistory"},
        ],
        "status": "backlog",
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    return cleaned[:64] or f"ep-{uuid.uuid4().hex[:6]}"


class HybridStore:
    """Unified SQLite + local filesystem repository for the Hybrid Control Center."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH, workspace_root: Path = ROOT):
        self.db_path = Path(db_path)
        self.workspace_root = Path(workspace_root)
        self.settings_path = self.workspace_root / "settings.json"
        self.episodes_dir = self.workspace_root / "episodes"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        now = _now()
        with self._connect() as conn:
            conn.executescript(schema_sql)
            # Seed settings from workspace settings.json if absent
            row = conn.execute("SELECT settings_json FROM yaf_settings WHERE id = 'global'").fetchone()
            if not row:
                s = load_settings(self.settings_path)
                conn.execute(
                    "INSERT INTO yaf_settings (id, settings_json, updated_at) VALUES ('global', ?, ?)",
                    (json.dumps(s), now),
                )
            # Seed channels if empty
            if conn.execute("SELECT COUNT(*) FROM yaf_channels").fetchone()[0] == 0:
                for ch in SEED_CHANNELS:
                    conn.execute(
                        """INSERT INTO yaf_channels
                           (id, name, handle, niche, default_aspect, target_countries_json,
                            creator_timezone, studio_heatmap_override, status, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            ch["id"],
                            ch["name"],
                            ch["handle"],
                            ch["niche"],
                            ch["default_aspect"],
                            json.dumps(ch["target_countries"]),
                            ch["creator_timezone"],
                            ch["studio_heatmap_override"],
                            ch["status"],
                            now,
                            now,
                        ),
                    )
            # Seed ideas if empty
            if conn.execute("SELECT COUNT(*) FROM yaf_ideas").fetchone()[0] == 0:
                for idea in SEED_IDEAS:
                    conn.execute(
                        """INSERT INTO yaf_ideas
                           (id, channel_id, title, niche, score, rubric, aspect, vidiq_summary,
                            promise, upload_slot, hooks_json, sources_json, status, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            idea["id"],
                            idea["channel_id"],
                            idea["title"],
                            idea["niche"],
                            idea["score"],
                            idea["rubric"],
                            idea["aspect"],
                            idea["vidiq_summary"],
                            idea["promise"],
                            idea["upload_slot"],
                            json.dumps(idea["hooks"]),
                            json.dumps(idea["sources"]),
                            idea["status"],
                            now,
                            now,
                        ),
                    )
            # Sync workspace episodes/*/episode.json into yaf_videos + yaf_approvals
            if self.episodes_dir.is_dir():
                for ep_file in sorted(self.episodes_dir.glob("*/episode.json")):
                    try:
                        ep = json.loads(ep_file.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        continue
                    slug = ep.get("slug") or ep_file.parent.name
                    ep["slug"] = slug
                    ep = self._enrich_local_clip_state(ep)
                    existing = conn.execute("SELECT slug FROM yaf_videos WHERE slug = ?", (slug,)).fetchone()
                    if not existing:
                        ch_id = "ch-mechanics" if "mechanic" in ep.get("niche", "").lower() else "ch-hawthorn"
                        conn.execute(
                            """INSERT INTO yaf_videos
                               (slug, channel_id, title, niche, aspect, status, episode_json,
                                r2_final_key, r2_thumb_key, created_at, updated_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, '', '', ?, ?)""",
                            (
                                slug,
                                ch_id,
                                ep.get("title", slug),
                                ep.get("niche", "General"),
                                ep.get("aspect", "9:16"),
                                ep.get("status", "draft"),
                                json.dumps(ep, ensure_ascii=False),
                                ep.get("created_at", now),
                                now,
                            ),
                        )
                    if not conn.execute("SELECT video_slug FROM yaf_approvals WHERE video_slug = ?", (slug,)).fetchone():
                        conn.execute(
                            """INSERT INTO yaf_approvals
                               (video_slug, digen_scene1_approved, digen_remaining_approved, qa_approved,
                                qa_checks_json, private_upload_approved, scheduled_publish_window, notes, updated_at)
                               VALUES (?, 0, 0, 0, '[false,false,false,false,false]', 0,
                                       'Wed/Thu/Fri 22:00–00:00 Asia/Dhaka (12:00–14:00 US ET / 17:00–19:00 UK)',
                                       'Scene-01 credit gate pending owner approval.', ?)""",
                            (slug, now),
                        )
            # Seed starter production queue job if empty
            if conn.execute("SELECT COUNT(*) FROM yaf_jobs").fetchone()[0] == 0:
                conn.execute(
                    """INSERT INTO yaf_jobs
                       (id, channel_id, video_slug, job_type, target_runner, status, payload_json, result_summary, created_at, updated_at)
                       VALUES (?, 'ch-hawthorn', 'pilot-01', 'pack_prompts', 'local_engine', 'completed',
                               '{"scenes":4,"aspect":"9:16"}', 'Packed 4 Digen prompts + US/UK/CA/AU upload schedule locally.', ?, ?)""",
                    ("job-seed-pack-01", now, now),
                )
                conn.execute(
                    """INSERT INTO yaf_jobs
                       (id, channel_id, video_slug, job_type, target_runner, status, payload_json, result_summary, created_at, updated_at)
                       VALUES (?, 'ch-hawthorn', 'pilot-01', 'digen_scene_01', 'local_engine', 'awaiting_approval',
                               '{"scene":1,"credits_gate":"required"}', 'Waiting for human Scene-01 credit approval.', ?, ?)""",
                    ("job-seed-digen-01", now, now),
                )

    def _enrich_local_clip_state(self, ep: dict[str, Any]) -> dict[str, Any]:
        slug = ep.get("slug", "")
        ep_dir = self.episodes_dir / slug
        scenes = ep.get("scenes", [])
        for idx, sc in enumerate(scenes, 1):
            clip = ep_dir / "clips" / f"scene-{idx:02d}.mp4"
            if clip.is_file() and clip.stat().st_size > 0:
                sc["clipStatus"] = "ready"
                sc["clipUrl"] = f"/api/media/{slug}/scene-{idx:02d}.mp4"
            else:
                sc.setdefault("clipStatus", "missing")
                sc.setdefault("clipUrl", "")
        if "hooks" not in ep or not ep["hooks"]:
            ep["hooks"] = [
                ep.get("script", "").split(".")[0].strip() + "." if ep.get("script") else "Opening visual hook.",
                "Alternative high-stakes problem hook for seconds 1–3.",
                "Direct close-up visual curiosity hook with zero preamble.",
            ]
        ep.setdefault("contains_synthetic_media", True)
        ep.setdefault("made_for_kids", False)
        return ep

    def get_settings(self) -> dict[str, Any]:
        if self.settings_path.is_file():
            return load_settings(self.settings_path)
        with self._connect() as conn:
            row = conn.execute("SELECT settings_json FROM yaf_settings WHERE id = 'global'").fetchone()
            return validate(json.loads(row["settings_json"])) if row else load_settings(self.settings_path)

    def update_settings(self, patch: dict[str, Any]) -> dict[str, Any]:
        allowed = {"provider", "depth", "fallback_to_gemini", "target_countries", "creator_timezone"}
        if not isinstance(patch, dict) or set(patch) - allowed:
            raise ValueError("Only provider, depth, fallback_to_gemini, target_countries, and creator_timezone can be updated")
        current = self.get_settings()
        clean = dict(patch)
        if "creator_timezone" in clean:
            current["publishing"]["creator_timezone"] = clean.pop("creator_timezone")
        current["research"].update(clean)
        saved = save_settings(current, self.settings_path)
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO yaf_settings (id, settings_json, updated_at) VALUES ('global', ?, ?)",
                (json.dumps(saved), _now()),
            )
        return saved

    def list_channels(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM yaf_channels ORDER BY created_at ASC").fetchall()
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "handle": r["handle"],
                "niche": r["niche"],
                "default_aspect": r["default_aspect"],
                "target_countries": json.loads(r["target_countries_json"]),
                "creator_timezone": r["creator_timezone"],
                "studio_heatmap_override": r["studio_heatmap_override"],
                "status": r["status"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    def upsert_channel(self, data: dict[str, Any]) -> dict[str, Any]:
        name = str(data.get("name", "")).strip()
        if not name:
            raise ValueError("Channel name is required")
        ch_id = _slugify(str(data.get("id") or f"ch-{name}"))
        handle = str(data.get("handle") or f"@{_slugify(name).replace('-', '')}").strip()
        if not handle.startswith("@"):
            handle = "@" + handle
        niche = str(data.get("niche") or "Original Micro-Stories").strip()
        aspect = str(data.get("default_aspect") or "9:16")
        if aspect not in ("9:16", "16:9"):
            raise ValueError("default_aspect must be 9:16 or 16:9")
        countries = data.get("target_countries") or ["US", "UK", "CA", "AU"]
        if isinstance(countries, str):
            countries = [c.strip().upper() for c in countries.split(",") if c.strip()]
        creator_tz = str(data.get("creator_timezone") or "Asia/Dhaka").strip()
        validate({"publishing": {"creator_timezone": creator_tz}})
        heatmap = str(data.get("studio_heatmap_override") or "").strip()[:300]
        status = str(data.get("status") or "active").strip()
        now = _now()
        with self._connect() as conn:
            existing = conn.execute("SELECT created_at FROM yaf_channels WHERE id = ?", (ch_id,)).fetchone()
            created_at = existing["created_at"] if existing else now
            conn.execute(
                """INSERT OR REPLACE INTO yaf_channels
                   (id, name, handle, niche, default_aspect, target_countries_json,
                    creator_timezone, studio_heatmap_override, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (ch_id, name, handle, niche, aspect, json.dumps(countries), creator_tz, heatmap, status, created_at, now),
            )
        return next(c for c in self.list_channels() if c["id"] == ch_id)

    def list_ideas(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM yaf_ideas ORDER BY score DESC, updated_at DESC").fetchall()
        return [
            {
                "id": r["id"],
                "channel_id": r["channel_id"],
                "title": r["title"],
                "niche": r["niche"],
                "score": r["score"],
                "rubric": r["rubric"],
                "aspect": r["aspect"],
                "vidiq_summary": r["vidiq_summary"],
                "promise": r["promise"],
                "upload_slot": r["upload_slot"],
                "hooks": json.loads(r["hooks_json"]),
                "sources": json.loads(r["sources_json"]),
                "status": r["status"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    def upsert_idea(self, data: dict[str, Any]) -> dict[str, Any]:
        title = str(data.get("title", "")).strip()
        if not title:
            raise ValueError("Idea title is required")
        idea_id = _slugify(str(data.get("id") or f"idea-{title}"))
        channel_id = str(data.get("channel_id") or "ch-hawthorn").strip()
        niche = str(data.get("niche") or "General Original Format").strip()
        score = max(1, min(100, int(data.get("score", 82))))
        aspect = str(data.get("aspect") or "9:16")
        if aspect not in ("9:16", "16:9"):
            raise ValueError("aspect must be 9:16 or 16:9")
        hooks = data.get("hooks") or []
        if isinstance(hooks, str):
            hooks = [h.strip() for h in hooks.splitlines() if h.strip()]
        sources = data.get("sources") or []
        now = _now()
        with self._connect() as conn:
            existing = conn.execute("SELECT created_at FROM yaf_ideas WHERE id = ?", (idea_id,)).fetchone()
            created_at = existing["created_at"] if existing else now
            conn.execute(
                """INSERT OR REPLACE INTO yaf_ideas
                   (id, channel_id, title, niche, score, rubric, aspect, vidiq_summary,
                    promise, upload_slot, hooks_json, sources_json, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    idea_id,
                    channel_id,
                    title,
                    niche,
                    score,
                    str(data.get("rubric") or f"Composite Score {score}/100"),
                    aspect,
                    str(data.get("vidiq_summary") or "Manual / Gemini qualitative entry (unverified search volume)"),
                    str(data.get("promise") or ""),
                    str(data.get("upload_slot") or "Wed/Thu/Fri 12:00–14:00 ET (22:00–00:00 BDT)"),
                    json.dumps(hooks),
                    json.dumps(sources),
                    str(data.get("status") or "shortlisted"),
                    created_at,
                    now,
                ),
            )
        return next(i for i in self.list_ideas() if i["id"] == idea_id)

    def list_videos(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM yaf_videos ORDER BY updated_at DESC").fetchall()
        videos = []
        for r in rows:
            ep = json.loads(r["episode_json"])
            ep["slug"] = r["slug"]
            ep["channel_id"] = r["channel_id"]
            ep["status"] = r["status"]
            ep["r2_final_key"] = r["r2_final_key"]
            ep["r2_thumb_key"] = r["r2_thumb_key"]
            ep = self._enrich_local_clip_state(ep)
            videos.append(ep)
        return videos

    def _write_local_episode_files(self, ep: dict[str, Any]) -> None:
        slug = ep["slug"]
        ep_dir = self.episodes_dir / slug
        (ep_dir / "clips").mkdir(parents=True, exist_ok=True)
        (ep_dir / "prompts").mkdir(parents=True, exist_ok=True)
        (ep_dir / "episode.json").write_text(json.dumps(ep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        for idx, s in enumerate(ep.get("scenes", []), 1):
            prompt_txt = (
                f"PROJECT: {ep['title']}\n"
                f"ASPECT RATIO: {ep['aspect']}\n"
                f"TARGET DURATION: {s['duration_seconds']} seconds\n"
                f"GLOBAL CONTINUITY: {ep.get('style_bible', 'Maintain visual continuity.')}\n"
                f"SCENE {idx:02d}: {s.get('name', 'Untitled')}\n"
                f"VIDEO PROMPT:\n{s['prompt']}\n"
                f"NARRATION/VOICE (if supported): {s.get('narration', '')}\n"
                "Avoid copyrighted characters, deceptive realism and unwanted on-screen text.\n"
            )
            (ep_dir / "prompts" / f"scene-{idx:02d}.txt").write_text(prompt_txt, encoding="utf-8")
        settings = self.get_settings()
        upload_plan = format_upload_plan(
            aspect=ep["aspect"],
            target_countries=settings["research"]["target_countries"],
            creator_tz=settings["publishing"]["creator_timezone"],
        )
        (ep_dir / "upload-schedule.txt").write_text(upload_plan + "\n", encoding="utf-8")
        seo = ep.get("seo", {})
        seo_txt = (
            f"TITLE: {seo.get('title', ep['title'])}\n\n"
            f"DESCRIPTION:\n{seo.get('description', '')}\n\n"
            f"TAGS: {', '.join(seo.get('tags', []))}\n\n"
            f"THUMBNAIL BRIEF:\n{seo.get('thumbnail_brief', '')}\n\n"
            f"---\n{upload_plan}\n"
        )
        (ep_dir / "seo-package.txt").write_text(seo_txt, encoding="utf-8")
        (ep_dir / "narration.txt").write_text(ep.get("script", "").strip() + "\n", encoding="utf-8")

    def upsert_video(self, data: dict[str, Any]) -> dict[str, Any]:
        slug = _slugify(str(data.get("slug") or data.get("title") or ""))
        title = str(data.get("title") or slug).strip()
        niche = str(data.get("niche") or "Original Micro-Stories").strip()
        aspect = str(data.get("aspect") or "9:16")
        if aspect not in ("9:16", "16:9"):
            raise ValueError("aspect must be 9:16 or 16:9")
        scenes = data.get("scenes") or []
        if not isinstance(scenes, list) or not scenes:
            raise ValueError("Video episode must include at least 1 scene")
        normalized_scenes = []
        for idx, s in enumerate(scenes, 1):
            dur = max(1, min(120, int(s.get("duration_seconds", 8))))
            prompt = str(s.get("prompt") or "").strip()
            if not prompt:
                raise ValueError(f"Scene {idx} prompt cannot be empty")
            normalized_scenes.append(
                {
                    "name": str(s.get("name") or f"Scene {idx:02d}").strip(),
                    "duration_seconds": dur,
                    "narration": str(s.get("narration") or "").strip(),
                    "prompt": prompt,
                    "clipStatus": str(s.get("clipStatus") or "missing"),
                    "clipUrl": str(s.get("clipUrl") or ""),
                }
            )
        channel_id = str(data.get("channel_id") or "ch-hawthorn")
        status = str(data.get("status") or "prompts-packed")
        seo_in = data.get("seo") or {}
        tags = seo_in.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        now = _now()
        ep = {
            "slug": slug,
            "channel_id": channel_id,
            "title": title,
            "niche": niche,
            "target_audience": str(data.get("target_audience") or "English-speaking US, UK, Canadian, and Australian viewers"),
            "aspect": aspect,
            "status": status,
            "made_for_kids": bool(data.get("made_for_kids", False)),
            "contains_synthetic_media": bool(data.get("contains_synthetic_media", True)),
            "hooks": list(data.get("hooks") or [title, "Stakes hook variant", "Direct visual hook variant"])[:3],
            "style_bible": str(
                data.get("style_bible")
                or "Stylized 3D tactile miniature animation with consistent character proportions, warm key light, zero on-screen text."
            ),
            "script": str(data.get("script") or " ".join(s["narration"] for s in normalized_scenes if s["narration"]) or title),
            "scenes": normalized_scenes,
            "seo": {
                "title": str(seo_in.get("title") or title),
                "description": str(seo_in.get("description") or f"{title}\n\n#Shorts #OriginalAnimation"),
                "tags": tags,
                "thumbnail_brief": str(seo_in.get("thumbnail_brief") or f"High-contrast close-up keyframe for {title}; zero clickbait."),
            },
            "updated_at": now,
        }
        with self._connect() as conn:
            existing = conn.execute("SELECT created_at, r2_final_key, r2_thumb_key FROM yaf_videos WHERE slug = ?", (slug,)).fetchone()
            created_at = existing["created_at"] if existing else now
            r2_final = str(data.get("r2_final_key") if "r2_final_key" in data else (existing["r2_final_key"] if existing else ""))
            r2_thumb = str(data.get("r2_thumb_key") if "r2_thumb_key" in data else (existing["r2_thumb_key"] if existing else ""))
            ep["created_at"] = created_at
            conn.execute(
                """INSERT OR REPLACE INTO yaf_videos
                   (slug, channel_id, title, niche, aspect, status, episode_json,
                    r2_final_key, r2_thumb_key, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (slug, channel_id, title, niche, aspect, status, json.dumps(ep, ensure_ascii=False), r2_final, r2_thumb, created_at, now),
            )
            if not conn.execute("SELECT video_slug FROM yaf_approvals WHERE video_slug = ?", (slug,)).fetchone():
                conn.execute(
                    """INSERT INTO yaf_approvals
                       (video_slug, digen_scene1_approved, digen_remaining_approved, qa_approved,
                        qa_checks_json, private_upload_approved, scheduled_publish_window, notes, updated_at)
                       VALUES (?, 0, 0, 0, '[false,false,false,false,false]', 0,
                               'Wed/Thu/Fri 22:00–00:00 Asia/Dhaka', 'Awaiting Scene-01 credit gate.', ?)""",
                    (slug, now),
                )
        self._write_local_episode_files(ep)
        return next(v for v in self.list_videos() if v["slug"] == slug)

    def promote_idea(self, idea_id: str, custom_slug: str = "") -> dict[str, Any]:
        ideas = {i["id"]: i for i in self.list_ideas()}
        if idea_id not in ideas:
            raise ValueError(f"Unknown idea id: {idea_id}")
        idea = ideas[idea_id]
        slug = _slugify(custom_slug or idea["title"])
        hook1 = idea["hooks"][0] if idea["hooks"] else idea["title"]
        video = self.upsert_video(
            {
                "slug": slug,
                "channel_id": idea["channel_id"],
                "title": idea["title"],
                "niche": idea["niche"],
                "aspect": idea["aspect"],
                "status": "prompts-packed",
                "hooks": idea["hooks"][:3],
                "style_bible": f"Stylized 3D visual continuity for {idea['niche']}. Crisp macro lighting, stable proportions across every shot, zero text or watermarks.",
                "script": f"{hook1} {idea['promise']} Watch how one tiny mechanism changes everything in seconds.",
                "scenes": [
                    {
                        "name": "Hook Contrast Shot (0–8s)",
                        "duration_seconds": 8,
                        "narration": hook1,
                        "prompt": f"Vertical {idea['aspect']} stylized 3D macro opening shot for '{idea['title']}'. Immediate visual contrast in frame 1, shallow depth of field, smooth camera push-in, zero text.",
                    },
                    {
                        "name": "Core Mechanism / Escalation (8–16s)",
                        "duration_seconds": 8,
                        "narration": idea["promise"],
                        "prompt": f"Vertical {idea['aspect']} cutaway / close-up continuing exact visual continuity for '{idea['title']}'. Clear physical motion showing the central detail in action, no text.",
                    },
                    {
                        "name": "Resolution & Payoff (16–24s)",
                        "duration_seconds": 8,
                        "narration": "That single hidden detail makes the entire system work safely.",
                        "prompt": f"Vertical {idea['aspect']} satisfying pull-back reveal shot resolving '{idea['title']}' with warm lighting contrast and coherent proportions, zero text.",
                    },
                ],
                "seo": {
                    "title": f"{idea['title']} ✨",
                    "description": f"{idea['promise']}\n\n#Shorts #{_slugify(idea['niche']).replace('-', '')}",
                    "tags": [idea["niche"].lower(), "animated short", "how things work", "micro story"],
                    "thumbnail_brief": f"Extreme high-contrast close-up of the central visual subject in '{idea['title']}', mobile-legible at 120px width, zero clickbait.",
                },
            }
        )
        with self._connect() as conn:
            conn.execute("UPDATE yaf_ideas SET status = 'in-production', updated_at = ? WHERE id = ?", (_now(), idea_id))
        return video

    def list_approvals(self) -> dict[str, dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM yaf_approvals").fetchall()
        return {
            r["video_slug"]: {
                "video_slug": r["video_slug"],
                "digen_scene1_approved": bool(r["digen_scene1_approved"]),
                "digen_remaining_approved": bool(r["digen_remaining_approved"]),
                "qa_approved": bool(r["qa_approved"]),
                "qa_checks": json.loads(r["qa_checks_json"]),
                "private_upload_approved": bool(r["private_upload_approved"]),
                "scheduled_publish_window": r["scheduled_publish_window"],
                "notes": r["notes"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        }

    def upsert_approval(self, data: dict[str, Any]) -> dict[str, Any]:
        slug = _slugify(str(data.get("video_slug") or ""))
        if not slug:
            raise ValueError("video_slug is required")
        current = self.list_approvals().get(
            slug,
            {
                "video_slug": slug,
                "digen_scene1_approved": False,
                "digen_remaining_approved": False,
                "qa_approved": False,
                "qa_checks": [False, False, False, False, False],
                "private_upload_approved": False,
                "scheduled_publish_window": "",
                "notes": "",
            },
        )
        for bool_key in ("digen_scene1_approved", "digen_remaining_approved", "qa_approved", "private_upload_approved"):
            if bool_key in data:
                current[bool_key] = bool(data[bool_key])
        if current["digen_remaining_approved"] and not current["digen_scene1_approved"]:
            raise ValueError("Scene-01 credit gate must be approved before approving remaining Digen scenes")
        if current["private_upload_approved"] and not current["qa_approved"]:
            raise ValueError("QA checklist gate must be approved before approving Private YouTube upload")
        if "qa_checks" in data and isinstance(data["qa_checks"], list):
            current["qa_checks"] = [bool(x) for x in data["qa_checks"][:5]]
        if "scheduled_publish_window" in data:
            current["scheduled_publish_window"] = str(data["scheduled_publish_window"])[:300]
        if "notes" in data:
            current["notes"] = str(data["notes"])[:500]
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO yaf_approvals
                   (video_slug, digen_scene1_approved, digen_remaining_approved, qa_approved,
                    qa_checks_json, private_upload_approved, scheduled_publish_window, notes, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    slug,
                    int(current["digen_scene1_approved"]),
                    int(current["digen_remaining_approved"]),
                    int(current["qa_approved"]),
                    json.dumps(current["qa_checks"]),
                    int(current["private_upload_approved"]),
                    current["scheduled_publish_window"],
                    current["notes"],
                    now,
                ),
            )
            # Keep episode status synchronized when QA / upload gates unlock
            new_status = None
            if current["private_upload_approved"]:
                new_status = "approved-for-upload"
            elif current["qa_approved"]:
                new_status = "qa-passed"
            elif current["digen_scene1_approved"]:
                new_status = "scene-1-approved"
            if new_status:
                vrow = conn.execute("SELECT episode_json FROM yaf_videos WHERE slug = ?", (slug,)).fetchone()
                if vrow:
                    ep = json.loads(vrow["episode_json"])
                    ep["status"] = new_status
                    conn.execute(
                        "UPDATE yaf_videos SET status = ?, episode_json = ?, updated_at = ? WHERE slug = ?",
                        (new_status, json.dumps(ep, ensure_ascii=False), now, slug),
                    )
                    ep_path = self.episodes_dir / slug / "episode.json"
                    if ep_path.is_file():
                        ep_path.write_text(json.dumps(ep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return self.list_approvals()[slug]

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM yaf_jobs ORDER BY updated_at DESC LIMIT 50").fetchall()
        return [
            {
                "id": r["id"],
                "channel_id": r["channel_id"],
                "video_slug": r["video_slug"],
                "job_type": r["job_type"],
                "target_runner": r["target_runner"],
                "status": r["status"],
                "payload": json.loads(r["payload_json"]),
                "result_summary": r["result_summary"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    def enqueue_job(self, data: dict[str, Any]) -> dict[str, Any]:
        allowed_types = {
            "research_niches",
            "pack_prompts",
            "digen_scene_01",
            "digen_remaining_scenes",
            "ffmpeg_render_local",
            "youtube_private_upload",
        }
        job_type = str(data.get("job_type") or "")
        if job_type not in allowed_types:
            raise ValueError(f"Unsupported job_type: {job_type}")
        video_slug = _slugify(str(data.get("video_slug") or "pilot-01"))
        approvals = self.list_approvals().get(video_slug, {})
        # Enforce credit & publishing gates on queued jobs!
        status = "queued"
        if job_type == "digen_scene_01" and not approvals.get("digen_scene1_approved"):
            status = "awaiting_approval"
        elif job_type == "digen_remaining_scenes" and not approvals.get("digen_remaining_approved"):
            status = "awaiting_approval"
        elif job_type == "youtube_private_upload" and not approvals.get("private_upload_approved"):
            status = "awaiting_approval"
        target_runner = "local_engine" if job_type in ("ffmpeg_render_local", "youtube_private_upload", "research_niches") else str(data.get("target_runner") or "local_engine")
        job_id = f"job-{uuid.uuid4().hex[:8]}"
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO yaf_jobs
                   (id, channel_id, video_slug, job_type, target_runner, status, payload_json, result_summary, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_id,
                    str(data.get("channel_id") or "ch-hawthorn"),
                    video_slug,
                    job_type,
                    target_runner,
                    status,
                    json.dumps(data.get("payload") or {}),
                    str(data.get("result_summary") or ("Blocked until human approval gate is checked." if status == "awaiting_approval" else "Queued for Local Engine worker.")),
                    now,
                    now,
                ),
            )
        return next(j for j in self.list_jobs() if j["id"] == job_id)

    def complete_job(self, job_id: str, status: str = "completed", result_summary: str = "") -> dict[str, Any]:
        if status not in ("queued", "running", "completed", "failed", "cancelled"):
            raise ValueError("Invalid job status")
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE yaf_jobs SET status = ?, result_summary = ?, updated_at = ? WHERE id = ?",
                (status, result_summary[:500], _now(), job_id),
            )
            if cur.rowcount == 0:
                raise ValueError(f"Unknown job id: {job_id}")
        return next(j for j in self.list_jobs() if j["id"] == job_id)

    def list_analytics(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM yaf_analytics ORDER BY updated_at DESC").fetchall()
        return [
            {
                "id": r["id"],
                "channel_id": r["channel_id"],
                "video_slug": r["video_slug"],
                "published_at": r["published_at"],
                "views_48h": r["views_48h"],
                "viewed_vs_swiped_pct": r["viewed_vs_swiped_pct"],
                "avg_completion_pct": r["avg_completion_pct"],
                "ctr_pct": r["ctr_pct"],
                "top_country": r["top_country"],
                "publish_slot_used": r["publish_slot_used"],
                "studio_heatmap_peak": r["studio_heatmap_peak"],
                "retention_notes": r["retention_notes"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    def upsert_analytics(self, data: dict[str, Any]) -> dict[str, Any]:
        video_slug = _slugify(str(data.get("video_slug") or ""))
        if not video_slug:
            raise ValueError("video_slug is required")
        rec_id = str(data.get("id") or f"ana-{video_slug}")
        channel_id = str(data.get("channel_id") or "ch-hawthorn")
        heatmap_peak = str(data.get("studio_heatmap_peak") or "").strip()[:200]
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO yaf_analytics
                   (id, channel_id, video_slug, published_at, views_48h, viewed_vs_swiped_pct,
                    avg_completion_pct, ctr_pct, top_country, publish_slot_used,
                    studio_heatmap_peak, retention_notes, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rec_id,
                    channel_id,
                    video_slug,
                    str(data.get("published_at") or now[:10]),
                    max(0, int(data.get("views_48h", 0))),
                    max(0.0, min(100.0, float(data.get("viewed_vs_swiped_pct", 0.0)))),
                    max(0.0, min(200.0, float(data.get("avg_completion_pct", 0.0)))),
                    max(0.0, min(100.0, float(data.get("ctr_pct", 0.0)))),
                    str(data.get("top_country") or "US").upper()[:10],
                    str(data.get("publish_slot_used") or ""),
                    heatmap_peak,
                    str(data.get("retention_notes") or "")[:600],
                    now,
                ),
            )
            if heatmap_peak:
                conn.execute(
                    "UPDATE yaf_channels SET studio_heatmap_override = ?, updated_at = ? WHERE id = ?",
                    (heatmap_peak, now, channel_id),
                )
        return next(a for a in self.list_analytics() if a["id"] == rec_id)

    def bootstrap(self) -> dict[str, Any]:
        settings = self.get_settings()
        upload_plan = compute_upload_windows(
            aspect="9:16",
            target_countries=settings["research"]["target_countries"],
            creator_tz=settings["publishing"]["creator_timezone"],
        )
        return {
            "runtime": "local_engine",
            "storageMode": "sqlite_local + workspace_files",
            "architecture": {
                "phase1_local_mvp": "active",
                "phase2_cloudflare_control_center": "ready",
                "phase3_cloud_queue_automation": "ready",
                "ffmpeg_location": "local_only",
            },
            "settings": settings,
            "channels": self.list_channels(),
            "ideas": self.list_ideas(),
            "videos": self.list_videos(),
            "approvals": self.list_approvals(),
            "jobs": self.list_jobs(),
            "analytics": self.list_analytics(),
            "vidiqLedger": VIDIQ_LEDGER,
            "vidiqKeywords": VIDIQ_KEYWORDS,
            "uploadPlan": upload_plan,
        }

    def export_sync_bundle(self) -> dict[str, Any]:
        snap = self.bootstrap()
        return {
            "settings": snap["settings"],
            "channels": snap["channels"],
            "ideas": snap["ideas"],
            "videos": snap["videos"],
            "approvals": snap["approvals"],
            "jobs": snap["jobs"],
            "analytics": snap["analytics"],
        }

    def import_sync_bundle(self, bundle: dict[str, Any]) -> dict[str, Any]:
        if "settings" in bundle and isinstance(bundle["settings"], dict):
            r = bundle["settings"].get("research", {})
            p = bundle["settings"].get("publishing", {})
            self.update_settings(
                {
                    "provider": r.get("provider", "auto"),
                    "depth": r.get("depth", "full"),
                    "fallback_to_gemini": r.get("fallback_to_gemini", True),
                    "target_countries": r.get("target_countries", ["US", "UK", "CA", "AU"]),
                    "creator_timezone": p.get("creator_timezone", "Asia/Dhaka"),
                }
            )
        for ch in bundle.get("channels", []):
            self.upsert_channel(ch)
        for idea in bundle.get("ideas", []):
            self.upsert_idea(idea)
        for vid in bundle.get("videos", []):
            self.upsert_video(vid)
        approvals = bundle.get("approvals", {})
        if isinstance(approvals, dict):
            for app in approvals.values():
                self.upsert_approval(app)
        for ana in bundle.get("analytics", []):
            self.upsert_analytics(ana)
        return self.bootstrap()
