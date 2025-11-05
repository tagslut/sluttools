#!/usr/bin/env python3
# tidal2qobuz.py
# Map a Tidal URL (track/album/playlist) to equivalent content on Qobuz (if available).
# Requires the 'keyring' library and a Qobuz App ID stored in the system's keychain.

import argparse
import csv
import html
import json
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

import certifi as _certifi

# Additional alias imports required by helper block
import requests  # for TIDAL OpenAPI fallback
import requests as _requests

try:
    import keyring
except ImportError:
    sys.exit(
        "Error: The 'keyring' library is required. Please install it with 'pip install keyring'"
    )

SERVICE_NAME = "sluttools.tidal2qobuz"
QOBUZ_APP_ID = keyring.get_password(SERVICE_NAME, "qobuz_app_id")
QOBUZ_USER_AUTH_TOKEN = keyring.get_password(SERVICE_NAME, "qobuz_user_auth_token")

QOBUZ_SEARCH_BASE = "https://www.qobuz.com/api.json/0.2/search"
QOBUZ_OPEN_TRACK = "https://open.qobuz.com/track/{id}"
QOBUZ_OPEN_ALBUM = "https://open.qobuz.com/album/{id}"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

try:
    import certifi  # optional but recommended; provides a reliable CA bundle

    _CAFILE = certifi.where()
except Exception:
    _CAFILE = None

# ---- TIDAL OpenAPI fallback fetcher (pages/playlist) ----
_TIDAL_OPENAPI_URL = "https://openapi.tidal.com/v2/pages/playlist"
_TIDAL_DEFAULT_COUNTRY = os.environ.get("TIDAL_COUNTRY", "LB")
_TIDAL_WEB_TOKEN = os.environ.get(
    "TIDAL_WEB_TOKEN"
)  # may be a static web token or a JWT
_PUBLIC_X_TIDAL = "wdgaB1CilGA-S_s2"

_tidal_session = _requests.Session()
_tidal_session.verify = _certifi.where()
_headers = {
    "accept": "application/json",
    "user-agent": "sluttools/tidal2qobuz",
    "origin": "https://listen.tidal.com",
    "referer": "https://listen.tidal.com/",
}
# If the provided token looks like a JWT (has 3 dot-separated parts and starts with 'eyJ'),
# use it as an Authorization bearer token and still send the known public x-tidal-token.
if (
    _TIDAL_WEB_TOKEN
    and _TIDAL_WEB_TOKEN.count(".") >= 2
    and _TIDAL_WEB_TOKEN.startswith(("eyJ", "eyJhb"))
):
    _headers["authorization"] = f"Bearer {_TIDAL_WEB_TOKEN}"
    _headers["x-tidal-token"] = _PUBLIC_X_TIDAL
else:
    # Otherwise treat it as the public web token; fall back to the known token if missing.
    _headers["x-tidal-token"] = _TIDAL_WEB_TOKEN or _PUBLIC_X_TIDAL

_tidal_session.headers.update(_headers)

_uuid_re = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def _retry_countries(preferred: Optional[str]) -> list[str]:
    """Return a small ordered set of country codes to try for region-locked playlists."""
    base = [
        c
        for c in [preferred, _TIDAL_DEFAULT_COUNTRY, "US", "FR", "NL", "DE", "GB"]
        if c
    ]
    # de-dup while preserving order
    seen = set()
    out = []
    for c in base:
        u = c.upper()
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _extract_playlist_uuid(s: str) -> str:
    """Extract a playlist UUID from a string or URL; raises ValueError if not found."""
    m = _uuid_re.search(s or "")
    if not m:
        raise ValueError("Could not extract playlist UUID from input.")
    return m.group(0)


def _normalize_artist_list(artists):
    """Return a comma-separated artist string from varied TIDAL artist structures."""
    if not artists:
        return ""
    names = []
    for a in artists:
        if isinstance(a, dict):
            if a.get("name"):
                names.append(a["name"])
            elif isinstance(a.get("artist"), dict) and a["artist"].get("name"):
                names.append(a["artist"]["name"])
    return ", ".join(n for n in names if n)


