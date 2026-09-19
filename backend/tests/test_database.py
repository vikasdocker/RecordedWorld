"""Tests for Phase 22: Database — schema, indexes, health, CRUD."""

import pytest
from sqlalchemy import inspect, text

from app.core.database import Base, engine, SessionLocal, check_db_health, init_db
from app.core.config import settings
from app.models.user import User
from app.models.friendship import Friendship
from app.models.location import Location
from app.models.category import Category
from app.models.tag import Tag
from app.models.capture import Capture
from app.models.game_world import GameWorld


@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


class TestDatabaseHealth:
    def test_health_check(self):
        """Database health check returns healthy."""
        health = check_db_health()
        assert health["status"] == "healthy"

    def test_database_type(self):
        """Correct database type is detected."""
        health = check_db_health()
        assert health["database"] in ("sqlite", "postgresql")


class TestSchema:
    def test_users_table_exists(self):
        """Users table exists."""
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "users" in tables

    def test_friendships_table_exists(self):
        """Friendships table exists."""
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "friendships" in tables

    def test_locations_table_exists(self):
        """Locations table exists."""
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "locations" in tables

    def test_categories_table_exists(self):
        """Categories table exists."""
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "categories" in tables

    def test_tags_table_exists(self):
        """Tags table exists."""
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "tags" in tables


class TestIndexes:
    def test_user_username_index(self):
        """User username has index."""
        inspector = inspect(engine)
        indexes = inspector.get_indexes("users")
        index_columns = [idx["column_names"] for idx in indexes]
        assert any("username" in cols for cols in index_columns)

    def test_user_email_index(self):
        """User email has index."""
        inspector = inspect(engine)
        indexes = inspector.get_indexes("users")
        index_columns = [idx["column_names"] for idx in indexes]
        assert any("email" in cols for cols in index_columns)

    def test_location_grid_cell_index(self):
        """Location grid_cell_id has index."""
        inspector = inspect(engine)
        indexes = inspector.get_indexes("locations")
        index_columns = [idx["column_names"] for idx in indexes]
        assert any("grid_cell_id" in cols for cols in index_columns)


class TestUserCRUD:
    def test_create_user(self, db):
        """Can create a user."""
        user = User(
            username="db_test_user",
            email="db@test.com",
            password_hash="salt:hash",
            display_name="DB Test",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        assert user.id is not None

    def test_read_user(self, db):
        """Can read a user."""
        user = db.query(User).filter(User.username == "db_test_user").first()
        assert user is not None
        assert user.email == "db@test.com"

    def test_update_user(self, db):
        """Can update a user."""
        user = db.query(User).filter(User.username == "db_test_user").first()
        user.display_name = "Updated Name"
        db.commit()
        db.refresh(user)
        assert user.display_name == "Updated Name"

    def test_delete_user(self, db):
        """Can delete a user."""
        user = db.query(User).filter(User.username == "db_test_user").first()
        db.delete(user)
        db.commit()
        assert db.query(User).filter(User.username == "db_test_user").first() is None


class TestLocationCRUD:
    def test_create_location(self, db):
        """Can create a location."""
        loc = Location(
            creator_id=1,
            title="DB Test Location",
            latitude=40.785,
            longitude=-73.968,
            moderation_state="approved",
            visibility="public",
        )
        db.add(loc)
        db.commit()
        db.refresh(loc)
        assert loc.id is not None

    def test_read_location(self, db):
        """Can read a location."""
        loc = db.query(Location).filter(Location.title == "DB Test Location").first()
        assert loc is not None
        assert loc.latitude == 40.785

    def test_delete_location(self, db):
        """Can delete a location."""
        loc = db.query(Location).filter(Location.title == "DB Test Location").first()
        if loc:
            db.delete(loc)
            db.commit()


class TestFriendshipCRUD:
    def test_create_friendship(self, db):
        """Can create a friendship."""
        # Create users first for foreign key
        for uid in [9001, 9002]:
            existing = db.query(User).filter(User.id == uid).first()
            if not existing:
                db.add(User(
                    id=uid,
                    username=f"friend_user_{uid}",
                    email=f"friend_{uid}@test.com",
                    password_hash="salt:hash",
                ))
        db.commit()

        friendship = Friendship(
            requester_id=9001,
            addressee_id=9002,
            status="pending",
        )
        db.add(friendship)
        db.commit()
        db.refresh(friendship)
        assert friendship.id is not None

    def test_read_friendship(self, db):
        """Can read a friendship."""
        friendship = db.query(Friendship).filter(
            Friendship.requester_id == 9001,
            Friendship.addressee_id == 9002,
        ).first()
        assert friendship is not None
        assert friendship.status == "pending"

    def test_update_friendship(self, db):
        """Can update friendship status."""
        friendship = db.query(Friendship).filter(
            Friendship.requester_id == 9001,
            Friendship.addressee_id == 9002,
        ).first()
        friendship.status = "accepted"
        db.commit()
        db.refresh(friendship)
        assert friendship.status == "accepted"

    def test_delete_friendship(self, db):
        """Can delete a friendship."""
        friendship = db.query(Friendship).filter(
            Friendship.requester_id == 9001,
            Friendship.addressee_id == 9002,
        ).first()
        if friendship:
            db.delete(friendship)
            db.commit()


class TestPostgreSQLCompatibility:
    def test_config_supports_postgres(self):
        """Config supports PostgreSQL URL."""
        assert hasattr(settings, "is_postgres")
        assert hasattr(settings, "is_sqlite")

    def test_config_postgres_properties(self):
        """PostgreSQL detection works."""
        # Current URL is SQLite
        assert settings.is_sqlite
        assert not settings.is_postgres
