from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine
from app.core.security import secret
from app.routers import assessments, auth, coding, intelligence, practice, questions, staff, students


@asynccontextmanager
async def lifespan(app):
    secret()
    yield


app = FastAPI(title="Placement Readiness API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings().cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, error: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {"loc": item["loc"], "msg": item["msg"], "type": item["type"]} for item in error.errors()
            ]
        },
        headers={"Cache-Control": "no-store"},
    )


@app.middleware("http")
async def no_store(request, next_request):
    response = await next_request(request)
    if request.url.path.startswith("/api/v1/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/v1/health", tags=["Health"])
def health():
    try:
        with engine().connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one_or_none()
            if revision:
                return {"status": "ok", "migration": revision}
    except SQLAlchemyError:
        pass
    return JSONResponse(status_code=503, content={"status": "database_unavailable"})


for router in (auth, students, assessments, practice, coding, intelligence, questions, staff):
    app.include_router(router.router, prefix="/api/v1")