def _iter_tracks_from_page(page_obj):
    """Yield track dicts from heterogeneous TIDAL page JSON structures."""
    # rows -> items -> data.tracks.items[*].item or data.pagedList(items)
    for row in page_obj.get("rows", []):
        for cell in row.get("items", []):
            data = cell.get("data") or {}
            tracks_obj = None
            if isinstance(data, dict):
                if (
                    "tracks" in data
                    and isinstance(data["tracks"], dict)
                    and "items" in data["tracks"]
                ):
                    tracks_obj = data["tracks"]["items"]
                elif (
                    "pagedList" in data
                    and isinstance(data["pagedList"], dict)
                    and data["pagedList"].get("type") == "TRACK"
                ):
                    tracks_obj = data["pagedList"].get("items", [])
            if tracks_obj:
                for it in tracks_obj:
                    t = it.get("item") if isinstance(it, dict) else it
                    if not isinstance(t, dict):
                        continue
                    if t.get("type") and t.get("type").lower() != "track":
                        continue
                    yield t
    # older variant
    for mod in page_obj.get("modules", []):
        if not isinstance(mod, dict):
            continue
        if mod.get("type", "").lower() in ("playlisttracks", "tracklist"):
            for it in mod.get("items", []):
                t = it.get("item") if isinstance(it, dict) else it
                if isinstance(t, dict):
                    yield t


def _fetch_playlist_tracks_openapi(
    src: str, *, country: str = None, locale: str = None
):
    """
    Return a list of normalized track dicts from the TIDAL OpenAPI `pages/playlist`.
    Fields per item: title, artist, album, isrc, duration, tidal_track_id
    Tries multiple countries if the first attempt returns 404/403 (region or not-found in that market).
    """
    pid = _extract_playlist_uuid(src)
    device_types = ["WEB", "BROWSER"]
    errors = []
    for cc in _retry_countries(country):
        loc = locale or f"en_{cc}"
        for dev in device_types:
            params = {
                "playlistId": pid,
                "countryCode": cc,
                "locale": loc,
                "deviceType": dev,
            }
            try:
                resp = _tidal_session.get(_TIDAL_OPENAPI_URL, params=params, timeout=20)
                if resp.status_code in (403, 404):
                    # Try next country/device
                    errors.append(f"{resp.status_code} for {cc}/{dev}")
                    continue
                resp.raise_for_status()
                page = resp.json()
            except Exception as e:
                errors.append(f"{type(e).__name__} for {cc}/{dev}: {e}")
                continue

            tracks = []
            for t in _iter_tracks_from_page(page):
                if isinstance(t.get("album"), dict):
                    album_title = t["album"].get("title")
                else:
                    album_title = t.get("albumTitle")
                tracks.append(
                    {
                        "title": t.get("title"),
                        "artist": _normalize_artist_list(
                            t.get("artists") or t.get("artistRoles") or []
                        ),
                        "album": album_title,
                        "isrc": t.get("isrc"),
                        "duration": t.get("duration"),
                        "tidal_track_id": t.get("id"),
                    }
                )
            if tracks:
                return tracks
            # If we parsed but got nothing, try next variant
    # If we reach here, no luck across variants: return [] and let caller decide
    if errors:
        # Surface a concise hint in verbose contexts; avoid hard-crashing the pipeline.
        if os.environ.get("TIDAL2QOBUZ_DEBUG"):
            print(
                "[debug] OpenAPI attempts failed:", "; ".join(errors), file=sys.stderr
            )
    return []


# ---- TIDAL URL normalizer ----
def _normalize_tidal_url(url: str) -> str:
    """
    Normalize various TIDAL public URLs to use the canonical 'listen.tidal.com' host
    because that host serves the public Next.js app with embedded playlist data.
    Keep listen.tidal.com as-is; rewrite tidal.com/www.tidal.com to listen.tidal.com.
    """
    try:
        u = urllib.parse.urlparse(url)
    except Exception:
        return url
    host = (u.netloc or "").lower()
    if host in ("tidal.com", "www.tidal.com"):
        return urllib.parse.urlunparse(
            ("https", "listen.tidal.com", u.path, u.params, u.query, u.fragment)
        )
    # already listen.tidal.com or another domain; leave unchanged
    return url


# ---------- Utilities ----------


