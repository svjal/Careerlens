"""Typed API response contracts exposed in FastAPI's generated OpenAPI docs."""

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    id: int
    email: str


class AuthSessionResponse(BaseModel):
    access_token: str = Field(description="Signed bearer token for authenticated API calls.")
    token_type: Literal["bearer"] = "bearer"
    user: UserResponse


class ResumeEntryResponse(BaseModel):
    heading: str = Field(description="Original resume text chosen as the entry heading.")
    details: List[str] = Field(
        default_factory=list,
        description="Original resume lines grouped beneath the entry heading.",
    )


class ResumeEntriesResponse(BaseModel):
    experience: List[ResumeEntryResponse] = Field(default_factory=list)
    education: List[ResumeEntryResponse] = Field(default_factory=list)
    projects: List[ResumeEntryResponse] = Field(default_factory=list)


class ResumeDetailResponse(BaseModel):
    id: int
    filename: str
    character_count: int
    text: str = Field(description="Extracted text retained so the heuristic groups can be checked.")
    sections: Dict[str, str]
    entries: ResumeEntriesResponse
    skills: List[str]
    resume_score: int = Field(ge=0, le=100)
    resume_score_type: Literal["completeness"] = "completeness"
    resume_score_notes: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None


class ResumeListItemResponse(BaseModel):
    id: int
    filename: str
    skills: List[str]
    resume_score: int = Field(ge=0, le=100)
    created_at: Optional[datetime] = None


class JobMatchResponse(BaseModel):
    id: int
    resume_id: int
    job_title: Optional[str] = None
    match_score: int = Field(ge=0, le=100)
    matching_skills: List[str]
    missing_skills: List[str]
    resume_skills: List[str]
    job_skills: List[str]
    explanation: str
    method: Literal["starter_keyword_overlap"]
    created_at: Optional[datetime] = None


class RoadmapItemResponse(BaseModel):
    timeframe: str
    focus: str
    action: str


class ProjectRecommendationResponse(BaseModel):
    skill: str
    idea: str


class CareerAnalysisResponse(BaseModel):
    id: int
    match_id: int
    analysis_method: Literal["local_rules_v1", "ollama_local"]
    match_score: int = Field(ge=0, le=100)
    resume_suggestions: List[str]
    recommended_skills: List[str]
    roadmap: List[RoadmapItemResponse]
    project_recommendations: List[ProjectRecommendationResponse]
    interview_questions: List[str]
    created_at: Optional[datetime] = None


class ApplicationResponse(BaseModel):
    id: int
    match_id: Optional[int] = None
    job_title: str
    company: Optional[str] = None
    job_url: Optional[str] = None
    status: Literal["saved", "applied", "interviewing", "offer", "rejected", "withdrawn"]
    notes: Optional[str] = None
    applied_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class DashboardResumeResponse(ResumeListItemResponse):
    resume_score_notes: List[str] = Field(default_factory=list)


class DashboardMatchResponse(BaseModel):
    id: int
    job_title: str
    resume_filename: str
    match_score: int = Field(ge=0, le=100)
    matching_skills: List[str]
    missing_skills: List[str]
    created_at: Optional[datetime] = None


class SkillCoverageItemResponse(BaseModel):
    skill: str
    match_count: int = Field(ge=1)


class SkillCoverageResponse(BaseModel):
    total_matches: int = Field(ge=0)
    matching_skills: List[SkillCoverageItemResponse]
    missing_skills: List[SkillCoverageItemResponse]


class DashboardSummaryResponse(BaseModel):
    resume_count: int
    match_count: int
    average_match_score: int = Field(ge=0, le=100)
    application_count: int
    application_counts: Dict[str, int]
    skill_coverage: SkillCoverageResponse
    latest_resume: Optional[DashboardResumeResponse] = None
    recent_matches: List[DashboardMatchResponse]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    message: str
