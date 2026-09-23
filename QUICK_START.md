# Docker Sandbox - Quick Start Guide

## 🎯 What You Need to Install

### 1. Docker Desktop (Windows Application)
**Download:** https://www.docker.com/products/docker-desktop/

**Install Steps:**
1. Download Docker Desktop installer
2. Run installer as administrator
3. Follow installation wizard
4. Restart computer when prompted
5. Launch Docker Desktop from Start menu
6. Wait for Docker to start (whale icon in system tray)

**Verify:**
```bash
docker --version
docker ps
```

### 2. Docker Python SDK (Python Package)
```bash
# Activate venv
cd d:\GitRepos\CodeCompletion
.\venv\Scripts\activate

# Install Docker SDK
pip install docker==7.1.0
```

### 3. Docker Image (Pull from Docker Hub)
```bash
docker pull python:3.11-slim
```
(Takes 2-5 minutes, ~200MB download)

## ✅ Verify Everything Works

Run the automated verification:
```bash
python backend\sandbox\setup_check.py
```

**Expected:** All checks should show ✅ PASS

## 🚀 Start Your Application

```bash
uvicorn backend.main:app --reload
```

## 🔍 Check Sandbox Status

**Browser:** http://localhost:8000/api/sandbox/status

**PowerShell:**
```powershell
Invoke-WebRequest -Uri http://localhost:8000/api/sandbox/status
```

**Expected Response:**
```json
{
  "status": "healthy",
  "active_runner": "docker",
  "docker_available": true
}
```

## ⚙️ Configuration (Optional)

Edit `backend\.env`:

```env
# Execution mode: auto (recommended), docker, or subprocess
SANDBOX_MODE=auto

# Timeout in seconds
SANDBOX_TIMEOUT=30

# Resource limits
SANDBOX_MEMORY_LIMIT=512m
SANDBOX_CPU_QUOTA=100000

# Security
SANDBOX_ENABLE_NETWORK=false
```

## 🧪 Run Tests

```bash
# Test Docker sandbox
pytest backend\sandbox\test_docker_sandbox.py -v

# Test all
pytest backend\sandbox\ -v
```

## 🆘 Common Issues

### Docker Not Running
**Fix:** Start Docker Desktop from Start menu, wait for it to fully start

### "Cannot connect to Docker daemon"
**Fix:** 
1. Restart Docker Desktop
2. Run as administrator
3. Check Docker Desktop settings

### "Image not found"
**Fix:** 
```bash
docker pull python:3.11-slim
```

### Using Subprocess Instead of Docker
**Fix:**
1. Verify Docker is running: `docker ps`
2. Check: `python backend\sandbox\setup_check.py`
3. Review logs for errors

## 📚 Full Documentation

- **Complete Setup Guide:** `DOCKER_SETUP.md`
- **Technical Details:** `backend/sandbox/README.md`
- **Integration Overview:** `INTEGRATION_SUMMARY.md`

## ✨ That's It!

Once Docker Desktop is running and you've installed the Python package, everything works automatically. The system will:
- ✅ Use Docker for secure isolation
- ✅ Fallback to subprocess if Docker unavailable
- ✅ Enforce resource limits
- ✅ Clean up automatically

Your chatbot is now production-ready with secure code execution! 🎉