def http_get(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    retries: int = 2,
    delay: float = 0.5,
) -> str:
    """HTTP GET with UA, optional headers, basic retry, and clearer SSL errors."""
    last_err = None
    req_headers = {"User-Agent": UA}
    if headers:
        req_headers.update(headers)
    for _ in range(retries + 1):
        try:
            resp = requests.get(url, headers=req_headers, timeout=15, verify=_CAFILE)
            resp.raise_for_status()
            return resp.text
        except requests.exceptions.SSLError as e:
            # Give a clearer hint and do not keep retrying on cert failures
            hint = (
                "SSL certificate verification failed. On macOS, install certifi in your venv (pip install certifi) "
                "or run the macOS 'Install Certificates.command' for your Python."
            )
            raise RuntimeError(f"GET failed for {url}: {e} — {hint}") from e
        except requests.exceptions.RequestException as e:
            last_err = e
            time.sleep(delay)
    raise RuntimeError(f"GET failed for {url}: {last_err}") from last_err


def strip_parens(text: str) -> str:
    """Remove parenthetical/bracketed substrings, used to reduce noise."""
    return re.sub(r"[\(\[][^)\]]*[\)\]]", "", text)


def normalize(text: str) -> str:
    """Lowercase, unescape, drop common edition terms and non-alphanumerics."""
    t = html.unescape(text or "")
    t = t.lower()
    t = strip_parens(t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    t = re.sub(
        r"\b(deluxe|remaster(ed)?|expanded|edition|anniversary|bonus|explicit|clean|mono|stereo)\b",
        "",
        t,
    )
    t = re.sub(r"\s+", " ", t).strip()
    return t


def token_set_ratio(a: str, b: str) -> float:
    """Compute soft overlap score using token sets of normalized strings (0..1)."""
    A = set(normalize(a).split())
    B = set(normalize(b).split())
    if not A or not B:
        return 0.0
    inter = len(A & B)
    denom = (len(A) + len(B)) / 2.0
    return inter / denom


def soft_equals(a: str, b: str, thresh: float = 0.6) -> bool:
    """Return True if token_set_ratio(a, b) >= threshold."""
    return token_set_ratio(a, b) >= thresh


def best_match_by_score(candidates: List[Tuple[float, Any]]) -> Optional[Any]:
    """Pick candidate item with highest score if above acceptance floor."""
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1] if candidates[0][0] >= 0.45 else None


# ---------- Tidal parsing (HTML/JSON-LD) ----------


def identify_tidal_kind(url: str) -> str:
    """Heuristically classify a TIDAL URL as track/album/playlist/unknown."""
    # looks for /track/, /album/, /playlist/ in the path
    path = urllib.parse.urlparse(url).path.lower()
    if "track" in path:
        return "track"
    if "album" in path:
        return "album"
    if "playlist" in path:
        return "playlist"
    return "unknown"


def extract_json_ld(html_text: str) -> List[dict]:
    """Extract and parse all JSON-LD script blocks from the given HTML."""
    out = []
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text,
        re.S | re.I,
    ):
        block = m.group(1).strip()
        try:
            data = json.loads(block)
            if isinstance(data, list):
                out.extend(data)
            else:
                out.append(data)
        except Exception:
            continue
    return out


def extract_og(html_text: str, prop: str) -> Optional[str]:
    """Return OpenGraph meta content value for the given property, if present."""
    # <meta property="og:title" content="...">
    m = re.search(
        rf'<meta\s+(?:property|name)=["\']{re.escape(prop)}["\']\s+content=["\']([^"\']+)["\']',
        html_text,
        re.I,
    )
    return html.unescape(m.group(1)) if m else None


def parse_tidal_track(html_text: str) -> Dict[str, Any]:
    """Parse track HTML/JSON-LD into a minimal dict: type, title, artist, album."""
    title = extract_og(html_text, "og:title") or ""
    # og:title often "Song Title - Artist"
    artist = ""
    if " - " in title:
        parts = title.split(" - ", 1)
        if len(parts) == 2:
            artist = parts[1].strip()
            title = parts[0].sctrip()
    # try JSON-LD for better accuracy
    for obj in extract_json_ld(html_text):
        if obj.get("@type") in ("MusicRecording",):
            title = obj.get("name") or title
            by = obj.get("byArtist")
            if isinstance(by, dict):
                artist = by.get("name") or artist
            elif isinstance(by, list) and by:
                artist = by[0].get("name") or artist
            album = (
                obj.get("inAlbum", {}) if isinstance(obj.get("inAlbum"), dict) else {}
            )
            album_title = album.get("name", "")
            return {
                "type": "track",
                "title": title,
                "artist": artist,
                "album": album_title,
            }
    # fallback
    return {"type": "track", "title": title, "artist": artist, "album": ""}


