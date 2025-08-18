import json
import os
from pathlib import Path
import logging
from collections import Counter
from typing import List, Tuple

from rich.progress import Progress
from rich.prompt import Prompt
from thefuzz import process as fuzzy_process

from .config import console, config
from .metadata import normalize_string
from .matcher import calculate_match_score
from .metadata import parse_filename_structure

logger = logging.getLogger(__name__)


def _filter_flac_lookup(flac_lookup: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Filter out invalid or hidden files (e.g., macOS AppleDouble '._' files)."""
    filtered: list[tuple[str, str]] = []
    for path, norm in flac_lookup:
        try:
            if Path(path).name.startswith("._"):
                continue
        except Exception:
            # In case of any unexpected value, keep it (fail open)
            pass
        filtered.append((path, norm))
    return filtered

def parse_m3u(path: Path) -> list[str]:
    """Parses a simple M3U or M3U8 playlist file."""
    with open(path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

def parse_json_playlist(path: Path) -> list[str]:
    """Parses a JSON file containing track information."""
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict) and "tracks" in data[0]:
        data = data[0]["tracks"]
    elif isinstance(data, dict) and "tracks" in data:
        data = data["tracks"]
    elif not isinstance(data, list):
        return []

    tracks = []
    for track in data:
        if isinstance(track, dict):
            parts = [track.get(k, '').strip() for k in ['artist', 'album', 'title', 'track']]
            search_string = ' '.join(filter(None, parts))
            tracks.append(search_string or str(track))
        else:
            tracks.append(str(track))
    return tracks

def get_playlist_tracks(playlist_input: str) -> list[str] | None:
    path = Path(playlist_input)
    if not path.exists():
        console.print(f"[red]Error: Input file not found at {path}[/red]")
        return None
    suffix = path.suffix.lower()
    if suffix in ('.m3u', '.m3u8', '.txt'):
        return parse_m3u(path)
    elif suffix == '.json':
        return parse_json_playlist(path)
    else:
        console.print(f"[red]Unsupported playlist format: {suffix}[/red]")
        return None

def review_uncertain_matches(uncertain_matches: dict) -> dict[str, str | None]:
    reviewed_matches = {}
    HIGH_CONFIDENCE_THRESHOLD = 88
    for track, candidates in uncertain_matches.items():
        console.print(f"\n[bold yellow]UNCERTAIN:[/] {track}")
        high_confidence = False
        if candidates and candidates[0][1] >= HIGH_CONFIDENCE_THRESHOLD:
            high_confidence = True
        for i, (candidate_path, score) in enumerate(candidates, 1):
            marker = " [high confidence]" if i == 1 and high_confidence else ""
            console.print(f"  {i}) [{int(score)}] {candidate_path}{marker}")
        console.print("  s) Skip", "  m) Manual path")
        if high_confidence:
            console.print("[green]Press Enter to accept the high-confidence match, or choose another option.[/green]")
        choice = Prompt.ask("Choice", choices=[str(i) for i in range(1, len(candidates) + 1)] + ["s", "m"], default="1")
        if choice.isdigit() and 1 <= int(choice) <= len(candidates):
            reviewed_matches[track] = candidates[int(choice) - 1][0]
        elif choice == "m":
            manual_path = Prompt.ask("Enter full path").strip()
            if manual_path and Path(manual_path).exists():
                reviewed_matches[track] = manual_path
            else:
                reviewed_matches[track] = None
        else:
            reviewed_matches[track] = None
    return reviewed_matches

def manual_match_unmatched(unmatched_tracks: list, flac_lookup: list[tuple[str, str]]) -> dict[str, str | None]:
    manual_matches = {}
    # Ensure we also filter hidden files for manual matching phase
    flac_lookup = _filter_flac_lookup(flac_lookup)
    path_map = {norm: path for path, norm in flac_lookup}
    library_choices = list(path_map.keys())
    for track in unmatched_tracks:
        console.print(f"\n[bold red]UNMATCHED:[/] {track}")
        # Use the original path if available, else the normalized string
        source_path = track if os.path.exists(track) else None
        if source_path:
            source_meta = parse_filename_structure(source_path)
        else:
            # Try to find the path from the lookup
            source_meta = parse_filename_structure(path_map.get(track, track))
        # Score all candidates using metadata-aware scorer
        scored_candidates = []
        for norm in library_choices:
            candidate_path = path_map[norm]
            candidate_meta = parse_filename_structure(candidate_path)
            score = calculate_match_score(source_meta, candidate_meta)
            scored_candidates.append((norm, score))
        # Sort by score descending, take top 5
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        candidates = scored_candidates[:5]
        for i, (norm, score) in enumerate(candidates, 1):
            console.print(f"  {i}) [{score}] {path_map[norm]}")
        console.print("  s) Skip", "  m) Manual path")
        # Default to first candidate on Enter for faster manual resolution
        choice = Prompt.ask("Choice", choices=[str(i) for i in range(1, len(candidates) + 1)] + ["s", "m"], default="1")
        if choice.isdigit() and 1 <= int(choice) <= len(candidates):
            manual_matches[track] = path_map[candidates[int(choice) - 1][0]]
        elif choice == "m":
            manual_path = Prompt.ask("Enter full path").strip()
            if manual_path and Path(manual_path).exists():
                manual_matches[track] = manual_path
            else:
                manual_matches[track] = None
        else:
            manual_matches[track] = None
    return manual_matches

def _build_inverted_index(library_choices: list[str]) -> dict:
    """Builds an inverted index from words to normalized track strings for fast lookup."""
    logger.info("Building inverted index for the library...")
    inverted_index = {}
    for norm in library_choices:
        words = {word for word in norm.split() if len(word) > 2}
        for word in words:
            if word not in inverted_index:
                inverted_index[word] = []
            inverted_index[word].append(norm)
    logger.info("Index built.")
    return inverted_index


def _word_overlap_fraction(a: str, b: str) -> float:
    """Compute fraction of overlapping words between two normalized strings.
    Uses words of length > 2. Returns 0.0..1.0. If no query words, returns 0.0.
    """
    a_words = {w for w in a.split() if len(w) > 2}
    b_words = {w for w in b.split() if len(w) > 2}
    if not a_words:
        return 0.0
    return len(a_words & b_words) / float(len(a_words))

def _tokenize_words(text: str) -> list[str]:
    """Simple alnum tokenizer used for building query/index words."""
    import re as _re
    if not text:
        return []
    return [w for w in _re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2]


def _build_query_text_from_source(source: str) -> str:
    """If the track string looks like a path, derive a better query from its metadata.
    Otherwise, return the original string.
    """
    try:
        if isinstance(source, str) and ("/" in source or source.lower().endswith(".flac")):
            meta = parse_filename_structure(source)
            parts = [meta.get("artist", ""), meta.get("title", ""), meta.get("album", "")]
            return " ".join(p for p in parts if p)
    except Exception:
        pass
    return source


def _get_candidates_from_index(norm_query: str, inverted_index: dict) -> list[str]:
    """Gets a set of candidate strings from the inverted index based on word overlap.
    Enhanced to handle path-like inputs via metadata tokenization.
    """
    # Build an improved query text first
    improved = _build_query_text_from_source(norm_query)
    query_words = set(_tokenize_words(improved))
    if not query_words:
        return []

    candidate_norms = set()
    for word in query_words:
        if word in inverted_index:
            candidate_norms.update(inverted_index[word])

    return list(candidate_norms)

def find_best_match(norm_query: str, candidate_choices: list[str], path_map: dict, original_source: str | None = None) -> tuple[str, float] | None:
    """Finds the best match from a list of pre-filtered candidates using metadata-aware scoring.

    Uses the original source string for metadata parsing when available (and especially
    when it looks like a filesystem path), falling back to norm_query otherwise.
    """
    if not candidate_choices:
        return None
    # Extract metadata for the source (query)
    # Prefer the original source string to retain path structure for parsing
    source_text = original_source or norm_query
    try:
        if isinstance(source_text, str) and ("/" in source_text or source_text.lower().endswith(".flac")):
            source_meta = parse_filename_structure(source_text)
        else:
            # If we have a direct mapping from norm to path, use it; else parse the text as-is
            source_path = path_map.get(norm_query, source_text)
            source_meta = parse_filename_structure(source_path)
    except Exception:
        # Fail-safe: parse whatever we have
        source_meta = parse_filename_structure(source_text)
    best_score = -1
    best_candidate_norm = None
    for candidate_norm in candidate_choices:
        candidate_path = path_map[candidate_norm]
        candidate_meta = parse_filename_structure(candidate_path)
        score = calculate_match_score(source_meta, candidate_meta)
        if score > best_score:
            best_score = score
            best_candidate_norm = candidate_norm
    if best_candidate_norm is not None:
        return path_map[best_candidate_norm], float(best_score)
    return None

def _score_candidates_with_metadata(norm_query: str, path_map: dict, library_choices: list[str], original_source: str | None = None, limit: int = 5) -> list[tuple[str, float]]:
    """Build top-N candidates scored with calculate_match_score for review.

    Returns a list of (candidate_path, composite_score) sorted desc.
    """
    # Build source metadata
    source_text = original_source or norm_query
    try:
        if isinstance(source_text, str) and ("/" in source_text or str(source_text).lower().endswith(".flac")):
            source_meta = parse_filename_structure(source_text)
        else:
            src_path = path_map.get(norm_query, source_text)
            source_meta = parse_filename_structure(src_path)
    except Exception:
        source_meta = parse_filename_structure(source_text)

    # Seed candidates using fuzzy to narrow down, then rescore with metadata
    seed_norms = [c[0] for c in fuzzy_process.extract(norm_query, library_choices, limit=max(limit * 10, 50))]
    seen = set()
    scored: list[tuple[str, float]] = []
    for norm in seed_norms:
        if norm in seen:
            continue
        seen.add(norm)
        cand_path = path_map[norm]
        cand_meta = parse_filename_structure(cand_path)
        score = float(calculate_match_score(source_meta, cand_meta))
        scored.append((cand_path, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:limit]

def perform_matching_with_review(
    tracks: list[str],
    flac_lookup: list[tuple[str, str]],
    threshold: int = 85,
    review_min: int = 65
) -> dict[str, str | None]:
    console.print(f"[blue]Matching {len(tracks)} tracks (threshold {threshold}, review {review_min})[/blue]")
    # Filter out AppleDouble and similar hidden files from the library list
    flac_lookup = _filter_flac_lookup(flac_lookup)
    path_map = {norm: path for path, norm in flac_lookup}
    library_choices = list(path_map.keys())
    inverted_index = _build_inverted_index(library_choices)

    results = {track: None for track in tracks}
    uncertain_candidates = {}
    unmatched_queue = []
    auto_match_scores = []
    used_library_paths: set[str] = set()

    with Progress(console=console) as progress:
        task = progress.add_task("[green]Finding matches...[/green]", total=len(tracks))
        for track in tracks:
            norm_query = normalize_string(track)
            if not norm_query:
                progress.update(task, advance=1)
                continue

            if norm_query in path_map:
                match_path, score = path_map[norm_query], 100
            else:
                candidate_choices = _get_candidates_from_index(norm_query, inverted_index)
                # Fallback: if index yields nothing, use fuzzy to collect a wider candidate pool
                if not candidate_choices:
                    candidate_choices = [c[0] for c in fuzzy_process.extract(norm_query, library_choices, limit=50)]
                match_path, score = find_best_match(norm_query, candidate_choices, path_map, original_source=track) or (None, 0)

            if match_path and match_path in used_library_paths:
                logger.debug("Skipping candidate already used: %s", match_path)
                match_path, score = None, 0

            # Apply word-overlap sanity check before accepting
            overlap_ok = False
            if match_path:
                # match_path corresponds to a path; need its normalized key to compute overlap.
                # Reverse-lookup norm from path_map
                # path_map maps norm->path, so build reverse lazily for this check
                try:
                    # small reverse map for this single check
                    matched_norm = next(n for n, p in path_map.items() if p == match_path)
                    overlap = _word_overlap_fraction(norm_query, matched_norm)
                    overlap_ok = overlap >= float(config.get('WORD_OVERLAP_REJECT', 0.15))
                except StopIteration:
                    overlap_ok = True  # if unknown, don't block
            if match_path and score >= threshold and overlap_ok:
                console.print(f"[green][AUTO][/green] {int(score)} {track} → {match_path}")
                console.print("─" * 80)
                results[track] = match_path
                auto_match_scores.append(score)
                used_library_paths.add(match_path)
            elif match_path and review_min <= score < threshold:
                # If word overlap is too low, downgrade to unmatched; if borderline, keep for review
                try:
                    matched_norm = next(n for n, p in path_map.items() if p == match_path)
                    overlap = _word_overlap_fraction(norm_query, matched_norm)
                except StopIteration:
                    overlap = 1.0
                review_floor = float(config.get('WORD_OVERLAP_REVIEW', 0.40))
                reject_floor = float(config.get('WORD_OVERLAP_REJECT', 0.15))
                if overlap < reject_floor:
                    unmatched_queue.append(track)
                else:
                    # Build metadata-scored candidates for consistent review display
                    candidates = _score_candidates_with_metadata(norm_query, path_map, library_choices, original_source=track, limit=5)
                    uncertain_candidates[track] = candidates
            else:
                unmatched_queue.append(track)
                if match_path:
                    logger.info("REJECTED: Low score (%.1f) for '%s' -> '%s'", score, track, match_path)
            progress.update(task, advance=1)

    HIGH_CONFIDENCE_THRESHOLD = 88
    if len(auto_match_scores) >= 5:
        score_counts = Counter(auto_match_scores)
        most_common_list = score_counts.most_common(1)
        if most_common_list:
            most_common_score, max_same_count = most_common_list[0]
            if max_same_count / len(auto_match_scores) > 0.7:
                console.print(f"\n[bold yellow]⚠️ SUSPICIOUS MATCHING DETECTED ⚠️[/bold yellow]")
                console.print(f"[yellow]{max_same_count}/{len(auto_match_scores)} tracks got score {most_common_score}. Moving to review.[/yellow]")
                for track, path in list(results.items()):
                    if path is not None:
                        norm_query = normalize_string(track)
                        candidate_norm = next((n for n, p in path_map.items() if p == path), None)
                        if candidate_norm:
                            source_meta = parse_filename_structure(track)
                            candidate_meta = parse_filename_structure(path)
                            score = calculate_match_score(source_meta, candidate_meta)
                            score_rounded = int(round(score))
                            if score_rounded < HIGH_CONFIDENCE_THRESHOLD:
                                # Build metadata-scored candidates for this track
                                candidates = _score_candidates_with_metadata(norm_query, path_map, library_choices, original_source=track, limit=5)
                                uncertain_candidates[track] = candidates
                                results[track] = None
                                logger.debug(f"[Suspicious] Sent to review: {track} (score={score}, rounded={score_rounded})")
                            else:
                                logger.debug(f"[Suspicious] Auto-matched: {track} (score={score}, rounded={score_rounded})")
                        else:
                            candidates = _score_candidates_with_metadata(norm_query, path_map, library_choices, original_source=track, limit=5)
                            uncertain_candidates[track] = candidates
                            results[track] = None
                            logger.debug(f"[Suspicious] Sent to review (no candidate_norm): {track}")

    if uncertain_candidates:
        console.print(f"\n[yellow]Reviewing {len(uncertain_candidates)} uncertain matches...[/yellow]")
        reviewed = review_uncertain_matches(uncertain_candidates)
        for track, path in reviewed.items():
            if path:
                results[track] = path
            else:
                unmatched_queue.append(track)

    if unmatched_queue:
        console.print(f"\n[red]Manual matching for {len(unmatched_queue)} remaining tracks...[/red]")
        manual_matches = manual_match_unmatched(unmatched_queue, flac_lookup)
        results.update(manual_matches)

    return results

def find_matches(tracks, flac_lookup, threshold=85, review_min=65):
    flac_lookup = _filter_flac_lookup(flac_lookup)
    path_map = {norm: path for path, norm in flac_lookup}
    library_choices = list(path_map.keys())
    inverted_index = _build_inverted_index(library_choices)

    results = {track: None for track in tracks}
    auto_match_scores: list[int] = []
    used_library_paths: set[str] = set()

    for track in tracks:
        norm_query = normalize_string(track)
        if not norm_query:
            continue

        if norm_query in path_map:
            match_path, score = path_map[norm_query], 100
        else:
            candidate_choices = _get_candidates_from_index(norm_query, inverted_index)
            if not candidate_choices:
                candidate_choices = [c[0] for c in fuzzy_process.extract(norm_query, library_choices, limit=50)]
            match_path, score = find_best_match(norm_query, candidate_choices, path_map, original_source=track) or (None, 0)

        if match_path and match_path in used_library_paths:
            logger.debug("Skipping candidate already used: %s", match_path)
            match_path, score = None, 0

        # Apply word-overlap sanity check
        overlap_ok = False
        if match_path:
            try:
                matched_norm = next(n for n, p in path_map.items() if p == match_path)
                overlap = _word_overlap_fraction(norm_query, matched_norm)
                overlap_ok = overlap >= float(config.get('WORD_OVERLAP_REJECT', 0.15))
            except StopIteration:
                overlap_ok = True
        if match_path and score >= threshold and overlap_ok:
            console.print(f"[green]MATCH:[/] '{track}' → '{match_path}' (Score: {int(score)})")
            results[track] = match_path
            auto_match_scores.append(int(round(score)))
            used_library_paths.add(match_path)
        else:
            results[track] = None

    if len(auto_match_scores) >= 5:
        score_counts = Counter(auto_match_scores)
        most_common_list = score_counts.most_common(1)
        if most_common_list:
            most_common_score, max_same_count = most_common_list[0]
            if max_same_count / len(auto_match_scores) > 0.7:
                console.print(f"\n⚠️ SUSPICIOUS MATCHING DETECTED ⚠️")
                console.print(f"{max_same_count}/{len(auto_match_scores)} tracks got score {most_common_score}. Moving to review.")
                for track, path in list(results.items()):
                    if path is not None:
                        results[track] = None

    return results

def write_match_json(matches: dict, output_path: str):
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)

def write_match_m3u(matches: dict, output_path: str):
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for i, (track, path) in enumerate(m for m in matches.items() if m[1] is not None):
            f.write(f"\n# Track {i+1}: {track}\n# {'='*60}\n{path}\n")

def write_songshift_json(tracks: list[dict], output_path: str, playlist_name: str = "Unmatched Tracks", service: str = "qobuz"):
    payload = [{"service": service, "serviceId": None, "name": playlist_name, "tracks": tracks}]
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        console.print(f"[bold green]✓ SongShift playlist saved:[/] {output_path} ({len(tracks)} tracks)")
    except Exception as e:
        console.print(f"[red]Error writing SongShift playlist: {e}[/red]")

def extract_unmatched_tracks(tracks_list: list[str], matches: dict) -> list[dict]:
    unmatched = []
    for track_name in tracks_list:
        if matches.get(track_name) is None:
            parts = track_name.split(' - ', 1)
            artist, title = parts if len(parts) == 2 else ("Unknown Artist", track_name)
            unmatched.append({"artist": artist.strip(), "track": title.strip()})
    return unmatched
