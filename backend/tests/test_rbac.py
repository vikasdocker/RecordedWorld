"""
Tests for RBAC (Role-Based Access Control).
"""
import pytest
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal, engine, Base
from app.models.user import User
from app.models.role import Role, user_roles, ROLE_LEVELS, get_role_level
from app.middleware.rbac import get_user_roles, get_user_max_role_level


client = TestClient(app)


@pytest.fixture(scope="module")
def setup_db():
    """Create tables, roles, and test users."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Create roles
        for name, level in ROLE_LEVELS.items():
            existing = db.query(Role).filter(Role.name == name).first()
            if not existing:
                role = Role(name=name, description=f"{name} role", level=level)
                db.add(role)
        db.commit()

        # Create test users
        uid = uuid.uuid4().hex[:8]
        viewer = User(
            username=f"viewer_{uid}",
            email=f"viewer_{uid}@example.com",
            password_hash="salt:hash",
            display_name="Viewer",
            location_sharing=True,
        )
        db.add(viewer)
        db.flush()

        creator = User(
            username=f"creator_{uid}",
            email=f"creator_{uid}@example.com",
            password_hash="salt:hash",
            display_name="Creator",
            location_sharing=True,
        )
        db.add(creator)
        db.flush()

        mod = User(
            username=f"mod_{uid}",
            email=f"mod_{uid}@example.com",
            password_hash="salt:hash",
            display_name="Moderator",
            location_sharing=True,
        )
        db.add(mod)
        db.flush()

        admin = User(
            username=f"admin_{uid}",
            email=f"admin_{uid}@example.com",
            password_hash="salt:hash",
            display_name="Admin",
            location_sharing=True,
        )
        db.add(admin)
        db.flush()

        # Assign roles
        viewer_role = db.query(Role).filter(Role.name == "viewer").first()
        creator_role = db.query(Role).filter(Role.name == "creator").first()
        mod_role = db.query(Role).filter(Role.name == "moderator").first()
        admin_role = db.query(Role).filter(Role.name == "admin").first()

        viewer.roles.append(viewer_role)
        creator.roles.append(creator_role)
        mod.roles.append(mod_role)
        admin.roles.append(admin_role)
        db.commit()

        db.refresh(viewer)
        db.refresh(creator)
        db.refresh(mod)
        db.refresh(admin)

        return {
            "viewer_id": viewer.id,
            "creator_id": creator.id,
            "mod_id": mod.id,
            "admin_id": admin.id,
        }
    finally:
        db.close()


class TestRoleModel:
    def test_role_levels(self):
        assert ROLE_LEVELS["viewer"] == 0
        assert ROLE_LEVELS["creator"] == 10
        assert ROLE_LEVELS["moderator"] == 50
        assert ROLE_LEVELS["admin"] == 100

    def test_get_role_level(self):
        assert get_role_level("admin") == 100
        assert get_role_level("unknown") == 0


class TestRBACLogic:
    def test_get_user_roles_viewer(self, setup_db):
        db = SessionLocal()
        try:
            roles = get_user_roles(db, setup_db["viewer_id"])
            assert "viewer" in roles
        finally:
            db.close()

    def test_get_user_roles_admin(self, setup_db):
        db = SessionLocal()
        try:
            roles = get_user_roles(db, setup_db["admin_id"])
            assert "admin" in roles
        finally:
            db.close()

    def test_max_role_level_viewer(self, setup_db):
        db = SessionLocal()
        try:
            level = get_user_max_role_level(db, setup_db["viewer_id"])
            assert level == 0
        finally:
            db.close()

    def test_max_role_level_admin(self, setup_db):
        db = SessionLocal()
        try:
            level = get_user_max_role_level(db, setup_db["admin_id"])
            assert level == 100
        finally:
            db.close()

    def test_max_role_level_unknown_user(self):
        db = SessionLocal()
        try:
            level = get_user_max_role_level(db, 999999)
            assert level == -1
        finally:
            db.close()


class TestRoleCreation:
    def test_create_role(self):
        db = SessionLocal()
        try:
            name = f"test_role_{uuid.uuid4().hex[:6]}"
            role = Role(name=name, description="Test role", level=25)
            db.add(role)
            db.commit()
            db.refresh(role)
            assert role.id is not None
            assert role.name == name
            assert role.level == 25
        finally:
            db.close()

    def test_user_role_assignment(self, setup_db):
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == setup_db["viewer_id"]).first()
            role_names = [r.name for r in user.roles]
            assert "viewer" in role_names
        finally:
            db.close()


class TestRoleModelFields:
    def test_role_model_fields(self):
        columns = {c.name for c in Role.__table__.columns}
        expected = {'id', 'name', 'description', 'level', 'created_at'}
        assert expected.issubset(columns)
