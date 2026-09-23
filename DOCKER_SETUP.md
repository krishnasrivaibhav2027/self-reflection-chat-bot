# Docker Sandbox Setup Guide

Complete guide to integrate Docker-based sandbox for secure test execution.

## 📋 Prerequisites

- Windows 10/11 64-bit: Pro, Enterprise, or Education (Build 19044+) OR Windows Home with WSL 2
- Python 3.8+ (already installed in your venv)
- Administrator access for Docker installation

## 🚀 Quick Start

### Step 1: Install Docker Desktop

1. **Download Docker Desktop**
   - Visit: https://www.docker.com/products/docker-desktop/
   - Click "Download for Windows"

2. **Install Docker Desktop**
   - Run the installer (Docker Desktop Installer.exe)
   - Follow the installation wizard
   - Enable WSL 2 if prompted
   - Restart your computer when prompted

3. **Start Docker Desktop**
   - Launch Docker Desktop from Start menu
   - Wait for Docker to start (whale icon in system tray should be steady)
   - You may need to accept the service agreement on first launch

4. **Verify Installation**
   ```bash
   docker --version
   docker ps
   ```
   You should see Docker version info and an empty container list.

### Step 2: Install Python Dependencies

1. **Activate your virtual environment**
   ```bash
   cd d:\GitRepos\CodeCompletion
   .\venv\Scripts\activate
   ```

2. **Install Docker SDK**
   ```bash
   pip install docker==7.1.0
   ```
   
   Or install all dependencies:
   ```bash
   pip install -r backend\requirements-docker.txt
   ```

### Step 3: Pull Docker Image

Pull the Python image used for test execution:

```bash
docker pull python:3.11-slim
```

This downloads a lightweight Python 3.11 image (~200MB, takes 2-5 minutes depending on your internet speed).

### Step 4: Verify Setup

Run the automated setup verification:

```bash
python backend\sandbox\setup_check.py
```

This script checks:
- ✅ Python version
- ✅ Docker SDK installation
- ✅ Docker daemon status
- ✅ Docker image availability
- ✅ Pytest installation
- ✅ Docker sandbox functionality
- ✅ Unified sandbox functionality

**Expected output:**
```
==============================================================
DOCKER SANDBOX SETUP VERIFICATION
==============================================================

1. Checking Python Version
✅ Python version is compatible (>= 3.8)

2. Checking Docker SDK for Python
✅ Docker SDK is installed (version: 7.1.0)

3. Checking Docker Daemon
✅ Docker is installed: Docker version 24.0.7, build ...
✅ Docker daemon is running

4. Checking Docker Image
✅ Image 'python:3.11-slim' is available

5. Checking Pytest
✅ pytest is installed (version: 8.0.0)

6. Testing Docker Sandbox
✅ Docker sandbox test passed
   Duration: 2543ms
   Container ID: a1b2c3d4e5f6

7. Testing Unified Sandbox
✅ Unified sandbox test passed
   Duration: 2312ms

==============================================================
SUMMARY
==============================================================
Python Version            ✅ PASS
Docker SDK                ✅ PASS
Docker Daemon             ✅ PASS
Docker Image              ✅ PASS
Pytest                    ✅ PASS
Docker Sandbox Test       ✅ PASS
Unified Sandbox Test      ✅ PASS

Success Rate: 100%

🎉 All checks passed! Docker sandbox is ready to use.
```

### Step 5: Configure Environment

Your `.env` file has been updated with default sandbox configuration:

```env
# Sandbox Configuration
SANDBOX_MODE=auto                    # auto, docker, or subprocess
SANDBOX_TIMEOUT=30                   # Timeout in seconds
SANDBOX_DOCKER_IMAGE=python:3.11-slim
SANDBOX_MEMORY_LIMIT=512m
SANDBOX_CPU_QUOTA=100000
SANDBOX_ENABLE_NETWORK=false
```

You can adjust these values as needed (see Configuration section below).

### Step 6: Start Your Application

```bash
uvicorn backend.main:app --reload
```

### Step 7: Verify Sandbox Status

Check sandbox health via API:

```bash
# Using curl
curl http://localhost:8000/api/sandbox/status

# Using PowerShell
Invoke-WebRequest -Uri http://localhost:8000/api/sandbox/status
```

Or visit in browser: http://localhost:8000/api/sandbox/status

**Expected response:**
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

## ⚙️ Configuration

### Sandbox Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `auto` | Automatically selects Docker if available, fallback to subprocess | **Recommended** - Best of both worlds |
| `docker` | Forces Docker execution | Production - Maximum isolation |
| `subprocess` | Forces subprocess execution | Development - Fastest startup |

### Resource Limits

