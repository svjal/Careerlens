from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models import JobAnalysis, JobMatch, Resume, User
from app.schemas import CareerAnalysisResponse, JobMatchResponse
from app.services.career_analyzer import analyze_career
from app.services.job_matcher import match_resume_to_job
from app.services.ollama_provider import CareerAnalysisError


router = APIRouter(prefix="/api/v1/jobs", tags=["job matching"])


class MatchRequest(BaseModel):
    resume_id: int
    job_description: str = Field(min_length=1, max_length=50_000)
    job_title: Optional[str] = Field(default=None, max_length=255)


@router.post(
    "/match",
    response_model=JobMatchResponse,
    summary="Compare a resume with a job description",
    description="Calculates overlap among recognized starter-list skills and saves the result for the signed-in account.",
)
def create_match(
    request: MatchRequest,
    database: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    resume = database.scalar(
        select(Resume).where(Resume.id == request.resume_id, Resume.user_id == user.id)
    )
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found. Upload it again and retry.")
    if not request.job_description.strip():
        raise HTTPException(status_code=400, detail="A job description is required.")

    result = match_resume_to_job(resume.extracted_text, request.job_description)
    match = JobMatch(
        user_id=user.id,
        resume_id=resume.id,
        job_title=request.job_title,
        job_description=request.job_description.strip(),
        match_score=int(result["match_score"]),
        matching_skills=result["matching_skills"],
        missing_skills=result["missing_skills"],
        job_skills=result["job_skills"],
    )
    database.add(match)
    database.commit()
    database.refresh(match)

    return {
        **result,
        "id": match.id,
        "resume_id": match.resume_id,
        "job_title": match.job_title,
        "created_at": match.created_at or datetime.now().astimezone(),
    }


@router.post(
    "/matches/{match_id}/analysis",
    response_model=CareerAnalysisResponse,
    summary="Generate a career plan",
    description="Creates resume suggestions, skill priorities, roadmap steps, project ideas, and interview questions.",
)
def create_career_analysis(
    match_id: int,
    database: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    match = database.scalar(
        select(JobMatch).where(JobMatch.id == match_id, JobMatch.user_id == user.id)
    )
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found.")

    try:
        analysis_data = analyze_career(
            resume_text=match.resume.extracted_text,
            sections=match.resume.sections,
            missing_skills=match.missing_skills,
            match_score=match.match_score,
            job_description=match.job_description,
        )
    except CareerAnalysisError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    stored_analysis = {key: value for key, value in analysis_data.items() if key != "match_score"}
    analysis = JobAnalysis(match_id=match.id, **stored_analysis)
    database.add(analysis)
    database.commit()
    database.refresh(analysis)
    return {
        **analysis_data,
        "id": analysis.id,
        "match_id": analysis.match_id,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
    }


@router.get(
    "/matches/{match_id}/analysis",
    response_model=CareerAnalysisResponse,
    summary="Read the latest career plan",
    description="Returns the newest saved plan for a match owned by the signed-in account.",
)
def latest_career_analysis(
    match_id: int,
    database: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    match = database.scalar(
        select(JobMatch).where(JobMatch.id == match_id, JobMatch.user_id == user.id)
    )
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found.")
    analysis = database.scalar(
        select(JobAnalysis)
        .where(JobAnalysis.match_id == match_id)
        .order_by(desc(JobAnalysis.created_at), desc(JobAnalysis.id))
        .limit(1)
    )
    if analysis is None:
        raise HTTPException(status_code=404, detail="No career plan has been created for this match yet.")
    return {
        "id": analysis.id,
        "match_id": analysis.match_id,
        "analysis_method": analysis.analysis_method,
        "match_score": match.match_score,
        "resume_suggestions": analysis.resume_suggestions,
        "recommended_skills": analysis.recommended_skills,
        "roadmap": analysis.roadmap,
        "project_recommendations": analysis.project_recommendations,
        "interview_questions": analysis.interview_questions,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
    }
