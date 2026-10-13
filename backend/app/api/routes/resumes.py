from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models import Resume, User
from app.schemas import ResumeDetailResponse, ResumeListItemResponse
from app.services.resume_parser import ResumeParseError, extract_resume_entries, parse_resume


router = APIRouter(prefix="/api/v1/resumes", tags=["resumes"])
MAX_RESUME_BYTES = 5 * 1024 * 1024


def serialize_resume(resume: Resume):
    return {
        "id": resume.id,
        "filename": resume.filename,
        "character_count": len(resume.extracted_text),
        "text": resume.extracted_text,
        "sections": resume.sections,
        "entries": extract_resume_entries(resume.sections),
        "skills": resume.skills,
        "resume_score": resume.resume_score,
        "resume_score_type": "completeness",
        "resume_score_notes": resume.resume_score_notes,
        "created_at": resume.created_at.isoformat() if resume.created_at else None,
    }


@router.get(
    "",
    response_model=list[ResumeListItemResponse],
    summary="List saved resumes",
    description="Lists only the signed-in account's resumes, newest first.",
)
def list_saved_resumes(
    database: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    resumes = database.scalars(
        select(Resume)
        .where(Resume.user_id == user.id)
        .order_by(desc(Resume.created_at), desc(Resume.id))
    ).all()
    return [
        {
            "id": resume.id,
            "filename": resume.filename,
            "skills": resume.skills,
            "resume_score": resume.resume_score,
            "created_at": resume.created_at.isoformat() if resume.created_at else None,
        }
        for resume in resumes
    ]


@router.get(
    "/{resume_id}",
    response_model=ResumeDetailResponse,
    summary="Open a saved resume",
    description="Returns extracted text, detected sections, likely entry groupings, and skills for one owned resume.",
)
def get_saved_resume(
    resume_id: int,
    database: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    resume = database.scalar(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user.id)
    )
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found.")
    return serialize_resume(resume)


@router.delete(
    "/{resume_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete a saved resume",
    description="Permanently deletes the resume, its matches, and career plans. Application tracker entries remain.",
)
def delete_saved_resume(
    resume_id: int,
    database: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    resume = database.scalar(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user.id)
    )
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found.")
    database.delete(resume)
    database.commit()
    return None


@router.post(
    "/parse",
    response_model=ResumeDetailResponse,
    summary="Upload and parse a resume",
    description="Accepts a text-based PDF or DOCX up to 5 MB, saves it to the signed-in account, and returns extracted content.",
)
async def parse_uploaded_resume(
    file: UploadFile = File(...),
    database: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Read and save a resume, returning its extracted text and skill summary."""
    filename = file.filename or ""
    content = await file.read(MAX_RESUME_BYTES + 1)
    await file.close()

    if len(content) > MAX_RESUME_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Resume files must be 5 MB or smaller.",
        )

    try:
        result = parse_resume(filename, content)
    except ResumeParseError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    resume = Resume(
        user_id=user.id,
        filename=filename,
        content_type=file.content_type,
        file_content=content,
        extracted_text=str(result["text"]),
        sections=result["sections"],
        skills=result["skills"],
        resume_score=int(result["resume_score"]),
        resume_score_notes=result["resume_score_notes"],
    )
    database.add(resume)
    database.commit()
    database.refresh(resume)
    return {**result, "id": resume.id}
