import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import JobAnalysis, JobApplication, JobMatch, Resume, User


class CareerLensApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def enable_sqlite_foreign_keys(connection, _connection_record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(self.engine)
        self.testing_session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

        def override_database():
            database = self.testing_session()
            try:
                yield database
            finally:
                database.close()

        app.dependency_overrides[get_db] = override_database
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()
        self.rules_provider = patch("app.services.career_analyzer.CAREER_ANALYSIS_PROVIDER", "rules")
        self.rules_provider.start()

    def tearDown(self):
        self.rules_provider.stop()
        self.client_context.__exit__(None, None, None)
        app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    @staticmethod
    def auth_header(token):
        return {"Authorization": "Bearer " + token}

    def register(self, email):
        response = self.client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "sample-password-123"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_openapi_docs_describe_response_contracts(self):
        docs_page = self.client.get("/docs")
        self.assertEqual(docs_page.status_code, 200)
        openapi_response = self.client.get("/openapi.json")
        self.assertEqual(openapi_response.status_code, 200)
        schema = openapi_response.json()
        self.assertIn("HTTPBearer", schema["components"]["securitySchemes"])

        resume_detail = schema["paths"]["/api/v1/resumes/{resume_id}"]["get"]
        self.assertTrue(resume_detail["security"])
        resume_upload = schema["paths"]["/api/v1/resumes/parse"]["post"]
        self.assertEqual(resume_upload["summary"], "Upload and parse a resume")
        resume_response = resume_upload["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual(resume_response["$ref"], "#/components/schemas/ResumeDetailResponse")
        self.assertIn("entries", schema["components"]["schemas"]["ResumeDetailResponse"]["properties"])
        dashboard_response = schema["components"]["schemas"]["DashboardSummaryResponse"]
        self.assertIn("skill_coverage", dashboard_response["properties"])

        job_match = schema["paths"]["/api/v1/jobs/match"]["post"]
        match_response = job_match["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual(match_response["$ref"], "#/components/schemas/JobMatchResponse")

        resume_delete = schema["paths"]["/api/v1/resumes/{resume_id}"]["delete"]
        self.assertEqual(resume_delete["responses"]["204"]["description"], "Successful Response")
        self.assertNotIn("content", resume_delete["responses"]["204"])

        account_delete = schema["paths"]["/api/v1/auth/account"]["delete"]
        self.assertEqual(account_delete["responses"]["204"]["description"], "Successful Response")
        self.assertTrue(account_delete["security"])

    def test_cors_allows_the_native_local_frontend(self):
        response = self.client.options(
            "/api/v1/auth/register",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            "http://127.0.0.1:5173",
        )

    def test_full_resume_to_tracker_flow_and_account_isolation(self):
        first_account = self.register("first@example.com")
        first_headers = self.auth_header(first_account["access_token"])

        self.assertEqual(
            self.client.get("/api/v1/auth/me", headers=first_headers).json()["email"],
            "first@example.com",
        )
        self.assertEqual(self.client.get("/api/v1/dashboard/summary").status_code, 401)

        sample_resume = Path(__file__).parents[1] / "sample_data" / "sample_resume.docx"
        with sample_resume.open("rb") as resume_file:
            upload = self.client.post(
                "/api/v1/resumes/parse",
                headers=first_headers,
                files={
                    "file": (
                        sample_resume.name,
                        resume_file,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
        self.assertEqual(upload.status_code, 200, upload.text)
        resume = upload.json()
        self.assertTrue({"experience", "education", "projects", "skills"}.issubset(resume["sections"]))
        self.assertTrue(resume["entries"]["experience"])
        self.assertTrue(resume["entries"]["education"])
        self.assertTrue(resume["entries"]["projects"])
        saved_resumes = self.client.get("/api/v1/resumes", headers=first_headers)
        self.assertEqual(saved_resumes.status_code, 200, saved_resumes.text)
        self.assertEqual(saved_resumes.json()[0]["id"], resume["id"])
        reopened_resume = self.client.get(
            "/api/v1/resumes/{}".format(resume["id"]), headers=first_headers
        )
        self.assertEqual(reopened_resume.status_code, 200, reopened_resume.text)
        self.assertEqual(reopened_resume.json()["text"], resume["text"])
        self.assertEqual(reopened_resume.json()["entries"], resume["entries"])

        match_response = self.client.post(
            "/api/v1/jobs/match",
            headers=first_headers,
            json={
                "resume_id": resume["id"],
                "job_title": "Backend Developer",
                "job_description": "Python, React, SQL, and Docker experience preferred.",
            },
        )
        self.assertEqual(match_response.status_code, 200, match_response.text)
        match = match_response.json()
        self.assertGreaterEqual(match["match_score"], 0)
        self.assertTrue(match["matching_skills"])

        analysis_response = self.client.post(
            "/api/v1/jobs/matches/{}/analysis".format(match["id"]),
            headers=first_headers,
        )
        self.assertEqual(analysis_response.status_code, 200, analysis_response.text)
        self.assertEqual(analysis_response.json()["analysis_method"], "local_rules_v1")

        second_match_response = self.client.post(
            "/api/v1/jobs/match",
            headers=first_headers,
            json={
                "resume_id": resume["id"],
                "job_title": "Platform Engineer",
                "job_description": "Python, React, and Kubernetes experience preferred.",
            },
        )
        self.assertEqual(second_match_response.status_code, 200, second_match_response.text)

        application_response = self.client.post(
            "/api/v1/applications",
            headers=first_headers,
            json={
                "match_id": match["id"],
                "job_title": "Backend Developer",
                "company": "Example Company",
            },
        )
        self.assertEqual(application_response.status_code, 201, application_response.text)
        application = application_response.json()
        status_response = self.client.patch(
            "/api/v1/applications/{}".format(application["id"]),
            headers=first_headers,
            json={"status": "applied"},
        )
        self.assertEqual(status_response.status_code, 200, status_response.text)
        self.assertEqual(status_response.json()["status"], "applied")

        first_dashboard = self.client.get(
            "/api/v1/dashboard/summary", headers=first_headers
        ).json()
        self.assertEqual(first_dashboard["resume_count"], 1)
        self.assertEqual(first_dashboard["match_count"], 2)
        self.assertEqual(first_dashboard["application_count"], 1)
        coverage = first_dashboard["skill_coverage"]
        self.assertEqual(coverage["total_matches"], 2)
        strength_counts = {item["skill"]: item["match_count"] for item in coverage["matching_skills"]}
        gap_counts = {item["skill"]: item["match_count"] for item in coverage["missing_skills"]}
        self.assertEqual(strength_counts["Python"], 2)
        self.assertEqual(gap_counts["Kubernetes"], 1)

        second_account = self.register("second@example.com")
        second_headers = self.auth_header(second_account["access_token"])
        second_dashboard = self.client.get(
            "/api/v1/dashboard/summary", headers=second_headers
        ).json()
        self.assertEqual(self.client.get("/api/v1/resumes", headers=second_headers).json(), [])
        self.assertEqual(
            self.client.get(
                "/api/v1/resumes/{}".format(resume["id"]), headers=second_headers
            ).status_code,
            404,
        )
        self.assertEqual(second_dashboard["resume_count"], 0)
        self.assertEqual(second_dashboard["match_count"], 0)
        self.assertEqual(second_dashboard["application_count"], 0)
        self.assertEqual(second_dashboard["skill_coverage"]["total_matches"], 0)
        self.assertEqual(second_dashboard["skill_coverage"]["matching_skills"], [])

        foreign_match = self.client.post(
            "/api/v1/jobs/match",
            headers=second_headers,
            json={"resume_id": resume["id"], "job_description": "Python role"},
        )
        self.assertEqual(foreign_match.status_code, 404)
        foreign_application_update = self.client.patch(
            "/api/v1/applications/{}".format(application["id"]),
            headers=second_headers,
            json={"status": "offer"},
        )
        self.assertEqual(foreign_application_update.status_code, 404)

        foreign_resume_delete = self.client.delete(
            "/api/v1/resumes/{}".format(resume["id"]), headers=second_headers
        )
        self.assertEqual(foreign_resume_delete.status_code, 404)

        resume_delete = self.client.delete(
            "/api/v1/resumes/{}".format(resume["id"]), headers=first_headers
        )
        self.assertEqual(resume_delete.status_code, 204, resume_delete.text)
        self.assertEqual(
            self.client.get(
                "/api/v1/resumes/{}".format(resume["id"]), headers=first_headers
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                "/api/v1/jobs/matches/{}/analysis".format(match["id"]),
                headers=first_headers,
            ).status_code,
            404,
        )

        remaining_applications = self.client.get(
            "/api/v1/applications", headers=first_headers
        )
        self.assertEqual(remaining_applications.status_code, 200, remaining_applications.text)
        self.assertEqual(len(remaining_applications.json()), 1)
        self.assertIsNone(remaining_applications.json()[0]["match_id"])
        self.assertEqual(remaining_applications.json()[0]["status"], "applied")

        dashboard_after_delete = self.client.get(
            "/api/v1/dashboard/summary", headers=first_headers
        ).json()
        self.assertEqual(dashboard_after_delete["resume_count"], 0)
        self.assertEqual(dashboard_after_delete["match_count"], 0)
        self.assertEqual(dashboard_after_delete["application_count"], 1)

    def test_account_deletion_checks_password_and_removes_owned_career_data(self):
        account = self.register("delete-me@example.com")
        headers = self.auth_header(account["access_token"])

        sample_resume = Path(__file__).parents[1] / "sample_data" / "sample_resume.docx"
        with sample_resume.open("rb") as resume_file:
            upload = self.client.post(
                "/api/v1/resumes/parse",
                headers=headers,
                files={
                    "file": (
                        sample_resume.name,
                        resume_file,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
        self.assertEqual(upload.status_code, 200, upload.text)
        resume = upload.json()

        match_response = self.client.post(
            "/api/v1/jobs/match",
            headers=headers,
            json={"resume_id": resume["id"], "job_description": "Python and React engineer."},
        )
        self.assertEqual(match_response.status_code, 200, match_response.text)
        match = match_response.json()
        analysis_response = self.client.post(
            "/api/v1/jobs/matches/{}/analysis".format(match["id"]),
            headers=headers,
        )
        self.assertEqual(analysis_response.status_code, 200, analysis_response.text)
        application_response = self.client.post(
            "/api/v1/applications",
            headers=headers,
            json={"match_id": match["id"], "job_title": "Software Engineer"},
        )
        self.assertEqual(application_response.status_code, 201, application_response.text)

        bad_password = self.client.request(
            "DELETE",
            "/api/v1/auth/account",
            headers=headers,
            json={"password": "incorrect-password"},
        )
        self.assertEqual(bad_password.status_code, 403)
        self.assertEqual(
            self.client.get("/api/v1/dashboard/summary", headers=headers).json()["resume_count"],
            1,
        )

        deleted = self.client.request(
            "DELETE",
            "/api/v1/auth/account",
            headers=headers,
            json={"password": "sample-password-123"},
        )
        self.assertEqual(deleted.status_code, 204, deleted.text)
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=headers).status_code, 401)

        with self.testing_session() as database:
            for model in (User, Resume, JobMatch, JobAnalysis, JobApplication):
                self.assertEqual(database.scalar(select(func.count(model.id))), 0, model.__name__)
