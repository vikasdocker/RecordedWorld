from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class GameWorld(Base):
    __tablename__ = "game_worlds"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    capture_id = Column(Integer, ForeignKey("captures.id"), nullable=False)
    map_data = Column(Text, nullable=True)  # JSON map configuration
    spawn_x = Column(Float, default=0.0)
    spawn_y = Column(Float, default=0.0)
    spawn_z = Column(Float, default=0.0)
    max_players = Column(Integer, default=20)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    capture = relationship("Capture", backref="worlds")
