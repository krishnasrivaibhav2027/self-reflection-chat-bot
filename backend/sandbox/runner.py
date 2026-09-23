import os
import sys
import re
import time
import asyncio
import logging
import tempfile
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List

logger = logging.getLogger("app.sandbox")


@dataclass
class SandboxExecutionResult:
    passed: bool
    output: str
    exit_code: int
    duration_ms: float


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


class SubprocessSandbox:
    """Isolated subprocess test runner for executing pytest suites against generated code.

    Uses asyncio.to_thread + blocking subprocess.run so it works on Windows
    where asyncio.create_subprocess_exec raises NotImplementedError under
    uvicorn's SelectorEventLoop.
    """

    def __init__(self, timeout_seconds: float = 30.0):
        self.timeout_seconds = timeout_seconds

    def _prepare_sanitized_env(self, work_dir: str) -> Dict[str, str]:
        """Build sandbox environment.

        Strips application secrets (DB URLs, API keys) but keeps everything
        needed for Python and third-party packages to work correctly.
        The sandbox uses sys.executable (venv Python), so venv site-packages
        are already on sys.path — we just need to avoid leaking secrets.
        """
        # Block keys that could leak credentials or affect the app
        blocked_prefixes = (
            "DATABASE_URL", "SECRET_KEY", "OPENROUTER_API_KEY", "XKIRO_API_KEY",
            "POSTGRES", "DB_", "AWS_", "AZURE_", "GOOGLE_", "OPENAI_",
        )
        env = {
            k: v for k, v in os.environ.items()
            if not any(k.upper().startswith(p) for p in blocked_prefixes)
        }
        # Ensure the sandbox temp dir is on PYTHONPATH so solution.py is importable
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{work_dir};{existing}" if existing else work_dir
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return env

    def _run_pytest_sync(
        self,
        cmd: list,
        cwd: str,
        env: Dict[str, str],
        timeout: float,
    ) -> subprocess.CompletedProcess:
        """Blocking pytest execution — called from a thread pool via asyncio.to_thread."""
        return subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=env,
            timeout=timeout,
        )

    async def run_tests(
        self,
        code: str,
        tests: str,
        timeout: Optional[float] = None,
        dependencies: Optional[List[str]] = None,
    ) -> SandboxExecutionResult:
        """Run pytest in an ephemeral directory with generated solution and test code."""
        start_time = time.perf_counter()
        effective_timeout = timeout or self.timeout_seconds

        cleaned_code = extract_code_block(code)
        cleaned_tests = extract_code_block(tests)

        with tempfile.TemporaryDirectory(prefix="sandbox_run_") as tmp_dir_str:
            tmp_path = Path(tmp_dir_str)
            (tmp_path / "solution.py").write_text(cleaned_code, encoding="utf-8")
            (tmp_path / "test_solution.py").write_text(cleaned_tests, encoding="utf-8")
            (tmp_path / "__init__.py").write_text("", encoding="utf-8")

            # Install planner-specified deps and auto-detected test deps
            await self._ensure_test_dependencies(cleaned_tests, extra_deps=dependencies)

            cmd = [
                sys.executable, "-m", "pytest",
                "-v", "--tb=short",
                "test_solution.py",
            ]
            env = self._prepare_sanitized_env(str(tmp_path))

            try:
                result = await asyncio.to_thread(
                    self._run_pytest_sync,
                    cmd, str(tmp_path), env, effective_timeout,
                )

                duration = (time.perf_counter() - start_time) * 1000
                stdout_str = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
                stderr_str = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
                combined = (stdout_str + ("\n" + stderr_str if stderr_str else "")).strip()

                return SandboxExecutionResult(
                    passed=(result.returncode == 0),
                    output=combined or "No output captured from pytest.",
                    exit_code=result.returncode,
                    duration_ms=round(duration, 2),
                )

            except subprocess.TimeoutExpired:
                duration = (time.perf_counter() - start_time) * 1000
                return SandboxExecutionResult(
                    passed=False,
                    output=f"Execution timed out after {effective_timeout:.1f}s.",
                    exit_code=-1,
                    duration_ms=round(duration, 2),
                )
            except Exception as e:
                duration = (time.perf_counter() - start_time) * 1000
                logger.error("Sandbox execution failed: %s", e, exc_info=True)
                return SandboxExecutionResult(
                    passed=False,
                    output=f"Internal sandbox error: {str(e)}",
                    exit_code=1,
                    duration_ms=round(duration, 2),
                )

    async def _ensure_test_dependencies(
        self, test_code: str, extra_deps: Optional[List[str]] = None
    ) -> None:
        """Auto-install missing test-related packages if detected in test code."""
        to_install = []

        # Detect pytest-asyncio usage
        if "pytest.mark.asyncio" in test_code or "@pytest.mark.asyncio" in test_code:
            try:
                import pytest_asyncio  # noqa
            except ImportError:
                to_install.append("pytest-asyncio")

        # Add planner-specified dependencies
        if extra_deps:
            to_install.extend(extra_deps)

        if not to_install:
            return

        logger.info("Auto-installing missing test deps: %s", to_install)
        cmd = [sys.executable, "-m", "pip", "install", "--quiet"] + to_install
        try:
            await asyncio.to_thread(
                subprocess.run,
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
                check=True,
            )
            logger.info("Successfully installed: %s", to_install)
        except Exception as e:
            logger.warning("Failed to auto-install test deps %s: %s", to_install, e)


# Global default instance
sandbox_runner = SubprocessSandbox()
