# Docker Sandbox Integration Guide

This guide explains how to set up and use Docker-based sandbox for secure, isolated test execution.

## Overview

The sandbox system supports two execution modes:
1. **Docker Sandbox** - Isolated containers with resource limits (recommended for production)
2. **Subprocess Sandbox** - Local process execution (development fallback)

The system automatically selects the best available runner or can be configured to force a specific mode.

## Features

### Docker Sandbox
- ✅ Complete isolation from host system
- ✅ Resource limits (CPU, memory)
- ✅ Network isolation
- ✅ Automatic cleanup
- ✅ Support for custom Python images
- ✅ Pre-installed test dependencies
- ✅ Secure execution with non-root user

### Subprocess Sandbox
- ✅ Fast startup (no container overhead)
- ✅ Direct access to venv packages
- ✅ Works on all platforms
- ✅ Good for development

## Installation

### 1. Desktop Requirements

Install **Docker Desktop** on your Windows machine:
- Download from: https://www.docker.com/products/docker-desktop/
- Requires Windows 10/11 64-bit: Pro, Enterprise, or Education (Build 19044 or higher)
- Or Windows 10/11 Home with WSL 2
- Ensure Docker Desktop is running after installation

### 2. Python Dependencies

Install Docker SDK in your virtual environment:

```bash
# Activate your venv first
cd d:\GitRepos\CodeCompletion
.\venv\Scripts\activate

# Install Docker SDK
pip install docker==7.1.0

# Or install from requirements file
pip install -r backend\requirements-docker.txt
```

### 3. Verify Installation

Check if Docker is properly installed and running:

```bash
docker --version
docker ps
```

You should see Docker version info and a list of running containers (may be empty).

### 4. Pull Base Image

Pull the Python image used by the sandbox:

```bash
docker pull python:3.11-slim
```

This may take a few minutes on first run.

## Configuration

Configure the sandbox via environment variables in `backend/.env`:

```env
# Sandbox Configuration
SANDBOX_MODE=auto                          # auto, docker, or subprocess
SANDBOX_TIMEOUT=30                         # Timeout in seconds
SANDBOX_DOCKER_IMAGE=python:3.11-slim      # Docker image to use
SANDBOX_MEMORY_LIMIT=512m                  # Memory limit (512m, 1g, etc.)
SANDBOX_CPU_QUOTA=100000                   # CPU quota (100000 = 1 core)
SANDBOX_ENABLE_NETWORK=false               # Allow network access in containers
```

### Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `SANDBOX_MODE` | `auto` | Execution mode: `auto`, `docker`, or `subprocess` |
| `SANDBOX_TIMEOUT` | `30` | Maximum execution time in seconds |
| `SANDBOX_DOCKER_IMAGE` | `python:3.11-slim` | Docker image for containers |
| `SANDBOX_MEMORY_LIMIT` | `512m` | Container memory limit |
| `SANDBOX_CPU_QUOTA` | `100000` | CPU quota (100000 = 1 CPU core) |
| `SANDBOX_ENABLE_NETWORK` | `false` | Enable network access in containers |

### Modes Explained

- **auto** (default): Automatically use Docker if available, fallback to subprocess
- **docker**: Force Docker execution (fails if Docker not available)
- **subprocess**: Force subprocess execution (ignores Docker even if available)

## Usage

### Basic Usage

The sandbox is automatically used by the chatbot workflow:

```python
from backend.sandbox.unified_runner import sandbox

# Run tests (automatically selects best runner)
result = await sandbox.run_tests(
    code="def add(a, b): return a + b",
    tests="from solution import add\ndef test_add(): assert add(2, 3) == 5"
)

print(f"Tests passed: {result.passed}")
print(f"Output: {result.output}")
```

### Direct Docker Usage

Force Docker sandbox usage:

```python
from backend.sandbox.docker_runner import DockerSandbox

sandbox = DockerSandbox(
    image="python:3.11-slim",
    timeout_seconds=30.0,
    memory_limit="512m",
    enable_network=False,
)

result = await sandbox.run_tests(code, tests)
```

### Health Check

Check sandbox status via API:

```bash
# Get detailed status
curl http://localhost:8000/api/sandbox/status

# Simple health check
curl http://localhost:8000/api/sandbox/health
```

Response example:
```json
{
  "status": "healthy",
  "mode": "auto",
  "active_runner": "docker",
  "subprocess_available": true,
  "docker_available": true,
  "docker_health": {
    "status": "healthy",
    "docker_version": "24.0.7",
    "containers_running": 0,
    "image_available": true,
    "image": "python:3.11-slim"
  }
}
```

## Testing

### Run Sandbox Tests

Test the subprocess sandbox:
```bash
pytest backend/sandbox/test_sandbox.py -v
```

Test the Docker sandbox (requires Docker running):
```bash
pytest backend/sandbox/test_docker_sandbox.py -v
```

Run all tests:
```bash
pytest backend/sandbox/ -v
```

### Manual Testing

Create a test script:

```python
# test_manual.py
import asyncio
from backend.sandbox.unified_runner import sandbox

async def main():
    code = """
def fibonacci(n: int) -> int:
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
"""
    
    tests = """
from solution import fibonacci

def test_fibonacci():
    assert fibonacci(0) == 0
    assert fibonacci(1) == 1
    assert fibonacci(5) == 5
    assert fibonacci(10) == 55
"""
    
    result = await sandbox.run_tests(code, tests)
    print(f"Passed: {result.passed}")
    print(f"Duration: {result.duration_ms}ms")
    print(f"Output:\n{result.output}")
    
    status = sandbox.get_status()
    print(f"\nStatus: {status}")

if __name__ == "__main__":
    asyncio.run(main())
```

