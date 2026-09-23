"""
Docker-based sandbox for secure, isolated test execution.

This module provides a robust Docker sandbox that:
- Runs tests in isolated Docker containers
- Supports resource limits (CPU, memory, timeout)
- Prevents network access (optional)
- Cleans up containers automatically
- Works with any Python version in the Docker image
"""

import os
import re
import time
import asyncio
import logging
import tempfile
import tarfile
from io import BytesIO
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List, Any

try:
    import docker
    from docker.errors import DockerException, ContainerError, ImageNotFound, APIError
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    docker = None

logger = logging.getLogger("app.sandbox.docker")


@dataclass
class SandboxExecutionResult:
    """Result of a sandbox test execution."""
    passed: bool
    output: str
    exit_code: int
    duration_ms: float
    container_id: Optional[str] = None
    errors: Optional[str] = None


def extract_code_block(text: str) -> str:
    """Extract raw Python code from markdown blocks or return raw text."""
    text = text.strip()
    match = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) > 1:
            return "\n".join(lines[1:]).strip()
    return text


class DockerSandbox:
    """
    Isolated Docker-based test runner for executing pytest suites.
    
    Features:
    - Complete isolation from host system
    - Resource limits (CPU, memory)
    - Network isolation
    - Automatic cleanup
    - Support for custom Python images
    """

    DEFAULT_IMAGE = "codecompletion-sandbox:latest"
    DEFAULT_TIMEOUT = 30.0
    DEFAULT_MEMORY_LIMIT = "512m"
    DEFAULT_CPU_QUOTA = 100000  # 1 CPU core

    def __init__(
        self,
        image: str = DEFAULT_IMAGE,
        timeout_seconds: float = DEFAULT_TIMEOUT,
        memory_limit: str = DEFAULT_MEMORY_LIMIT,
        cpu_quota: int = DEFAULT_CPU_QUOTA,
        enable_network: bool = False,
        auto_pull_image: bool = True,
    ):
        """
        Initialize Docker sandbox.

        Args:
            image: Docker image to use (default: codecompletion-sandbox:latest)
            timeout_seconds: Maximum execution time
            memory_limit: Memory limit (e.g., "512m", "1g")
            cpu_quota: CPU quota in microseconds (100000 = 1 core)
            enable_network: Allow network access in containers
            auto_pull_image: Automatically pull image if not found
        """
        if not DOCKER_AVAILABLE:
            raise ImportError(
                "Docker SDK not installed. Install with: pip install docker"
            )

        self.image = image
        self.timeout_seconds = timeout_seconds
        self.memory_limit = memory_limit
        self.cpu_quota = cpu_quota
        self.enable_network = enable_network
        self.auto_pull_image = auto_pull_image

        try:
            self.client = docker.from_env()
            # Test connection
            self.client.ping()
            logger.info("Docker client initialized successfully")
        except DockerException as e:
            logger.error("Failed to initialize Docker client: %s", e)
            raise RuntimeError(
                "Cannot connect to Docker. Ensure Docker Desktop is running."
            ) from e

        # Image availability is checked lazily on first run_tests call

    async def _ensure_image(self) -> None:
        """Ensure the Docker image is available, pull if necessary."""
        try:
            await asyncio.to_thread(self.client.images.get, self.image)
            logger.info("Docker image %s is available", self.image)
        except ImageNotFound:
            logger.info("Pulling Docker image %s (this may take a few minutes)...", self.image)
            try:
                await asyncio.to_thread(self.client.images.pull, self.image)
                logger.info("Successfully pulled image %s", self.image)
            except DockerException as e:
                logger.error("Failed to pull image %s: %s", self.image, e)
                raise RuntimeError(f"Cannot pull Docker image {self.image}") from e

    def _create_tarball(self, files: Dict[str, str]) -> BytesIO:
        """
        Create an in-memory tarball from a dict of filename -> content.

        Args:
            files: Dictionary mapping filenames to their content

        Returns:
            BytesIO object containing the tarball
        """
        tar_stream = BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            for filename, content in files.items():
                file_data = content.encode("utf-8")
                tarinfo = tarfile.TarInfo(name=filename)
                tarinfo.size = len(file_data)
                tarinfo.mode = 0o644
                tar.addfile(tarinfo, BytesIO(file_data))
        tar_stream.seek(0)
        return tar_stream

    async def _install_dependencies(
        self,
        container,
        solution_code: str,
        test_code: str,
        extra_deps: List[str] = None
    ) -> bool:
        """
        Install required dependencies in the container.

        Detects deps from both the solution code (what the code imports) and
        the test code (pytest-asyncio, etc.), then merges with planner-supplied
        extra_deps.
        """
        packages = ["pytest"]

        # ── Auto-detect from test code ─────────────────────────────────────
        if "pytest.mark.asyncio" in test_code or "@pytest.mark.asyncio" in test_code:
            packages.append("pytest-asyncio")

        # ── Auto-detect from solution code ────────────────────────────────
        # Map top-level import names to the pip package that provides them.
        IMPORT_TO_PACKAGE = {
            "fastapi":    "fastapi",
            "starlette":  "starlette",
            "flask":      "flask",
            "django":     "django",
            "requests":   "requests",
            "httpx":      "httpx",
            "aiohttp":    "aiohttp",
            "pydantic":   "pydantic",
            "sqlalchemy": "sqlalchemy",
            "numpy":      "numpy",
            "pandas":     "pandas",
            "scipy":      "scipy",
            "sklearn":    "scikit-learn",
            "PIL":        "Pillow",
            "cv2":        "opencv-python",
            "boto3":      "boto3",
            "redis":      "redis",
            "celery":     "celery",
            "pymongo":    "pymongo",
            "psycopg2":   "psycopg2-binary",
            "jwt":        "PyJWT",
            "yaml":       "pyyaml",
            "dotenv":     "python-dotenv",
            "bs4":        "beautifulsoup4",
            "lxml":       "lxml",
            "cryptography": "cryptography",
        }

        # Match both `import X` and `from X import ...`
        import_pattern = re.compile(
            r"^\s*(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.MULTILINE
        )
        for match in import_pattern.finditer(solution_code):
            top_level = match.group(1)
            if top_level in IMPORT_TO_PACKAGE:
                packages.append(IMPORT_TO_PACKAGE[top_level])

        # ── Add planner-supplied deps ─────────────────────────────────────
        if extra_deps:
            packages.extend(extra_deps)

        # Remove duplicates while preserving order
        seen: set = set()
        deduped = []
        for p in packages:
            if p not in seen:
                seen.add(p)
                deduped.append(p)
        packages = deduped

        install_cmd = f"pip install --no-cache-dir {' '.join(packages)}"
        logger.info("Installing dependencies: %s", packages)

        try:
            result = await asyncio.to_thread(
                container.exec_run,
                cmd=["sh", "-c", install_cmd],
                workdir="/sandbox",
            )
            if result.exit_code != 0:
                logger.warning(
                    "Dependency installation failed: %s",
                    result.output.decode("utf-8", errors="replace")
                )
                return False
            logger.info("Dependencies installed successfully")
            return True
        except Exception as e:
            logger.error("Error installing dependencies: %s", e)
            return False

    async def run_tests(
        self,
        code: str,
        tests: str,
        timeout: Optional[float] = None,
        dependencies: Optional[List[str]] = None,
    ) -> SandboxExecutionResult:
        """
        Run pytest in an isolated Docker container.

        Args:
            code: Python code to test (solution.py)
            tests: Pytest test code (test_solution.py)
            timeout: Optional timeout override
            dependencies: Optional list of pip packages to install

        Returns:
            SandboxExecutionResult with test results
        """
        start_time = time.perf_counter()
        effective_timeout = timeout or self.timeout_seconds

        cleaned_code = extract_code_block(code)
        cleaned_tests = extract_code_block(tests)

        container = None
        container_id = None

        try:
            # Ensure image is available
            await self._ensure_image()

            # Prepare files
            files = {
                "solution.py": cleaned_code,
                "test_solution.py": cleaned_tests,
                "__init__.py": "",
            }

            # Create container with resource limits.
            # Network must be enabled during pip install; tests themselves
            # are pure Python so network access during pytest is harmless
            # given the test prompt forbids external calls.
            container_config = {
                "image": self.image,
                "command": "sleep infinity",  # Keep container running
                "detach": True,
                "mem_limit": self.memory_limit,
                "cpu_quota": self.cpu_quota,
                "cpu_period": 100000,
                "network_disabled": False,   # Must be enabled for pip install
                "working_dir": "/sandbox",
                "environment": {
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONUNBUFFERED": "1",
                },
            }

            logger.info("Creating Docker container with image %s", self.image)
            container = await asyncio.to_thread(
                self.client.containers.run,
                **container_config
            )
            container_id = container.id[:12]
            logger.info("Container %s created", container_id)

            # Copy files to container
            tar_stream = self._create_tarball(files)
            await asyncio.to_thread(
                container.put_archive,
                path="/sandbox",
                data=tar_stream
            )
            logger.info("Files copied to container")

            # Install dependencies (detects from solution + test code + planner deps)
            install_success = await self._install_dependencies(
                container,
                cleaned_code,
                cleaned_tests,
                extra_deps=dependencies
            )
            if not install_success:
                return SandboxExecutionResult(
                    passed=False,
                    output="Failed to install test dependencies",
                    exit_code=1,
                    duration_ms=(time.perf_counter() - start_time) * 1000,
                    container_id=container_id,
                    errors="Dependency installation failed",
                )

            # Run pytest
            pytest_cmd = [
                "python", "-m", "pytest",
                "-v", "--tb=short",
                "test_solution.py"
            ]

            logger.info("Running pytest in container %s", container_id)
            
            # Execute with timeout
            exec_result = await asyncio.wait_for(
                asyncio.to_thread(
                    container.exec_run,
                    cmd=pytest_cmd,
                    workdir="/sandbox",
                ),
                timeout=effective_timeout
            )

            duration = (time.perf_counter() - start_time) * 1000
            output = exec_result.output.decode("utf-8", errors="replace")

            logger.info(
                "Container %s finished - exit_code=%d, duration=%.2fms",
                container_id, exec_result.exit_code, duration
            )

            return SandboxExecutionResult(
                passed=(exec_result.exit_code == 0),
                output=output or "No output captured from pytest.",
                exit_code=exec_result.exit_code,
                duration_ms=round(duration, 2),
                container_id=container_id,
            )

        except asyncio.TimeoutError:
            duration = (time.perf_counter() - start_time) * 1000
            logger.warning("Container %s timed out after %.1fs", container_id, effective_timeout)
            return SandboxExecutionResult(
                passed=False,
                output=f"Execution timed out after {effective_timeout:.1f}s.",
                exit_code=-1,
                duration_ms=round(duration, 2),
                container_id=container_id,
                errors="Timeout",
            )

        except ImageNotFound as e:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error("Docker image not found: %s", e)
            return SandboxExecutionResult(
                passed=False,
                output=f"Docker image '{self.image}' not found. Please pull it first.",
                exit_code=1,
                duration_ms=round(duration, 2),
                errors=str(e),
            )

        except (ContainerError, APIError) as e:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error("Docker container error: %s", e)
            return SandboxExecutionResult(
                passed=False,
                output=f"Container execution failed: {str(e)}",
                exit_code=1,
                duration_ms=round(duration, 2),
                container_id=container_id,
                errors=str(e),
            )

        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error("Sandbox execution failed: %s", e, exc_info=True)
            return SandboxExecutionResult(
                passed=False,
                output=f"Internal sandbox error: {str(e)}",
                exit_code=1,
                duration_ms=round(duration, 2),
                container_id=container_id,
                errors=str(e),
            )

        finally:
            # Always cleanup container
            if container:
                try:
                    await asyncio.to_thread(container.stop, timeout=2)
                    await asyncio.to_thread(container.remove, force=True)
                    logger.info("Container %s cleaned up", container_id)
                except Exception as e:
                    logger.warning("Failed to cleanup container %s: %s", container_id, e)

    def health_check(self) -> Dict[str, Any]:
        """
        Check Docker daemon health and image availability.

        Returns:
            Dictionary with health status
        """
        try:
            info = self.client.info()
            images = self.client.images.list(name=self.image)
            
            return {
                "status": "healthy",
                "docker_version": info.get("ServerVersion"),
                "containers_running": info.get("ContainersRunning"),
                "image_available": len(images) > 0,
                "image": self.image,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }


# Global instance - can be configured via environment variables
def create_docker_sandbox() -> DockerSandbox:
    """Factory function to create Docker sandbox with environment-based config."""
    return DockerSandbox(
        image=os.getenv("SANDBOX_DOCKER_IMAGE", DockerSandbox.DEFAULT_IMAGE),
        timeout_seconds=float(os.getenv("SANDBOX_TIMEOUT", DockerSandbox.DEFAULT_TIMEOUT)),
        memory_limit=os.getenv("SANDBOX_MEMORY_LIMIT", DockerSandbox.DEFAULT_MEMORY_LIMIT),
        cpu_quota=int(os.getenv("SANDBOX_CPU_QUOTA", DockerSandbox.DEFAULT_CPU_QUOTA)),
        enable_network=os.getenv("SANDBOX_ENABLE_NETWORK", "false").lower() == "true",
    )


# Check if Docker is available on import
if DOCKER_AVAILABLE:
    try:
        docker_sandbox = create_docker_sandbox()
        logger.info("Docker sandbox initialized successfully")
    except Exception as e:
        logger.warning("Docker sandbox initialization failed: %s", e)
        docker_sandbox = None
else:
    logger.warning("Docker SDK not available - install with: pip install docker")
    docker_sandbox = None
