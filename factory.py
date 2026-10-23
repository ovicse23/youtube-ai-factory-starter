#!/usr/bin/env python3
"""YouTube AI Factory: offline-first project preparation + media assembler.

No paid AI API or third-party service is called by this script.
"""
from __future__ import annotations
import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from research_router import load_settings, save_settings, research_instructions
from upload_timing import compute_upload_windows, format_upload_plan

ROOT = Path(__file__).resolve().parent
EPISODES = ROOT / "episodes"

def die(message):
    raise SystemExit(f"ERROR: {message}")

def read_episode(slug):
    path = EPISODES / slug / "episode.json"
    if not path.is_file(): die(f"Missing {path}. Run 'new' first.")
    return json.loads(path.read_text(encoding="utf-8"))

def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def check_episode(ep):
    for key in ("slug", "title", "niche", "aspect", "target_audience", "script", "scenes", "seo"):
        if not ep.get(key): die(f"episode.json: missing '{key}'")
    if ep["aspect"] not in ("9:16", "16:9"): die("Aspect must be 9:16 or 16:9")
    if not isinstance(ep["scenes"], list) or not ep["scenes"]: die("Scenes must be a non-empty list")
    for i, s in enumerate(ep["scenes"], 1):
        if not s.get("prompt") or not s.get("duration_seconds"):
            die(f"Scene {i} missing prompt/duration_seconds")
        if not (1 <= s["duration_seconds"] <= 120): die(f"Scene {i}: invalid duration")
    return True

def new(args):
    slug = re.sub(r"[^a-z0-9-]+", "-", args.slug.lower()).strip("-")
    if not slug: die("Invalid episode slug")
    path = EPISODES / slug
    if path.exists(): die(f"Episode already exists: {slug}")
    template = json.loads((ROOT / "examples" / "sample-episode.json").read_text(encoding="utf-8"))
    template.update({"slug": slug, "title": args.title, "niche": args.niche, "aspect": args.aspect,
                     "status": "draft", "created_at": datetime.now(timezone.utc).isoformat()})
    template["seo"]["title"] = args.title
    write_json(path / "episode.json", template)
    (path / "clips").mkdir()
    print(f"Created {path / 'episode.json'}\nEdit the scenes and SEO, then run: python3 factory.py pack {slug}")

def pack(args):
    ep = read_episode(args.slug)
    check_episode(ep)
    settings = load_settings()
    path = EPISODES / args.slug
    shots = path / "prompts"
    shots.mkdir(exist_ok=True)
    for i, s in enumerate(ep["scenes"], 1):
        text = f"PROJECT: {ep['title']}\nASPECT RATIO: {ep['aspect']}\nTARGET DURATION: {s['duration_seconds']} seconds\n"
        text += f"GLOBAL CONTINUITY: {ep.get('style_bible','Maintain visual continuity.')}\n"
        text += f"SCENE {i:02d}: {s.get('name','Untitled')}\nVIDEO PROMPT:\n{s['prompt']}\n"
        text += f"NARRATION/VOICE (if supported): {s.get('narration', '')}\n"
        text += "Avoid copyrighted characters, deceptive realism and unwanted on-screen text.\n"
        (shots / f"scene-{i:02d}.txt").write_text(text, encoding="utf-8")
    upload_plan = format_upload_plan(
        aspect=ep["aspect"],
        target_countries=settings["research"]["target_countries"],
        creator_tz=settings["publishing"]["creator_timezone"],
    )
    (path / "upload-schedule.txt").write_text(upload_plan + "\n", encoding="utf-8")
    seo = ep["seo"]
    seo_text = f"TITLE: {seo.get('title', ep['title'])}\n\nDESCRIPTION:\n{seo.get('description', '')}\n"
    seo_text += "\nTAGS: " + ", ".join(seo.get("tags", [])) + "\n"
    seo_text += f"\nTHUMBNAIL BRIEF:\n{seo.get('thumbnail_brief', '')}\n"
    seo_text += f"\n---\n{upload_plan}\n"
    (path / "seo-package.txt").write_text(seo_text, encoding="utf-8")
    (path / "narration.txt").write_text(ep["script"].strip() + "\n", encoding="utf-8")
    print(f"Generated {len(ep['scenes'])} Digen prompts in {shots}")
    print(f"Generated SEO + Top-Tier Upload Schedule in {path / 'seo-package.txt'}\n")
    print("Next: generate clips in Digen, then save scene-01.mp4, scene-02.mp4, ... in clips/.")

