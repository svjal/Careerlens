import json
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes.auth import Credentials, login, register
from app.api.routes.applications import ApplicationCreate, ApplicationUpdate, create_application, list_applications, update_application
from app.api.routes.dashboard import dashboard_summary
from app.api.routes.jobs import MatchRequest, create_career_analysis, create_match, latest_career_analysis
from app.core.config import JWT_SECRET_KEY
from app.core.security import (
    create_access_token,
    hash_password,
    read_access_token,
    verify_password,
)
from app.db.base import Base
from app.models import JobApplication, JobMatch, Resume, User
from app.services.career_analyzer import analyze_career
from app.services.job_matcher import match_resume_to_job
from app.services.ollama_provider import CareerAnalysisError, NoRedirectHandler, analyze_with_ollama
from app.services.resume_parser import (
    ResumeParseError,
    detect_sections,
    extract_resume_entries,
    extract_skills,
    parse_resume,
)
from app.services.resume_scorer import score_resume


class ResumeParsingTests(unittest.TestCase):
    def test_text_pdf_parses_and_detects_a_section(self):
        content_stream = b"BT /F1 12 Tf 40 140 Td (Summary) Tj 0 -20 Td (Python developer) Tj ET"
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            b"<< /Length " + str(len(content_stream)).encode("ascii") + b" >>\nstream\n" + content_stream + b"\nendstream",
        ]
        pdf = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for object_id, body in enumerate(objects, start=1):
            offsets.append(len(pdf))
            pdf.extend(f"{object_id} 0 obj\n".encode("ascii"))
            pdf.extend(body + b"\nendobj\n")
        xref_offset = len(pdf)
        pdf.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
        for offset in offsets[1:]:
            pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        pdf.extend(
            f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
        )

        parsed = parse_resume("sample.pdf", bytes(pdf))

        self.assertIn("Python developer", parsed["text"])
        self.assertEqual(parsed["sections"]["summary"], "Python developer")

    def test_detect_sections_collects_lines_until_next_heading(self):
        text = """Summary
Early-career developer.
Experience
Built a Python API.
Education
Computer science degree.
"""

        sections = detect_sections(text)

        self.assertEqual(sections["summary"], "Early-career developer.")
        self.assertEqual(sections["experience"], "Built a Python API.")
        self.assertEqual(sections["education"], "Computer science degree.")

    def test_resume_entry_extraction_groups_experience_education_and_projects(self):
        entries = extract_resume_entries(
            {
                "experience": (
                    "Software Engineer | Acme | 2021-2023\n"
                    "Built an API.\n"
                    "Product Analyst | Beta | 2020-2021\n"
                    "Improved a reporting workflow."
                ),
                "education": (
                    "BSc Computer Science | Example University | 2018-2022\n"
                    "MSc Data Science | Example Institute | 2022-2024"
                ),
                "projects": (
                    "Career Dashboard — Created a FastAPI service.\n"
                    "Portfolio Tracker — Built a React application."
                ),
            }
        )

        self.assertEqual(len(entries["experience"]), 2)
        self.assertEqual(entries["experience"][0]["heading"], "Software Engineer | Acme | 2021-2023")
        self.assertEqual(entries["experience"][0]["details"], ["Built an API."])
        self.assertEqual(len(entries["education"]), 2)
        self.assertEqual(entries["education"][1]["heading"], "MSc Data Science | Example Institute | 2022-2024")
        self.assertEqual(len(entries["projects"]), 2)
        self.assertEqual(entries["projects"][0]["heading"], "Career Dashboard")
        self.assertEqual(entries["projects"][0]["details"], ["Created a FastAPI service."])

    def test_skill_extraction_is_case_insensitive_and_deduplicated(self):
        skills = extract_skills("Python, python, PostgreSQL, and React")

        self.assertEqual(skills, ["PostgreSQL", "Python", "React"])

    def test_skill_aliases_normalize_to_canonical_names_for_matching(self):
        resume_text = "Postgres, POSTGRESQL, K8s, and React.js"
        job_description = "PostgreSQL, Kubernetes, and React"

        self.assertEqual(
            extract_skills(resume_text),
            ["Kubernetes", "PostgreSQL", "React"],
        )

        result = match_resume_to_job(resume_text, job_description)

        self.assertEqual(result["match_score"], 100)
        self.assertEqual(result["matching_skills"], ["Kubernetes", "PostgreSQL", "React"])
        self.assertEqual(result["missing_skills"], [])

    def test_skill_extraction_does_not_match_java_inside_javascript(self):
        self.assertEqual(extract_skills("JavaScript developer"), ["JavaScript"])
        self.assertEqual(extract_skills("React.js developer"), ["React"])
        self.assertEqual(extract_skills("JS and TS developer"), ["JavaScript", "TypeScript"])

    def test_sample_docx_parses_into_text_sections_and_score(self):
        sample_path = Path(__file__).parents[1] / "sample_data" / "sample_resume.docx"

        parsed = parse_resume(sample_path.name, sample_path.read_bytes())

        self.assertGreater(parsed["character_count"], 0)
        self.assertIn("text", parsed)
        self.assertIsInstance(parsed["skills"], list)
        self.assertTrue({"experience", "education", "projects", "skills"}.issubset(parsed["sections"]))
        self.assertTrue(parsed["entries"]["experience"])
        self.assertTrue(parsed["entries"]["education"])
        self.assertTrue(parsed["entries"]["projects"])
        self.assertGreaterEqual(len(parsed["skills"]), 1)
        self.assertEqual(parsed["resume_score_type"], "completeness")

    def test_unsupported_file_type_has_actionable_message(self):
        with self.assertRaisesRegex(ResumeParseError, "PDF or DOCX"):
            parse_resume("resume.txt", b"plain text")


