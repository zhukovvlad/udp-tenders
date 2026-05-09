from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pathlib import Path
import logging
import time
import os

load_dotenv(Path(__file__).parent / ".env")

from logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

from database import engine, Base
from s3 import ensure_bucket
from routers import invoices, dashboard, export, settings, projects, material_classes, reference_prices

Base.metadata.create_all(bind=engine)
try:
    ensure_bucket()
    logger.info("MinIO bucket готов")
except Exception as e:
    logger.warning(f"MinIO недоступен при старте: {e}")

app = FastAPI(title="УПД Трекер цен", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(material_classes.router, prefix="/api/material-classes", tags=["material-classes"])
app.include_router(reference_prices.router, prefix="/api/reference-prices", tags=["reference-prices"])
app.include_router(invoices.router, prefix="/api/invoices", tags=["invoices"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
