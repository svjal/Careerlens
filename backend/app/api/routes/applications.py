from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models import JobApplication, JobMatch, User
from app.schemas import ApplicationResponse


router = APIRouter(prefix="/api/v1/applications", tags=["application tracker"])
ApplicationStatus = Literal["saved", "applied", "interviewing", "offer", "rejected", "withdrawn"]


class ApplicationCreate(BaseModel):
    job_title: str = Field(min_length=1, max_length=255)
    company: Optional[str] = Field(default=None, max_length=255)
    job_url: Optional[str] = Field(default=None, max_length=2000)
    match_id: Optional[int] = None
    notes: Optional[str] = Field(default=None, max_length=5000)


class ApplicationUpdate(BaseModel):
    status: Optional[ApplicationStatus] = None
    notes: Optional[str] = Field(default=None, max_length=5000)


def serialize_application(application: JobApplication):
    return {
        "id": application.id,
        "match_id": application.match_id,
        "job_title": application.job_title,
        "company": application.company,
        "job_url": application.job_url,
        "status": application.status,
        "notes": application.notes,
        "applied_at": application.applied_at.isoformat() if application.applied_at else None,
        "created_at": application.created_at.isoformat() if application.created_at else None,
    }


@router.get(
    "",
    response_model=list[ApplicationResponse],
    summary="List applications",
    description="Lists application tracker records belonging to the signed-in account, newest first.",
)
def list_applications(
    database: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    applications = database.scalars(
        select(JobApplication)
        .where(JobApplication.user_id == user.id)
        .order_by(desc(JobApplication.created_at), desc(JobApplication.id))
    ).all()
    return [serialize_application(application) for application in applications]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApplicationResponse,
    summary="Add an application",
    description="Saves a tracker entry, optionally linked to one of the signed-in account's job matches.",
)
def create_application(
    request: ApplicationCreate,
    database: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    match = None
    if request.match_id is not None:
        match = database.scalar(
            select(JobMatch).where(
                JobMatch.id == request.match_id,
                JobMatch.user_id == user.id,
            )
        )
        if match is None:
            raise HTTPException(status_code=404, detail="Match not found.")

    title = request.job_title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="A job title is required.")

    application = JobApplication(
        user_id=user.id,
        match_id=request.match_id,
        job_title=title,
        company=request.company.strip() if request.company else None,
        job_url=request.job_url.strip() if request.job_url else None,
        notes=request.notes.strip() if request.notes else None,
        status="saved",
    )
    database.add(application)
    database.commit()
    database.refresh(application)
    return serialize_application(application)


@router.patch(
    "/{application_id}",
    response_model=ApplicationResponse,
    summary="Update an application",
    description="Updates the status or notes on an owned tracker entry.",
)
def update_application(
    application_id: int,
    request: ApplicationUpdate,
    database: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    application = database.scalar(
        select(JobApplication).where(
            JobApplication.id == application_id,
            JobApplication.user_id == user.id,
        )
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found.")

    changes = request.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] is not None:
        application.status = changes["status"]
        if application.status == "applied" and application.applied_at is None:
            application.applied_at = datetime.now(timezone.utc)
    if "notes" in changes:
        application.notes = changes["notes"].strip() if changes["notes"] else None

    database.commit()
    database.refresh(application)
    return serialize_application(application)
