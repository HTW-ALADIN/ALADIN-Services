from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes import graphs, health, runs, threads
from config import settings
from core.checkpointer import CheckpointerManager, reset_manager, set_manager
from core.limits import RunLimiter, reset_limiter, set_limiter
from core.store import registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager = CheckpointerManager(mode=settings.checkpointer, postgres_url=settings.postgres_url)
    try:
        await manager.initialize()
        if settings.checkpointer == "postgres":
            registry.configure(settings.postgres_url, postgres=True)
        set_manager(manager)
        set_limiter(
            RunLimiter(
                concurrency=settings.run_concurrency, timeout_seconds=settings.run_timeout_seconds
            )
        )
        yield
    finally:
        reset_manager()
        reset_limiter()
        registry.configure()
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