def status(args):
    ep = read_episode(args.slug)
    path = EPISODES / args.slug
    print(f"{ep['title']} | {ep['niche']} | {ep['aspect']} | {ep.get('status','draft')}")
    ready = 0
    for i in range(1, len(ep["scenes"]) + 1):
        clip = path / "clips" / f"scene-{i:02d}.mp4"
        exists = clip.is_file() and clip.stat().st_size > 0
        ready += exists
        print(f"  scene-{i:02d}: {'READY' if exists else 'MISSING'}")
    print(f"Clips: {ready}/{len(ep['scenes'])}")
    print("Rendered:", (path / "output" / "final.mp4").is_file())

def ffmpeg_run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode:
        die("ffmpeg failed: " + result.stderr[-1800:])

def render(args):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        die("Install FFmpeg and ffprobe first (e.g. brew install ffmpeg).")
    ep = read_episode(args.slug)
    check_episode(ep)
    path = EPISODES / args.slug
    clips = [path / "clips" / f"scene-{i:02d}.mp4" for i in range(1,len(ep["scenes"])+1)]
    for f in clips:
        if not f.is_file() or f.stat().st_size == 0: die(f"Missing clip: {f}")
    outdir = path / "output"
    work = outdir / "normalized"
    work.mkdir(parents=True, exist_ok=True)
    width,height = (1080,1920) if ep["aspect"] == "9:16" else (1920,1080)
    files = []
    for i, clip in enumerate(clips, 1):
        info = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(clip)], capture_output=True, text=True)
        has_audio = bool(info.stdout.strip())
        dest = work / f"part-{i:02d}.mp4"
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(clip)]
        if not has_audio:
            cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
        video_filter = (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p")
        cmd += ["-map", "0:v:0", "-map", "0:a:0" if has_audio else "1:a:0", "-vf", video_filter,
                "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k", "-shortest", str(dest)]
        ffmpeg_run(cmd)
        files.append(dest)
    concat = work / "concat.txt"
    concat.write_text("".join(f"file '{f.name}'\n" for f in files), encoding="utf-8")
    joined = outdir / "joined.mp4"
    ffmpeg_run(["ffmpeg","-y","-hide_banner","-loglevel","error","-f","concat","-safe","0","-i",str(concat),"-c","copy",str(joined)])
    narration = path / "narration.wav"
    final = outdir / "final.mp4"
    if narration.is_file():
        ffmpeg_run(["ffmpeg","-y","-hide_banner","-loglevel","error","-i",str(joined),"-i",str(narration),
            "-filter_complex","[0:a]volume=0.17[bg];[1:a]volume=1.0[voice];[bg][voice]amix=inputs=2:duration=first:dropout_transition=2[aout]",
            "-map","0:v:0","-map","[aout]","-c:v","copy","-c:a","aac","-b:a","192k",str(final)])
    else:
        shutil.copy2(joined, final)
    preview = outdir / "preview-thumbnail.jpg"
    ffmpeg_run(["ffmpeg","-y","-hide_banner","-loglevel","error","-ss","1","-i",str(final),"-frames:v","1","-q:v","2",str(preview)])
    ep["status"] = "rendered-review-required"
    write_json(path / "episode.json", ep)
    print(f"SUCCESS: {final}\nThumbnail candidate: {preview}\nReview the video before publishing.")

def show_settings(args):
    print(json.dumps(load_settings(), indent=2, ensure_ascii=False))


def set_research(args):
    settings = load_settings()
    r = settings['research']
    p = settings['publishing']
    if args.provider is not None: r['provider'] = args.provider
    if args.depth is not None: r['depth'] = args.depth
    if args.fallback is not None: r['fallback_to_gemini'] = args.fallback == 'on'
    if args.countries is not None:
        r['target_countries'] = [c.strip().upper() for c in args.countries.split(',') if c.strip()]
    if args.creator_tz is not None:
        p['creator_timezone'] = args.creator_tz
    print(json.dumps(save_settings(settings), indent=2))


def plan_research(args):
    result = research_instructions(load_settings(), args.topic)
    if args.output:
        target = ROOT / 'research' / args.output
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result, encoding='utf-8')
        print(f'Agent research instructions: {target}')
    else:
        print(result)


