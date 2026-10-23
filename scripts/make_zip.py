#!/usr/bin/env python3
"""Build a clean, shareable ZIP archive of youtube-ai-factory-starter.

Excludes secrets (.env, .secrets, .agents/mcp_config.json, *.token.json),
build caches (__pycache__, .DS_Store, *.tmp), rendered heavy media, and *.zip.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_NAME = "youtube-ai-factory-starter.zip"
EXCLUDED_DIRS = {"__pycache__", ".secrets", "output", ".git"}
EXCLUDED_FILES = {".DS_Store", ".env", ARCHIVE_NAME}


def should_skip(rel_path: Path) -> bool:
    if any(part in EXCLUDED_DIRS for part in rel_path.parts):
        return True
    name = rel_path.name
    if name in EXCLUDED_FILES:
        return True
    if name.endswith((".pyc", ".pyo", ".tmp", ".zip", ".token.json")):
        return True
    if rel_path.as_posix() == ".agents/mcp_config.json":
        return True
    if name == "narration.wav":
        return True
    if "clips" in rel_path.parts and name.endswith(".mp4"):
        return True
    return False


def build_zip(dest: Path | None = None) -> Path:
    out_path = dest or (ROOT / ARCHIVE_NAME)
    prefix = ROOT.name
    count = 0
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in sorted(ROOT.rglob("*")):
            rel = item.relative_to(ROOT)
            if should_skip(rel):
                continue
            arcname = f"{prefix}/{rel.as_posix()}"
            if item.is_dir():
                if not any(item.iterdir()):
                    zf.writestr(arcname + "/", "")
            elif item.is_file():
                zf.write(item, arcname)
                count += 1
    print(f"Created {out_path} ({count} files, {out_path.stat().st_size:,} bytes)")
    return out_path


if __name__ == "__main__":
    build_zip()
