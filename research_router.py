"""Validated, offline routing policy for Antigravity's YouTube research agents.

This file does not call Gemini or vidIQ and consumes no credits. Connected
Antigravity agent skills perform the research according to the saved policy.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from upload_timing import format_upload_plan, validate_timezone

ROOT = Path(__file__).resolve().parent
SETTINGS_FILE = ROOT / 'settings.json'
DIGEN_MCP_ENDPOINT = 'https://api.digen.ai/v2/gateway/agent/openapi/mcp'
VIDIQ_MCP_ENDPOINT = 'https://mcp.vidiq.com/mcp'

DEFAULTS = {
    'research': {
        'provider': 'auto',
        'fallback_to_gemini': True,
        'depth': 'full',
        'target_countries': ['US', 'UK', 'CA', 'AU'],
        'minimum_source_links': 3,
        'require_source_dates': True,
        'allow_unverified_estimates': False,
        'include_upload_time_research': True,
    },
    'video': {
        'provider': 'digen',
        'mcp_endpoint': DIGEN_MCP_ENDPOINT,
        'require_credit_approval': True,
        'automatic_paid_retries': False,
    },
    'publishing': {
        'require_approval': True,
        'default_visibility': 'private',
        'optimize_top_tier_upload_time': True,
        'creator_timezone': 'Asia/Dhaka',
    },
}


def validate(settings: dict) -> dict:
    if not isinstance(settings, dict):
        raise ValueError('Settings must be a JSON object')
    result = deepcopy(DEFAULTS)
    for section, values in settings.items():
        if section not in result or not isinstance(values, dict):
            raise ValueError(f'Unknown or invalid settings section: {section}')
        unknown = set(values) - set(result[section])
        if unknown:
            raise ValueError(f'Unrecognized setting(s) in {section}: {sorted(unknown)}')
        result[section].update(values)
    r = result['research']
    if r['provider'] not in {'auto', 'vidiq', 'gemini'}:
        raise ValueError('research.provider must be auto, vidiq, or gemini')
    if r['depth'] not in {'quick', 'full'}:
        raise ValueError('research.depth must be quick or full')
    if not isinstance(r['fallback_to_gemini'], bool):
        raise ValueError('research.fallback_to_gemini must be boolean')
    if (not isinstance(r['require_source_dates'], bool)
            or not isinstance(r['allow_unverified_estimates'], bool)
            or not isinstance(r['include_upload_time_research'], bool)):
        raise ValueError('Research evidence toggles must be boolean')
    if (not isinstance(r['minimum_source_links'], int) or isinstance(r['minimum_source_links'], bool)
            or not 1 <= r['minimum_source_links'] <= 20):
        raise ValueError('minimum_source_links must be an integer between 1 and 20')
    if not isinstance(r['target_countries'], list) or not r['target_countries'] or not all(
        isinstance(x, str) and x.strip() for x in r['target_countries']):
        raise ValueError('target_countries must be a nonempty list of strings')
    v = result['video']
    if v['provider'] != 'digen':
        raise ValueError('Video provider must remain digen')
    if not isinstance(v['mcp_endpoint'], str) or not v['mcp_endpoint'].startswith('https://'):
        raise ValueError('video.mcp_endpoint must be an HTTPS Digen MCP URL')
    if v['require_credit_approval'] is not True or v['automatic_paid_retries'] is not False:
        raise ValueError('Digen credit safety settings cannot be relaxed in the starter')
    p = result['publishing']
    if p['require_approval'] is not True or p['default_visibility'] != 'private':
        raise ValueError('Publishing must remain private with approval in the starter')
    if not isinstance(p['optimize_top_tier_upload_time'], bool):
        raise ValueError('publishing.optimize_top_tier_upload_time must be boolean')
    p['creator_timezone'] = validate_timezone(p['creator_timezone'])
    return result


def load_settings(path: Path = SETTINGS_FILE) -> dict:
    if not path.is_file():
        return deepcopy(DEFAULTS)
    return validate(json.loads(path.read_text(encoding='utf-8')))


def save_settings(settings: dict, path: Path = SETTINGS_FILE) -> dict:
    data = validate(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    # No credentials or tokens belong in settings.json.
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temp.replace(path)
    return data


def route_research(settings: dict, *, vidiq_available: bool | None = None, gemini_available: bool | None = None) -> dict:
    """Route using VERIFIED availability only; unknown is never silently treated as online."""
    r = validate(settings)['research']
    provider, fallback = r['provider'], r['fallback_to_gemini']
    if provider == 'gemini':
        selected = 'gemini' if gemini_available is not False else None
    elif provider == 'vidiq':
        selected = 'vidiq' if vidiq_available is True else ('gemini' if fallback and gemini_available is not False and vidiq_available is False else None)
    else:
        selected = ('vidiq' if vidiq_available is True else
                    'gemini' if fallback and vidiq_available is False and gemini_available is not False else None)
    return {
        'requested': provider,
        'selected': selected,
        'status': 'ready' if selected else 'requires_live_check',
        'fallback_allowed': bool(fallback and provider != 'gemini'),
        'notes': (
            'An Antigravity agent must check live MCP/model availability before conducting research.'
            if not selected else
            'vidIQ requires connected MCP and credits; Gemini uses Antigravity with Skills and web tools, not consumer-plan API access.'
        ),
    }


def research_instructions(settings: dict, topic: str = 'Discover the next original YouTube topic') -> str:
    validated = validate(settings)
    r = validated['research']
    v = validated['video']
    p = validated['publishing']
    provider = r['provider']
    fallback = r['fallback_to_gemini']
    route = {
        'auto': f'Check vidIQ MCP ({VIDIQ_MCP_ENDPOINT}) access and credits first; use vidIQ when authenticated and sufficient. If unavailable, {"use Gemini in Antigravity" if fallback else "stop and report the blocker"}.',
        'vidiq': f'Use vidIQ MCP ({VIDIQ_MCP_ENDPOINT}) research tools exclusively as primary. If unavailable, {"switch to Gemini via Antigravity" if fallback else "stop; do not silently use Gemini"}.',
        'gemini': 'Use Gemini through the active Antigravity agent, its web research tools, and local YouTube Skills; NEVER invoke vidIQ tools.',
    }[provider]
    shorts_timing = format_upload_plan(
        aspect='9:16',
        target_countries=r['target_countries'],
        creator_tz=p['creator_timezone'],
    )
    return f'''# RESEARCH JOB — YouTube AI Factory

User request: {topic}

RESEARCH & PRODUCTION SETTINGS (from settings.json)
- Selected research mode: {provider} (fallback_to_gemini={fallback})
- Research depth: {r['depth']}
- Top-tier target countries: {', '.join(r['target_countries'])}
- Creator local timezone: {p['creator_timezone']}
- Include top-tier upload best-time research: {r['include_upload_time_research']}
- Required source URLs: at least {r['minimum_source_links']} (dated={r['require_source_dates']})
- Digen MCP endpoint: {v['mcp_endpoint']}
- vidIQ MCP endpoint: {VIDIQ_MCP_ENDPOINT}

MANDATORY PROVIDER RULE
{route}

WORKFLOW
1. Open .agents/skills/research-router/SKILL.md, .agents/skills/niche-scout/SKILL.md and .agents/skills/hook-script/SKILL.md.
2. Research original niche and video opportunities for {', '.join(r['target_countries'])} with verifiable links, dated observations, competition indicators, candidate titles and 3 honest hooks per shortlisted idea.
3. Perform Top-Tier Country Upload Best-Time Research: verify audience-overlap windows across {', '.join(r['target_countries'])} for Shorts (9:16) vs Long-Form (16:9), include the 1–2h (Shorts) / 2–3h (Long-Form) PRIVATE upload indexing buffer, convert times to {p['creator_timezone']}, and remind owner to switch to YouTube Studio's "When your viewers are on YouTube" heatmap once 28+ days of data exist.
4. Attribute every numeric search-volume/competition metric to vidIQ or another named verified source. Gemini-only mode MUST NOT invent vidIQ metrics, RPM, competitor retention or private channel analytics. Clearly mark qualitative judgments.
5. Preserve research sources, upload-time schedule, provider used, model/tool observations and limitations in research/ with a dated filename.
6. Create a Digen-ready scene plan (`python3 factory.py new ...` / `pack ...`). Video generation uses Digen only ({v['mcp_endpoint']}). Never spend Digen credits without owner approval; never automatically publish publicly.
7. This is an agent instruction file: this Python CLI is not an AI model and does not by itself perform online research.

{shorts_timing}
'''
