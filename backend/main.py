import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from auth import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, get_current_user
from config import settings
from logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

from database import engine
from routers import admin as admin_router
from routers import auth as auth_router
from routers import dashboard, export, invoices, material_classes, projects, reference_prices, suppliers
from routers import orgs as orgs_router
from routers import settings as settings_router
from s3 import ensure_bucket


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация при старте приложения (не при импорте модуля)."""
    try:
        ensure_bucket()
        logger.info("MinIO bucket готов")
    except Exception as e:
        logger.warning(f"MinIO недоступен при старте: {e}")
    yield


app = FastAPI(title="УПД Трекер цен", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,  # НЕ wildcard — нужен конкретный origin для credentials
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-CSRF-Token"],
)


# ---------------------------------------------------------------------------
#  CSRF middleware — double-submit cookie protection
# ---------------------------------------------------------------------------

# Пути, которые НЕ требуют CSRF-токена:
# - /api/auth/login — единственный POST до выдачи куки (куки ещё нет)
# - /docs, /openapi.json, /redoc — Swagger UI
_CSRF_EXEMPT = {"/api/auth/login", "/docs", "/openapi.json", "/redoc", "/docs/oauth2-redirect"}


@app.middleware("http")
async def csrf_middleware(request: Request, call_next):
    """Проверяет CSRF double-submit cookie для state-changing запросов.

    /api/auth/refresh и /api/auth/logout НЕ исключены — к моменту их вызова
    CSRF-кука уже установлена. На них дополнительно навешан Depends(require_csrf)
    как defense-in-depth (middleware + dependency).
    """
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return await call_next(request)
    if request.url.path in _CSRF_EXEMPT:
        return await call_next(request)
    cookie = request.cookies.get(CSRF_COOKIE_NAME)
    header = request.headers.get(CSRF_HEADER_NAME)
    if not cookie or not header or cookie != header:
        return JSONResponse({"detail": "CSRF token mismatch"}, status_code=403)
    return await call_next(request)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    try:
        response = await call_next(request)
        elapsed = (time.time() - start) * 1000
        if response.status_code >= 400:
            logger.warning(f"{request.method} {request.url.path} → {response.status_code} ({elapsed:.0f}ms)")
        else:
            logger.info(f"{request.method} {request.url.path} → {response.status_code} ({elapsed:.0f}ms)")
        return response
    except Exception:
        elapsed = (time.time() - start) * 1000
        logger.exception(f"{request.method} {request.url.path} → 500 ({elapsed:.0f}ms)")
        raise

from fastapi import Depends

# Auth router — без обязательной авторизации (login, me, refresh, logout)
app.include_router(auth_router.router)

# Список зависимостей для бизнес-роутеров
_auth_dep = [Depends(get_current_user)]

# Admin и org-management — авторизация + проверка роли на каждом endpoint внутри роутера
app.include_router(admin_router.router)
app.include_router(orgs_router.router)

# Бизнес-роутеры — требуют валидного access-токена
app.include_router(projects.router, prefix="/api/projects", tags=["projects"], dependencies=_auth_dep)
app.include_router(material_classes.router, prefix="/api/material-classes", tags=["material-classes"], dependencies=_auth_dep)
app.include_router(reference_prices.router, prefix="/api/reference-prices", tags=["reference-prices"], dependencies=_auth_dep)
app.include_router(invoices.router, prefix="/api/invoices", tags=["invoices"], dependencies=_auth_dep)
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"], dependencies=_auth_dep)
app.include_router(export.router, prefix="/api/export", tags=["export"], dependencies=_auth_dep)
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"], dependencies=_auth_dep)
app.include_router(suppliers.router, prefix="/api/suppliers", tags=["suppliers"], dependencies=_auth_dep)


@app.get("/api/health")
def health():
    return {"status": "ok"}
