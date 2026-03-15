"""Hundtracker Backend - FastAPI application."""
import asyncio
import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth, chat, hunt_teams, hunts, notifications, websocket
from app.services.mqtt_service import run_mqtt_listener
from app.tasks import run_cleanup_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: run migrations, start MQTT listener. Shutdown: cancel MQTT."""
    logger.info("Starting Hundtracker backend")
    # Run migrations (run before app: alembic upgrade head)
    import subprocess
    try:
        subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=".",
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.warning("Migration skipped or failed: %s (run: alembic upgrade head)", e)

    mqtt_task = asyncio.create_task(run_mqtt_listener())
    cleanup_task = asyncio.create_task(run_cleanup_loop())
    logger.info("MQTT listener and cleanup started")
    yield
    mqtt_task.cancel()
    cleanup_task.cancel()
    for t in (mqtt_task, cleanup_task):
        try:
            await t
        except asyncio.CancelledError:
            pass
    logger.info("Shutdown complete")


app = FastAPI(
    title="Hundtracker Backend",
    description="Backend for hunter tracker app - hunt teams, dogs, positions, chat",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(hunt_teams.router)
app.include_router(hunts.router)
app.include_router(chat.router)
app.include_router(notifications.router)
app.include_router(websocket.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
