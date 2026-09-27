import pytest


@pytest.fixture(autouse=True)
def _reset_state():
    from core import checkpointer, limits
    from core.store import registry

    registry.clear()
    checkpointer.reset_manager()
    limits.reset_limiter()
    import main

    main._manager_initialized = False
    main.ensure_runtime()
    yield
    registry.clear()
    checkpointer.reset_manager()
    limits.reset_limiter()
    main._manager_initialized = False
