import asyncio

import pytest


@pytest.fixture(autouse=True)
def _ensure_event_loop():
    """Python 3.14 no longer auto-creates an event loop for
    asyncio.get_event_loop() on the main thread. Some tests call it
    directly (rather than using pytest-asyncio's async def tests), so
    make sure a loop exists before each test runs.
    """
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    yield