def parse_tidal_album(html_text: str) -> Dict[str, Any]:
    """Parse album HTML/JSON-LD into a dict with album, artist and optional tracks."""
    album_title = extract_og(html_text, "og:title") or ""
    artist = extract_og(html_text, "music:musician") or ""
    # JSON-LD can refine
    for obj in extract_json_ld(html_text):
        if obj.get("@type") in ("MusicAlbum",):
            album_title = obj.get("name") or album_title
            by = obj.get("byArtist")
            if isinstance(by, dict):
                artist = by.get("name") or artist
            tracks = []
            for t in obj.get("track", []) or []:
                if isinstance(t, dict):
                    tname = t.get("name") or ""
                    trk_by = t.get("byArtist")
                    tartist = ""
                    if isinstance(trk_by, dict):
                        tartist = trk_by.get("name") or ""
                    elif isinstance(trk_by, list) and trk_by:
                        tartist = trk_by[0].get("name") or ""
                    tracks.append({"title": tname, "artist": tartist or artist})
            return {
                "type": "album",
                "album": album_title,
                "artist": artist,
                "tracks": tracks,
            }
    return {"type": "album", "album": album_title, "artist": artist, "tracks": []}


def _extract_next_data(html_text: str) -> Optional[dict]:
    """Extract Next.js data from <script id="__NEXT_DATA__"> or window.__NEXT_DATA__ assignment."""
    # Inline script tag with id
    m = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        html_text,
        re.S | re.I,
    )
    blob = None
    if m:
        blob = m.group(1).strip()
    else:
        # Assignment form: window.__NEXT_DATA__ = {...};
        m2 = re.search(
            r"__NEXT_DATA__\s*=\s*(\{.*?\})\s*;?\s*</script>", html_text, re.S | re.I
        )
        if m2:
            blob = m2.group(1).strip()
    if not blob:
        return None
    try:
        return json.loads(html.unescape(blob))
    except Exception:
        # Sometimes JSON has invalid control chars; try a basic cleanup
        try:
            cleaned = blob.replace("\n", " ").replace("\r", " ")
            return json.loads(cleaned)
        except Exception:
            return None


def _collect_tracks_from_json(obj: Any, out: List[dict]):
    """Recursively collect {title, artist} pairs from arbitrary JSON."""
    if isinstance(obj, dict):
        t = obj.get("title") or obj.get("name")
        a = obj.get("artist") or obj.get("artists") or obj.get("byArtist")
        artist_name = None
        if isinstance(a, dict):
            artist_name = a.get("name") or None
        elif isinstance(a, list) and a:
            names = []
            for it in a:
                if isinstance(it, dict) and it.get("name"):
                    names.append(str(it.get("name")))
                elif isinstance(it, str):
                    names.append(it)
            if names:
                artist_name = ", ".join(names)
        elif isinstance(a, str):
            artist_name = a
        if isinstance(t, str) and artist_name and t.strip() and artist_name.strip():
            out.append({"title": t.strip(), "artist": artist_name.strip()})
        for k, v in obj.items():
            if k in (
                "items",
                "tracks",
                "results",
                "data",
                "rows",
                "cells",
                "entities",
                "nodes",
                "edges",
            ):
                _collect_tracks_from_json(v, out)
            elif isinstance(v, (dict, list)):
                _collect_tracks_from_json(v, out)
    elif isinstance(obj, list):
        for it in obj:
            _collect_tracks_from_json(it, out)


