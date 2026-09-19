"""
Gameplay Service

Handles exploration, collection, quests, achievements, and player progression.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.gameplay import (
    PlayerProgress, Quest, PlayerQuest, Achievement, PlayerAchievement,
    DiscoveredLocation, CollectedLocation,
)


class GameplayService:
    """Service for gameplay mechanics."""

    def __init__(self, db: Session):
        self.db = db

    # --- Player Progress ---

    def get_or_create_progress(self, user_id: int) -> PlayerProgress:
        """Get or create player progress."""
        progress = self.db.query(PlayerProgress).filter(
            PlayerProgress.user_id == user_id
        ).first()
        if not progress:
            progress = PlayerProgress(user_id=user_id)
            self.db.add(progress)
            self.db.commit()
            self.db.refresh(progress)
        return progress

    def add_experience(self, user_id: int, xp: int) -> PlayerProgress:
        """Add experience points and check for level up."""
        progress = self.get_or_create_progress(user_id)
        progress.experience_points += xp
        # Level up formula: level = sqrt(xp / 100) + 1
        import math
        new_level = int(math.sqrt(progress.experience_points / 100)) + 1
        progress.level = new_level
        self.db.commit()
        self.db.refresh(progress)
        return progress

    # --- Exploration ---

    def discover_location(self, user_id: int, location_id: int) -> bool:
        """Discover a new location. Returns True if newly discovered."""
        existing = self.db.query(DiscoveredLocation).filter(
            and_(
                DiscoveredLocation.user_id == user_id,
                DiscoveredLocation.location_id == location_id,
            )
        ).first()
        if existing:
            return False

        discovery = DiscoveredLocation(user_id=user_id, location_id=location_id)
        self.db.add(discovery)
        self.db.commit()

        # Update progress
        progress = self.get_or_create_progress(user_id)
        progress.locations_discovered += 1
        self.db.commit()
        return True

    def get_discovered_count(self, user_id: int) -> int:
        """Get number of discovered locations."""
        return self.db.query(DiscoveredLocation).filter(
            DiscoveredLocation.user_id == user_id
        ).count()

    def get_discovered_locations(self, user_id: int) -> List[int]:
        """Get list of discovered location IDs."""
        results = self.db.query(DiscoveredLocation.location_id).filter(
            DiscoveredLocation.user_id == user_id
        ).all()
        return [r[0] for r in results]

    # --- Collection ---

    def collect_location(self, user_id: int, location_id: int) -> bool:
        """Collect (favorite) a location. Returns True if newly collected."""
        existing = self.db.query(CollectedLocation).filter(
            and_(
                CollectedLocation.user_id == user_id,
                CollectedLocation.location_id == location_id,
            )
        ).first()
        if existing:
            return False

        collection = CollectedLocation(user_id=user_id, location_id=location_id)
        self.db.add(collection)
        self.db.commit()

        # Update progress
        progress = self.get_or_create_progress(user_id)
        progress.locations_collected += 1
        self.db.commit()
        return True

    def uncollect_location(self, user_id: int, location_id: int) -> bool:
        """Remove a location from collection."""
        collection = self.db.query(CollectedLocation).filter(
            and_(
                CollectedLocation.user_id == user_id,
                CollectedLocation.location_id == location_id,
            )
        ).first()
        if not collection:
            return False
        self.db.delete(collection)
        self.db.commit()
        return True

    def get_collected_count(self, user_id: int) -> int:
        """Get number of collected locations."""
        return self.db.query(CollectedLocation).filter(
            CollectedLocation.user_id == user_id
        ).count()

    # --- Quests ---

    def create_quest(
        self,
        quest_id: str,
        title: str,
        description: Optional[str],
        quest_type: str,
        required_action: str,
        required_count: int = 1,
        reward_xp: int = 100,
        reward_title: Optional[str] = None,
    ) -> Quest:
        """Create a new quest."""
        quest = Quest(
            quest_id=quest_id,
            title=title,
            description=description,
            quest_type=quest_type,
            required_action=required_action,
            required_count=required_count,
            reward_xp=reward_xp,
            reward_title=reward_title,
        )
        self.db.add(quest)
        self.db.commit()
        self.db.refresh(quest)
        return quest

    def accept_quest(self, user_id: int, quest_id: int) -> PlayerQuest:
        """Accept a quest."""
        existing = self.db.query(PlayerQuest).filter(
            and_(
                PlayerQuest.user_id == user_id,
                PlayerQuest.quest_id == quest_id,
            )
        ).first()
        if existing:
            return existing

        pq = PlayerQuest(user_id=user_id, quest_id=quest_id)
        self.db.add(pq)
        self.db.commit()
        self.db.refresh(pq)
        return pq

    def update_quest_progress(self, user_id: int, quest_id: int, count: int = 1) -> Optional[PlayerQuest]:
        """Update quest progress."""
        pq = self.db.query(PlayerQuest).filter(
            and_(
                PlayerQuest.user_id == user_id,
                PlayerQuest.quest_id == quest_id,
                PlayerQuest.is_completed == False,
            )
        ).first()
        if not pq:
            return None

        pq.current_count += count
        quest = self.db.query(Quest).filter(Quest.id == quest_id).first()
        if quest and pq.current_count >= quest.required_count:
            pq.is_completed = True
            pq.completed_at = datetime.now(timezone.utc)
            # Grant XP
            self.add_experience(user_id, quest.reward_xp)

        self.db.commit()
        self.db.refresh(pq)
        return pq

    def get_active_quests(self, user_id: int) -> List[PlayerQuest]:
        """Get user's active (incomplete) quests."""
        return self.db.query(PlayerQuest).filter(
            and_(
                PlayerQuest.user_id == user_id,
                PlayerQuest.is_completed == False,
            )
        ).all()

    def get_completed_quests(self, user_id: int) -> List[PlayerQuest]:
        """Get user's completed quests."""
        return self.db.query(PlayerQuest).filter(
            and_(
                PlayerQuest.user_id == user_id,
                PlayerQuest.is_completed == True,
            )
        ).all()

    # --- Achievements ---

    def create_achievement(
        self,
        achievement_id: str,
        title: str,
        description: Optional[str],
        category: str,
        required_value: int,
        reward_xp: int = 50,
        reward_title: Optional[str] = None,
    ) -> Achievement:
        """Create a new achievement."""
        achievement = Achievement(
            achievement_id=achievement_id,
            title=title,
            description=description,
            category=category,
            required_value=required_value,
            reward_xp=reward_xp,
            reward_title=reward_title,
        )
        self.db.add(achievement)
        self.db.commit()
        self.db.refresh(achievement)
        return achievement

    def check_and_award_achievements(self, user_id: int) -> List[Achievement]:
        """Check and award any earned achievements."""
        progress = self.get_or_create_progress(user_id)
        earned = []

        achievements = self.db.query(Achievement).all()
        for achievement in achievements:
            # Check if already earned
            existing = self.db.query(PlayerAchievement).filter(
                and_(
                    PlayerAchievement.user_id == user_id,
                    PlayerAchievement.achievement_id == achievement.id,
                )
            ).first()
            if existing:
                continue

            # Check requirement
            value = 0
            if achievement.category == "exploration":
                value = progress.locations_discovered
            elif achievement.category == "collection":
                value = progress.locations_collected
            elif achievement.category == "social":
                value = progress.friends_count
            elif achievement.category == "creation":
                value = progress.locations_created

            if value >= achievement.required_value:
                pa = PlayerAchievement(user_id=user_id, achievement_id=achievement.id)
                self.db.add(pa)
                self.add_experience(user_id, achievement.reward_xp)
                earned.append(achievement)

        self.db.commit()
        return earned

    def get_earned_achievements(self, user_id: int) -> List[PlayerAchievement]:
        """Get user's earned achievements."""
        return self.db.query(PlayerAchievement).filter(
            PlayerAchievement.user_id == user_id
        ).all()

    def get_all_achievements(self) -> List[Achievement]:
        """Get all available achievements."""
        return self.db.query(Achievement).all()