def plan_upload(args):
    settings = load_settings()
    countries = (
        [c.strip().upper() for c in args.countries.split(',') if c.strip()]
        if args.countries else settings['research']['target_countries']
    )
    tz = args.creator_tz or settings['publishing']['creator_timezone']
    if args.json:
        data = compute_upload_windows(
            aspect=args.aspect,
            target_countries=countries,
            creator_tz=tz,
            ref_date=args.date,
        )
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(format_upload_plan(
            aspect=args.aspect,
            target_countries=countries,
            creator_tz=tz,
            ref_date=args.date,
        ))


def sync_cloud(args):
    from scripts.cloudflare_sync import sync_with_cloudflare
    res = sync_with_cloudflare(mode=args.mode, remote_url=args.remote)
    print(json.dumps(res, indent=2, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    n = sub.add_parser("new", help="Create a draft episode")
    n.add_argument("slug"); n.add_argument("--title", required=True); n.add_argument("--niche", required=True)
    n.add_argument("--aspect", choices=["9:16","16:9"], default="9:16"); n.set_defaults(func=new)
    for command, handler in [("pack",pack),("status",status),("render",render)]:
        c = sub.add_parser(command)
        c.add_argument("slug"); c.set_defaults(func=handler)
    s = sub.add_parser('settings', help='Show persisted research provider and production settings')
    s.set_defaults(func=show_settings)
    sr = sub.add_parser('set-research', help='Set vidIQ, Gemini or Auto without changing Digen')
    sr.add_argument('--provider', choices=['auto', 'vidiq', 'gemini'])
    sr.add_argument('--depth', choices=['quick', 'full'])
    sr.add_argument('--fallback', choices=['on', 'off'])
    sr.add_argument('--countries', help='Comma-separated top-tier country codes (e.g. US,UK,CA,AU)')
    sr.add_argument('--creator-tz', help='Creator IANA timezone (e.g. Asia/Dhaka, UTC, America/New_York)')
    sr.set_defaults(func=set_research)
    rp = sub.add_parser('research-plan', help='Generate provider-aware instructions for Antigravity')
    rp.add_argument('--topic', default='Find promising original YouTube video niches and first episodes')
    rp.add_argument('--output', help='Save under research/ (relative filename)')
    rp.set_defaults(func=plan_research)
    up = sub.add_parser('upload-plan', help='Compute DST-aware top-tier country upload & schedule windows')
    up.add_argument('--aspect', choices=['9:16', '16:9'], default='9:16', help='9:16 Shorts or 16:9 Long-form')
    up.add_argument('--countries', help='Comma-separated target markets (defaults to settings.json)')
    up.add_argument('--creator-tz', help='Creator IANA timezone (defaults to settings.json)')
    up.add_argument('--date', help='Reference YYYY-MM-DD date for DST calculation')
    up.add_argument('--json', action='store_true', help='Output structured JSON')
    up.set_defaults(func=plan_upload)
    sy = sub.add_parser('sync', help='Push or pull Hybrid Control Center state with Cloudflare')
    sy.add_argument('--mode', choices=['push', 'pull'], default='push')
    sy.add_argument('--remote', default='https://youtube-ai-factory.ovi-cse23.workers.dev')
    sy.set_defaults(func=sync_cloud)
    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
