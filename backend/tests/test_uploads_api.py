"""
Tests for Upload Jobs API endpoints.
"""
import pytest
import uuid
import io
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal, engine, Base
from app.models.user import User


client = TestClient(app)


@pytest.fixture(scope="module")
def setup_db():
    """Create tables and test user."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        uid = uuid.uuid4().hex[:8]
        user = User(
            username=f"upload_api_test_{uid}",
            email=f"upload_api_{uid}@example.com",
            password_hash="salt:hash",
            display_name="Upload API Test User",
            location_sharing=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


class TestUploadJobsAPI:
    def test_create_upload_job(self, setup_db):
        response = client.post("/api/uploads/", params={
            "filename": "test_video.mp4",
            "file_size": 1024000,
            "mime_type": "video/mp4",
            "user_id": setup_db,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"].startswith("up-")
        assert data["file_size"] == 1024000
        assert data["upload_url"] is not None

    def test_list_upload_jobs(self, setup_db):
        # Create one first
        client.post("/api/uploads/", params={
            "filename": "list_test.mp4",
            "file_size": 500000,
            "user_id": setup_db,
        })
        response = client.get(f"/api/uploads/?user_id={setup_db}")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) > 0

    def test_get_upload_job(self, setup_db):
        create = client.post("/api/uploads/", params={
            "filename": "get_test.mp4",
            "file_size": 200000,
            "user_id": setup_db,
        })
        job_id = create.json()["job_id"]
        response = client.get(f"/api/uploads/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["filename"] == "get_test.mp4"

    def test_get_upload_job_not_found(self):
        response = client.get("/api/uploads/nonexistent")
        assert response.status_code == 404

    def test_upload_data_chunk(self, setup_db):
        create = client.post("/api/uploads/", params={
            "filename": "chunk_test.mp4",
            "file_size": 100,
            "user_id": setup_db,
        })
        job_id = create.json()["job_id"]

        # Upload a small chunk
        chunk = b"x" * 50
        response = client.put(
            f"/api/uploads/{job_id}/data?offset=0",
            files={"file": ("chunk.bin", io.BytesIO(chunk), "application/octet-stream")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["bytes_uploaded"] == 50
        assert data["progress"] == 50.0

    def test_upload_offset_mismatch(self, setup_db):
        create = client.post("/api/uploads/", params={
            "filename": "offset_test.mp4",
            "file_size": 200,
            "user_id": setup_db,
        })
        job_id = create.json()["job_id"]

        # Try uploading at wrong offset
        chunk = b"x" * 50
        response = client.put(
            f"/api/uploads/{job_id}/data?offset=100",
            files={"file": ("chunk.bin", io.BytesIO(chunk), "application/octet-stream")},
        )
        assert response.status_code == 409

    def test_complete_upload(self, setup_db):
        create = client.post("/api/uploads/", params={
            "filename": "complete_test.mp4",
            "file_size": 50,
            "user_id": setup_db,
        })
        job_id = create.json()["job_id"]

        # Upload full data
        chunk = b"x" * 50
        client.put(
            f"/api/uploads/{job_id}/data?offset=0",
            files={"file": ("chunk.bin", io.BytesIO(chunk), "application/octet-stream")},
        )

        # Complete
        response = client.post(f"/api/uploads/{job_id}/complete")
        assert response.status_code == 200
        assert response.json()["status"] == "complete"

    def test_cancel_upload(self, setup_db):
        create = client.post("/api/uploads/", params={
            "filename": "cancel_test.mp4",
            "file_size": 1000,
            "user_id": setup_db,
        })
        job_id = create.json()["job_id"]

        response = client.post(f"/api/uploads/{job_id}/cancel")
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"

    def test_resume_upload(self, setup_db):
        create = client.post("/api/uploads/", params={
            "filename": "resume_test.mp4",
            "file_size": 1000,
            "user_id": setup_db,
        })
        job_id = create.json()["job_id"]

        # Cancel first
        client.post(f"/api/uploads/{job_id}/cancel")

        # Resume
        response = client.post(f"/api/uploads/{job_id}/resume")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "resumed"
        assert data["retry_count"] == 1

    def test_resume_completed_fails(self, setup_db):
        create = client.post("/api/uploads/", params={
            "filename": "resume_completed.mp4",
            "file_size": 50,
            "user_id": setup_db,
        })
        job_id = create.json()["job_id"]

        # Upload and complete
        chunk = b"x" * 50
        client.put(
            f"/api/uploads/{job_id}/data?offset=0",
            files={"file": ("chunk.bin", io.BytesIO(chunk), "application/octet-stream")},
        )
        client.post(f"/api/uploads/{job_id}/complete")

        # Try to resume
        response = client.post(f"/api/uploads/{job_id}/resume")
        assert response.status_code == 400
