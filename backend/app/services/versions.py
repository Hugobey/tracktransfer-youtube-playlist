"""Detect mix and version phrases in track titles.

Plain titles and Original Mix are close. Extended, radio, remix, live,
instrumental, and edit versions are not interchangeable.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

PRIORITY: tuple[str, ...] = (
    "live",
    "remix",
    "instrumental",
    "acoustic",
    "radio",
    "extended",
    "dub",
    "vip",
    "club",
    "edit",
    "original",
)

_PHRASES: dict[str, tuple[str, ...]] = {
    "live": (r"live at", r"live from", r"live version", r"live session", r"live"),
    "remix": (r"reworks?", r"bootlegs?", r"remix(?:es)?", r"rmx"),
    "instrumental": (r"instrumentals?", r"inst\.?\s*mix(?:es)?"),
    "acoustic": (r"acoustics?",),
    "radio": (r"radio edits?", r"radio mix(?:es)?", r"radio versions?", r"short edits?"),
    "extended": (
        r"extended mix(?:es)?",
        r"extended versions?",
        r"extended edits?",
        r"ext\.?\s*mix(?:es)?",
        r"extended",
    ),
    "dub": (r"dub mix(?:es)?", r"dubs?"),
    "vip": (r"v\.?i\.?p\.?", r"vips?"),
    "club": (r"club mix(?:es)?",),
    "edit": (r"edits?",),
    "original": (r"original mix(?:es)?", r"original versions?", r"orig\.?\s*mix(?:es)?"),
}

QUERY_PHRASE: dict[str, str] = {
    "live": "Live",
    "remix": "Remix",
    "instrumental": "Instrumental",
    "acoustic": "Acoustic",
    "radio": "Radio Edit",
    "extended": "Extended Mix",
    "dub": "Dub",
    "vip": "VIP",
    "club": "Club Mix",
    "edit": "Edit",
    "original": "Original Mix",
}

VERSION_LABEL: dict[str | None, str] = {
    None: "the studio recording",
    "original": "the original mix",
    "extended": "the extended mix",
    "radio": "the radio edit",
    "remix": "a remix",
    "live": "a live version",
    "instrumental": "an instrumental",
    "acoustic": "an acoustic version",
    "dub": "a dub",
    "vip": "a VIP",
    "club": "a club mix",
    "edit": "an edit",
}

_NOISE = re.compile(
    r"""
    \([^)]*(?:official|lyric|lyrics|audio|video|hd|remaster(?:ed)?)[^)]*\)
    | \[[^\]]*(?:official|lyric|lyrics|audio|video|hd|remaster(?:ed)?)[^\]]*\]
    | \((?:feat|ft|featuring)\b[^)]*\)
    | \[(?:feat|ft|featuring)\b[^\]]*\]
    | \b(?:official\s+audio|official\s+video|lyric\s+video|lyrics|remastered|remaster)\b
    """,
    re.IGNORECASE | re.VERBOSE,
)
_FEAT_TAIL = re.compile(r"\b(?:feat|ft|featuring)\b.*$", re.IGNORECASE)


def _compile(kind: str) -> re.Pattern[str]:
    body = "|".join(_PHRASES[kind])
    return re.compile(rf"\b(?:{body})\b", re.IGNORECASE)


_COMPILED = {kind: _compile(kind) for kind in PRIORITY}


@dataclass(frozen=True)
class VersionInfo:
    kind: str | None
    phrase: str | None


def detect_version(title: str) -> VersionInfo:
    for kind in PRIORITY:
        if _COMPILED[kind].search(title or ""):
            return VersionInfo(kind=kind, phrase=QUERY_PHRASE[kind])
    return VersionInfo(kind=None, phrase=None)


def strip_version(title: str) -> str:
    text = _NOISE.sub(" ", title or "")
    text = _FEAT_TAIL.sub(" ", text)
    for kind in PRIORITY:
        text = _COMPILED[kind].sub(" ", text)
    text = re.sub(r"[()\[\]{}]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -–—")
    return text


def normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.lower()
    value = re.sub(r"\s+&\s+", " and ", value)
    value = re.sub(r"&", "", value)
    value = value.replace("'", "").replace("\u2019", "").replace("`", "")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def tokens(text: str) -> list[str]:
    raw = normalize(text).split()
    stop = {"feat", "ft", "featuring", "vs", "and", "the", "of"}
    kept = [token for token in raw if token not in stop and len(token) > 1]
    if kept:
        return kept
    return [token for token in raw if len(token) > 1] or raw


def version_compatibility(source: str | None, candidate: str | None) -> float:
    if source == candidate:
        return 1.0
    table = {
        ("original", None): 0.94,
        (None, "original"): 0.94,
        ("club", "original"): 0.48,
        ("original", "club"): 0.48,
        ("club", None): 0.52,
        (None, "club"): 0.52,
        ("extended", "club"): 0.55,
        ("club", "extended"): 0.55,
        ("edit", None): 0.35,
        (None, "edit"): 0.4,
        ("edit", "original"): 0.3,
        ("original", "edit"): 0.3,
        ("vip", "original"): 0.2,
        ("original", "vip"): 0.2,
        ("vip", None): 0.2,
        (None, "vip"): 0.2,
        ("dub", "original"): 0.15,
        ("original", "dub"): 0.15,
        ("dub", None): 0.2,
        (None, "dub"): 0.2,
    }
    score = table.get((source, candidate))
    if score is not None:
        return score
    studio = {None, "original"}
    marked = {"extended", "radio", "remix", "live", "instrumental", "acoustic", "vip", "dub", "edit", "club"}
    if source in studio and candidate in marked:
        return 0.06
    if candidate in studio and source in marked:
        return 0.1
    if source != candidate:
        return 0.06
    return 0.5