Configure container resource limits in `.env`:

```env
# Memory limits (examples)
SANDBOX_MEMORY_LIMIT=256m   # Light workloads
SANDBOX_MEMORY_LIMIT=512m   # Default
SANDBOX_MEMORY_LIMIT=1g     # Heavy workloads
SANDBOX_MEMORY_LIMIT=2g     # Very heavy workloads

# CPU limits (100000 = 1 core)
SANDBOX_CPU_QUOTA=50000     # 0.5 cores
SANDBOX_CPU_QUOTA=100000    # 1 core (default)
SANDBOX_CPU_QUOTA=200000    # 2 cores

# Execution timeout
SANDBOX_TIMEOUT=15          # Quick tests
SANDBOX_TIMEOUT=30          # Default
SANDBOX_TIMEOUT=60          # Complex tests
SANDBOX_TIMEOUT=120         # Very complex tests
```

### Network Access

By default, containers have **no network access** for security. Enable if needed:

```env
SANDBOX_ENABLE_NETWORK=true
```

⚠️ **Warning**: Only enable network if tests require external API calls or downloads.

## 🧪 Testing

### Run Sandbox Tests

```bash
# Test subprocess sandbox
pytest backend\sandbox\test_sandbox.py -v

# Test Docker sandbox
pytest backend\sandbox\test_docker_sandbox.py -v

# Run all sandbox tests
pytest backend\sandbox\ -v
```

### Manual Test

Create a test file `test_manual.py`:

```python
import asyncio
from backend.sandbox.unified_runner import sandbox

async def main():
    code = """
def factorial(n: int) -> int:
    if n <= 1:
        return 1
    return n * factorial(n - 1)
"""
    
    tests = """
from solution import factorial

def test_factorial():
    assert factorial(0) == 1
    assert factorial(5) == 120
    assert factorial(10) == 3628800
"""
    
    print("Running tests...")
    result = await sandbox.run_tests(code, tests)
    
    print(f"Tests passed: {result.passed}")
    print(f"Duration: {result.duration_ms}ms")
    print(f"Output:\n{result.output}")

asyncio.run(main())
```

Run it:
```bash
python test_manual.py
```

## 🔧 Troubleshooting

### Docker Desktop Not Starting

**Symptoms:**
- Docker Desktop stuck at "Starting..."
- Error: "Docker Desktop is not running"

**Solutions:**
1. **Check WSL 2**:
   ```bash
   wsl --status
   wsl --update
   ```

2. **Restart Docker Service**:
   - Open Services (Win + R, type `services.msc`)
   - Find "Docker Desktop Service"
   - Right-click → Restart

3. **Reset Docker Desktop**:
   - Docker Desktop → Troubleshoot → Reset to factory defaults

4. **Check Hyper-V** (Windows Pro/Enterprise):
   - Control Panel → Programs → Turn Windows features on/off
   - Enable "Hyper-V" and "Containers"
   - Restart computer

### Cannot Connect to Docker Daemon

**Symptoms:**
```
docker.errors.DockerException: Error while fetching server API version
```

**Solutions:**
1. Ensure Docker Desktop is running (check system tray)
2. Restart Docker Desktop
3. Run setup check: `python backend\sandbox\setup_check.py`

### Permission Denied

**Symptoms:**
```
docker: permission denied while trying to connect to the Docker daemon
```

**Solutions:**
1. Run Docker Desktop as administrator
2. Add your user to docker-users group:
   - Computer Management → Local Users and Groups → Groups
   - Double-click "docker-users"
   - Add your user
   - Restart computer

### Image Pull Fails

**Symptoms:**
```
Error response from daemon: Get https://registry-1.docker.io/v2/: net/http: timeout
```

**Solutions:**
1. Check internet connection
2. Configure Docker proxy (if behind corporate firewall):
   - Docker Desktop → Settings → Resources → Proxies
3. Try alternative image:
   ```env
   SANDBOX_DOCKER_IMAGE=python:3.10-slim
   ```

### Tests Always Use Subprocess

**Symptoms:**
- API shows `"active_runner": "subprocess"`
- Docker tests are skipped

**Solutions:**
1. Ensure Docker is running: `docker ps`
2. Check Docker SDK: `pip install docker`
3. Verify Docker health: `python backend\sandbox\setup_check.py`
4. Check logs for Docker initialization errors

### Container Cleanup Issues

**Symptoms:**
- Many stopped containers accumulating
- Disk space running low

**Solutions:**
```bash
# List all containers
docker ps -a

# Remove all stopped containers
docker container prune -f

# Remove all unused images
docker image prune -a -f

# Full cleanup
docker system prune -a -f
```

### Timeout Errors