def parse_tidal_playlist(html_text: str) -> Dict[str, Any]:
    """Parse playlist HTML (JSON-LD/Next.js) into title and list of {title, artist}."""
    # Tidal playlist pages often embed track data in a Next.js JSON block.
    tracks: List[Dict[str, str]] = []
    title = extract_og(html_text, "og:title") or "Playlist"

    # Try JSON-LD MusicPlaylist first
    try:
        for obj in extract_json_ld(html_text):
            if isinstance(obj, dict) and obj.get("@type") in (
                "MusicPlaylist",
                "Playlist",
            ):
                tlist = obj.get("track") or obj.get("tracks") or []
                for t in tlist:
                    if not isinstance(t, dict):
                        continue
                    nm = t.get("name") or t.get("title")
                    by = t.get("byArtist") or t.get("artist") or t.get("artists")
                    artist_name = ""
                    if isinstance(by, dict):
                        artist_name = by.get("name") or ""
                    elif isinstance(by, list) and by:
                        if isinstance(by[0], dict):
                            artist_name = by[0].get("name") or ""
                        elif isinstance(by[0], str):
                            artist_name = by[0]
                    if isinstance(nm, str) and artist_name:
                        tracks.append(
                            {"title": nm.strip(), "artist": artist_name.strip()}
                        )
        if tracks:
            # de-duplicate
            seen = set()
            uniq = []
            for t in tracks:
                k = (t["title"], t["artist"])
                if k not in seen:
                    seen.add(k)
                    uniq.append(t)
            return {"type": "playlist", "title": title, "tracks": uniq}
    except Exception:
        pass

    # Try Next.js data
    data = _extract_next_data(html_text)
    if data:
        tmp: List[dict] = []
        _collect_tracks_from_json(data, tmp)
        # If the greedy collector yields nothing, try a targeted path commonly used by listen.tidal.com:
        # data.props.pageProps.dehydratedState.queries[*].state.data.rows[*].items[*].data.tracks.items[*].item
        if not tmp:
            try:
                pp = data.get("props", {}).get("pageProps", {})
                dehyd = pp.get("dehydratedState", {}) or {}
                queries = dehyd.get("queries", []) or []
                for q in queries:
                    state = q.get("state", {}) or {}
                    d = state.get("data", {}) or {}
                    for row in d.get("rows", []) or []:
                        for cell in row.get("items", []) or []:
                            cell_data = cell.get("data", {}) or {}
                            tracks_obj = None
                            if isinstance(cell_data, dict):
                                if (
                                    "tracks" in cell_data
                                    and isinstance(cell_data["tracks"], dict)
                                    and "items" in cell_data["tracks"]
                                ):
                                    tracks_obj = cell_data["tracks"]["items"]
                                elif (
                                    "pagedList" in cell_data
                                    and isinstance(cell_data["pagedList"], dict)
                                    and cell_data["pagedList"].get("type") == "TRACK"
                                ):
                                    tracks_obj = cell_data["pagedList"].get("items", [])
                            if tracks_obj:
                                for it in tracks_obj:
                                    t = it.get("item") if isinstance(it, dict) else it
                                    if isinstance(t, dict) and (
                                        t.get("title") or t.get("name")
                                    ):
                                        title = t.get("title") or t.get("name") or ""
                                        artists = t.get("artists") or []
                                        artist_name = ""
                                        if isinstance(artists, list) and artists:
                                            if isinstance(artists[0], dict):
                                                artist_name = (
                                                    artists[0].get("name") or ""
                                                )
                                            elif isinstance(artists[0], str):
                                                artist_name = artists[0]
                                        if title and artist_name:
                                            tmp.append(
                                                {"title": title, "artist": artist_name}
                                            )
            except Exception:
                pass
        # De-duplicate tmp into tracks
        seen = set()
        for t in tmp:
            key = (t.get("title"), t.get("artist"))
            if key not in seen and t.get("title") and t.get("artist"):
                seen.add(key)
                tracks.append({"title": t.get("title"), "artist": t.get("artist")})

    # Fallbacks: greedy regex patterns
    if not tracks:
        # pattern 1: "title":"...","artist":"..."
        for m in re.finditer(
            r'\{\s*"title"\s*:\s*"([^"\\]+)"\s*,\s*"artist"\s*:\s*"([^"\\]+)"',
            html_text,
        ):
            ttitle = html.unescape(m.group(1))
            tartist = html.unescape(m.group(2))
            if ttitle and tartist:
                tracks.append({"title": ttitle, "artist": tartist})
        # pattern 2: "trackTitle":"...","artistName":"..."
        for m in re.finditer(
            r'\{[^}]*"trackTitle"\s*:\s*"([^"\\]+)"[^}]*"artistName"\s*:\s*"([^"\\]+)"[^}]*\}',
            html_text,
        ):
            ttitle = html.unescape(m.group(1))
            tartist = html.unescape(m.group(2))
            if ttitle and tartist:
                tracks.append({"title": ttitle, "artist": tartist})
        # de-duplicate while preserving order
        seen = set()
        uniq = []
        for t in tracks:
            key = (t["title"], t["artist"])
            if key not in seen:
                seen.add(key)
                uniq.append(t)
        tracks = uniq

    return {"type": "playlist", "title": title, "tracks": tracks}


