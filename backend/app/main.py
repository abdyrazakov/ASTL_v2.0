from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import Response

from app.core.storage import OUTPUT_DIR
from app.routers import intersections, jobs, profiles, simulations, videos


class SPAStaticFiles(StaticFiles):
    """StaticFiles с фолбэком на index.html для путей клиентского роутера
    (React Router), например /editor или /analysis при прямом переходе или
    обновлении страницы — иначе такие пути отдавали бы 404."""

    async def get_response(self, path: str, scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and not path.startswith("assets/"):
                return await super().get_response("index.html", scope)
            raise

app = FastAPI(title="ASTL — Smart Traffic Light Analytics", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(videos.router)
app.include_router(profiles.router)
app.include_router(jobs.router)
# этап 2: профили перекрёстка и прогоны симуляции
app.include_router(intersections.router)
app.include_router(simulations.router)

app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Раздача собранного frontend — ОБЯЗАТЕЛЬНО последней: Starlette проверяет маршруты
# в порядке регистрации, а Mount("/", ..., html=True) перехватывает любой путь как
# SPA-фолбэк. Если смонтировать его раньше /api/*, все API-запросы будут получать
# index.html вместо данных.
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", SPAStaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
