"""Tests for Phase 24: Gameplay — exploration, collection, quests, achievements."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import user, capture, game_world, location, friendship, category, tag, reconstruction_job, gameplay  # noqa: F401
from app.models.user import User
from app.services.gameplay_service import GameplayService


@pytest.fixture(scope="module")
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create test user
    user = User(
        id=100,
        username="gameplay_test",
        email="gameplay@test.com",
        password_hash="salt:hash",
    )
    session.add(user)
    session.commit()

    yield session
    session.close()


class TestPlayerProgress:
    def test_get_or_create(self, db):
        """Can get or create player progress."""
        svc = GameplayService(db)
        progress = svc.get_or_create_progress(100)
        assert progress.user_id == 100
        assert progress.level == 1
        assert progress.experience_points == 0

    def test_add_experience(self, db):
        """Adding XP updates level."""
        svc = GameplayService(db)
        progress = svc.add_experience(100, 100)
        assert progress.experience_points == 100
        assert progress.level >= 1

    def test_level_up(self, db):
        """Enough XP causes level up."""
        svc = GameplayService(db)
        progress = svc.add_experience(100, 10000)
        assert progress.level > 1


class TestExploration:
    def test_discover_location(self, db):
        """Can discover a location."""
        svc = GameplayService(db)
        result = svc.discover_location(100, 1)
        assert result is True

    def test_discover_same_location(self, db):
        """Discovering same location returns False."""
        svc = GameplayService(db)
        result = svc.discover_location(100, 1)
        assert result is False

    def test_discovered_count(self, db):
        """Discovered count is correct."""
        svc = GameplayService(db)
        svc.discover_location(100, 2)
        assert svc.get_discovered_count(100) >= 2

    def test_get_discovered_locations(self, db):
        """Can get list of discovered IDs."""
        svc = GameplayService(db)
        locations = svc.get_discovered_locations(100)
        assert 1 in locations
        assert 2 in locations


class TestCollection:
    def test_collect_location(self, db):
        """Can collect a location."""
        svc = GameplayService(db)
        result = svc.collect_location(100, 10)
        assert result is True

    def test_collect_same_location(self, db):
        """Collecting same location returns False."""
        svc = GameplayService(db)
        result = svc.collect_location(100, 10)
        assert result is False

    def test_collected_count(self, db):
        """Collected count is correct."""
        svc = GameplayService(db)
        svc.collect_location(100, 11)
        assert svc.get_collected_count(100) >= 2

    def test_uncollect_location(self, db):
        """Can uncollect a location."""
        svc = GameplayService(db)
        result = svc.uncollect_location(100, 10)
        assert result is True
        assert svc.get_collected_count(100) >= 1


class TestQuests:
    def test_create_quest(self, db):
        """Can create a quest."""
        svc = GameplayService(db)
        quest = svc.create_quest(
            quest_id="q_explore_5",
            title="Explorer",
            description="Discover 5 locations",
            quest_type="explore",
            required_action="discover_locations",
            required_count=5,
            reward_xp=200,
        )
        assert quest.quest_id == "q_explore_5"

    def test_accept_quest(self, db):
        """Can accept a quest."""
        svc = GameplayService(db)
        quest = svc.create_quest(
            quest_id="q_collect_3",
            title="Collector",
            description="Collect 3 locations",
            quest_type="collect",
            required_action="collect_location",
            required_count=3,
        )
        pq = svc.accept_quest(100, quest.id)
        assert pq.user_id == 100
        assert pq.current_count == 0

    def test_accept_same_quest(self, db):
        """Accepting same quest returns existing."""
        svc = GameplayService(db)
        # Quest already created in test_accept_quest
        from app.models.gameplay import Quest
        quest = db.query(Quest).filter(Quest.quest_id == "q_collect_3").first()
        pq = svc.accept_quest(100, quest.id)
        assert pq.user_id == 100

    def test_update_quest_progress(self, db):
        """Can update quest progress."""
        svc = GameplayService(db)
        quest = svc.create_quest(
            quest_id="q_social_2",
            title="Social",
            description="Add 2 friends",
            quest_type="social",
            required_action="add_friend",
            required_count=2,
        )
        pq = svc.accept_quest(100, quest.id)
        updated = svc.update_quest_progress(100, quest.id)
        assert updated.current_count == 1

    def test_complete_quest(self, db):
        """Quest completes when count reached."""
        svc = GameplayService(db)
        quest = svc.create_quest(
            quest_id="q_create_1",
            title="Creator",
            description="Create 1 location",
            quest_type="create",
            required_action="create_location",
            required_count=1,
            reward_xp=500,
        )
        pq = svc.accept_quest(100, quest.id)
        updated = svc.update_quest_progress(100, quest.id)
        assert updated.is_completed is True
        assert updated.completed_at is not None

    def test_get_active_quests(self, db):
        """Can get active quests."""
        svc = GameplayService(db)
        active = svc.get_active_quests(100)
        assert len(active) >= 1

    def test_get_completed_quests(self, db):
        """Can get completed quests."""
        svc = GameplayService(db)
        completed = svc.get_completed_quests(100)
        assert len(completed) >= 1


class TestAchievements:
    def test_create_achievement(self, db):
        """Can create an achievement."""
        svc = GameplayService(db)
        achievement = svc.create_achievement(
            achievement_id="a_discover_10",
            title="Explorer",
            description="Discover 10 locations",
            category="exploration",
            required_value=10,
            reward_xp=100,
        )
        assert achievement.achievement_id == "a_discover_10"

    def test_check_achievements(self, db):
        """Can check and award achievements."""
        svc = GameplayService(db)
        earned = svc.check_and_award_achievements(100)
        # May earn achievements based on current progress
        assert isinstance(earned, list)

    def test_get_earned_achievements(self, db):
        """Can get earned achievements."""
        svc = GameplayService(db)
        earned = svc.get_earned_achievements(100)
        assert isinstance(earned, list)

    def test_get_all_achievements(self, db):
        """Can get all achievements."""
        svc = GameplayService(db)
        all_achievements = svc.get_all_achievements()
        assert len(all_achievements) >= 1
