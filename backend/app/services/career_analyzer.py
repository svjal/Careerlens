import re
from typing import Dict, List

from app.core.config import CAREER_ANALYSIS_PROVIDER
from app.services.ollama_provider import analyze_with_ollama


PROJECT_IDEAS = {
    "Python": "Build a small Python service that cleans and summarizes a real dataset.",
    "FastAPI": "Add a documented FastAPI endpoint with validation, error handling, and a few unit tests.",
    "SQL": "Create a relational schema for an application tracker and write queries for useful summaries.",
    "PostgreSQL": "Extend a small app with PostgreSQL tables, migrations, and a searchable history view.",
    "React": "Build a responsive dashboard that turns an API response into clear metrics and charts.",
    "TypeScript": "Add typed API responses and form validation to a small React application.",
    "Docker": "Package a small app and its database with a local Docker Compose workflow.",
    "AWS": "Document how a small app could run in the cloud, then prototype the architecture locally before using paid services.",
    "Git": "Create a clean project history with focused commits, a useful README, and a reviewed pull request.",
    "Data Analysis": "Analyze a public dataset and explain the findings with a reproducible notebook and short report.",
    "Machine Learning": "Build a small baseline model, compare it with a simple heuristic, and document its limits.",
}

QUESTION_TEMPLATES = {
    "Python": "How would you structure a Python project so its logic can be tested and reused?",
    "FastAPI": "How would you validate a request and return useful errors from a FastAPI endpoint?",
    "SQL": "Describe a query you wrote that joined or summarized data. How did you check its result?",
    "PostgreSQL": "How would you model data that needs to be queried by both owner and creation date?",
    "React": "How would you keep a React form's fields and validation messages in sync?",
    "TypeScript": "What types would you define for a frontend request and its API response?",
    "Docker": "How would you make a development environment consistent across two machines?",
    "AWS": "What would you monitor after deploying a small web application?",
    "Git": "How do you use commits and branches to make a change easier to review?",
    "Data Analysis": "How would you check whether a dataset is complete and suitable for analysis?",
    "Machine Learning": "How would you choose a baseline and evaluate whether a model is useful?",
}


def analyze_career_with_rules(
    resume_text: str,
    sections: Dict[str, str],
    missing_skills: List[str],
    match_score: int,
) -> Dict[str, object]:
    suggestions = []
    if not sections.get("summary"):
        suggestions.append(
            "Add a short professional summary tailored to the role, using two or three skills you can support with examples."
        )
    if sections.get("experience") and not re.search(r"\d+\s*(%|percent|users|customers|hours|days|weeks|projects)", resume_text, re.I):
        suggestions.append(
            "Strengthen experience bullets with concrete outcomes, such as time saved, users supported, or work delivered."
        )
    if not sections.get("projects"):
        suggestions.append(
            "Add one or two relevant projects with a short description of the problem, your contribution, and the result."
        )
    if not sections.get("skills"):
        suggestions.append(
            "Add a clearly labeled skills section so relevant tools and methods are easy to find."
        )
    if not suggestions:
        suggestions.append(
            "Keep the strongest role-relevant evidence near the top and make each bullet specific about your contribution."
        )

    priority_skills = missing_skills[:5]
    if priority_skills:
        skill_text = ", ".join(priority_skills)
        roadmap = [
            {
                "timeframe": "Next 1–2 weeks",
                "focus": "Choose the two most important skill gaps for this role: " + skill_text + ".",
                "action": "Review the job description and write down one concrete example or learning goal for each gap.",
            },
            {
                "timeframe": "Weeks 3–5",
                "focus": "Build evidence for one priority skill.",
                "action": "Complete a small project and document what you built, the decisions you made, and the result.",
            },
            {
                "timeframe": "Weeks 6–8",
                "focus": "Turn the evidence into a stronger application.",
                "action": "Update relevant resume bullets and practice explaining your project and trade-offs aloud.",
            },
        ]
    else:
        roadmap = [
            {
                "timeframe": "This week",
                "focus": "Make your existing strengths easy to verify.",
                "action": "Tailor the top resume bullets to the role and prepare short examples that show your contribution.",
            },
            {
                "timeframe": "Next 2–3 weeks",
                "focus": "Add proof of impact.",
                "action": "Choose a project or work example and describe its scope, your decisions, and measurable result.",
            },
            {
                "timeframe": "Next month",
                "focus": "Practice the interview story.",
                "action": "Rehearse concise examples for technical, collaboration, and problem-solving questions.",
            },
        ]

    project_recommendations = [
        {"skill": skill, "idea": PROJECT_IDEAS.get(skill, "Build a small project that demonstrates " + skill + " and document your decisions and results.")}
        for skill in priority_skills[:3]
    ]
    interview_questions = [
        QUESTION_TEMPLATES.get(skill, "Describe a project where you used " + skill + ". What trade-offs did you make?")
        for skill in (priority_skills[:3] or ["Python", "SQL"])
    ]
    interview_questions.extend(
        [
            "Tell me about a project or task where you had to learn something unfamiliar. How did you approach it?",
            "Describe a time you received feedback and changed your approach.",
        ]
    )

    return {
        "analysis_method": "local_rules_v1",
        "match_score": match_score,
        "resume_suggestions": suggestions,
        "recommended_skills": priority_skills,
        "roadmap": roadmap,
        "project_recommendations": project_recommendations,
        "interview_questions": interview_questions,
    }


def analyze_career(
    resume_text: str,
    sections: Dict[str, str],
    missing_skills: List[str],
    match_score: int,
    job_description: str = "",
) -> Dict[str, object]:
    """Select the configured analysis engine without silently changing methods."""
    if CAREER_ANALYSIS_PROVIDER == "ollama":
        return analyze_with_ollama(
            resume_text=resume_text,
            sections=sections,
            missing_skills=missing_skills,
            match_score=match_score,
            job_description=job_description,
        )
    return analyze_career_with_rules(
        resume_text=resume_text,
        sections=sections,
        missing_skills=missing_skills,
        match_score=match_score,
    )
