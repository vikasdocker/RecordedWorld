from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Float, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class PlayerProgress(Base):
    """Player's overall progress and statistics."""
    __tablename__ = "player_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)

    # Exploration stats
    locations_discovered = Column(Integer, default=0)
    total_distance_traveled = Column(Float, default=0.0)  # meters
    time_played_seconds = Column(Integer, default=0)

    # Collection stats
    locations_collected = Column(Integer, default=0)
    items_collected = Column(Integer, default=0)

    # Social stats
    friends_count = Column(Integer, default=0)
    locations_created = Column(Integer, default=0)

    # Progression
    experience_points = Column(Integer, default=0)
    level = Column(Integer, default=1)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", backref="progress")


class Quest(Base):
    """A quest that players can complete."""
    __tablename__ = "quests"

    id = Column(Integer, primary_key=True, index=True)
    quest_id = Column(String, unique=True, nullable=False, index=True)

    # Quest info
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    quest_type = Column(String, nullable=False)  # explore, collect, social, create

    # Requirements
    required_action = Column(String, nullable=False)  # discover_locations, collect_item, etc.
    required_count = Column(Integer, default=1)

    # Rewards
    reward_xp = Column(Integer, default=100)
    reward_title = Column(String, nullable=True)

    # State
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PlayerQuest(Base):
    """Player's progress on a quest."""
    __tablename__ = "player_quests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    quest_id = Column(Integer, ForeignKey("quests.id"), nullable=False, index=True)

    # Progress
    current_count = Column(Integer, default=0)
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", backref="player_quests")
    quest = relationship("Quest", backref="player_quests")


class Achievement(Base):
    """An achievement players can earn."""
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, index=True)
    achievement_id = Column(String, unique=True, nullable=False, index=True)

    # Achievement info
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    icon_url = Column(String, nullable=True)

    # Category
    category = Column(String, nullable=False)  # exploration, collection, social, creation

    # Requirement
    required_value = Column(Integer, nullable=False)

    # Rewards
    reward_xp = Column(Integer, default=50)
    reward_title = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PlayerAchievement(Base):
    """Player's earned achievement."""
    __tablename__ = "player_achievements"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    achievement_id = Column(Integer, ForeignKey("achievements.id"), nullable=False, index=True)

    earned_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="achievements")
    achievement = relationship("Achievement", backref="earned_by")


class DiscoveredLocation(Base):
    """Tracks which locations a player has discovered."""
    __tablename__ = "discovered_locations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False, index=True)

    discovered_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="discovered_locations")
    location = relationship("Location", backref="discovered_by")


class CollectedLocation(Base):
    """Tracks which locations a player has collected (favorited)."""
    __tablename__ = "collected_locations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False, index=True)

    collected_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="collected_locations")
    location = relationship("Location", backref="collected_by")


class GameEvent(Base):
    """An in-game event (real-world or virtual)."""
    __tablename__ = "game_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, unique=True, nullable=False, index=True)

    # Event info
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    event_type = Column(String, nullable=False)  # real_world, virtual, community, challenge

    # Location (optional for virtual events)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    radius_meters = Column(Float, nullable=True)  # event area radius

    # Timing
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)

    # Rewards
    reward_xp = Column(Integer, default=100)
    reward_title = Column(String, nullable=True)

    # State
    status = Column(String, default="scheduled")  # scheduled, active, completed, cancelled
    max_participants = Column(Integer, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    location = relationship("Location", backref="events")
    creator = relationship("User", backref="created_events")


class EventParticipant(Base):
    """Tracks event participation."""
    __tablename__ = "event_participants"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("game_events.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Participation
    status = Column(String, default="registered")  # registered, checked_in, completed, no_show
    score = Column(Integer, default=0)

    registered_at = Column(DateTime(timezone=True), server_default=func.now())
    checked_in_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    event = relationship("GameEvent", backref="participants")
    user = relationship("User", backref="event_participations")


class VirtualMeetup(Base):
    """A virtual meetup between players."""
    __tablename__ = "virtual_meetups"

    id = Column(Integer, primary_key=True, index=True)
    meetup_id = Column(String, unique=True, nullable=False, index=True)

    # Meetup info
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Host
    host_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Location anchor
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True, index=True)

    # Timing
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    max_duration_minutes = Column(Integer, default=60)

    # Capacity
    max_participants = Column(Integer, default=10)

    # State
    status = Column(String, default="scheduled")  # scheduled, active, ended, cancelled

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    host = relationship("User", backref="hosted_meetups")
    location = relationship("Location", backref="meetups")


class MeetupParticipant(Base):
    """Tracks meetup participation."""
    __tablename__ = "meetup_participants"

    id = Column(Integer, primary_key=True, index=True)
    meetup_id = Column(Integer, ForeignKey("virtual_meetups.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Participation
    status = Column(String, default="joined")  # joined, left, kicked
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    left_at = Column(DateTime(timezone=True), nullable=True)

    meetup = relationship("VirtualMeetup", backref="participants")
    user = relationship("User", backref="meetup_participations")
