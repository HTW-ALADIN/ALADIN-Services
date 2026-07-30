from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.routers import linalg, maxima, optimize, sat

app = FastAPI(title="SageMath Wrapper Service")

app.include_router(sat.router)
app.include_router(linalg.router)
app.include_router(optimize.router)
app.include_router(maxima.router)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "internal error"})


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}