"""
Camera Intrinsics Service

Manages camera intrinsic parameters for accurate 3D reconstruction.
Stores per-device calibration data and provides focal length estimation.
"""
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CameraIntrinsics:
    """Camera intrinsic parameters."""
    device_id: str
    focal_length_mm: float
    sensor_width_mm: float
    sensor_height_mm: float
    principal_point_x: float = 0.5  # normalized 0-1
    principal_point_y: float = 0.5
    distortion_coefficients: List[float] = field(default_factory=list)
    image_width_px: int = 0
    image_height_px: int = 0

    @property
    def focal_length_x_px(self) -> float:
        """Focal length in pixels (horizontal)."""
        if self.image_width_px <= 0 or self.sensor_width_mm <= 0:
            return 0.0
        return self.focal_length_mm * self.image_width_px / self.sensor_width_mm

    @property
    def focal_length_y_px(self) -> float:
        """Focal length in pixels (vertical)."""
        if self.image_height_px <= 0 or self.sensor_height_mm <= 0:
            return 0.0
        return self.focal_length_mm * self.image_height_px / self.sensor_height_mm

    @property
    def fov_horizontal_deg(self) -> float:
        """Horizontal field of view in degrees."""
        if self.sensor_width_mm <= 0 or self.focal_length_mm <= 0:
            return 0.0
        return 2 * math.degrees(math.atan(self.sensor_width_mm / (2 * self.focal_length_mm)))

    @property
    def fov_vertical_deg(self) -> float:
        """Vertical field of view in degrees."""
        if self.sensor_height_mm <= 0 or self.focal_length_mm <= 0:
            return 0.0
        return 2 * math.degrees(math.atan(self.sensor_height_mm / (2 * self.focal_length_mm)))

    @property
    def projection_matrix(self) -> List[List[float]]:
        """3x3 intrinsic projection matrix."""
        fx = self.focal_length_x_px
        fy = self.focal_length_y_px
        cx = self.image_width_px * self.principal_point_x
        cy = self.image_height_px * self.principal_point_y
        return [
            [fx, 0, cx],
            [0, fy, cy],
            [0, 0, 1],
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "focal_length_mm": self.focal_length_mm,
            "sensor_width_mm": self.sensor_width_mm,
            "sensor_height_mm": self.sensor_height_mm,
            "principal_point": [self.principal_point_x, self.principal_point_y],
            "distortion": self.distortion_coefficients,
            "image_size": [self.image_width_px, self.image_height_px],
            "fov_h_deg": self.fov_horizontal_deg,
            "fov_v_deg": self.fov_vertical_deg,
        }


# Common device intrinsics database
DEVICE_INTRINSICS_DB: Dict[str, CameraIntrinsics] = {
    "iphone_15_pro": CameraIntrinsics(
        device_id="iphone_15_pro",
        focal_length_mm=6.86,
        sensor_width_mm=6.17,
        sensor_height_mm=4.63,
        image_width_px=4032,
        image_height_px=3024,
    ),
    "iphone_14": CameraIntrinsics(
        device_id="iphone_14",
        focal_length_mm=6.86,
        sensor_width_mm=6.17,
        sensor_height_mm=4.63,
        image_width_px=4032,
        image_height_px=3024,
    ),
    "pixel_8_pro": CameraIntrinsics(
        device_id="pixel_8_pro",
        focal_length_mm=6.9,
        sensor_width_mm=6.17,
        sensor_height_mm=4.63,
        image_width_px=4080,
        image_height_px=3060,
    ),
    "samsung_s24": CameraIntrinsics(
        device_id="samsung_s24",
        focal_length_mm=6.3,
        sensor_width_mm=6.17,
        sensor_height_mm=4.63,
        image_width_px=4000,
        image_height_px=3000,
    ),
}


class CameraIntrinsicsService:
    """Manages camera intrinsics for 3D reconstruction."""

    def __init__(self):
        self.calibrations: Dict[str, CameraIntrinsics] = dict(DEVICE_INTRINSICS_DB)

    def get_intrinsics(self, device_id: str) -> Optional[CameraIntrinsics]:
        return self.calibrations.get(device_id)

    def register_device(self, intrinsics: CameraIntrinsics):
        self.calibrations[intrinsics.device_id] = intrinsics

    def estimate_from_metadata(
        self,
        device_make: str = "",
        device_model: str = "",
        image_width: int = 0,
        image_height: int = 0,
        focal_length_35mm: float = 0.0,
    ) -> CameraIntrinsics:
        device_key = f"{device_make}_{device_model}".lower().replace(" ", "_")
        if device_key in self.calibrations:
            return self.calibrations[device_key]

        # Estimate from 35mm equivalent focal length
        if focal_length_35mm > 0:
            sensor_crop = 1.0
            real_focal = focal_length_35mm * sensor_crop
            return CameraIntrinsics(
                device_id=device_key,
                focal_length_mm=real_focal,
                sensor_width_mm=6.17,
                sensor_height_mm=4.63,
                image_width_px=image_width or 1920,
                image_height_px=image_height or 1080,
            )

        # Default fallback
        return CameraIntrinsics(
            device_id=device_key,
            focal_length_mm=4.0,
            sensor_width_mm=6.17,
            sensor_height_mm=4.63,
            image_width_px=image_width or 1920,
            image_height_px=image_height or 1080,
        )

    def undistort_point(
        self,
        x: float, y: float,
        intrinsics: CameraIntrinsics,
    ) -> Tuple[float, float]:
        """Simple radial undistortion."""
        if not intrinsics.distortion_coefficients:
            return x, y

        k1 = intrinsics.distortion_coefficients[0] if len(intrinsics.distortion_coefficients) > 0 else 0
        cx = intrinsics.image_width_px * intrinsics.principal_point_x
        cy = intrinsics.image_height_px * intrinsics.principal_point_y

        dx = (x - cx) / intrinsics.focal_length_x_px
        dy = (y - cy) / intrinsics.focal_length_y_px
        r2 = dx * dx + dy * dy

        factor = 1 + k1 * r2
        undist_x = dx * factor * intrinsics.focal_length_x_px + cx
        undist_y = dy * factor * intrinsics.focal_length_y_px + cy
        return undist_x, undist_y

    def get_stats(self) -> Dict[str, Any]:
        return {
            "registered_devices": len(self.calibrations),
            "devices": list(self.calibrations.keys()),
        }


# Module-level singleton
camera_intrinsics_service = CameraIntrinsicsService()
