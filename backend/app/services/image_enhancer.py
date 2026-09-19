"""
Image Enhancement Service

Provides basic image enhancement for reconstruction quality.
"""
import numpy as np
from typing import Optional
from dataclasses import dataclass


@dataclass
class EnhancementResult:
    """Result of image enhancement."""
    enhanced_image: np.ndarray
    brightness_delta: float = 0.0
    contrast_delta: float = 0.0
    sharpened: bool = False
    denoised: bool = False


class ImageEnhancer:
    """
    Basic image enhancement for improving reconstruction quality.

    Provides:
      - Brightness/contrast normalization
      - Noise reduction
      - Sharpening
      - White balance correction
    """

    def enhance(
        self,
        image: np.ndarray,
        normalize_brightness: bool = True,
        normalize_contrast: bool = True,
        denoise: bool = False,
        sharpen: bool = False,
        target_brightness: float = 0.5,
        target_contrast: float = 0.5,
    ) -> EnhancementResult:
        """
        Enhance an image for better reconstruction.

        Args:
            image: H x W x 3 RGB image (uint8)
            normalize_brightness: Adjust brightness to target
            normalize_contrast: Adjust contrast to target
            denoise: Apply noise reduction
            sharpen: Apply sharpening filter
            target_brightness: Target mean brightness (0-1)
            target_contrast: Target contrast level (0-1)

        Returns:
            EnhancementResult with enhanced image and deltas
        """
        if image is None or len(image.shape) != 3:
            raise ValueError("Invalid image")

        result = image.copy().astype(np.float32)
        brightness_delta = 0.0
        contrast_delta = 0.0

        # Brightness normalization
        if normalize_brightness:
            current_brightness = np.mean(result) / 255.0
            brightness_delta = target_brightness - current_brightness
            result = np.clip(result + brightness_delta * 255, 0, 255)

        # Contrast normalization
        if normalize_contrast:
            current_std = np.std(result) / 128.0
            if current_std > 0:
                contrast_delta = target_contrast - current_std
                mean = np.mean(result)
                result = (result - mean) * (target_contrast / current_std) + mean
                result = np.clip(result, 0, 255)

        # Denoising (simple box blur)
        if denoise:
            result = self._simple_denoise(result)

        # Sharpening (unsharp mask)
        if sharpen:
            result = self._simple_sharpen(result)

        return EnhancementResult(
            enhanced_image=result.astype(np.uint8),
            brightness_delta=brightness_delta,
            contrast_delta=contrast_delta,
            sharpened=sharpen,
            denoised=denoise,
        )

    def _simple_denoise(self, image: np.ndarray) -> np.ndarray:
        """Simple box filter denoising."""
        h, w, c = image.shape
        result = image.copy()

        # 3x3 box filter
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                for ch in range(c):
                    result[y, x, ch] = np.mean(
                        image[y-1:y+2, x-1:x+2, ch]
                    )

        return result

    def _simple_sharpen(self, image: np.ndarray) -> np.ndarray:
        """Simple unsharp mask sharpening."""
        # Blur
        kernel = np.ones((3, 3)) / 9.0
        import cv2
        blurred = cv2.filter2D(image.astype(np.float32), -1, kernel)

        # Unsharp mask: original + (original - blurred) * amount
        amount = 0.5
        sharpened = image.astype(np.float32) + amount * (image.astype(np.float32) - blurred)
        return np.clip(sharpened, 0, 255)

    def normalize_for_reconstruction(
        self, image: np.ndarray
    ) -> np.ndarray:
        """
        Normalize image specifically for 3D reconstruction.

        Applies brightness normalization and mild contrast enhancement.
        """
        result = self.enhance(
            image,
            normalize_brightness=True,
            normalize_contrast=True,
            target_brightness=0.45,
            target_contrast=0.6,
        )
        return result.enhanced_image


# Module-level singleton
image_enhancer = ImageEnhancer()
