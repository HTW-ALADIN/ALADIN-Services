from fastapi import FastAPI

from api.routes import download, export, graph, health, search

app = FastAPI(
    title="academic-search-service",
    description=(
        "Unified search/export/download/citation-graph API over academic-mcp "
        "and scimesh. This service has no built-in authentication -- see the "
        "README's Security Disclaimer before exposing it beyond a trusted network."
    ),
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(search.router)
app.include_router(export.router)
app.include_router(download.router)
app.include_router(graph.router)
