"""
Tests for Phase 14 — Online/Offline Presence and Party/Group System.

Comprehensive test coverage for PresenceService and PartyService.
"""

import time
import pytest
from app.services.presence_service import (
    PresenceService, PresenceState, PlayerPresence,
)
from app.services.party_service import (
    PartyService, Party, PartyMember, PartyInvite,
    PartyRole, PartyState,
)


# =========================================================================
# Presence Service Tests
# =========================================================================

class TestPresenceConnect:
    def setup_method(self):
        PresenceService.clear()

    def test_connect_creates_presence(self):
        p = PresenceService.connect(1, "alice")
        assert p.player_id == 1
        assert p.username == "alice"
        assert p.state == PresenceState.ONLINE

    def test_connect_sets_timestamps(self):
        p = PresenceService.connect(1, "alice")
        assert p.last_seen > 0
        assert p.connected_since > 0
        assert p.last_activity > 0

    def test_connect_sets_world(self):
        p = PresenceService.connect(1, "alice", world_id=42)
        assert p.world_id == 42

    def test_connect_reconnect(self):
        PresenceService.connect(1, "alice")
        PresenceService.disconnect(1)
        p = PresenceService.connect(1, "alice")
        assert p.state == PresenceState.ONLINE
        assert p.connected_since > 0


class TestPresenceDisconnect:
    def setup_method(self):
        PresenceService.clear()

    def test_disconnect_sets_offline(self):
        PresenceService.connect(1, "alice")
        p = PresenceService.disconnect(1)
        assert p.state == PresenceState.OFFLINE

    def test_disconnect_clears_activity(self):
        PresenceService.connect(1, "alice")
        PresenceService.update_activity(1, "exploring")
        p = PresenceService.disconnect(1)
        assert p.activity == ""

    def test_disconnect_not_connected(self):
        p = PresenceService.disconnect(999)
        assert p is None


class TestPresenceHeartbeat:
    def setup_method(self):
        PresenceService.clear()

    def test_heartbeat_updates_last_seen(self):
        PresenceService.connect(1, "alice")
        before = time.time()
        p = PresenceService.heartbeat(1)
        assert p.last_seen >= before

    def test_heartbeat_restores_from_away(self):
        PresenceService.connect(1, "alice")
        PresenceService.set_state(1, PresenceState.AWAY)
        p = PresenceService.heartbeat(1)
        assert p.state == PresenceState.ONLINE

    def test_heartbeat_unknown_player(self):
        p = PresenceService.heartbeat(999)
        assert p is None


class TestPresenceActivity:
    def setup_method(self):
        PresenceService.clear()

    def test_update_activity(self):
        PresenceService.connect(1, "alice")
        p = PresenceService.update_activity(1, "building")
        assert p.activity == "building"

    def test_update_activity_updates_timestamps(self):
        PresenceService.connect(1, "alice")
        before = time.time()
        PresenceService.update_activity(1, "exploring")
        p = PresenceService.get_presence(1)
        assert p.last_activity >= before
        assert p.last_seen >= before


class TestPresenceState:
    def setup_method(self):
        PresenceService.clear()

    def test_set_state(self):
        PresenceService.connect(1, "alice")
        p = PresenceService.set_state(1, PresenceState.DO_NOT_DISTURB)
        assert p.state == PresenceState.DO_NOT_DISTURB

    def test_set_status_text(self):
        PresenceService.connect(1, "alice")
        p = PresenceService.set_status_text(1, "Exploring downtown!")
        assert p.status_text == "Exploring downtown!"

    def test_set_status_text_truncated(self):
        PresenceService.connect(1, "alice")
        p = PresenceService.set_status_text(1, "x" * 200)
        assert len(p.status_text) == 100


