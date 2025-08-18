import pytest
import sqlite3
import os

@pytest.fixture
def setup_database(tmp_path):
    """Fixture to set up a temporary database for testing."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE IF NOT EXISTS flacs (path TEXT PRIMARY KEY)")
    conn.close()
    yield str(db_path)
    os.remove(db_path)
