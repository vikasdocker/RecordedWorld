"""End-to-end pipeline: Mobile capture -> Backend processing -> PC client display."""
import asyncio
from pathlib import Path
from typing import Optional
from datetime import datetime
from dataclasses import dataclass

from app.services.video_processor import get_processor
from app.services.world_generator import generator
from app.services.video_stitcher import VideoStitcher
from app.services.alignment import AlignmentService


@dataclass
class PipelineResult:
    capture_id: int
    status: str
    world_id: Optional[int] = None
    model_path: Optional[str] = None
    world_config: Optional[dict] = None
    processing_time_ms: int = 0
    error: Optional[str] = None


class E2EPipeline:
    """Orchestrates the full capture-to-world pipeline."""

    def __init__(self):
        self.processor = get_processor()
        self.stitcher = VideoStitcher()
        self.alignment = AlignmentService()
        self.active_jobs: dict[int, dict] = {}

    async def run_pipeline(
        self,
        capture_id: int,
        video_path: str,
        gps_data: Optional[dict] = None,
    ) -> PipelineResult:
        """Execute the full pipeline from video to 3D world."""
        start_time = datetime.utcnow()
        self.active_jobs[capture_id] = {"status": "running", "step": "init"}

        try:
            # Step 1: Validate input video
            self.active_jobs[capture_id]["step"] = "validate"
            await self._validate_video(video_path)

            # Step 2: Stitch multiple clips if needed
            self.active_jobs[capture_id]["step"] = "stitch"
            stitched_path = await self.stitcher.stitch_video(video_path)

            # Step 3: Extract and align frames
            self.active_jobs[capture_id]["step"] = "align"
            aligned_frames = await self.alignment.align_frames(stitched_path)

            # Step 4: Process video to 3D model
            self.active_jobs[capture_id]["step"] = "process_3d"
            process_result = await self.processor.process_capture(
                capture_id, stitched_path
            )

            # Step 5: Generate world configuration
            self.active_jobs[capture_id]["step"] = "generate_world"
            world_config = generator.generate_from_capture(
                capture_id=capture_id,
                model_path=process_result["model_path"],
                point_cloud_data={"gps": gps_data} if gps_data else None,
            )

            # Step 6: Export world for PC client
            self.active_jobs[capture_id]["step"] = "export"
            output_dir = Path("uploads") / f"capture_{capture_id}"
            config_path = generator.export_world(capture_id, output_dir)

            elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000

            self.active_jobs[capture_id] = {"status": "complete"}

            return PipelineResult(
                capture_id=capture_id,
                status="ready",
                world_id=capture_id,
                model_path=process_result["model_path"],
                world_config={
                    "name": world_config.name,
                    "spawn": world_config.spawn_points[0] if world_config.spawn_points else None,
                    "boundaries": world_config.boundaries,
                    "objects_count": len(world_config.objects),
                },
                processing_time_ms=int(elapsed),
            )

        except Exception as e:
            self.active_jobs[capture_id] = {"status": "failed", "error": str(e)}
            return PipelineResult(
                capture_id=capture_id,
                status="failed",
                error=str(e),
            )

    async def _validate_video(self, video_path: str):
        """Validate video file exists and is playable."""
        path = Path(video_path)
        if not path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")
        if path.stat().st_size == 0:
            raise ValueError("Video file is empty")

    def get_job_status(self, capture_id: int) -> Optional[dict]:
        """Get current status of a processing job."""
        return self.active_jobs.get(capture_id)

    def get_all_jobs(self) -> dict:
        """Get all active jobs."""
        return self.active_jobs


# Singleton
pipeline = E2EPipeline()