class TestPresenceQueries:
    def setup_method(self):
        PresenceService.clear()

    def test_get_presence(self):
        PresenceService.connect(1, "alice")
        p = PresenceService.get_presence(1)
        assert p is not None
        assert p.username == "alice"

    def test_get_by_username(self):
        PresenceService.connect(1, "alice")
        p = PresenceService.get_by_username("alice")
        assert p is not None
        assert p.player_id == 1

    def test_get_by_username_case_insensitive(self):
        PresenceService.connect(1, "Alice")
        p = PresenceService.get_by_username("alice")
        assert p is not None

    def test_is_online(self):
        PresenceService.connect(1, "alice")
        assert PresenceService.is_online(1)
        assert not PresenceService.is_online(999)

    def test_get_online_players(self):
        PresenceService.connect(1, "alice")
        PresenceService.connect(2, "bob")
        PresenceService.connect(3, "charlie")
        PresenceService.disconnect(2)
        online = PresenceService.get_online_players()
        ids = {p.player_id for p in online}
        assert 1 in ids
        assert 3 in ids
        assert 2 not in ids

    def test_get_online_count(self):
        PresenceService.connect(1, "alice")
        PresenceService.connect(2, "bob")
        assert PresenceService.get_online_count() == 2

    def test_get_world_players(self):
        PresenceService.connect(1, "alice", world_id=1)
        PresenceService.connect(2, "bob", world_id=2)
        PresenceService.connect(3, "charlie", world_id=1)
        players = PresenceService.get_world_players(1)
        ids = {p.player_id for p in players}
        assert 1 in ids
        assert 3 in ids
        assert 2 not in ids

    def test_get_friend_presences(self):
        PresenceService.connect(1, "alice")
        PresenceService.connect(2, "bob")
        PresenceService.connect(3, "charlie")
        friends = PresenceService.get_friend_presences(1, {2, 3})
        ids = {p.player_id for p in friends}
        assert 2 in ids
        assert 3 in ids

    def test_set_party(self):
        PresenceService.connect(1, "alice")
        p = PresenceService.set_party(1, "party-123")
        assert p.party_id == "party-123"


class TestPresenceCleanup:
    def setup_method(self):
        PresenceService.clear()

    def test_check_away_timeout(self):
        PresenceService.connect(1, "alice")
        # Simulate old activity
        p = PresenceService.get_presence(1)
        p.last_activity = time.time() - 600  # 10 min ago
        away = PresenceService.check_away_timeout()
        assert 1 in away
        assert PresenceService.get_presence(1).state == PresenceState.AWAY

    def test_check_away_no_timeout(self):
        PresenceService.connect(1, "alice")
        PresenceService.update_activity(1, "exploring")
        away = PresenceService.check_away_timeout()
        assert 1 not in away

    def test_cleanup_stale(self):
        PresenceService.connect(1, "alice")
        PresenceService.disconnect(1)
        p = PresenceService.get_presence(1)
        p.last_seen = time.time() - 100000  # 24+ hours ago
        removed = PresenceService.cleanup_stale()
        assert 1 in removed
        assert PresenceService.get_presence(1) is None


class TestPresenceStats:
    def setup_method(self):
        PresenceService.clear()

    def test_stats(self):
        PresenceService.connect(1, "alice")
        PresenceService.connect(2, "bob")
        PresenceService.set_state(2, PresenceState.AWAY)
        PresenceService.connect(3, "charlie")
        PresenceService.disconnect(3)
        stats = PresenceService.get_stats()
        assert stats["online"] == 1
        assert stats["away"] == 1
        assert stats["offline"] == 1
        assert stats["total_tracked"] == 3


class TestPresenceToDict:
    def setup_method(self):
        PresenceService.clear()

    def test_to_dict(self):
        PresenceService.connect(1, "alice")
        p = PresenceService.get_presence(1)
        d = p.to_dict()
        assert d["player_id"] == 1
        assert d["state"] == "online"
        assert "seconds_since_seen" in d

    def test_is_online_property(self):
        p = PlayerPresence(player_id=1, username="alice", state=PresenceState.ONLINE)
        assert p.is_online

    def test_is_available_property(self):
        p = PlayerPresence(player_id=1, username="alice", state=PresenceState.AWAY)
        assert p.is_available
        p2 = PlayerPresence(player_id=2, username="bob", state=PresenceState.OFFLINE)
        assert not p2.is_available


# =========================================================================
# Party Service Tests
# =========================================================================

class TestPartyCreate:
    def setup_method(self):
        PartyService.clear()

    def test_create_party(self):
        party = PartyService.create_party(1, "alice")
        assert party.leader_id == 1
        assert party.leader_name == "alice"
        assert party.is_active
        assert len(party.members) == 1

    def test_create_party_with_name(self):
        party = PartyService.create_party(1, "alice", name="Adventure Squad")
        assert party.name == "Adventure Squad"

    def test_create_party_custom_size(self):
        party = PartyService.create_party(1, "alice", max_size=4)
        assert party.max_size == 4

    def test_create_party_already_in_party(self):
        PartyService.create_party(1, "alice")
        with pytest.raises(ValueError, match="already in a party"):
            PartyService.create_party(1, "alice")

    def test_create_party_sets_leader(self):
        party = PartyService.create_party(1, "alice")
        assert party.members[1].role == PartyRole.LEADER


