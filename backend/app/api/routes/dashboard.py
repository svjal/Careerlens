from collections import Counter

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models import JobApplication, JobMatch, Resume, User
from app.schemas import DashboardSummaryResponse


router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])
APPLICATION_STATUSES = ["saved", "applied", "interviewing", "offer", "rejected", "withdrawn"]


@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
    summary="Read dashboard summary",
    description=(
        "Returns account-scoped counts, application statuses, top skill overlaps and gaps "
        "across saved comparisons, the newest resume, and up to five recent matches."
    ),
)
def dashboard_summary(
    database: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    resume_count = database.scalar(
        select(func.count(Resume.id)).where(Resume.user_id == user.id)
    ) or 0
    match_count = database.scalar(
        select(func.count(JobMatch.id)).where(JobMatch.user_id == user.id)
    ) or 0
    average_score = database.scalar(
        select(func.avg(JobMatch.match_score)).where(JobMatch.user_id == user.id)
    ) or 0
    application_count = database.scalar(
        select(func.count(JobApplication.id)).where(JobApplication.user_id == user.id)
    ) or 0

    latest_resume = database.scalar(
        select(Resume)
        .where(Resume.user_id == user.id)
        .order_by(desc(Resume.created_at), desc(Resume.id))
        .limit(1)
    )
    status_rows = database.execute(
        select(JobApplication.status, func.count(JobApplication.id))
        .where(JobApplication.user_id == user.id)
        .group_by(JobApplication.status)
    ).all()
    application_counts = {status: 0 for status in APPLICATION_STATUSES}
    application_counts.update({status: count for status, count in status_rows})

    recent_rows = database.execute(
        select(JobMatch, Resume.filename)
        .join(Resume, Resume.id == JobMatch.resume_id)
        .where(JobMatch.user_id == user.id)
        .order_by(desc(JobMatch.created_at), desc(JobMatch.id))
        .limit(5)
    ).all()
    recent_matches = [
        {
            "id": match.id,
            "job_title": match.job_title or "Untitled role",
            "resume_filename": filename,
            "match_score": match.match_score,
            "matching_skills": match.matching_skills,
            "missing_skills": match.missing_skills,
            "created_at": match.created_at.isoformat() if match.created_at else None,
        }
        for match, filename in recent_rows
    ]

    skill_rows = database.execute(
        select(JobMatch.matching_skills, JobMatch.missing_skills).where(
            JobMatch.user_id == user.id
        )
    ).all()
    matching_skill_counts = Counter()
    missing_skill_counts = Counter()
    for matching_skills, missing_skills in skill_rows:
        # Count each skill once per comparison, even if old data contains duplicates.
        matching_skill_counts.update(set(matching_skills or []))
        missing_skill_counts.update(set(missing_skills or []))

    def top_skills(counts):
        return [
            {"skill": skill, "match_count": count}
            for skill, count in sorted(
                counts.items(), key=lambda item: (-item[1], item[0].casefold())
            )[:6]
        ]

    return {
        "resume_count": resume_count,
        "match_count": match_count,
        "average_match_score": round(float(average_score)),
        "application_count": application_count,
        "application_counts": application_counts,
        "skill_coverage": {
            "total_matches": match_count,
            "matching_skills": top_skills(matching_skill_counts),
            "missing_skills": top_skills(missing_skill_counts),
        },
        "latest_resume": (
            {
                "id": latest_resume.id,
                "filename": latest_resume.filename,
                "skills": latest_resume.skills,
                "resume_score": latest_resume.resume_score,
                "resume_score_notes": latest_resume.resume_score_notes,
                "created_at": latest_resume.created_at.isoformat() if latest_resume.created_at else None,
            }
            if latest_resume
            else None
        ),
        "recent_matches": recent_matches,
    }
