"""
Router for sandbox health checks and status monitoring.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import logging

from backend.sandbox.unified_runner import sandbox

logger = logging.getLogger("app.sandbox.router")

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])


class SandboxStatusResponse(BaseModel):
    """Sandbox status response model."""
    status: str
    mode: str
    active_runner: str
    subprocess_available: bool
    docker_available: bool
    docker_health: Dict[str, Any] | None = None


@router.get("/status", response_model=SandboxStatusResponse)
async def get_sandbox_status():
    """
    Get current sandbox status and health information.
    
    Returns information about:
    - Current sandbox mode (auto, docker, subprocess)
    - Active runner being used
    - Docker availability and health
    - Subprocess availability
    """
    try:
        status = sandbox.get_status()
        return SandboxStatusResponse(
            status="healthy",
            mode=status["mode"],
            active_runner=status["active_runner"],
            subprocess_available=status["subprocess_available"],
            docker_available=status["docker_available"],
            docker_health=status.get("docker_health"),
        )
    except Exception as e:
        logger.error("Failed to get sandbox status: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get sandbox status: {str(e)}"
        )


@router.get("/health")
async def sandbox_health_check():
    """
    Simple health check endpoint for monitoring.
    
    Returns 200 if sandbox is operational, 503 otherwise.
    """
    try:
        status = sandbox.get_status()
        if status["active_runner"]:
            return {
                "status": "healthy",
                "runner": status["active_runner"]
            }
        else:
            raise HTTPException(
                status_code=503,
                detail="No sandbox runner available"
            )
    except Exception as e:
        logger.error("Sandbox health check failed: %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"Sandbox unhealthy: {str(e)}"
        )
