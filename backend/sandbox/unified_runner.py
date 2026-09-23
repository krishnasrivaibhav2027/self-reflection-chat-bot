"""
Unified sandbox interface that automatically selects the best available runner.

Priority:
1. Docker sandbox (if Docker is available and enabled)
2. Subprocess sandbox (fallback)
"""

import os
import logging
from typing import Optional, List
from enum import Enum

from backend.sandbox.runner import SubprocessSandbox, SandboxExecutionResult

try:
    from backend.sandbox.docker_runner import DockerSandbox, DOCKER_AVAILABLE
except ImportError:
    DOCKER_AVAILABLE = False
    DockerSandbox = None

logger = logging.getLogger("app.sandbox.unified")


class SandboxMode(str, Enum):
    """Available sandbox execution modes."""
    AUTO = "auto"  # Auto-select best available
    DOCKER = "docker"  # Force Docker
    SUBPROCESS = "subprocess"  # Force subprocess


class UnifiedSandbox:
    """
    Unified sandbox that automatically selects the best runner.
    
    Supports both Docker-based and subprocess-based execution with
    automatic fallback.
    """

    def __init__(
        self,
        mode: SandboxMode = SandboxMode.AUTO,
        timeout_seconds: float = 30.0,
        docker_image: str = "codecompletion-sandbox:latest",
        docker_memory_limit: str = "512m",
        docker_cpu_quota: int = 100000,
        enable_network: bool = False,
    ):
        """
        Initialize unified sandbox.

        Args:
            mode: Sandbox mode (auto, docker, or subprocess)
            timeout_seconds: Maximum execution time
            docker_image: Docker image to use (if Docker mode)
            docker_memory_limit: Memory limit for Docker containers
            docker_cpu_quota: CPU quota for Docker containers
            enable_network: Allow network access in Docker containers
        """
        self.mode = mode
        self.timeout_seconds = timeout_seconds
        
        # Initialize subprocess runner (always available)
        self.subprocess_runner = SubprocessSandbox(timeout_seconds=timeout_seconds)
        
        # Try to initialize Docker runner
        self.docker_runner = None
        if DOCKER_AVAILABLE and mode in (SandboxMode.AUTO, SandboxMode.DOCKER):
            try:
                self.docker_runner = DockerSandbox(
                    image=docker_image,
                    timeout_seconds=timeout_seconds,
                    memory_limit=docker_memory_limit,
                    cpu_quota=docker_cpu_quota,
                    enable_network=enable_network,
                )
                logger.info("Docker sandbox initialized successfully")
            except Exception as e:
                logger.warning("Docker sandbox initialization failed: %s", e)
                if mode == SandboxMode.DOCKER:
                    raise RuntimeError(
                        "Docker mode requested but Docker is not available"
                    ) from e

        # Determine active runner
        self._determine_active_runner()

    def _determine_active_runner(self) -> None:
        """Determine which runner to use based on mode and availability."""
        if self.mode == SandboxMode.SUBPROCESS:
            self.active_runner = self.subprocess_runner
            self.active_mode = "subprocess"
            logger.info("Using subprocess sandbox (forced)")
        elif self.mode == SandboxMode.DOCKER:
            if not self.docker_runner:
                raise RuntimeError("Docker mode requested but Docker is not available")
            self.active_runner = self.docker_runner
            self.active_mode = "docker"
            logger.info("Using Docker sandbox (forced)")
        else:  # AUTO mode
            if self.docker_runner:
                self.active_runner = self.docker_runner
                self.active_mode = "docker"
                logger.info("Using Docker sandbox (auto-selected)")
            else:
                self.active_runner = self.subprocess_runner
                self.active_mode = "subprocess"
                logger.info("Using subprocess sandbox (fallback)")

    async def run_tests(
        self,
        code: str,
        tests: str,
        timeout: Optional[float] = None,
        dependencies: Optional[List[str]] = None,
    ) -> SandboxExecutionResult:
        """
        Run tests using the active runner.

        Args:
            code: Python code to test
            tests: Pytest test code
            timeout: Optional timeout override
            dependencies: Optional list of pip packages to install

        Returns:
            SandboxExecutionResult with test results
        """
        logger.info("Running tests with %s sandbox", self.active_mode)

        # Both runners accept the same signature; pass dependencies unconditionally
        return await self.active_runner.run_tests(
            code, tests, timeout, dependencies
        )

    def get_status(self) -> dict:
        """Get status information about available runners."""
        status = {
            "mode": self.mode.value,
            "active_runner": self.active_mode,
            "subprocess_available": True,
            "docker_available": self.docker_runner is not None,
        }

        if self.docker_runner:
            try:
                health = self.docker_runner.health_check()
                status["docker_health"] = health
            except Exception as e:
                status["docker_health"] = {"status": "error", "error": str(e)}

        return status


def create_unified_sandbox() -> UnifiedSandbox:
    """
    Factory function to create unified sandbox with environment-based config.
    
    Environment variables:
    - SANDBOX_MODE: auto, docker, or subprocess (default: auto)
    - SANDBOX_TIMEOUT: timeout in seconds (default: 30)
    - SANDBOX_DOCKER_IMAGE: Docker image (default: codecompletion-sandbox:latest)
    - SANDBOX_MEMORY_LIMIT: memory limit (default: 512m)
    - SANDBOX_CPU_QUOTA: CPU quota (default: 100000)
    - SANDBOX_ENABLE_NETWORK: enable network (default: false)
    """
    mode_str = os.getenv("SANDBOX_MODE", "auto").lower()
    try:
        mode = SandboxMode(mode_str)
    except ValueError:
        logger.warning("Invalid SANDBOX_MODE '%s', using auto", mode_str)
        mode = SandboxMode.AUTO

    return UnifiedSandbox(
        mode=mode,
        timeout_seconds=float(os.getenv("SANDBOX_TIMEOUT", "30")),
        docker_image=os.getenv("SANDBOX_DOCKER_IMAGE", "codecompletion-sandbox:latest"),
        docker_memory_limit=os.getenv("SANDBOX_MEMORY_LIMIT", "512m"),
        docker_cpu_quota=int(os.getenv("SANDBOX_CPU_QUOTA", "100000")),
        enable_network=os.getenv("SANDBOX_ENABLE_NETWORK", "false").lower() == "true",
    )


# Global instance - use this in your application
sandbox = create_unified_sandbox()