class TestPartyInvite:
    def setup_method(self):
        PartyService.clear()

    def test_invite(self):
        party = PartyService.create_party(1, "alice")
        invite = PartyService.invite_to_party(party.party_id, 1, 2)
        assert invite.inviter_id == 1
        assert invite.invitee_id == 2

    def test_invite_not_in_party(self):
        party = PartyService.create_party(1, "alice")
        with pytest.raises(ValueError, match="not in this party"):
            PartyService.invite_to_party(party.party_id, 999, 2)

    def test_invite_already_member(self):
        party = PartyService.create_party(1, "alice")
        with pytest.raises(ValueError, match="already in this party"):
            PartyService.invite_to_party(party.party_id, 1, 1)

    def test_invite_party_full(self):
        party = PartyService.create_party(1, "alice", max_size=1)
        with pytest.raises(ValueError, match="Party is full"):
            PartyService.invite_to_party(party.party_id, 1, 2)

    def test_invite_already_in_other_party(self):
        party1 = PartyService.create_party(1, "alice")
        party2 = PartyService.create_party(2, "bob")
        PartyService.join_party(party2.party_id, 3, "charlie")
        with pytest.raises(ValueError, match="already in another party"):
            PartyService.invite_to_party(party1.party_id, 1, 3)

    def test_invite_duplicate(self):
        party = PartyService.create_party(1, "alice")
        PartyService.invite_to_party(party.party_id, 1, 2)
        with pytest.raises(ValueError, match="Invite already pending"):
            PartyService.invite_to_party(party.party_id, 1, 2)

    def test_invite_not_active(self):
        party = PartyService.create_party(1, "alice")
        PartyService.dissolve_party(1)
        with pytest.raises(ValueError, match="dissolved"):
            PartyService.invite_to_party(party.party_id, 1, 2)


class TestPartyAccept:
    def setup_method(self):
        PartyService.clear()

    def test_accept_invite(self):
        party = PartyService.create_party(1, "alice")
        invite = PartyService.invite_to_party(party.party_id, 1, 2)
        result = PartyService.accept_invite(invite.invite_id, 2)
        assert 2 in result.members
        assert len(result.members) == 2

    def test_accept_wrong_player(self):
        party = PartyService.create_party(1, "alice")
        invite = PartyService.invite_to_party(party.party_id, 1, 2)
        with pytest.raises(ValueError, match="not for you"):
            PartyService.accept_invite(invite.invite_id, 3)

    def test_accept_expired(self):
        party = PartyService.create_party(1, "alice")
        invite = PartyService.invite_to_party(party.party_id, 1, 2)
        invite.expires_at = time.time() - 100
        with pytest.raises(ValueError, match="expired"):
            PartyService.accept_invite(invite.invite_id, 2)

    def test_accept_already_in_party(self):
        party = PartyService.create_party(1, "alice")
        invite = PartyService.invite_to_party(party.party_id, 1, 2)
        PartyService.accept_invite(invite.invite_id, 2)  # now 2 is in party
        # Try to accept another invite for player 2
        invite2 = PartyService.invite_to_party(party.party_id, 1, 3)
        # Player 2 tries to accept invite meant for player 3
        with pytest.raises(ValueError, match="not for you"):
            PartyService.accept_invite(invite2.invite_id, 2)


class TestPartyJoin:
    def setup_method(self):
        PartyService.clear()

    def test_join_party(self):
        party = PartyService.create_party(1, "alice")
        result = PartyService.join_party(party.party_id, 2, "bob")
        assert 2 in result.members
        assert result.members[2].username == "bob"

    def test_join_full_party(self):
        party = PartyService.create_party(1, "alice", max_size=1)
        with pytest.raises(ValueError, match="Party is full"):
            PartyService.join_party(party.party_id, 2, "bob")

    def test_join_already_in_party(self):
        party1 = PartyService.create_party(1, "alice")
        party2 = PartyService.create_party(2, "bob")
        PartyService.join_party(party2.party_id, 3, "charlie")
        with pytest.raises(ValueError, match="already in a party"):
            PartyService.join_party(party1.party_id, 3, "charlie")

    def test_join_dissolved_party(self):
        party = PartyService.create_party(1, "alice")
        PartyService.dissolve_party(1)
        with pytest.raises(ValueError, match="dissolved"):
            PartyService.join_party(party.party_id, 2, "bob")