def parse_tidal_url(url: str) -> Dict[str, Any]:
    """
    Try fetching and parsing the TIDAL URL with multiple host fallbacks to handle
    DNS or regional issues (listen.tidal.com vs tidal.com vs www.tidal.com).
    If HTML fetching fails but the path indicates a playlist, return a minimal
    object so the caller can attempt API-based fallbacks.
    """
    kind = identify_tidal_kind(url)

    # Build candidate URLs: original, normalized-to-open, and host fallbacks
    candidates = []
    try:
        u = urllib.parse.urlparse(url)
    except Exception:
        u = None
    if u:
        candidates.append(url)
        host = (u.netloc or "").lower()
        # Prefer listen.tidal.com variant
        open_url = urllib.parse.urlunparse(
            ("https", "listen.tidal.com", u.path, u.params, u.query, u.fragment)
        )
        if open_url not in candidates:
            candidates.append(open_url)
        # Add tidal.com and www.tidal.com variants
        tidal_url = urllib.parse.urlunparse(
            ("https", "tidal.com", u.path, u.params, u.query, u.fragment)
        )
        if tidal_url not in candidates:
            candidates.append(tidal_url)
        www_tidal_url = urllib.parse.urlunparse(
            ("https", "www.tidal.com", u.path, u.params, u.query, u.fragment)
        )
        if www_tidal_url not in candidates:
            candidates.append(www_tidal_url)
    else:
        # Fallback: try normalized only
        candidates.append(_normalize_tidal_url(url))

    last_err: Optional[Exception] = None
    html_text: Optional[str] = None
    used_url = None
    for cu in candidates:
        try:
            html_text = http_get(cu)
            used_url = cu
            break
        except Exception as e:
            last_err = e
            continue

    if html_text is None:
        # If we cannot fetch HTML at all, surface a softer failure for playlists so
        # the caller can use the OpenAPI fallback later.
        if kind == "playlist":
            return {"type": "playlist", "title": "", "tracks": []}
        # Otherwise, raise the last error to keep behavior explicit.
        raise RuntimeError(f"GET failed for {candidates[0]}: {last_err}")

    if kind == "track":
        return parse_tidal_track(html_text)
    elif kind == "album":
        return parse_tidal_album(html_text)
    elif kind == "playlist":
        return parse_tidal_playlist(html_text)
    else:
        # Try to infer from JSON-LD if path was ambiguous
        objs = extract_json_ld(html_text)
        types = {o.get("@type") for o in objs if isinstance(o, dict)}
        if "MusicRecording" in types:
            return parse_tidal_track(html_text)
        if "MusicAlbum" in types:
            return parse_tidal_album(html_text)
        return {"type": "unknown"}


# ---------- Qobuz search ----------


def qobuz_search(query: str) -> dict:
    """Query the Qobuz search API and return parsed JSON; requires stored credentials."""
    if not QOBUZ_APP_ID or not QOBUZ_USER_AUTH_TOKEN:
        error_message = "Error: Qobuz credentials not found in Keychain.\n"
        error_message += f"Please store them by running the following commands:\n\n"
        if not QOBUZ_APP_ID:
            error_message += f"  keyring set {SERVICE_NAME} qobuz_app_id\n"
        if not QOBUZ_USER_AUTH_TOKEN:
            error_message += f"  keyring set {SERVICE_NAME} qobuz_user_auth_token\n"
        raise SystemExit(error_message)

    params = {"app_id": QOBUZ_APP_ID, "query": query}
    url = QOBUZ_SEARCH_BASE + "?" + urllib.parse.urlencode(params)

    headers = {}
    if QOBUZ_USER_AUTH_TOKEN:
        headers["X-User-Auth-Token"] = QOBUZ_USER_AUTH_TOKEN

    data = http_get(url, headers=headers)
    try:
        return json.loads(data)
    except Exception as e:
        raise RuntimeError(f"Qobuz search parse error: {e}; raw={data[:280]}")


