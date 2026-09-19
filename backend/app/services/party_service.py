"""
Party/Group System

Allows players to form groups for shared exploration, chat, and world traversal.
Parties have a leader, members, invite system, and shared world state.

- Party size limit (configurable, default 8)
- Invite/accept/decline/kick/leave
- Leader transfer
- Party-wide chat channel
- World sharing (party members teleport to same location)
"""

import uuid
import time
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field


class PartyRole(str, Enum):
    """Roles within a party."""
    LEADER = "leader"
    MEMBER = "member"


class PartyState(str, Enum):
    """Party lifecycle states."""
    ACTIVE = "active"
    DISSOLVED = "dissolved"


@dataclass
class PartyInvite:
    """An invitation to join a party."""
    invite_id: str
    party_id: str
    inviter_id: int
    invitee_id: int
    created_at: float = 0.0
    expires_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "invite_id": self.invite_id,
            "party_id": self.party_id,
            "inviter_id": self.inviter_id,
            "invitee_id": self.invitee_id,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at if self.expires_at else False


@dataclass
class PartyMember:
    """A member of a party."""
    player_id: int
    username: str
    role: PartyRole = PartyRole.MEMBER
    joined_at: float = 0.0
    last_active: float = 0.0

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "username": self.username,
            "role": self.role.value,
            "joined_at": self.joined_at,
            "last_active": self.last_active,
        }


@dataclass
class Party:
    """A group of players."""
    party_id: str
    leader_id: int
    leader_name: str
    name: str = ""
    state: PartyState = PartyState.ACTIVE
    members: Dict[int, PartyMember] = field(default_factory=dict)
    created_at: float = 0.0
    max_size: int = 8
    world_id: int = 0
    shared_position: Optional[dict] = None  # teleport sync

    def to_dict(self) -> dict:
        return {
            "party_id": self.party_id,
            "leader_id": self.leader_id,
            "leader_name": self.leader_name,
            "name": self.name,
            "state": self.state.value,
            "member_count": len(self.members),
            "max_size": self.max_size,
            "members": [m.to_dict() for m in self.members.values()],
            "world_id": self.world_id,
            "created_at": self.created_at,
        }

    @property
    def is_full(self) -> bool:
        return len(self.members) >= self.max_size

    @property
    def is_active(self) -> bool:
        return self.state == PartyState.ACTIVE

    @property
    def member_ids(self) -> Set[int]:
        return set(self.members.keys())


