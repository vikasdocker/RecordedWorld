"""
Visual Landmark Service

Manages visual landmarks for visual localization.
"""
import hashlib
import numpy as np
from typing import List, Optional, Tuple
from dataclasses import dataclass
from sqlalchemy.orm import Session

from app.models.visual_landmark import VisualLandmark, LandmarkMatch


@dataclass
class LandmarkMatchResult:
    """Result of a visual landmark matching query."""
    landmark_id: int
    score: float  # 0.0-1.0
    distance_meters: float
    latitude: float
    longitude: float
    altitude: Optional[float]
    inlier_count: int = 0


class VisualLandmarkService:
    """
    Service for managing visual landmarks and performing visual localization.

    Workflow:
      1. Extract features from a capture image
      2. Store as a landmark with geographic position
      3. For new captures, match features against stored landmarks
      4. Use matched landmarks for visual localization
    """

    def __init__(self, db: Session):
        self.db = db

    def extract_and_store_landmark(
        self,
        capture_id: int,
        location_id: Optional[int],
        latitude: float,
        longitude: float,
        altitude: Optional[float],
        image_path: str,
        descriptors: np.ndarray,
        keypoints: np.ndarray,
        feature_type: str = "sift",
        quality_score: float = 0.0,
    ) -> VisualLandmark:
        """
        Extract features from an image and store as a landmark.

        Args:
            capture_id: Source capture ID
            location_id: Associated location ID
            latitude, longitude, altitude: Geographic position
            image_path: Path to source image
            descriptors: Feature descriptors (N x D array)
            keypoints: Keypoint positions (N x 2 array)
            feature_type: Type of features (sift, orb, akaze)
            quality_score: Quality score 0-1
        """
        # Compute image hash
        image_hash = None
        try:
            with open(image_path, "rb") as f:
                image_hash = hashlib.sha256(f.read()).hexdigest()
        except Exception:
            pass

        # Serialize descriptors and keypoints
        import pickle
        descriptor_data = pickle.dumps(descriptors) if descriptors is not None else None
        keypoint_data = pickle.dumps(keypoints) if keypoints is not None else None

        landmark = VisualLandmark(
            capture_id=capture_id,
            location_id=location_id,
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
            feature_type=feature_type,
            descriptor_count=len(descriptors) if descriptors is not None else 0,
            descriptor_data=descriptor_data,
            keypoint_data=keypoint_data,
            image_path=image_path,
            image_hash=image_hash,
            quality_score=quality_score,
        )

        self.db.add(landmark)
        self.db.commit()
        self.db.refresh(landmark)
        return landmark

    def find_nearby_landmarks(
        self,
        latitude: float,
        longitude: float,
        radius_meters: float = 1000.0,
        limit: int = 50,
    ) -> List[VisualLandmark]:
        """Find landmarks within a radius of a coordinate."""
        from app.core.geospatial import WGS84Coordinate, bounding_box

        center = WGS84Coordinate(latitude, longitude)
        min_lat, max_lat, min_lon, max_lon = bounding_box(center, radius_meters)

        return (
            self.db.query(VisualLandmark)
            .filter(
                VisualLandmark.latitude.between(min_lat, max_lat),
                VisualLandmark.longitude.between(min_lon, max_lon),
            )
            .order_by(VisualLandmark.quality_score.desc().nullslast())
            .limit(limit)
            .all()
        )

    def match_landmarks(
        self,
        query_descriptors: np.ndarray,
        latitude: float,
        longitude: float,
        radius_meters: float = 5000.0,
        max_results: int = 10,
        min_score: float = 0.3,
    ) -> List[LandmarkMatchResult]:
        """
        Match query descriptors against stored landmarks.

        Uses brute-force descriptor matching with ratio test.
        """
        # Find candidate landmarks nearby
        candidates = self.find_nearby_landmarks(latitude, longitude, radius_meters, limit=200)

        if not candidates or query_descriptors is None:
            return []

        results = []
        import pickle

        for landmark in candidates:
            if landmark.descriptor_data is None:
                continue

            try:
                stored_descriptors = pickle.loads(landmark.descriptor_data)
            except Exception:
                continue

            # Brute-force matching with ratio test
            score = self._compute_match_score(query_descriptors, stored_descriptors)

            if score >= min_score:
                # Compute distance
                from app.core.geospatial import WGS84Coordinate, haversine_distance
                dist = haversine_distance(
                    WGS84Coordinate(latitude, longitude),
                    WGS84Coordinate(landmark.latitude, landmark.longitude, landmark.altitude or 0),
                )

                results.append(LandmarkMatchResult(
                    landmark_id=landmark.id,
                    score=score,
                    distance_meters=dist,
                    latitude=landmark.latitude,
                    longitude=landmark.longitude,
                    altitude=landmark.altitude,
                ))

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:max_results]

    def _compute_match_score(
        self,
        query_descriptors: np.ndarray,
        stored_descriptors: np.ndarray,
        ratio_threshold: float = 0.75,
    ) -> float:
        """
        Compute match score using ratio test.

        Returns ratio of good matches to total features.
        """
        if len(query_descriptors) == 0 or len(stored_descriptors) == 0:
            return 0.0

        # Compute pairwise distances
        distances = np.linalg.norm(
            query_descriptors[:, np.newaxis] - stored_descriptors,
            axis=2,
        )

        # For each query feature, find best and second-best match
        good_matches = 0
        for i in range(len(query_descriptors)):
            sorted_dists = np.sort(distances[i])
            if len(sorted_dists) >= 2:
                if sorted_dists[0] < ratio_threshold * sorted_dists[1]:
                    good_matches += 1
            elif len(sorted_dists) == 1:
                good_matches += 1

        return good_matches / len(query_descriptors) if len(query_descriptors) > 0 else 0.0

    def update_match_stats(self, landmark_id: int):
        """Update match count for a landmark."""
        landmark = self.db.query(VisualLandmark).filter(VisualLandmark.id == landmark_id).first()
        if landmark:
            from datetime import datetime, timezone
            landmark.match_count += 1
            landmark.last_matched_at = datetime.now(timezone.utc)
            self.db.commit()

    def get_landmark_stats(self) -> dict:
        """Get statistics about the landmark database."""
        from sqlalchemy import func

        total = self.db.query(func.count(VisualLandmark.id)).scalar() or 0
        by_type = (
            self.db.query(VisualLandmark.feature_type, func.count(VisualLandmark.id))
            .group_by(VisualLandmark.feature_type)
            .all()
        )

        return {
            "total_landmarks": total,
            "by_feature_type": {t: c for t, c in by_type},
        }
