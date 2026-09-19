from typing import Optional, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.models.friendship import Friendship
from app.models.user import User


class FriendshipService:
    """Business logic for friend relationships."""

    @staticmethod
    def get_friendship(db: Session, user_a: int, user_b: int) -> Optional[Friendship]:
        """Get existing friendship row between two users (any direction)."""
        return db.query(Friendship).filter(
            or_(
                and_(Friendship.requester_id == user_a, Friendship.addressee_id == user_b),
                and_(Friendship.requester_id == user_b, Friendship.addressee_id == user_a),
            )
        ).first()

    @staticmethod
    def send_request(db: Session, requester_id: int, addressee_id: int) -> Friendship:
        """Send a friend request. Raises ValueError on invalid conditions."""
        if requester_id == addressee_id:
            raise ValueError("Cannot send friend request to yourself")

        addressee = db.query(User).filter(User.id == addressee_id).first()
        if not addressee:
            raise ValueError("User not found")

        existing = FriendshipService.get_friendship(db, requester_id, addressee_id)
        if existing:
            if existing.status == "accepted":
                raise ValueError("Already friends")
            elif existing.status == "blocked":
                raise ValueError("Cannot send friend request to this user")
            elif existing.status == "pending":
                if existing.requester_id == requester_id:
                    raise ValueError("Friend request already sent")
                else:
                    # Reverse pending request exists — auto-accept
                    existing.status = "accepted"
                    db.commit()
                    db.refresh(existing)
                    return existing
            elif existing.status == "rejected":
                # Update existing rejected request
                existing.requester_id = requester_id
                existing.addressee_id = addressee_id
                existing.status = "pending"
                db.commit()
                db.refresh(existing)
                return existing

        friendship = Friendship(
            requester_id=requester_id,
            addressee_id=addressee_id,
            status="pending",
        )
        db.add(friendship)
        db.commit()
        db.refresh(friendship)
        return friendship

    @staticmethod
    def accept_request(db: Session, friendship_id: int, user_id: int) -> Friendship:
        """Accept a pending friend request. Only addressee can accept."""
        friendship = db.query(Friendship).filter(Friendship.id == friendship_id).first()
        if not friendship:
            raise ValueError("Friend request not found")
        if friendship.addressee_id != user_id:
            raise ValueError("Only the recipient can accept this request")
        if friendship.status != "pending":
            raise ValueError(f"Request is not pending (status: {friendship.status})")

        friendship.status = "accepted"
        db.commit()
        db.refresh(friendship)
        return friendship

    @staticmethod
    def reject_request(db: Session, friendship_id: int, user_id: int) -> Friendship:
        """Reject a pending friend request. Only addressee can reject."""
        friendship = db.query(Friendship).filter(Friendship.id == friendship_id).first()
        if not friendship:
            raise ValueError("Friend request not found")
        if friendship.addressee_id != user_id:
            raise ValueError("Only the recipient can reject this request")
        if friendship.status != "pending":
            raise ValueError(f"Request is not pending (status: {friendship.status})")

        friendship.status = "rejected"
        db.commit()
        db.refresh(friendship)
        return friendship

    @staticmethod
    def remove_friend(db: Session, friendship_id: int, user_id: int) -> bool:
        """Remove an accepted friendship. Either party can remove."""
        friendship = db.query(Friendship).filter(Friendship.id == friendship_id).first()
        if not friendship:
            raise ValueError("Friendship not found")
        if friendship.status != "accepted":
            raise ValueError("Not currently friends")
        if user_id not in (friendship.requester_id, friendship.addressee_id):
            raise ValueError("Not part of this friendship")

        db.delete(friendship)
        db.commit()
        return True

    @staticmethod
    def block_user(db: Session, blocker_id: int, blocked_id: int) -> Friendship:
        """Block a user. Creates or updates friendship row with blocked status."""
        if blocker_id == blocked_id:
            raise ValueError("Cannot block yourself")

        blocked_user = db.query(User).filter(User.id == blocked_id).first()
        if not blocked_user:
            raise ValueError("User not found")

        existing = FriendshipService.get_friendship(db, blocker_id, blocked_id)
        if existing:
            existing.status = "blocked"
            # Ensure requester is the blocker for consistency
            if existing.requester_id != blocker_id:
                existing.requester_id = blocker_id
                existing.addressee_id = blocked_id
            db.commit()
            db.refresh(existing)
            return existing

        friendship = Friendship(
            requester_id=blocker_id,
            addressee_id=blocked_id,
            status="blocked",
        )
        db.add(friendship)
        db.commit()
        db.refresh(friendship)
        return friendship

    @staticmethod
    def unblock_user(db: Session, blocker_id: int, blocked_id: int) -> bool:
        """Unblock a user by removing the blocked relationship."""
        friendship = db.query(Friendship).filter(
            Friendship.requester_id == blocker_id,
            Friendship.addressee_id == blocked_id,
            Friendship.status == "blocked",
        ).first()
        if not friendship:
            raise ValueError("Block relationship not found")

        db.delete(friendship)
        db.commit()
        return True

    @staticmethod
    def get_friends(db: Session, user_id: int) -> List[Tuple[Friendship, User]]:
        """Get all accepted friends for a user."""
        friendships = db.query(Friendship).filter(
            or_(
                and_(Friendship.requester_id == user_id, Friendship.status == "accepted"),
                and_(Friendship.addressee_id == user_id, Friendship.status == "accepted"),
            )
        ).all()

        friends = []
        for f in friendships:
            friend_uid = f.addressee_id if f.requester_id == user_id else f.requester_id
            friend_user = db.query(User).filter(User.id == friend_uid).first()
            if friend_user:
                friends.append((f, friend_user))
        return friends

    @staticmethod
    def get_pending_requests(db: Session, user_id: int, direction: str = "received") -> List[Tuple[Friendship, User]]:
        """Get pending friend requests. direction: 'received' or 'sent'."""
        if direction == "received":
            friendships = db.query(Friendship).filter(
                Friendship.addressee_id == user_id,
                Friendship.status == "pending",
            ).all()
            other_id_attr = "requester_id"
        else:
            friendships = db.query(Friendship).filter(
                Friendship.requester_id == user_id,
                Friendship.status == "pending",
            ).all()
            other_id_attr = "addressee_id"

        results = []
        for f in friendships:
            other_uid = getattr(f, other_id_attr)
            other_user = db.query(User).filter(User.id == other_uid).first()
            if other_user:
                results.append((f, other_user))
        return results

    @staticmethod
    def get_blocked_users(db: Session, user_id: int) -> List[Friendship]:
        """Get all users blocked by user_id."""
        return db.query(Friendship).filter(
            Friendship.requester_id == user_id,
            Friendship.status == "blocked",
        ).all()

    @staticmethod
    def is_blocked(db: Session, user_a: int, user_b: int) -> bool:
        """Check if either user has blocked the other."""
        blocked = db.query(Friendship).filter(
            Friendship.status == "blocked",
            or_(
                and_(Friendship.requester_id == user_a, Friendship.addressee_id == user_b),
                and_(Friendship.requester_id == user_b, Friendship.addressee_id == user_a),
            )
        ).first()
        return blocked is not None

    @staticmethod
    def are_friends(db: Session, user_a: int, user_b: int) -> bool:
        """Check if two users are friends."""
        friendship = db.query(Friendship).filter(
            Friendship.status == "accepted",
            or_(
                and_(Friendship.requester_id == user_a, Friendship.addressee_id == user_b),
                and_(Friendship.requester_id == user_b, Friendship.addressee_id == user_a),
            )
        ).first()
        return friendship is not None

    @staticmethod
    def get_friend_ids(db: Session, user_id: int) -> set:
        """Get set of all friend user IDs."""
        friends = FriendshipService.get_friends(db, user_id)
        return {f[1].id for f in friends}
