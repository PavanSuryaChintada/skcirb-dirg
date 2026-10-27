import os

import pytest

# Force an in-memory SQLite database before the app is imported, so the suite never
# reaches a real database or the network, whatever is set in the developer's shell.
os.environ["DATABASE_URL"] = "sqlite://"

from app.config import get_settings  # noqa: E402
from app.db import get_engine  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_config():
    get_settings.cache_clear()
    get_engine.cache_clear()
    yield
    get_settings.cache_clear()
    get_engine.cache_clear()
