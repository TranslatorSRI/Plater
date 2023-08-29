
import asyncio
import pytest

# this avoids some errors related to async fixture event_loops
# discussed here - https://github.com/pytest-dev/pytest-asyncio/issues/257
@pytest.fixture(scope="session")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()
