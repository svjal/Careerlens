from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.applications import router as applications_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.resumes import router as resumes_router
from app.core.config import CORS_ALLOWED_ORIGINS
from app.schemas import HealthResponse


app = FastAPI(
    title="CareerLens API",
    version="0.1.0",
    description=(
        "Local-first resume and job analysis API. Protected routes require the bearer "
        "token returned by the register or login endpoints."
    ),
    openapi_tags=[
        {"name": "health", "description": "Check whether the local API process is running."},
        {"name": "authentication", "description": "Create a local account and obtain a bearer token."},
        {"name": "resumes", "description": "Upload, inspect, reuse, and delete your own resumes."},
        {"name": "job matching", "description": "Compare one of your saved resumes with a job description and create a career plan."},
        {"name": "dashboard", "description": "Read your saved-resume, match, and application summary."},
        {"name": "application tracker", "description": "Save application records and update their status or notes."},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resumes_router)
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(dashboard_router)
app.include_router(applications_router)


@app.get(
    "/api/health",
    tags=["health"],
    response_model=HealthResponse,
    summary="Check API health",
    description="Returns a small status response without requiring authentication.",
)
def health_check():
    return {"status": "ok", "message": "CareerLens API is running"}
