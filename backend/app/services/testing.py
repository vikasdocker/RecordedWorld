"""User testing and feedback system."""
import json
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from dataclasses import dataclass, field, asdict


@dataclass
class FeedbackEntry:
    id: int
    user_id: int
    category: str  # bug, feature, performance, ux
    severity: str  # low, medium, high, critical
    title: str
    description: str
    screenshot_path: Optional[str] = None
    device_info: Optional[dict] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "open"  # open, in_progress, resolved, wont_fix


@dataclass
class TestSession:
    id: int
    user_id: int
    start_time: str
    end_time: Optional[str] = None
    captures_created: int = 0
    worlds_explored: int = 0
    errors_encountered: int = 0
    avg_fps: float = 0
    avg_latency_ms: float = 0


class TestingHarness:
    """Manages user testing sessions and feedback collection."""

    def __init__(self, data_dir: Path = Path("test_data")):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.feedback: List[FeedbackEntry] = []
        self.sessions: List[TestSession] = []
        self.next_feedback_id = 1
        self.next_session_id = 1
        self._load_data()

    def _load_data(self):
        """Load existing test data from disk."""
        feedback_file = self.data_dir / "feedback.json"
        sessions_file = self.data_dir / "sessions.json"

        if feedback_file.exists():
            with open(feedback_file) as f:
                data = json.load(f)
                self.feedback = [FeedbackEntry(**item) for item in data]
                self.next_feedback_id = len(self.feedback) + 1

        if sessions_file.exists():
            with open(sessions_file) as f:
                data = json.load(f)
                self.sessions = [TestSession(**item) for item in data]
                self.next_session_id = len(self.sessions) + 1

    def _save_data(self):
        """Persist test data to disk."""
        with open(self.data_dir / "feedback.json", "w") as f:
            json.dump([asdict(entry) for entry in self.feedback], f, indent=2)

        with open(self.data_dir / "sessions.json", "w") as f:
            json.dump([asdict(s) for s in self.sessions], f, indent=2)

    def submit_feedback(
        self,
        user_id: int,
        category: str,
        severity: str,
        title: str,
        description: str,
        screenshot_path: Optional[str] = None,
        device_info: Optional[dict] = None,
    ) -> FeedbackEntry:
        """Submit a feedback entry."""
        entry = FeedbackEntry(
            id=self.next_feedback_id,
            user_id=user_id,
            category=category,
            severity=severity,
            title=title,
            description=description,
            screenshot_path=screenshot_path,
            device_info=device_info,
        )
        self.next_feedback_id += 1
        self.feedback.append(entry)
        self._save_data()
        return entry

    def start_session(self, user_id: int) -> TestSession:
        """Start a new testing session."""
        session = TestSession(
            id=self.next_session_id,
            user_id=user_id,
            start_time=datetime.utcnow().isoformat(),
        )
        self.next_session_id += 1
        self.sessions.append(session)
        self._save_data()
        return session

    def end_session(
        self,
        session_id: int,
        captures_created: int = 0,
        worlds_explored: int = 0,
        errors_encountered: int = 0,
        avg_fps: float = 0,
        avg_latency_ms: float = 0,
    ):
        """End a testing session with summary stats."""
        for session in self.sessions:
            if session.id == session_id:
                session.end_time = datetime.utcnow().isoformat()
                session.captures_created = captures_created
                session.worlds_explored = worlds_explored
                session.errors_encountered = errors_encountered
                session.avg_fps = avg_fps
                session.avg_latency_ms = avg_latency_ms
                break
        self._save_data()

    def get_feedback_by_category(self, category: str) -> List[FeedbackEntry]:
        """Get all feedback for a category."""
        return [f for f in self.feedback if f.category == category]

    def get_feedback_by_severity(self, severity: str) -> List[FeedbackEntry]:
        """Get all feedback for a severity level."""
        return [f for f in self.feedback if f.severity == severity]

    def get_summary(self) -> dict:
        """Get testing summary statistics."""
        return {
            "total_feedback": len(self.feedback),
            "feedback_by_category": {
                cat: len(self.get_feedback_by_category(cat))
                for cat in ["bug", "feature", "performance", "ux"]
            },
            "feedback_by_severity": {
                sev: len(self.get_feedback_by_severity(sev))
                for sev in ["low", "medium", "high", "critical"]
            },
            "total_sessions": len(self.sessions),
            "avg_session_duration": self._calc_avg_session_duration(),
        }

    def _calc_avg_session_duration(self) -> float:
        """Calculate average session duration in minutes."""
        durations = []
        for s in self.sessions:
            if s.end_time:
                start = datetime.fromisoformat(s.start_time)
                end = datetime.fromisoformat(s.end_time)
                durations.append((end - start).total_seconds() / 60)
        return sum(durations) / len(durations) if durations else 0


# Singleton
testing = TestingHarness()
