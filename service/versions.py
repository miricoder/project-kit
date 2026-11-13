"""The app's version and what changed in it, for the update notice (slice 15).

The version is baked into the image at build time (APP_VERSION, from `git describe`), so the
service and the web app it serves always agree. What changed comes from CHANGELOG.md, in Keep a
Changelog form: `## [1.2.0] - 2026-11-13` followed by bullet points.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "app-version.txt"
CHANGELOG = ROOT / "CHANGELOG.md"

_HEAD = re.compile(r"^##\s+\[?([^\]\s]+)\]?(?:\s*[-–—]\s*(\S+))?", re.M)


def current_version() -> str:
    """APP_VERSION, else the file the image build wrote, else "dev"."""
    env = os.environ.get("APP_VERSION", "").strip()
    if env:
        return env
    if VERSION_FILE.is_file():
        text = VERSION_FILE.read_text().strip()
        if text:
            return text
    return "dev"


def version_key(version: Optional[str]) -> Optional[Tuple[int, int, int]]:
    """(major, minor, patch) from "v1.2.0", "1.2.0-3-gabc" and the like; None if it has none."""
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", version or "")
    return tuple(int(g) for g in match.groups()) if match else None  # type: ignore[return-value]


def parse_changelog(text: str) -> List[Dict[str, Any]]:
    """Released entries, newest first. Unreleased and unnumbered sections are left out."""
    heads = list(_HEAD.finditer(text))
    entries = []
    for i, head in enumerate(heads):
        version = head.group(1)
        if version_key(version) is None:
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = text[head.end():end]
        notes = [m.group(1).strip() for m in re.finditer(r"^\s*[-*]\s+(.+)$", body, re.M)]
        entries.append({"version": version, "date": head.group(2), "notes": notes})
    entries.sort(key=lambda e: version_key(e["version"]), reverse=True)
    return entries


def whats_new(entries: List[Dict[str, Any]], since: Optional[str],
              current: Optional[str]) -> List[Dict[str, Any]]:
    """Entries newer than `since` and no newer than `current`, newest first. A `since` with
    no version number gets only the current version's entry."""
    top = version_key(current)
    low = version_key(since)
    picked = []
    for entry in entries:
        key = version_key(entry["version"])
        if top is not None and key > top:
            continue
        if low is None:
            if top is not None and key == top:
                picked.append(entry)
            continue
        if key > low:
            picked.append(entry)
    return picked


def read_changelog(path: Path) -> List[Dict[str, Any]]:
    try:
        return parse_changelog(path.read_text(encoding="utf-8"))
    except OSError:
        return []
