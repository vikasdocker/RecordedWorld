"""
Tests for Upload Job and Permission models.
"""
import pytest
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal, engine, Base
from app.models.user import User
from app.models.upload_job import UploadJob
from app.models.permission import Permission, ResourceACL


client = TestClient(app)


@pytest.fixture(scope="module")
def test_user():
    """Create a test user."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        uid = uuid.uuid4().hex[:8]
        user = User(
            username=f"upload_test_{uid}",
            email=f"upload_test_{uid}@example.com",
            password_hash="salt:hash",
            display_name="Upload Test User",
            location_sharing=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


class TestUploadJob:
    def test_create_upload_job(self, test_user):
        db = SessionLocal()
        try:
            uid = uuid.uuid4().hex[:8]
            job = UploadJob(
                job_id=f"test-upload-{uid}",
                user_id=test_user.id,
                filename="video.mp4",
                file_size=1024000,
                mime_type="video/mp4",
                status="created",
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            assert job.id is not None
            assert job.job_id == f"test-upload-{uid}"
            assert job.status == "created"
            assert job.bytes_uploaded == 0
            assert job.progress == 0.0
        finally:
            db.close()

    def test_upload_job_progress(self, test_user):
        db = SessionLocal()
        try:
            uid = uuid.uuid4().hex[:8]
            job = UploadJob(
                job_id=f"test-upload-{uid}",
                user_id=test_user.id,
                filename="video2.mp4",
                file_size=2048000,
                status="uploading",
                bytes_uploaded=1024000,
                progress=50.0,
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            assert job.bytes_uploaded == 1024000
            assert job.progress == 50.0
        finally:
            db.close()

    def test_upload_job_tus_support(self, test_user):
        db = SessionLocal()
        try:
            uid = uuid.uuid4().hex[:8]
            job = UploadJob(
                job_id=f"test-upload-{uid}",
                user_id=test_user.id,
                filename="video3.mp4",
                file_size=3072000,
                status="uploading",
                tus_upload_id=f"tus-{uid}",
                upload_offset=1024000,
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            assert job.tus_upload_id == f"tus-{uid}"
            assert job.upload_offset == 1024000
        finally:
            db.close()


class TestPermission:
    def test_create_permission(self, test_user):
        db = SessionLocal()
        try:
            perm = Permission(
                resource_type="location",
                resource_id=uuid.uuid4().int % 100000,
                permission="read",
                user_id=test_user.id,
            )
            db.add(perm)
            db.commit()
            db.refresh(perm)

            assert perm.id is not None
            assert perm.resource_type == "location"
            assert perm.permission == "read"
        finally:
            db.close()

    def test_create_group_permission(self, test_user):
        db = SessionLocal()
        try:
            perm = Permission(
                resource_type="location",
                resource_id=uuid.uuid4().int % 100000,
                permission="read",
                group="friends",
            )
            db.add(perm)
            db.commit()
            db.refresh(perm)

            assert perm.group == "friends"
            assert perm.user_id is None
        finally:
            db.close()


class TestResourceACL:
    def test_create_acl(self, test_user):
        db = SessionLocal()
        try:
            acl = ResourceACL(
                resource_type="location",
                resource_id=uuid.uuid4().int % 100000,
                owner_id=test_user.id,
                visibility="public",
                allow_anonymous_read="true",
                allow_authenticated_read="true",
                allow_friends_read="true",
                allow_owner_write="true",
            )
            db.add(acl)
            db.commit()
            db.refresh(acl)

            assert acl.id is not None
            assert acl.visibility == "public"
            assert acl.allow_anonymous_read == "true"
        finally:
            db.close()

    def test_create_private_acl(self, test_user):
        db = SessionLocal()
        try:
            acl = ResourceACL(
                resource_type="capture",
                resource_id=uuid.uuid4().int % 100000,
                owner_id=test_user.id,
                visibility="private",
                allow_anonymous_read="false",
                allow_authenticated_read="false",
                allow_friends_read="false",
                allow_owner_write="true",
            )
            db.add(acl)
            db.commit()
            db.refresh(acl)

            assert acl.visibility == "private"
            assert acl.allow_anonymous_read == "false"
        finally:
            db.close()


class TestUploadJobAPI:
    def test_upload_job_model_fields(self):
        """Test that UploadJob model has all expected fields."""
        columns = {c.name for c in UploadJob.__table__.columns}
        expected = {
            'id', 'job_id', 'user_id', 'capture_id', 'filename', 'file_size',
            'mime_type', 'file_hash', 'status', 'bytes_uploaded', 'progress',
            'upload_offset', 'upload_url', 'tus_upload_id', 'validation_status',
            'validation_errors', 'error_message', 'retry_count', 'max_retries',
            'storage_path', 'storage_backend', 'created_at', 'started_at',
            'completed_at', 'expires_at', 'client_info'
        }
        assert expected.issubset(columns)


class TestPermissionModelFields:
    def test_permission_model_fields(self):
        """Test that Permission model has all expected fields."""
        columns = {c.name for c in Permission.__table__.columns}
        expected = {
            'id', 'resource_type', 'resource_id', 'permission', 'granted_by',
            'user_id', 'group', 'expires_at', 'created_at'
        }
        assert expected.issubset(columns)

    def test_resource_acl_model_fields(self):
        """Test that ResourceACL model has all expected fields."""
        columns = {c.name for c in ResourceACL.__table__.columns}
        expected = {
            'id', 'resource_type', 'resource_id', 'owner_id', 'visibility',
            'allow_anonymous_read', 'allow_authenticated_read',
            'allow_friends_read', 'allow_owner_write', 'created_at', 'updated_at'
        }
        assert expected.issubset(columns)
