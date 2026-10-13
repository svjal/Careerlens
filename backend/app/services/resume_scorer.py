import re
from typing import Dict, List


def score_resume(text: str, sections: Dict[str, str], skills: List[str]) -> Dict[str, object]:
    """Score basic resume completeness, not a candidate's qualifications."""
    score = 0
    notes = []

    section_points = {
        "summary": (10, "Add a short professional summary tailored to the roles you want."),
        "experience": (20, "Add a clearly labeled experience section, including relevant internships or volunteer work."),
        "education": (15, "Add a clearly labeled education section."),
        "projects": (15, "Add one or two projects that show how you apply your skills."),
        "skills": (15, "Add a clearly labeled skills section."),
    }

    for section, (points, suggestion) in section_points.items():
        if sections.get(section):
            score += points
        else:
            notes.append(suggestion)

    if len(skills) >= 5:
        score += 10
    else:
        notes.append("List a few more role-relevant skills that you can support with examples.")

    has_measurable_outcome = re.search(
        r"\b\d+\s*(?:%|percent|users|customers|projects|hours|days|weeks)\b",
        text,
        flags=re.IGNORECASE,
    )
    if has_measurable_outcome:
        score += 15
    else:
        notes.append("Where accurate, add measurable outcomes to experience or project bullets.")

    return {
        "resume_score": score,
        "resume_score_type": "completeness",
        "resume_score_notes": notes,
    }
