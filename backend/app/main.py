from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import time

from app.core.config import settings
from app.core.database import Base, engine
from app.routers import users, captures, game_worlds, pipeline, testing, monitoring, locations, friends, tags, privacy, moderation, events, uploads
from app.services.monitoring import metrics, logger

# Import all models so Base.metadata.create_all() creates their tables
from app.models import user, capture, game_world, location, friendship, category, tag, reconstruction_job, gameplay, upload_job, permission, role, reconstruction_metadata, visual_landmark  # noqa: F401


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = (time.time() - start) * 1000

        metrics.increment("http_requests_total", labels={
            "method": request.method,
            "path": request.url.path,
            "status": str(response.status_code),
        })
        metrics.histogram("http_request_duration_ms", duration, labels={
            "method": request.method,
            "path": request.url.path,
        })

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    logger.info("Recorded World API started")
    yield
    logger.info("Recorded World API shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(MetricsMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(captures.router)
app.include_router(game_worlds.router)
app.include_router(pipeline.router)
app.include_router(testing.router)
app.include_router(monitoring.router)
app.include_router(locations.router)
app.include_router(friends.router)
app.include_router(tags.router)
app.include_router(privacy.router)
app.include_router(moderation.router)
app.include_router(events.router)
app.include_router(events.meetup_router)
app.include_router(uploads.router)


@app.get("/")
def root():
    return {"message": "Recorded World API", "version": settings.APP_VERSION}


@app.get("/health")
def health():
    return {"status": "healthy"}