**Symptoms:**
```
Execution timed out after 30.0s
```

**Solutions:**
1. Increase timeout:
   ```env
   SANDBOX_TIMEOUT=60
   ```
2. Check for infinite loops in test code
3. Optimize test complexity

### Memory Limit Errors

**Symptoms:**
```
Container killed due to memory limit
```

**Solutions:**
1. Increase memory limit:
   ```env
   SANDBOX_MEMORY_LIMIT=1g
   ```
2. Check Docker Desktop resources:
   - Settings → Resources → Advanced
   - Increase Memory allocation

## 🎯 Advanced Usage

### Custom Docker Image

Build an optimized image with pre-installed dependencies:

```bash
cd backend\sandbox
docker build -t codecompletion-sandbox:latest .
```

Update `.env`:
```env
SANDBOX_DOCKER_IMAGE=codecompletion-sandbox:latest
```

**Benefits:**
- Faster container startup
- Pre-installed common packages (pytest, numpy, pandas, etc.)
- Security hardened with non-root user

### Multiple Python Versions

Test code with different Python versions:

```python
from backend.sandbox.docker_runner import DockerSandbox

# Test with Python 3.9
sandbox_39 = DockerSandbox(image="python:3.9-slim")
result = await sandbox_39.run_tests(code, tests)

# Test with Python 3.11
sandbox_311 = DockerSandbox(image="python:3.11-slim")
result = await sandbox_311.run_tests(code, tests)

# Test with Python 3.12
sandbox_312 = DockerSandbox(image="python:3.12-slim")
result = await sandbox_312.run_tests(code, tests)
```

### Monitoring

Monitor sandbox performance:

```python
import logging

# Enable debug logging
logging.getLogger("app.sandbox").setLevel(logging.DEBUG)
```

Check Docker stats:
```bash
# Monitor container resource usage
docker stats

# View Docker events
docker events
```

## 📊 Performance Comparison

| Metric | Docker Sandbox | Subprocess Sandbox |
|--------|----------------|-------------------|
| Startup Time | 1-3s | 0.1-0.5s |
| Security | Excellent | Moderate |
| Isolation | Complete | Limited |
| Resource Control | Yes | No |
| Network Isolation | Yes | No |
| Production Ready | Yes | No |

## 🔒 Security Best Practices

1. **Keep network disabled** unless absolutely necessary
2. **Set reasonable resource limits** to prevent DoS
3. **Update Docker images** regularly:
   ```bash
   docker pull python:3.11-slim
   ```
4. **Monitor container activity**:
   ```bash
   docker ps
   docker logs <container_id>
   ```
5. **Use custom image** with security hardening
6. **Never run Docker as root** on host
7. **Limit timeout** to prevent resource exhaustion

## 📚 Additional Resources

- [Docker Desktop Documentation](https://docs.docker.com/desktop/windows/)
- [Docker Python SDK](https://docker-py.readthedocs.io/)
- [WSL 2 Setup Guide](https://docs.microsoft.com/en-us/windows/wsl/install)
- [Sandbox README](backend/sandbox/README.md)

## 🆘 Getting Help

If you encounter issues:

1. **Run setup verification**:
   ```bash
   python backend\sandbox\setup_check.py
   ```

2. **Check Docker status**:
   ```bash
   docker --version
   docker ps
   docker info
   ```

3. **View application logs**:
   - Check console output when running uvicorn
   - Look for "app.sandbox" logger messages

4. **Test Docker manually**:
   ```bash
   docker run hello-world
   docker run python:3.11-slim python --version
   ```

5. **Check sandbox API**:
   ```bash
   curl http://localhost:8000/api/sandbox/health
   ```

## ✅ Checklist

Before deploying to production:

- [ ] Docker Desktop installed and running
- [ ] Docker SDK installed: `pip install docker`
- [ ] Base image pulled: `docker pull python:3.11-slim`
- [ ] Setup verification passes: `python backend\sandbox\setup_check.py`
- [ ] All tests pass: `pytest backend\sandbox\ -v`
- [ ] Sandbox status API works: `http://localhost:8000/api/sandbox/status`
- [ ] Resource limits configured appropriately
- [ ] Network access disabled (unless required)
- [ ] Timeout configured for expected workload
- [ ] Monitoring and logging enabled
- [ ] Docker containers cleaned up regularly

## 🎉 Success!

Once all checks pass, your Docker sandbox is ready! The chatbot will now:

1. **Automatically use Docker** for test execution when available
2. **Fallback to subprocess** if Docker is unavailable
3. **Provide complete isolation** for untrusted code
4. **Enforce resource limits** to prevent abuse
5. **Clean up automatically** after each test run

Your application is now ready for secure code execution! 🚀
