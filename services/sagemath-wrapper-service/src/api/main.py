import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.dynamic_routes import register_routes
from src.registry.loader import load_registry

app = FastAPI(title="SageMath Wrapper Service")

# Load all registry YAMLs and register routes dynamically
_registry_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "registry")
_operations = load_registry(_registry_path)
register_routes(app, _operations)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "internal error"})


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}