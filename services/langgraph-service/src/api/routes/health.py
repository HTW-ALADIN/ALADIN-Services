from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readiness() -> dict[str, object]:
    from config import settings
    from core.checkpointer import get_manager

    try:
        manager = get_manager()
    except Exception as exc:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=503, content={"status": "not-ready", "detail": str(exc)})

    ok, detail = await manager.health()
    gateway_ok = True
    gateway_detail = "llm gateway check skipped (no API key configured)"
    if settings.llm_gateway_api_key:
        import httpx

        url = settings.llm_gateway_base_url.rstrip("/") + "/generate"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.post(url, json={"ping": True})
            gateway_ok = response.status_code < 500
            gateway_detail = f"gateway probe returned {response.status_code}"
        except Exception as exc:
            gateway_ok = False
            gateway_detail = f"gateway unreachable: {exc}"

    ready = ok and (gateway_ok or not settings.llm_gateway_api_key)
    if settings.llm_gateway_api_key and not gateway_ok:
        ready = False

    from fastapi.responses import JSONResponse

    payload = {
        "status": "ready" if ready else "not-ready",
        "checkpointer": {"mode": manager.mode, "ready": ok, "detail": detail},
        "gateway": {"reachable": gateway_ok, "detail": gateway_detail},
    }
    return JSONResponse(status_code=200 if ready else 503, content=payload)
