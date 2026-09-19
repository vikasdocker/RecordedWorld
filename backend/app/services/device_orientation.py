"""
Device Orientation Processing Service

Processes accelerometer and gyroscope data from mobile devices.
Converts device orientation to world-space rotation for 3D reconstruction.
"""
import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np


@dataclass
class OrientationSample:
    """A single orientation sample from device sensors."""
    timestamp_ms: float
    # Accelerometer (m/s²)
    accel_x: float = 0.0
    accel_y: float = 0.0
    accel_z: float = 0.0
    # Gyroscope (rad/s)
    gyro_x: float = 0.0
    gyro_y: float = 0.0
    gyro_z: float = 0.0
    # Magnetometer (µT)
    mag_x: float = 0.0
    mag_y: float = 0.0
    mag_z: float = 0.0


@dataclass
class EulerAngles:
    """Euler angles in degrees."""
    heading: float = 0.0   # yaw (0-360)
    pitch: float = 0.0     # -90 to 90
    roll: float = 0.0      # -180 to 180

    def to_quaternion(self) -> Tuple[float, float, float, float]:
        h = math.radians(self.heading)
        p = math.radians(self.pitch)
        r = math.radians(self.roll)

        cy = math.cos(h * 0.5)
        sy = math.sin(h * 0.5)
        cp = math.cos(p * 0.5)
        sp = math.sin(p * 0.5)
        cr = math.cos(r * 0.5)
        sr = math.sin(r * 0.5)

        w = cr * cp * cy + sr * sp * sy
        x = sr * cp * cy - cr * sp * sy
        y = cr * sp * cy + sr * cp * sy
        z = cr * cp * sy - sr * sp * cy
        return (w, x, y, z)

    def to_rotation_matrix(self) -> np.ndarray:
        h = math.radians(self.heading)
        p = math.radians(self.pitch)
        r = math.radians(self.roll)

        cy, sy = math.cos(h), math.sin(h)
        cp, sp = math.cos(p), math.sin(p)
        cr, sr = math.cos(r), math.sin(r)

        return np.array([
            [cy*cr + sy*sp*sr, -cy*sr + sy*sp*cr, sy*cp],
            [cp*sr, cp*cr, -sp],
            [-sy*cr + cy*sp*sr, sy*sr + cy*sp*cr, cy*cp],
        ])


@dataclass
class OrientationResult:
    """Processed orientation result."""
    euler: EulerAngles
    quaternion: Tuple[float, float, float, float]
    rotation_matrix: np.ndarray
    confidence: float  # 0.0 to 1.0
    gravity_vector: Tuple[float, float, float]
    is_upright: bool
    samples_used: int


class DeviceOrientationProcessor:
    """Processes device orientation from sensor data."""

    GRAVITY = 9.81
    ALPHA = 0.98  # Complementary filter coefficient

    def __init__(self):
        self.orientation_history: List[OrientationResult] = []
        self.max_history = 100

    def process_samples(
        self, samples: List[OrientationSample]
    ) -> Optional[OrientationResult]:
        if not samples:
            return None

        # Low-pass filter for gravity estimation
        gravity = self._estimate_gravity(samples)

        # Compute tilt from gravity
        pitch = math.degrees(math.atan2(-gravity[0], math.sqrt(gravity[1]**2 + gravity[2]**2)))
        roll = math.degrees(math.atan2(gravity[1], gravity[2]))

        # Integrate gyroscope for heading
        heading = self._integrate_gyro(samples)

        euler = EulerAngles(heading=heading, pitch=pitch, roll=roll)
        quat = euler.to_quaternion()
        rot_matrix = euler.to_rotation_matrix()

        # Upright check
        is_upright = abs(gravity[2]) > self.GRAVITY * 0.7

        # Confidence based on gravity magnitude consistency
        grav_mag = math.sqrt(sum(g*g for g in gravity))
        confidence = max(0.0, min(1.0, 1.0 - abs(grav_mag - self.GRAVITY) / self.GRAVITY))

        result = OrientationResult(
            euler=euler,
            quaternion=quat,
            rotation_matrix=rot_matrix,
            confidence=confidence,
            gravity_vector=tuple(gravity),
            is_upright=is_upright,
            samples_used=len(samples),
        )

        self.orientation_history.append(result)
        if len(self.orientation_history) > self.max_history:
            self.orientation_history.pop(0)

        return result

    def _estimate_gravity(self, samples: List[OrientationSample]) -> List[float]:
        gravity = [0.0, 0.0, self.GRAVITY]
        for sample in samples:
            gravity[0] = self.ALPHA * gravity[0] + (1 - self.ALPHA) * sample.accel_x
            gravity[1] = self.ALPHA * gravity[1] + (1 - self.ALPHA) * sample.accel_y
            gravity[2] = self.ALPHA * gravity[2] + (1 - self.ALPHA) * sample.accel_z
        return gravity

    def _integrate_gyro(self, samples: List[OrientationSample]) -> float:
        if len(samples) < 2:
            return 0.0

        heading = 0.0
        for i in range(1, len(samples)):
            dt = (samples[i].timestamp_ms - samples[i-1].timestamp_ms) / 1000.0
            if dt > 0:
                heading += math.degrees(samples[i].gyro_z * dt)

        return heading % 360.0

    def smooth_orientation(
        self, window_size: int = 5
    ) -> Optional[OrientationResult]:
        recent = self.orientation_history[-window_size:]
        if not recent:
            return None

        avg_heading = sum(r.euler.heading for r in recent) / len(recent)
        avg_pitch = sum(r.euler.pitch for r in recent) / len(recent)
        avg_roll = sum(r.euler.roll for r in recent) / len(recent)

        euler = EulerAngles(heading=avg_heading, pitch=avg_pitch, roll=avg_roll)
        return OrientationResult(
            euler=euler,
            quaternion=euler.to_quaternion(),
            rotation_matrix=euler.to_rotation_matrix(),
            confidence=sum(r.confidence for r in recent) / len(recent),
            gravity_vector=recent[-1].gravity_vector,
            is_upright=recent[-1].is_upright,
            samples_used=sum(r.samples_used for r in recent),
        )

    def get_capture_orientation(
        self, samples: List[OrientationSample]
    ) -> Tuple[float, float, float]:
        result = self.process_samples(samples)
        if not result:
            return (0.0, 0.0, 0.0)
        return (result.euler.heading, result.euler.pitch, result.euler.roll)


# Module-level singleton
orientation_processor = DeviceOrientationProcessor()
