from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes import graphs, health, runs, threads
from config import settings
from core.checkpointer import CheckpointerManager, set_manager
from core.limits import RunLimiter, set_limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager = CheckpointerManager(
        mode=settings.checkpointer,
        postgres_url=settings.postgres_url,
    )
    await manager.initialize()
    set_manager(manager)
    set_limiter(
        RunLimiter(
            concurrency=settings.run_concurrency, timeout_seconds=settings.run_timeout_seconds
        )
    )
    global _manager_initialized
    _manager_initialized = True
    yield
    await manager.aclose()


app = FastAPI(
    title="langgraph-service",
    description=(
        "Generic LangGraph execution engine over caller-supplied graph definitions. "
        "LLM nodes route through llm-gateway-service. "
        "This service has no built-in authentication -- see the "
        "README's Security Disclaimer before exposing it beyond a trusted network."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(graphs.router)
app.include_router(threads.router)
app.include_router(runs.router)

_manager_initialized = False


def ensure_runtime() -> None:
    """Initialize checkpointer/limiter synchronously for tests and CLI use."""
    global _manager_initialized
    if _manager_initialized:
        return
    import asyncio

    manager = CheckpointerManager(
        mode=settings.checkpointer,
        postgres_url=settings.postgres_url,
    )
    asyncio.run(manager.initialize())
    set_manager(manager)
    set_limiter(
        RunLimiter(
            concurrency=settings.run_concurrency, timeout_seconds=settings.run_timeout_seconds
        )
    )
    _manager_initialized = True


ensure_runtime()