def pick_best_track(
    qres: dict, t_title: str, t_artist: str, t_album: str = ""
) -> Optional[dict]:
    """Score Qobuz tracks against title/artist/album and return the best match."""
    tracks = (qres.get("tracks") or {}).get("items") or []
    scored = []
    for tr in tracks:
        q_title = tr.get("title", "")
        q_artist = (tr.get("performer", {}) or {}).get("name", "") or (
            tr.get("album", {}).get("artist", {}) or {}
        ).get("name", "")
        q_album = (tr.get("album") or {}).get("title", "")
        # score = weighted sum of overlaps
        s_title = token_set_ratio(t_title, q_title) * 0.5
        s_artist = token_set_ratio(t_artist, q_artist) * 0.3
        s_album = token_set_ratio(t_album, q_album) * 0.2 if t_album else 0.0
        score = s_title + s_artist + s_album
        scored.append((score, tr))
    return best_match_by_score(scored)


def pick_best_album(qres: dict, a_title: str, a_artist: str = "") -> Optional[dict]:
    """Score Qobuz albums against title/artist and return the best match."""
    albums = (qres.get("albums") or {}).get("items") or []
    scored = []
    for al in albums:
        q_title = al.get("title", "")
        q_artist = (al.get("artist") or {}).get("name", "")
        s_title = token_set_ratio(a_title, q_title) * 0.6
        s_artist = token_set_ratio(a_artist, q_artist) * 0.4 if a_artist else 0.0
        score = s_title + s_artist
        scored.append((score, al))
    return best_match_by_score(scored)