Run it:
```bash
python test_manual.py
```

## Custom Docker Image

For faster execution, build a custom image with pre-installed dependencies:

```bash
# Build custom image
cd backend/sandbox
docker build -t codecompletion-sandbox:latest .

# Update .env to use custom image
SANDBOX_DOCKER_IMAGE=codecompletion-sandbox:latest
```

The custom image includes:
- pytest and pytest-asyncio
- Common packages (requests, aiohttp, numpy, pandas)
- Non-root user for security

## Troubleshooting

### Docker Not Starting

**Problem**: `Cannot connect to Docker daemon`

**Solutions**:
1. Ensure Docker Desktop is running (check system tray)
2. Restart Docker Desktop
3. Check Windows services: Docker Desktop Service should be running

### Permission Errors

**Problem**: `Permission denied` when accessing Docker

**Solutions**:
1. Run Docker Desktop as administrator
2. Add your user to docker-users group (Windows)
3. Restart your computer after adding to group

### Image Pull Fails

**Problem**: `Failed to pull image`

**Solutions**:
1. Check internet connection
2. Try: `docker pull python:3.11-slim` manually
3. Use different image: `SANDBOX_DOCKER_IMAGE=python:3.10-slim`

### Containers Not Cleaning Up

**Problem**: Old containers accumulating

**Solutions**:
```bash
# List all containers
docker ps -a

# Remove all stopped containers
docker container prune -f

# Force remove specific container
docker rm -f <container_id>
```

### Memory Limit Errors

**Problem**: Container crashes due to memory limit

**Solutions**:
1. Increase memory limit: `SANDBOX_MEMORY_LIMIT=1g`
2. Check Docker Desktop resource limits (Settings → Resources)

### Timeout Issues

**Problem**: Tests timing out

**Solutions**:
1. Increase timeout: `SANDBOX_TIMEOUT=60`
2. Optimize test code
3. Check if infinite loops in code

### Subprocess Fallback

**Problem**: Always using subprocess instead of Docker

**Solutions**:
1. Check Docker is running: `docker ps`
2. Check logs for Docker initialization errors
3. Verify `SANDBOX_MODE=auto` in .env
4. Test Docker manually: `docker run hello-world`

## Security Considerations

### Docker Sandbox Security

✅ **Provided protections**:
- Isolated from host filesystem
- Network disabled by default
- Resource limits (CPU, memory)
- Non-root user execution
- Automatic cleanup

⚠️ **Important notes**:
- Do not enable network unless necessary
- Keep resource limits reasonable
- Regularly update Docker images
- Monitor container resource usage

### Subprocess Sandbox Security

⚠️ **Limitations**:
- Shares host filesystem (limited isolation)
- Can access venv packages
- No resource limits
- Not recommended for untrusted code

✅ **Best for**:
- Development and testing
- Trusted code execution
- When Docker unavailable

## Performance

### Startup Times

| Runner | First Run | Subsequent Runs |
|--------|-----------|-----------------|
| Docker | 2-5s | 1-3s |
| Subprocess | 0.1-0.5s | 0.1-0.5s |

### Resource Usage

Docker containers are limited to:
- **Memory**: 512MB (configurable)
- **CPU**: 1 core (configurable)
- **Network**: Disabled (configurable)

### Optimization Tips

1. **Use custom image** with pre-installed dependencies
2. **Keep memory limits** reasonable (512m-1g)
3. **Set appropriate timeout** based on expected test duration
4. **Monitor Docker resources** in Docker Desktop

## Advanced Configuration

### Multiple Python Versions

Run tests with different Python versions:

```python
# Test with Python 3.9
sandbox_39 = DockerSandbox(image="python:3.9-slim")
result = await sandbox_39.run_tests(code, tests)

# Test with Python 3.11
sandbox_311 = DockerSandbox(image="python:3.11-slim")
result = await sandbox_311.run_tests(code, tests)
```

### Custom Resource Limits

```python
sandbox = DockerSandbox(
    memory_limit="1g",      # 1 GB RAM
    cpu_quota=200000,       # 2 CPU cores
    timeout_seconds=60.0,   # 1 minute timeout
)
```

### Enable Network Access

For tests that need network:

```python
sandbox = DockerSandbox(enable_network=True)
```

Or via environment:
```env
SANDBOX_ENABLE_NETWORK=true
```

## API Reference

### SandboxExecutionResult

```python
@dataclass
class SandboxExecutionResult:
    passed: bool              # Whether all tests passed
    output: str              # Combined stdout/stderr from pytest
    exit_code: int           # Process exit code (0 = success)
    duration_ms: float       # Execution duration in milliseconds
    container_id: Optional[str]  # Docker container ID (if Docker)
    errors: Optional[str]    # Error messages (if any)
```

### UnifiedSandbox Methods

```python
class UnifiedSandbox:
    async def run_tests(
        code: str,           # Python code to test
        tests: str,          # Pytest test code
        timeout: Optional[float] = None  # Optional timeout override
    ) -> SandboxExecutionResult
    
    def get_status() -> dict  # Get sandbox status
```

## Monitoring

### Logs

Sandbox logs are available in application logs:

```python
import logging
logging.getLogger("app.sandbox").setLevel(logging.INFO)
```

### Metrics to Monitor

- Test execution duration
- Success/failure rate
- Container cleanup status
- Docker daemon health
- Resource usage

## Support

For issues or questions:
1. Check this README
2. Review logs in application console
3. Test Docker manually: `docker run hello-world`
4. Check Docker Desktop status and logs