class MatchingAndAdviceTests(unittest.TestCase):
    def test_match_score_is_share_of_recognized_job_skills(self):
        result = match_resume_to_job(
            "Python React PostgreSQL",
            "We need Python, React, Docker, and SQL experience.",
        )

        self.assertEqual(result["match_score"], 50)
        self.assertEqual(result["matching_skills"], ["Python", "React"])
        self.assertEqual(result["missing_skills"], ["Docker", "SQL"])

    def test_resume_completeness_score_is_bounded_and_explained(self):
        result = score_resume(
            text="Worked with 12 users and shipped several projects.",
            sections={
                "summary": "Developer",
                "experience": "Engineer",
                "education": "Degree",
                "projects": "Project",
                "skills": "Skills",
            },
            skills=["Python", "React", "SQL", "Git", "Docker"],
        )

        self.assertEqual(result["resume_score"], 100)
        self.assertEqual(result["resume_score_type"], "completeness")
        self.assertEqual(result["resume_score_notes"], [])

    def test_career_plan_targets_missing_skills(self):
        plan = analyze_career(
            resume_text="Experience\nBuilt an API.",
            sections={"experience": "Built an API."},
            missing_skills=["Docker", "AWS"],
            match_score=50,
        )

        self.assertEqual(plan["analysis_method"], "local_rules_v1")
        self.assertEqual(plan["recommended_skills"], ["Docker", "AWS"])
        self.assertTrue(plan["roadmap"])
        self.assertTrue(plan["project_recommendations"])
        self.assertTrue(plan["interview_questions"])


class AuthenticationUtilityTests(unittest.TestCase):
    def test_password_is_salted_and_verifies(self):
        first_hash = hash_password("a-long-test-password")
        second_hash = hash_password("a-long-test-password")

        self.assertNotEqual(first_hash, second_hash)
        self.assertTrue(verify_password("a-long-test-password", first_hash))
        self.assertFalse(verify_password("wrong-password", first_hash))

    def test_signed_token_reads_user_id_and_rejects_tampering(self):
        token = create_access_token(42, "unit-test-secret", 10)

        self.assertEqual(read_access_token(token, "unit-test-secret"), 42)
        with self.assertRaises(ValueError):
            read_access_token(token, "different-secret")

    def test_expired_token_is_rejected(self):
        token = create_access_token(42, "unit-test-secret", 0)

        with self.assertRaises(ValueError):
            read_access_token(token, "unit-test-secret")


class AuthenticationRouteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.database = Session(self.engine)

    def tearDown(self):
        self.database.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_first_account_claims_existing_local_records_and_can_sign_in(self):
        resume = Resume(
            filename="old-local-resume.docx",
            file_content=b"sample",
            extracted_text="Python developer",
            sections={},
            skills=["Python"],
            resume_score=10,
            resume_score_notes=[],
        )
        self.database.add(resume)
        self.database.flush()
        match = JobMatch(
            resume_id=resume.id,
            job_description="Python role",
            match_score=100,
            matching_skills=["Python"],
            missing_skills=[],
            job_skills=["Python"],
        )
        application = JobApplication(job_title="Software Engineer")
        self.database.add_all([match, application])
        self.database.commit()

        created = register(
            Credentials(email="Learner@Example.com", password="a-long-test-password"),
            self.database,
        )
        user = self.database.scalar(select(User).where(User.email == "learner@example.com"))

        self.assertEqual(created["user"]["email"], "learner@example.com")
        self.assertTrue(verify_password("a-long-test-password", user.password_hash))
        self.assertEqual(self.database.get(Resume, resume.id).user_id, user.id)
        self.assertEqual(self.database.get(JobMatch, match.id).user_id, user.id)
        self.assertEqual(self.database.get(JobApplication, application.id).user_id, user.id)

        session = login(
            Credentials(email="learner@example.com", password="a-long-test-password"),
            self.database,
        )
        self.assertEqual(read_access_token(session["access_token"], JWT_SECRET_KEY), user.id)