class PartyService:
    """
    Manages party creation, invites, membership, and lifecycle.

    All operations are synchronous (in-memory store).
    Thread-safe via GIL for CPython; use locks for production.
    """

    _parties: Dict[str, Party] = {}  # party_id -> Party
    _player_party: Dict[int, str] = {}  # player_id -> party_id
    _invites: Dict[str, PartyInvite] = {}  # invite_id -> PartyInvite
    _default_max_size: int = 8
    _invite_expiry: float = 300.0  # 5 minutes

    @classmethod
    def create_party(
        cls,
        leader_id: int,
        leader_name: str,
        name: str = "",
        max_size: int = 0,
        world_id: int = 0,
    ) -> Party:
        """
        Create a new party with the given player as leader.

        Raises ValueError if player is already in a party.
        """
        if leader_id in cls._player_party:
            raise ValueError("Player is already in a party")

        if max_size <= 0:
            max_size = cls._default_max_size

        party_id = str(uuid.uuid4())[:12]
        now = time.time()

        leader = PartyMember(
            player_id=leader_id,
            username=leader_name,
            role=PartyRole.LEADER,
            joined_at=now,
            last_active=now,
        )

        party = Party(
            party_id=party_id,
            leader_id=leader_id,
            leader_name=leader_name,
            name=name or f"{leader_name}'s Party",
            members={leader_id: leader},
            created_at=now,
            max_size=max_size,
            world_id=world_id,
        )

        cls._parties[party_id] = party
        cls._player_party[leader_id] = party_id

        return party

    @classmethod
    def invite_to_party(
        cls,
        party_id: str,
        inviter_id: int,
        invitee_id: int,
    ) -> PartyInvite:
        """
        Invite a player to a party.

        Raises ValueError on invalid conditions.
        """
        party = cls._parties.get(party_id)
        if not party or not party.is_active:
            raise ValueError("Party not found or dissolved")

        if inviter_id not in party.members:
            raise ValueError("Inviter is not in this party")

        if invitee_id in party.members:
            raise ValueError("Invitee is already in this party")

        if party.is_full:
            raise ValueError("Party is full")

        if invitee_id in cls._player_party:
            raise ValueError("Invitee is already in another party")

        # Check for existing invite
        for invite in cls._invites.values():
            if invite.party_id == party_id and invite.invitee_id == invitee_id and not invite.is_expired:
                raise ValueError("Invite already pending")

        now = time.time()
        invite = PartyInvite(
            invite_id=str(uuid.uuid4())[:8],
            party_id=party_id,
            inviter_id=inviter_id,
            invitee_id=invitee_id,
            created_at=now,
            expires_at=now + cls._invite_expiry,
        )

        cls._invites[invite.invite_id] = invite
        return invite

    @classmethod
    def accept_invite(cls, invite_id: str, player_id: int) -> Party:
        """
        Accept a party invite.

        Raises ValueError on invalid conditions.
        """
        invite = cls._invites.get(invite_id)
        if not invite:
            raise ValueError("Invite not found")

        if invite.invitee_id != player_id:
            raise ValueError("This invite is not for you")

        if invite.is_expired:
            del cls._invites[invite_id]
            raise ValueError("Invite has expired")

        party = cls._parties.get(invite.party_id)
        if not party or not party.is_active:
            raise ValueError("Party not found or dissolved")

        if party.is_full:
            raise ValueError("Party is full")

        if player_id in cls._player_party:
            raise ValueError("You are already in a party")

        now = time.time()
        member = PartyMember(
            player_id=player_id,
            username=invite.invitee_id and "",  # will be set by caller
            role=PartyRole.MEMBER,
            joined_at=now,
            last_active=now,
        )

        party.members[player_id] = member
        cls._player_party[player_id] = party.party_id
        del cls._invites[invite_id]

        return party

    @classmethod
    def join_party(cls, party_id: str, player_id: int, username: str) -> Party:
        """
        Join a party directly (no invite needed, e.g., open party).

        Raises ValueError on invalid conditions.
        """
        party = cls._parties.get(party_id)
        if not party or not party.is_active:
            raise ValueError("Party not found or dissolved")

        if party.is_full:
            raise ValueError("Party is full")

        if player_id in cls._player_party:
            raise ValueError("Player is already in a party")

        now = time.time()
        member = PartyMember(
            player_id=player_id,
            username=username,
            role=PartyRole.MEMBER,
            joined_at=now,
            last_active=now,
        )

        party.members[player_id] = member
        cls._player_party[player_id] = party_id

        return party

    @classmethod
    def leave_party(cls, player_id: int) -> Optional[str]:
        """
        Leave a party. If the leader leaves, leadership transfers or party dissolves.
        Returns the party_id that was left, or None.
        """
        party_id = cls._player_party.get(player_id)
        if not party_id:
            return None

        party = cls._parties.get(party_id)
        if not party:
            cls._player_party.pop(player_id, None)
            return None

        # Remove member
        party.members.pop(player_id, None)
        cls._player_party.pop(player_id, None)

        # Handle leader departure
        if player_id == party.leader_id:
            remaining = [m for m in party.members.values() if m.role == PartyRole.MEMBER]
            if remaining:
                # Transfer leadership
                new_leader = remaining[0]
                new_leader.role = PartyRole.LEADER
                party.leader_id = new_leader.player_id
                party.leader_name = new_leader.username
            else:
                # No members left — dissolve
                party.state = PartyState.DISSOLVED
                cls._cleanup_party(party_id)

        return party_id

    @classmethod
    def kick_member(cls, leader_id: int, target_id: int) -> bool:
        """
        Kick a member from the party. Only leader can kick.
        Returns True if kicked.
        """
        party_id = cls._player_party.get(leader_id)
        if not party_id:
            return False

        party = cls._parties.get(party_id)
        if not party or party.leader_id != leader_id:
            return False

        if target_id == leader_id:
            return False  # can't kick yourself

        if target_id not in party.members:
            return False

        party.members.pop(target_id, None)
        cls._player_party.pop(target_id, None)

        return True

    @classmethod
    def transfer_leader(cls, current_leader_id: int, new_leader_id: int) -> bool:
        """
        Transfer party leadership. Only current leader can transfer.
        Returns True if transferred.
        """
        party_id = cls._player_party.get(current_leader_id)
        if not party_id:
            return False

        party = cls._parties.get(party_id)
        if not party or party.leader_id != current_leader_id:
            return False

        if new_leader_id not in party.members:
            return False

        # Demote current leader
        party.members[current_leader_id].role = PartyRole.MEMBER
        # Promote new leader
        party.members[new_leader_id].role = PartyRole.LEADER
        party.leader_id = new_leader_id
        party.leader_name = party.members[new_leader_id].username

        return True

    @classmethod
    def dissolve_party(cls, leader_id: int) -> bool:
        """Dissolve a party. Only leader can dissolve."""
        party_id = cls._player_party.get(leader_id)
        if not party_id:
            return False

        party = cls._parties.get(party_id)
        if not party or party.leader_id != leader_id:
            return False

        party.state = PartyState.DISSOLVED
        cls._cleanup_party(party_id)
        return True

    @classmethod
    def set_world(cls, party_id: str, world_id: int) -> Optional[Party]:
        """Set the shared world for a party."""
        party = cls._parties.get(party_id)
        if party and party.is_active:
            party.world_id = world_id
            return party
        return None

    @classmethod
    def set_shared_position(cls, party_id: str, position: dict) -> Optional[Party]:
        """Set shared position for party teleport sync."""
        party = cls._parties.get(party_id)
        if party and party.is_active:
            party.shared_position = position
            return party
        return None

    @classmethod
    def get_party(cls, party_id: str) -> Optional[Party]:
        """Get a party by ID."""
        return cls._parties.get(party_id)

    @classmethod
    def get_player_party(cls, player_id: int) -> Optional[Party]:
        """Get the party a player belongs to."""
        party_id = cls._player_party.get(player_id)
        if party_id:
            return cls._parties.get(party_id)
        return None

    @classmethod
    def get_pending_invites(cls, player_id: int) -> List[PartyInvite]:
        """Get all pending invites for a player."""
        return [
            inv for inv in cls._invites.values()
            if inv.invitee_id == player_id and not inv.is_expired
        ]

    @classmethod
    def revoke_invite(cls, invite_id: str, revoker_id: int) -> bool:
        """Revoke an invite. Only the inviter or party leader can revoke."""
        invite = cls._invites.get(invite_id)
        if not invite:
            return False

        if invite.inviter_id != revoker_id:
            party = cls._parties.get(invite.party_id)
            if not party or party.leader_id != revoker_id:
                return False

        del cls._invites[invite_id]
        return True

    @classmethod
    def cleanup_expired_invites(cls) -> int:
        """Remove expired invites. Returns count removed."""
        expired = [
            iid for iid, inv in cls._invites.items()
            if inv.is_expired
        ]
        for iid in expired:
            del cls._invites[iid]
        return len(expired)

    @classmethod
    def _cleanup_party(cls, party_id: str):
        """Remove all party references."""
        party = cls._parties.get(party_id)
        if party:
            for pid in list(party.members.keys()):
                cls._player_party.pop(pid, None)
            # Remove invites for this party
            to_remove = [
                iid for iid, inv in cls._invites.items()
                if inv.party_id == party_id
            ]
            for iid in to_remove:
                del cls._invites[iid]

    @classmethod
    def get_all_parties(cls) -> List[Party]:
        """Get all active parties."""
        return [p for p in cls._parties.values() if p.is_active]

    @classmethod
    def get_stats(cls) -> dict:
        """Get party statistics."""
        active = [p for p in cls._parties.values() if p.is_active]
        total_members = sum(len(p.members) for p in active)
        return {
            "total_parties": len(active),
            "total_members": total_members,
            "pending_invites": len(cls._invites),
            "avg_party_size": round(total_members / len(active), 1) if active else 0,
        }

    @classmethod
    def clear(cls):
        """Clear all party data (for testing)."""
        cls._parties.clear()
        cls._player_party.clear()
        cls._invites.clear()
