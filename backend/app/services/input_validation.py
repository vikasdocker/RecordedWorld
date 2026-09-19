"""
Input Validation Utilities

Sanitize and validate user inputs.
"""

import re
import html
from typing import Optional, Tuple


# Constants
MAX_USERNAME_LENGTH = 30
MIN_USERNAME_LENGTH = 3
MAX_EMAIL_LENGTH = 254
MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 5000
MAX_SEARCH_LENGTH = 100

# Patterns
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """Sanitize a string input."""
    if not isinstance(value, str):
        return ""
    value = value.strip()
    value = html.escape(value)
    value = value[:max_length]
    return value


def validate_username(username: str) -> Tuple[bool, str]:
    """Validate username format."""
    if not username:
        return False, "Username is required"
    if len(username) < MIN_USERNAME_LENGTH:
        return False, f"Username must be at least {MIN_USERNAME_LENGTH} characters"
    if len(username) > MAX_USERNAME_LENGTH:
        return False, f"Username must be at most {MAX_USERNAME_LENGTH} characters"
    if not USERNAME_PATTERN.match(username):
        return False, "Username can only contain letters, numbers, underscores, and hyphens"
    return True, ""


def validate_email(email: str) -> Tuple[bool, str]:
    """Validate email format."""
    if not email:
        return False, "Email is required"
    if len(email) > MAX_EMAIL_LENGTH:
        return False, "Email is too long"
    if not EMAIL_PATTERN.match(email):
        return False, "Invalid email format"
    return True, ""


def validate_hex_color(color: str) -> Tuple[bool, str]:
    """Validate hex color format."""
    if not color:
        return False, "Color is required"
    if not HEX_COLOR_PATTERN.match(color):
        return False, "Color must be in #RRGGBB format"
    return True, ""


def validate_title(title: str) -> Tuple[bool, str]:
    """Validate a title field."""
    if not title:
        return False, "Title is required"
    title = title.strip()
    if len(title) > MAX_TITLE_LENGTH:
        return False, f"Title must be at most {MAX_TITLE_LENGTH} characters"
    return True, ""


def validate_description(desc: str) -> Tuple[bool, str]:
    """Validate a description field."""
    if desc and len(desc) > MAX_DESCRIPTION_LENGTH:
        return False, f"Description must be at most {MAX_DESCRIPTION_LENGTH} characters"
    return True, ""


def validate_latitude(lat: float) -> Tuple[bool, str]:
    """Validate latitude."""
    if lat < -90 or lat > 90:
        return False, "Latitude must be between -90 and 90"
    return True, ""


def validate_longitude(lon: float) -> Tuple[bool, str]:
    """Validate longitude."""
    if lon < -180 or lon > 180:
        return False, "Longitude must be between -180 and 180"
    return True, ""


def validate_search_query(query: str) -> Tuple[bool, str]:
    """Validate search query."""
    if not query:
        return False, "Search query is required"
    query = query.strip()
    if len(query) > MAX_SEARCH_LENGTH:
        return False, f"Search query must be at most {MAX_SEARCH_LENGTH} characters"
    return True, ""


def validate_moderation_state(state: str) -> Tuple[bool, str]:
    """Validate moderation state."""
    valid_states = {"pending", "approved", "rejected", "flagged"}
    if state not in valid_states:
        return False, f"Invalid state. Must be one of: {', '.join(valid_states)}"
    return True, ""


def validate_visibility(visibility: str) -> Tuple[bool, str]:
    """Validate visibility setting."""
    valid = {"public", "friends_only", "hidden"}
    if visibility not in valid:
        return False, f"Invalid visibility. Must be one of: {', '.join(valid)}"
    return True, ""
