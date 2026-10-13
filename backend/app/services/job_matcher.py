from typing import Dict, List

from app.services.resume_parser import extract_skills


def match_resume_to_job(resume_text: str, job_description: str) -> Dict[str, object]:
    resume_skills = set(extract_skills(resume_text))
    job_skills = set(extract_skills(job_description))
    matching_skills: List[str] = sorted(resume_skills & job_skills, key=str.casefold)
    missing_skills: List[str] = sorted(job_skills - resume_skills, key=str.casefold)

    if job_skills:
        score = round(len(matching_skills) / len(job_skills) * 100)
        explanation = (
            "Score is the share of recognized skills in the job description "
            "that also appear in the resume."
        )
    else:
        score = 0
        explanation = (
            "No skills from the starter skills list were recognized in the job description, "
            "so a score could not be calculated."
        )

    return {
        "match_score": score,
        "matching_skills": matching_skills,
        "missing_skills": missing_skills,
        "resume_skills": sorted(resume_skills, key=str.casefold),
        "job_skills": sorted(job_skills, key=str.casefold),
        "explanation": explanation,
        "method": "starter_keyword_overlap",
    }
