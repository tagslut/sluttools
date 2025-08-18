"""
Deprecated compatibility utilities for matching.

This module remains to provide calculate_match_score and some small
formatting helpers used by legacy code/tests. New code should use the
high-level matching functions in sluttools.matching.
"""
import os
import textwrap
import re
import unicodedata
from typing import Iterable, List, Tuple

import warnings as _warnings
# Emit a one-time deprecation warning on import to guide users.
_warnings.warn(
    "sluttools.matcher is deprecated; use sluttools.matching for matching logic.\n"
    "Only calculate_match_score remains supported here for compatibility.",
    DeprecationWarning,
    stacklevel=2,
)

_JUNK_TOKENS = {
    "ep","remix","mix","version","edit","original","single","album","live",
    "feat","featuring","feat.","vs","vol","vol.","pt","pt.","part","deluxe",
    "remastered","remaster","bonus","instrumental","mono","stereo"
}

_SERIES_HINTS = {"adult only","new path","fafep010","signatune core","nuances de nuit"}

def _norm(s: str, field: str = None) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s).lower()
    s = s.replace("&", " and ").replace("+", " and ").replace("|", " ")
    s = re.sub(r"[’'`]", "'", s)
    # Keep catalog-ish tags like BP SINGLE TRACK #123 but strip most bracket noise
    s = re.sub(r"\\(.*?\\)(?!bp single track).*?|\\[.*?\\]|\\{.*?\\}", " ", s)
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    s = re.sub(r"\\s+", " ", s).strip()
    # Album-specific normalization: strip common suffixes
    if field == "album":
        s = re.sub(r"( - (ep|single|album|remaster|deluxe|edition|reissue|expanded|bonus|mono|stereo))$", "", s)
    return s

def _tokens(s: str, field: str = None):
    toks = [t for t in _norm(s, field=field).split() if t]
    core = [t for t in toks if t not in _JUNK_TOKENS]
    junk = [t for t in toks if t in _JUNK_TOKENS]
    return core, junk

def _ordered_phrase_score(a: str, b: str) -> float:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb:
        return 0.9
    ac = na.split()
    bc = nb.split()
    if len(ac) == 1 and ac[0] in bc:
        return 0.7
    i = j = m = 0
    while i < len(ac) and j < len(bc):
        if ac[i] == bc[j]:
            m += 1
            i += 1
            j += 1
        else:
            j += 1
    base = m / max(len(ac), 1)
    return base * 0.8

def _token_overlap_score(a: str, b: str, *, field: str | None = None) -> float:
    ac, aj = _tokens(a, field=field)
    bc, bj = _tokens(b, field=field)
    if not ac or not bc:
        return 0.0
    set_a, set_b = set(ac), set(bc)
    jacc = len(set_a & set_b) / max(len(set_a | set_b), 1)
    junk = 0.2 * (len(set(aj) & set(bj)) / max(len(set(aj) | set(bj)) or 1, 1))
    return min(1.0, jacc + junk)

def _series_hint_bonus(a: str, b: str) -> float:
    an, bn = _norm(a), _norm(b)
    for h in _SERIES_HINTS:
        if h in an and h in bn:
            return 0.3
    return 0.0