class OllamaProviderTests(unittest.TestCase):
    def test_sends_local_non_streaming_json_schema_request_and_validates_output(self):
        plan_json = {
            "resume_suggestions": ["Add a result to the experience bullet using accurate numbers."],
            "recommended_skills": ["Docker"],
            "roadmap": [{
                "timeframe": "Next two weeks",
                "focus": "Practice Docker basics",
                "action": "Containerize a small service and record the steps.",
            }],
            "project_recommendations": [{
                "skill": "Docker",
                "idea": "Package one API and document how to run it locally.",
            }],
            "interview_questions": ["How did you decide what to put in the container?"],
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self, _size=-1):
                return json.dumps({"message": {"content": json.dumps(plan_json)}}).encode("utf-8")

        with patch("app.services.ollama_provider.OLLAMA_MODEL", "gemma3:1b"), patch(
            "app.services.ollama_provider.build_opener"
        ) as mocked_build_opener:
            mocked_build_opener.return_value.open.return_value = FakeResponse()
            result = analyze_with_ollama(
                resume_text="Python developer",
                sections={"experience": "Built an API"},
                missing_skills=["Docker"],
                match_score=50,
                job_description="Build and deploy API services.",
            )

        request = mocked_build_opener.return_value.open.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/chat")
        self.assertFalse(body["stream"])
        self.assertIn("properties", body["format"])
        self.assertEqual(result["analysis_method"], "ollama_local")
        self.assertEqual(result["match_score"], 50)
        self.assertEqual(result["recommended_skills"], ["Docker"])
        self.assertTrue(any(isinstance(handler, NoRedirectHandler) for handler in mocked_build_opener.call_args.args))

    def test_refuses_remote_ollama_host(self):
        with patch("app.services.ollama_provider.OLLAMA_MODEL", "gemma3:1b"), patch(
            "app.services.ollama_provider.OLLAMA_BASE_URL", "https://example.com"
        ), patch("app.services.ollama_provider.build_opener") as mocked_build_opener:
            with self.assertRaisesRegex(CareerAnalysisError, "loopback"):
                analyze_with_ollama("resume", {}, [], 0, "job")

        mocked_build_opener.assert_not_called()


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.database = Session(self.engine)
        self.owner = User(email="owner@example.com", password_hash="test-hash")
        self.other_user = User(email="other@example.com", password_hash="test-hash")
        self.database.add_all([self.owner, self.other_user])
        self.database.flush()
        self.resume = Resume(
            user_id=self.owner.id,
            filename="owner-resume.docx",
            file_content=b"sample",
            extracted_text="Python developer",
            sections={"experience": "Built a Python API."},
            skills=["Python"],
            resume_score=20,
            resume_score_notes=[],
        )
        self.database.add(self.resume)
        self.database.commit()

    def tearDown(self):
        self.database.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_resume_match_analysis_and_tracker_are_scoped_to_owner(self):
        match_result = create_match(
            MatchRequest(
                resume_id=self.resume.id,
                job_description="Python developer. Docker experience preferred.",
                job_title="Backend Developer",
            ),
            self.database,
            self.owner,
        )

        with self.assertRaises(HTTPException) as access_error:
            create_match(
                MatchRequest(resume_id=self.resume.id, job_description="Python developer"),
                self.database,
                self.other_user,
            )
        self.assertEqual(access_error.exception.status_code, 404)

        with self.assertRaises(HTTPException):
            create_career_analysis(match_result["id"], self.database, self.other_user)
        analysis = create_career_analysis(match_result["id"], self.database, self.owner)
        self.assertEqual(analysis["analysis_method"], "local_rules_v1")
        with self.assertRaises(HTTPException):
            latest_career_analysis(match_result["id"], self.database, self.other_user)

        with self.assertRaises(HTTPException):
            create_application(
                ApplicationCreate(job_title="Backend Developer", match_id=match_result["id"]),
                self.database,
                self.other_user,
            )
        application = create_application(
            ApplicationCreate(job_title="Backend Developer", match_id=match_result["id"]),
            self.database,
            self.owner,
        )
        self.assertEqual(len(list_applications(self.database, self.owner)), 1)
        self.assertEqual(list_applications(self.database, self.other_user), [])
        with self.assertRaises(HTTPException):
            update_application(
                application["id"],
                ApplicationUpdate(status="applied"),
                self.database,
                self.other_user,
            )

        owner_summary = dashboard_summary(self.database, self.owner)
        other_summary = dashboard_summary(self.database, self.other_user)
        self.assertEqual(owner_summary["resume_count"], 1)
        self.assertEqual(owner_summary["match_count"], 1)
        self.assertEqual(owner_summary["application_count"], 1)
        self.assertEqual(other_summary["resume_count"], 0)
        self.assertEqual(other_summary["match_count"], 0)
        self.assertEqual(other_summary["application_count"], 0)


if __name__ == "__main__":
    unittest.main()