class TestPartyLeave:
    def setup_method(self):
        PartyService.clear()

    def test_leave_party(self):
        party = PartyService.create_party(1, "alice")
        PartyService.join_party(party.party_id, 2, "bob")
        result = PartyService.leave_party(2)
        assert result == party.party_id
        assert 2 not in PartyService.get_party(party.party_id).members

    def test_leave_leader_transfers(self):
        party = PartyService.create_party(1, "alice")
        PartyService.join_party(party.party_id, 2, "bob")
        PartyService.leave_party(1)
        updated = PartyService.get_party(party.party_id)
        assert updated.leader_id == 2
        assert updated.leader_name == "bob"
        assert updated.members[2].role == PartyRole.LEADER

    def test_leave_last_member_dissolves(self):
        party = PartyService.create_party(1, "alice")
        PartyService.leave_party(1)
        assert PartyService.get_party(party.party_id).state == PartyState.DISSOLVED

    def test_leave_not_in_party(self):
        result = PartyService.leave_party(999)
        assert result is None


class TestPartyKick:
    def setup_method(self):
        PartyService.clear()

    def test_kick_member(self):
        party = PartyService.create_party(1, "alice")
        PartyService.join_party(party.party_id, 2, "bob")
        result = PartyService.kick_member(1, 2)
        assert result is True
        assert 2 not in PartyService.get_party(party.party_id).members

    def test_kick_not_leader(self):
        party = PartyService.create_party(1, "alice")
        PartyService.join_party(party.party_id, 2, "bob")
        result = PartyService.kick_member(2, 1)
        assert result is False

    def test_kick_self(self):
        party = PartyService.create_party(1, "alice")
        result = PartyService.kick_member(1, 1)
        assert result is False

    def test_kick_not_in_party(self):
        result = PartyService.kick_member(999, 1)
        assert result is False


class TestPartyTransfer:
    def setup_method(self):
        PartyService.clear()

    def test_transfer_leader(self):
        party = PartyService.create_party(1, "alice")
        PartyService.join_party(party.party_id, 2, "bob")
        result = PartyService.transfer_leader(1, 2)
        assert result is True
        updated = PartyService.get_party(party.party_id)
        assert updated.leader_id == 2

    def test_transfer_not_leader(self):
        party = PartyService.create_party(1, "alice")
        PartyService.join_party(party.party_id, 2, "bob")
        result = PartyService.transfer_leader(2, 1)
        assert result is False

    def test_transfer_to_non_member(self):
        party = PartyService.create_party(1, "alice")
        result = PartyService.transfer_leader(1, 999)
        assert result is False


class TestPartyDissolve:
    def setup_method(self):
        PartyService.clear()

    def test_dissolve(self):
        party = PartyService.create_party(1, "alice")
        result = PartyService.dissolve_party(1)
        assert result is True
        assert PartyService.get_party(party.party_id).state == PartyState.DISSOLVED

    def test_dissolve_not_leader(self):
        party = PartyService.create_party(1, "alice")
        PartyService.join_party(party.party_id, 2, "bob")
        result = PartyService.dissolve_party(2)
        assert result is False

    def test_dissolve_cleans_up_members(self):
        party = PartyService.create_party(1, "alice")
        PartyService.join_party(party.party_id, 2, "bob")
        PartyService.dissolve_party(1)
        assert PartyService.get_player_party(1) is None
        assert PartyService.get_player_party(2) is None


class TestPartyWorld:
    def setup_method(self):
        PartyService.clear()

    def test_set_world(self):
        party = PartyService.create_party(1, "alice")
        result = PartyService.set_world(party.party_id, 42)
        assert result.world_id == 42

    def test_set_shared_position(self):
        party = PartyService.create_party(1, "alice")
        pos = {"lat": 37.7749, "lon": -122.4194}
        result = PartyService.set_shared_position(party.party_id, pos)
        assert result.shared_position == pos


class TestPartyInvites:
    def setup_method(self):
        PartyService.clear()

    def test_get_pending_invites(self):
        party = PartyService.create_party(1, "alice")
        PartyService.invite_to_party(party.party_id, 1, 2)
        PartyService.invite_to_party(party.party_id, 1, 3)
        invites = PartyService.get_pending_invites(2)
        assert len(invites) == 1
        assert invites[0].invitee_id == 2

    def test_revoke_invite(self):
        party = PartyService.create_party(1, "alice")
        invite = PartyService.invite_to_party(party.party_id, 1, 2)
        result = PartyService.revoke_invite(invite.invite_id, 1)
        assert result is True
        assert len(PartyService.get_pending_invites(2)) == 0

    def test_revoke_invite_by_leader(self):
        party = PartyService.create_party(1, "alice")
        PartyService.join_party(party.party_id, 2, "bob")
        invite = PartyService.invite_to_party(party.party_id, 2, 3)
        result = PartyService.revoke_invite(invite.invite_id, 1)  # leader revokes
        assert result is True

    def test_cleanup_expired(self):
        party = PartyService.create_party(1, "alice")
        invite = PartyService.invite_to_party(party.party_id, 1, 2)
        invite.expires_at = time.time() - 100
        removed = PartyService.cleanup_expired_invites()
        assert removed == 1