def calculate_match_score(source, candidate):
    """
    source/candidate are dict-like:
      { 'artist': str, 'title': str, 'album': str|None, 'year': int|None, 'duration': float|None }
    Returns score in [0, 100].
    """
    title_dir = _ordered_phrase_score(source.get('title',''), candidate.get('title',''))
    title_tok = _token_overlap_score(source.get('title',''), candidate.get('title',''))
    # Improved artist matching: substring or token inclusion counts as strong match
    src_artist = source.get('artist','')
    cand_artist = candidate.get('artist','')
    artist_dir = _ordered_phrase_score(src_artist, cand_artist)
    artist_tok = _token_overlap_score(src_artist, cand_artist)
    artist_bias = 0.0
    # New: if src_artist is a substring or token in cand_artist, count as strong match
    norm_src_artist = _norm(src_artist)
    norm_cand_artist = _norm(cand_artist)
    if norm_src_artist and norm_src_artist in norm_cand_artist:
        artist_dir = 1.0
        artist_tok = 1.0
    elif norm_src_artist and any(tok == norm_src_artist for tok in norm_cand_artist.split()):
        artist_dir = 1.0
        artist_tok = 1.0
    if artist_dir >= 0.9 or artist_tok >= 0.9:
        artist_bias += 0.20
    elif artist_tok < 0.3 and artist_dir < 0.3:
        artist_bias -= 0.15
    # Album normalization: pass field='album' to token overlap
    album_tok = _token_overlap_score(
        source.get('album',''), candidate.get('album',''), field='album')
    # Series hints: fall back to raw path text if album/title missing
    series_left = (source.get('album','') + " " + source.get('title','')).strip() or source.get('path','') or ""
    series_right = (candidate.get('album','') + " " + candidate.get('title','')).strip() or candidate.get('path','') or ""
    series_bonus = _series_hint_bonus(series_left, series_right)
    year_bonus = 0.0
    sy, cy = source.get('year'), candidate.get('year')
    if isinstance(sy, int) and isinstance(cy, int):
        dy = abs(sy - cy)
        if dy <= 2:
            year_bonus += 0.06
        elif dy > 5:
            year_bonus -= 0.06
    dur_bonus = 0.0
    sd, cd = source.get('duration'), candidate.get('duration')
    if isinstance(sd, (int,float)) and isinstance(cd, (int,float)) and sd > 0 and cd > 0:
        diff = abs(sd - cd) / max(sd, cd)
        if diff <= 0.05:
            dur_bonus += 0.10
        elif diff <= 0.10:
            dur_bonus += 0.05
        elif diff >= 0.25:
            dur_bonus -= 0.08
    base = (
        0.55 * title_dir +
        0.20 * title_tok +
        0.15 * max(artist_dir, artist_tok) +
        0.05 * album_tok
    )
    score = base + artist_bias + series_bonus + year_bonus + dur_bonus
    return max(0, min(100, round(score * 100, 1)))


def _shorten(txt: str, width: int) -> str:
    if not txt:
        return "—"
    txt = " ".join(str(txt).split())
    if len(txt) <= width:
        return txt
    return textwrap.shorten(txt, width=width, placeholder="…")


def format_match_cells(
    *,
    score: int,
    src_title: str,
    src_artist: str = "",
    cand_title: str = "",
    cand_artist: str = "",
    cand_path: str = "",
) -> Tuple[str, str, str, str]:
    """Return 4 aligned cells: SCORE, SOURCE, CANDIDATE, WHERE (basename)."""
    source = f"{src_title}" if not src_artist else f"{src_title} — {src_artist}"
    candidate = f"{cand_title}" if not cand_artist else f"{cand_title} — {cand_artist}"
    where = os.path.basename(cand_path) if cand_path else ""
    source = _shorten(source, _MAX_COL_WIDTHS["source"])
    candidate = _shorten(candidate, _MAX_COL_WIDTHS["candidate"])
    where = _shorten(where, _MAX_COL_WIDTHS["where"])
    return (f"{score:>3}", source, candidate, where)


def render_match_table(rows: Iterable[Tuple[str, str, str, str]]) -> str:
    """Render a monospace-friendly table."""
    rows = list(rows)
    if not rows:
        return "(no matches)"
    headers = ("SCR", "SOURCE", "CANDIDATE", "WHERE")
    col_widths: List[int] = [
        max(len(headers[0]), max(len(r[0]) for r in rows)),
        max(len(headers[1]), max(len(r[1]) for r in rows)),
        max(len(headers[2]), max(len(r[2]) for r in rows)),
        max(len(headers[3]), max(len(r[3]) for r in rows)),
    ]
    def fmt_row(r: Tuple[str, str, str, str]) -> str:
        return (
            f" {r[0]:>{col_widths[0]}} │ "
            f"{r[1]:<{col_widths[1]}} │ "
            f"{r[2]:<{col_widths[2]}} │ "
            f"{r[3]:<{col_widths[3]}}"
        )
    top = (
        f" {headers[0]:>{col_widths[0]}} │ "
        f"{headers[1]:<{col_widths[1]}} │ "
        f"{headers[2]:<{col_widths[2]}} │ "
        f"{headers[3]:<{col_widths[3]}}"
    )
    rule = (
        f" {'─'*col_widths[0]}─┼─"
        f"{'─'*col_widths[1]}─┼─"
        f"{'─'*col_widths[2]}─┼─"
        f"{'─'*col_widths[3]}"
    )
    body = "\n".join(fmt_row(r) for r in rows)
    return f"{top}\n{rule}\n{body}"
