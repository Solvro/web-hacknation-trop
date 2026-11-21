"""FastAPI app: `trop.api.app:app`. Mode via TROP_MODE (mock | offline | live) or `trop serve --mock`."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from trop.api import deps
from trop.api.routes import router
from trop.api.streams import ensure_replay_files
from trop.config import settings

DESCRIPTION = "TROP API — scam-ad campaign attribution. In mock mode every endpoint serves a fictional universe (not real data)."


def create_app(mode: str | None = None) -> FastAPI:
    mode = (mode or deps.current_mode()).lower()
    deps.set_store(deps.make_store(mode))
    base = settings.api_base_path.rstrip("/") or "/api/v1"

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            if mode == "mock":      # the canned recordings are fictional: never copied in real mode
                ensure_replay_files()
        except OSError:
            pass
        yield

    app = FastAPI(title="TROP API", version="0.1.0", description=DESCRIPTION, openapi_url=f"{base}/openapi.json", docs_url=f"{base}/docs",
                  redoc_url=None, lifespan=lifespan)
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()] or ["*"]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Next-Cursor", "X-TROP-Mode"])

    @app.middleware("http")
    async def mode_header(request: Request, call_next):
        resp = await call_next(request)
        resp.headers["X-TROP-Mode"] = mode
        return resp

    @app.exception_handler(HTTPException)
    async def http_exc(_: Request, exc: HTTPException):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))

    app.include_router(router, prefix=base)
    return app


app = create_app()
