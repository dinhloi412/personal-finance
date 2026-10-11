"""The FastAPI application.

One process, one port, one origin. In development the Vite dev server proxies
`/api` here (see `frontend/vite.config.ts`); in normal use `frontend/dist` is
built once and served by this same app, so there is no CORS surface at all and
opening the app is opening one URL.

Startup does exactly two things: bring the schema up to date, and make sure a
fresh database already has a rate so that nothing shows as "not converted" on
first run.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__, fx
from app.database import SessionLocal, init_db
from app.money import BASE_CURRENCIES
from app.routers import assets, cash, deposits, market, portfolio, settings

logger = logging.getLogger(__name__)

#: Where the built frontend lives, relative to backend/ (this file is
#: backend/app/main.py). Absent until the frontend has been built once.
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

#: Only the dev server needs an origin other than this one.
DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def _ensure_rates() -> None:
    """Give a fresh database a usable rate for every base it may be read in.

    Both bases are seeded, not only the one currently in force, because the
    user can switch bases from any page: a database seeded for VND alone would
    read a USD valuation of a dong portfolio as nothing at all, since none of
    it could be converted.

    Seeding is not a refresh: it writes only what is missing, so a real rate
    learned later is never overwritten by the placeholder on the next start.
    """
    session = SessionLocal()
    try:
        for base in BASE_CURRENCIES:
            fx.seed_rates(session, base)
    finally:
        session.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    _ensure_rates()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="SoTaiSan API",
        version=__version__,
        description=(
            "Track stocks, funds, crypto and cash in VND and USD. "
            "No goals, no advice, no cloud."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=DEV_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(settings.router)
    app.include_router(assets.router)
    app.include_router(cash.router)
    app.include_router(deposits.router)
    app.include_router(portfolio.router)
    app.include_router(market.router)

    @app.get("/api/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built SPA, if it has been built.

    The API works without it (`/docs` is always there), which is what makes the
    backend testable on its own.
    """
    if not FRONTEND_DIST.is_dir():
        logger.info("frontend not built yet; serving the API only")
        return

    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        """Any non-API path is a route of the single-page app.

        A missing file still answers with `index.html` on purpose: a deep link
        like `/holdings` must survive a refresh, and the router in the browser
        will show the not-found view if the route really does not exist.
        """
        if path.startswith("api/"):
            raise StarletteHTTPException(status_code=404, detail="Not found")
        candidate = FRONTEND_DIST / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")


app = create_app()
