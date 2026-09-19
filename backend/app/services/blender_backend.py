"""
Blender Backend — Detection, Configuration, Subprocess Wrapper

Detects Blender on the system, provides configurable path via
BLENDER_PATH env var with automatic discovery fallback, and wraps
subprocess calls with timeouts, error handling, and logging.

Falls back to pure-Python implementations when Blender is unavailable.
"""

import os
import sys
import json
import shutil
import logging
import platform
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Common Blender installation paths per platform
_WINDOWS_PATHS = [
    r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 3.5\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 3.4\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 3.3\blender.exe",
]

_LINUX_PATHS = [
    "/usr/bin/blender",
    "/usr/local/bin/blender",
    "/snap/bin/blender",
    "/opt/blender/blender",
    os.path.expanduser("~/.local/bin/blender"),
]

_MACOS_PATHS = [
    "/Applications/Blender.app/Contents/MacOS/Blender",
    os.path.expanduser("~/Applications/Blender.app/Contents/MacOS/Blender"),
]

DEFAULT_TIMEOUT = 120  # seconds
MAX_TIMEOUT = 600  # 10 minutes


@dataclass
class BlenderInfo:
    """Information about a detected Blender installation."""
    path: str
    version: str = "unknown"
    python_version: str = "unknown"
    available: bool = True
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BlenderBackend:
    """
    Blender detection and subprocess execution backend.

    Usage:
        backend = BlenderBackend()
        if backend.is_available():
            result = backend.run_script(script_path)
        else:
            # fall back to pure Python
            ...
    """

    _instance: Optional["BlenderBackend"] = None
    _blender_path: Optional[str] = None
    _blender_info: Optional[BlenderInfo] = None
    _detection_done: bool = False

    def __new__(cls) -> "BlenderBackend":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._detection_done:
            self._detect_blender()

    def _detect_blender(self):
        """Detect Blender: env var first, then platform-specific paths, then PATH."""
        self._detection_done = True

        # 1. Check BLENDER_PATH env var
        env_path = os.environ.get("BLENDER_PATH")
        if env_path:
            if self._validate_blender_path(env_path):
                self._blender_path = env_path
                self._blender_info = self._probe_blender(env_path)
                logger.info(f"Blender detected from BLENDER_PATH: {env_path} (v{self._blender_info.version})")
                return
            else:
                logger.warning(f"BLENDER_PATH set to '{env_path}' but Blender not found there")

        # 2. Check platform-specific common paths
        if platform.system() == "Windows":
            search_paths = _WINDOWS_PATHS
        elif platform.system() == "Darwin":
            search_paths = _MACOS_PATHS
        else:
            search_paths = _LINUX_PATHS

        for path in search_paths:
            if self._validate_blender_path(path):
                self._blender_path = path
                self._blender_info = self._probe_blender(path)
                logger.info(f"Blender detected at: {path} (v{self._blender_info.version})")
                return

        # 3. Check system PATH
        blender_in_path = shutil.which("blender")
        if blender_in_path and self._validate_blender_path(blender_in_path):
            self._blender_path = blender_in_path
            self._blender_info = self._probe_blender(blender_in_path)
            logger.info(f"Blender detected in PATH: {blender_in_path} (v{self._blender_info.version})")
            return

        # 4. Not found
        self._blender_path = None
        self._blender_info = BlenderInfo(path="", available=False)
        logger.warning(
            "Blender not found. Set BLENDER_PATH env var or install Blender. "
            "Falling back to pure-Python implementations."
        )

    def _validate_blender_path(self, path: str) -> bool:
        """Validate that a path points to a Blender executable."""
        p = Path(path)
        if not p.exists():
            return False
        if not p.is_file():
            return False
        # On Windows, check extension
        if platform.system() == "Windows" and not p.suffix.lower() in (".exe", ""):
            return False
        return True

    def _probe_blender(self, path: str) -> BlenderInfo:
        """Get Blender version info via --version flag."""
        try:
            result = subprocess.run(
                [path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            version = "unknown"
            python_version = "unknown"
            for line in result.stdout.splitlines():
                if line.startswith("Blender"):
                    parts = line.split()
                    if len(parts) >= 2:
                        version = parts[1]
                if "Python" in line:
                    python_version = line.strip()
            return BlenderInfo(path=path, version=version, python_version=python_version)
        except Exception as e:
            logger.warning(f"Could not probe Blender version: {e}")
            return BlenderInfo(path=path, version="unknown")

    def is_available(self) -> bool:
        """Check if Blender is available."""
        return self._blender_path is not None

    def get_path(self) -> Optional[str]:
        """Get the Blender executable path."""
        return self._blender_path

    def get_info(self) -> BlenderInfo:
        """Get Blender version info."""
        if self._blender_info is None:
            return BlenderInfo(path="", available=False)
        return self._blender_info

    def run_script(
        self,
        script: str,
        timeout: int = DEFAULT_TIMEOUT,
        script_args: Optional[Dict[str, Any]] = None,
    ) -> "BlenderResult":
        """
        Run a Blender Python script in background mode.

        Args:
            script: Python script content (not path) to execute
            timeout: Subprocess timeout in seconds
            script_args: Dict of args to pass as JSON via environment variable

        Returns:
            BlenderResult with stdout, stderr, return code
        """
        if not self.is_available():
            return BlenderResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr="Blender not available",
                execution_time_ms=0,
            )

        timeout = min(timeout, MAX_TIMEOUT)

        with tempfile.TemporaryDirectory(prefix="rw_blender_") as tmpdir:
            script_path = Path(tmpdir) / "script.py"
            script_path.write_text(script, encoding="utf-8")

            # Pass args via environment variable
            env = os.environ.copy()
            if script_args:
                env["RW_BLENDER_ARGS"] = json.dumps(script_args)

            # Write args to file for reliability
            args_path = Path(tmpdir) / "args.json"
            if script_args:
                args_path.write_text(json.dumps(script_args), encoding="utf-8")

            cmd = [
                self._blender_path,
                "--background",
                "--python", str(script_path),
            ]

            start = datetime.now(timezone.utc)
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=tmpdir,
                    env=env,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000

                # Check for output files
                output_files = list(Path(tmpdir).glob("output_*"))

                return BlenderResult(
                    success=result.returncode == 0,
                    return_code=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    execution_time_ms=round(elapsed),
                    output_files=[str(f) for f in output_files],
                )

            except subprocess.TimeoutExpired:
                elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                logger.error(f"Blender script timed out after {timeout}s")
                return BlenderResult(
                    success=False,
                    return_code=-2,
                    stdout="",
                    stderr=f"Timeout after {timeout}s",
                    execution_time_ms=round(elapsed),
                )
            except Exception as e:
                elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                logger.error(f"Blender execution error: {e}")
                return BlenderResult(
                    success=False,
                    return_code=-3,
                    stdout="",
                    stderr=str(e),
                    execution_time_ms=round(elapsed),
                )

    def run_script_file(
        self,
        script_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
        script_args: Optional[Dict[str, Any]] = None,
    ) -> "BlenderResult":
        """Run a Blender Python script file in background mode."""
        script_content = script_path.read_text(encoding="utf-8")
        return self.run_script(script_content, timeout=timeout, script_args=script_args)


@dataclass
class BlenderResult:
    """Result of a Blender subprocess execution."""
    success: bool
    return_code: int
    stdout: str
    stderr: str
    execution_time_ms: int
    output_files: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "return_code": self.return_code,
            "stdout": self.stdout[:500],
            "stderr": self.stderr[:500],
            "execution_time_ms": self.execution_time_ms,
            "output_files": self.output_files,
        }


# Singleton
blender_backend = BlenderBackend()