def build_query_for_track(t: Dict[str, Any]) -> str:
    """Build a compact search query from a track dict (artist, title, optional album)."""
    parts = [t.get("artist") or "", t.get("title") or ""]
    if t.get("album"):
        parts.append(t["album"])
    return " ".join(p for p in parts if p).strip()


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint: resolve a TIDAL URL to Qobuz links; supports JSON/CSV output."""
    parser = argparse.ArgumentParser(description="Map a Tidal URL to Qobuz content")
    parser.add_argument("url", help="Tidal track/album/playlist URL")
    parser.add_argument("--json", dest="json_out", help="Write results to JSON file")
    parser.add_argument(
        "--csv", dest="csv_out", help="Write results to CSV file (playlist only)"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "--tidal-country",
        dest="tidal_country",
        help="TIDAL country code (for OpenAPI fallback)",
    )
    args = parser.parse_args(argv)

    url = args.url
    kind = identify_tidal_kind(url)
    if kind == "unknown":
        print(f"[error] Could not determine Tidal URL type: {url}", file=sys.stderr)
        return 2

    try:
        parsed = parse_tidal_url(url)
    except Exception as e:
        print(f"[error] Failed to load/parse Tidal URL: {e}", file=sys.stderr)
        return 3

    results: Dict[str, Any] = {
        "source": {"url": url, "type": parsed.get("type")},
        "matches": [],
    }

    if parsed.get("type") == "track":
        qq = build_query_for_track(parsed)
        if args.verbose:
            print(f"[info] Searching Qobuz for: {qq}")
        qres = qobuz_search(qq)
        best = pick_best_track(
            qres,
            parsed.get("title", ""),
            parsed.get("artist", ""),
            parsed.get("album", ""),
        )
        if best:
            link = QOBUZ_OPEN_TRACK.format(id=best.get("id"))
            print(
                f"Track: {parsed.get('artist','')} - {parsed.get('title','')}\n → {link}"
            )
            results["matches"].append(
                {
                    "type": "track",
                    "qobuz_id": best.get("id"),
                    "open_url": link,
                    "title": best.get("title"),
                    "artist": (best.get("performer") or {}).get("name"),
                }
            )
        else:
            print("[warn] No suitable Qobuz track found.")

    elif parsed.get("type") == "album":
        a_title = parsed.get("album", "")
        a_artist = parsed.get("artist", "")
        query = f"{a_artist} {a_title}".strip()
        if args.verbose:
            print(f"[info] Searching Qobuz for album: {query}")
        qres = qobuz_search(query)
        best = pick_best_album(qres, a_title, a_artist)
        if best:
            link = QOBUZ_OPEN_ALBUM.format(id=best.get("id"))
            print(f"Album: {a_artist} - {a_title}\n → {link}")
            results["matches"].append(
                {
                    "type": "album",
                    "qobuz_id": best.get("id"),
                    "open_url": link,
                    "title": best.get("title"),
                    "artist": (best.get("artist") or {}).get("name"),
                }
            )
        else:
            print("[warn] No suitable Qobuz album found.")

    elif parsed.get("type") == "playlist":
        tracks = parsed.get("tracks") or []
        if not tracks:
            api_tracks = _fetch_playlist_tracks_openapi(
                url, country=getattr(args, "tidal_country", None)
            )
            if api_tracks:
                print("[info] Using TIDAL OpenAPI fallback for playlist tracks")
                tracks = [
                    {
                        "title": t.get("title"),
                        "artist": t.get("artist"),
                        "album": t.get("album"),
                    }
                    for t in api_tracks
                ]
        if not tracks:
            # last resort: re-fetch HTML from listen.tidal.com explicitly and parse again
            try:
                # Build an listen.tidal.com URL explicitly to ensure we hit the Next.js app
                u = urllib.parse.urlparse(url)
                open_url = urllib.parse.urlunparse(
                    ("https", "listen.tidal.com", u.path, u.params, u.query, u.fragment)
                )
                html2 = http_get(open_url, headers={"User-Agent": UA})
                parsed2 = parse_tidal_playlist(html2)
                tracks = parsed2.get("tracks") or tracks
                if tracks:
                    print("[info] Using HTML Next.js fallback from listen.tidal.com")
            except Exception as e:
                if args.verbose:
                    print(f"[warn] HTML fallback failed: {e}")
        if not tracks:
            print("[warn] Playlist contained no parsable tracks.")
            print(
                "[hint] This can happen if the playlist is private or region-locked, or if your token is mismatched."
            )
            print("[hint] Try one of the following:")
            print("       • Unset TIDAL_WEB_TOKEN to use the public web token")
            print(
                "       • Or export a valid JWT to TIDAL_WEB_TOKEN (will be used as Authorization: Bearer)"
            )
            print("       • Or pass --tidal-country US (or another country code)")
            if args.verbose:
                print(
                    "[hint] This can happen if the playlist is private or region-locked, or if your token is mismatched."
                )
                print("[hint] Try one of the following:")
                print("       • Unset TIDAL_WEB_TOKEN to use the public web token")
                print(
                    "       • Or export a valid JWT to TIDAL_WEB_TOKEN (will be used as Authorization: Bearer)"
                )
                print("       • Or pass --tidal-country US (or another country code)")
        print(f"Playlist: {parsed.get('title','')} — {len(tracks)} track(s)")
        # optional CSV writer
        csv_writer = None
        csv_file = None
        if args.csv_out:
            csv_file = open(args.csv_out, "w", newline="", encoding="utf-8")
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(["title", "artist", "qobuz_open_url", "qobuz_id"])
        for i, t in enumerate(tracks, 1):
            qq = build_query_for_track(t)
            if args.verbose:
                print(f"[info] [{i}/{len(tracks)}] Searching: {qq}")
            try:
                qres = qobuz_search(qq)
                best = pick_best_track(
                    qres, t.get("title", ""), t.get("artist", ""), t.get("album", "")
                )
            except SystemExit as se:
                # credentials error bubbled up, re-raise for clarity
                if csv_file:
                    csv_file.close()
                raise
            except Exception as e:
                best = None
                if args.verbose:
                    print(f"[warn] Qobuz search failed for '{qq}': {e}")
            if best:
                link = QOBUZ_OPEN_TRACK.format(id=best.get("id"))
                print(f"  - {t.get('artist','')} - {t.get('title','')} → {link}")
                results["matches"].append(
                    {
                        "type": "track",
                        "qobuz_id": best.get("id"),
                        "open_url": link,
                        "title": best.get("title"),
                        "artist": (best.get("performer") or {}).get("name"),
                    }
                )
                if csv_writer:
                    csv_writer.writerow(
                        [t.get("title", ""), t.get("artist", ""), link, best.get("id")]
                    )
            else:
                print(f"  - {t.get('artist','')} - {t.get('title','')} → [no match]")
            time.sleep(0.15)  # be gentle
        if csv_file:
            csv_file.close()
    else:
        print(f"[error] Unhandled parsed type: {parsed.get('type')}", file=sys.stderr)
        return 4

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        if args.verbose:
            print(f"[info] Wrote JSON: {args.json_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