class TestPartyQueries:
    def setup_method(self):
        PartyService.clear()

    def test_get_party(self):
        party = PartyService.create_party(1, "alice")
        result = PartyService.get_party(party.party_id)
        assert result is not None

    def test_get_player_party(self):
        party = PartyService.create_party(1, "alice")
        result = PartyService.get_player_party(1)
        assert result is not None
        assert result.party_id == party.party_id

    def test_get_player_party_none(self):
        assert PartyService.get_player_party(999) is None

    def test_get_all_parties(self):
        PartyService.create_party(1, "alice")
        PartyService.create_party(2, "bob")
        parties = PartyService.get_all_parties()
        assert len(parties) == 2


class TestPartyStats:
    def setup_method(self):
        PartyService.clear()

    def test_stats(self):
        p1 = PartyService.create_party(1, "alice")
        PartyService.join_party(p1.party_id, 2, "bob")
        p2 = PartyService.create_party(3, "charlie")
        stats = PartyService.get_stats()
        assert stats["total_parties"] == 2
        assert stats["total_members"] == 3
        assert stats["avg_party_size"] == 1.5


class TestPartyToDict:
    def setup_method(self):
        PartyService.clear()

    def test_to_dict(self):
        party = PartyService.create_party(1, "alice", name="Test Party")
        d = party.to_dict()
        assert d["party_id"] == party.party_id
        assert d["leader_id"] == 1
        assert d["name"] == "Test Party"
        assert d["member_count"] == 1
        assert len(d["members"]) == 1

    def test_member_to_dict(self):
        party = PartyService.create_party(1, "alice")
        member = party.members[1]
        d = member.to_dict()
        assert d["player_id"] == 1
        assert d["role"] == "leader"

    def test_invite_to_dict(self):
        party = PartyService.create_party(1, "alice")
        invite = PartyService.invite_to_party(party.party_id, 1, 2)
        d = invite.to_dict()
        assert d["inviter_id"] == 1
        assert d["invitee_id"] == 2


# =========================================================================
# Cross-Service Integration
# =========================================================================

class TestPresencePartyIntegration:
    def setup_method(self):
        PresenceService.clear()
        PartyService.clear()

    def test_party_updates_presence(self):
        PresenceService.connect(1, "alice")
        PresenceService.connect(2, "bob")
        party = PartyService.create_party(1, "alice")
        PartyService.join_party(party.party_id, 2, "bob")
        PresenceService.set_party(1, party.party_id)
        PresenceService.set_party(2, party.party_id)
        assert PresenceService.get_presence(1).party_id == party.party_id
        assert PresenceService.get_presence(2).party_id == party.party_id

    def test_leave_party_clears_presence(self):
        PresenceService.connect(1, "alice")
        party = PartyService.create_party(1, "alice")
        PresenceService.set_party(1, party.party_id)
        PartyService.leave_party(1)
        PresenceService.set_party(1, None)
        assert PresenceService.get_presence(1).party_id is None


class TestEdgeCases:
    def setup_method(self):
        PresenceService.clear()
        PartyService.clear()

    def test_presence_clear(self):
        PresenceService.connect(1, "alice")
        PresenceService.clear()
        assert PresenceService.get_online_count() == 0

    def test_party_clear(self):
        PartyService.create_party(1, "alice")
        PartyService.clear()
        assert len(PartyService.get_all_parties()) == 0

    def test_massive_party_join(self):
        party = PartyService.create_party(1, "alice", max_size=8)
        for i in range(2, 9):
            PartyService.join_party(party.party_id, i, f"player{i}")
        assert len(party.members) == 8
        assert party.is_full

    def test_party_full_then_leave(self):
        party = PartyService.create_party(1, "alice", max_size=2)
        PartyService.join_party(party.party_id, 2, "bob")
        assert party.is_full
        PartyService.leave_party(2)
        assert not party.is_full
        PartyService.join_party(party.party_id, 3, "charlie")
        assert party.is_full
