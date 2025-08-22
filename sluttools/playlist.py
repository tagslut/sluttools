import logging
from typing import Optional, Protocol

logger = logging.getLogger(__name__)


class DatabaseInterface(Protocol):
    """Protocol for database operations."""
    
    def track_exists(self, track_id: str) -> bool:
        """Check if a track exists in the database."""
        ...
    
    def batch_insert_tracks(self, tracks: list[dict]) -> None:
        """Insert multiple tracks into the database."""
        ...


class MockDatabase:
    """Mock database implementation for testing/placeholder purposes."""
    
    def __init__(self):
        self._existing_track_ids = set()
    
    def track_exists(self, track_id: str) -> bool:
        return track_id in self._existing_track_ids
    
    def batch_insert_tracks(self, tracks: list[dict]) -> None:
        for track in tracks:
            track_id = _extract_track_id(track)
            if track_id:
                self._existing_track_ids.add(track_id)


def _extract_track_id(track: dict) -> Optional[str]:
    """
    Extract track ID from track dictionary.
    Prioritizes 'id' over 'track_id' for consistency.
    """
    if not isinstance(track, dict):
        return None
    
    # Prioritize 'id' over 'track_id'
    return track.get('id') or track.get('track_id')


def update_library_from_playlist(tracks: list[dict], database: DatabaseInterface = None) -> dict:
    """
    Processes tracks from a playlist, adding new ones to the library
    and skipping duplicates.
    
    Args:
        tracks: List of track dictionaries to process
        database: Database interface for operations (uses mock if None)
    
    Returns:
        Dictionary with counts of new and skipped tracks
    
    Raises:
        TypeError: If tracks is not a list
        ValueError: If tracks list is empty
    """
    if not isinstance(tracks, list):
        raise TypeError("tracks must be a list")
    
    if not tracks:
        logger.warning("Empty tracks list provided")
        return {"new": 0, "skipped": 0}
    
    # Use mock database if none provided
    if database is None:
        database = MockDatabase()
    
    new_or_updated_count = 0
    already_indexed_count = 0
    skipped_invalid_count = 0
    to_insert = []

    try:
        for i, track in enumerate(tracks):
            track_id = _extract_track_id(track)
            
            if not track_id:
                logger.warning("Track at index %d has no valid ID (missing 'id' or 'track_id'). Skipping.", i)
                skipped_invalid_count += 1
                continue

            if database.track_exists(track_id):
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("Track (%s) already exists in database. Skipping.", track_id)
                already_indexed_count += 1
            else:
                to_insert.append(track)
                new_or_updated_count += 1
        
        # Batch insert new tracks
        if to_insert:
            database.batch_insert_tracks(to_insert)
            logger.info("Successfully inserted %d new tracks", len(to_insert))
        
        if skipped_invalid_count > 0:
            logger.warning("Skipped %d tracks due to missing or invalid IDs", skipped_invalid_count)
        
        logger.info("Library update complete: %d new/updated, %d already indexed, %d invalid", 
                   new_or_updated_count, already_indexed_count, skipped_invalid_count)

        return {
            "new": new_or_updated_count, 
            "skipped": already_indexed_count,
            "invalid": skipped_invalid_count
        }
    
    except Exception as e:
        logger.error("Error during library update: %s", str(e))
        raise
