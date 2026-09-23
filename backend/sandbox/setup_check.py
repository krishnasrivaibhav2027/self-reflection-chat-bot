"""
Setup verification script for Docker sandbox integration.

Run this script to verify your Docker sandbox setup:
    python backend/sandbox/setup_check.py
"""

import sys
import subprocess
import asyncio


def check_python_version():
    """Check Python version."""
    print("=" * 60)
    print("1. Checking Python Version")
    print("=" * 60)
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")
    if version.major >= 3 and version.minor >= 8:
        print("✅ Python version is compatible (>= 3.8)")
        return True
    else:
        print("❌ Python version too old. Need Python 3.8 or higher")
        return False


def check_docker_sdk():
    """Check if Docker SDK is installed."""
    print("\n" + "=" * 60)
    print("2. Checking Docker SDK for Python")
    print("=" * 60)
    try:
        import docker
        print(f"✅ Docker SDK is installed (version: {docker.__version__})")
        return True
    except ImportError:
        print("❌ Docker SDK not installed")
        print("   Install with: pip install docker")
        return False


def check_docker_daemon():
    """Check if Docker daemon is running."""
    print("\n" + "=" * 60)
    print("3. Checking Docker Daemon")
    print("=" * 60)
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print(f"✅ Docker is installed: {result.stdout.strip()}")
        else:
            print("❌ Docker command failed")
            return False

        # Check if daemon is running
        result = subprocess.run(
            ["docker", "ps"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("✅ Docker daemon is running")
            return True
        else:
            print("❌ Docker daemon is not running")
            print("   Start Docker Desktop and try again")
            return False

    except FileNotFoundError:
        print("❌ Docker is not installed")
        print("   Download from: https://www.docker.com/products/docker-desktop/")
        return False
    except subprocess.TimeoutExpired:
        print("❌ Docker command timed out")
        print("   Docker Desktop may be starting. Wait and try again.")
        return False
    except Exception as e:
        print(f"❌ Error checking Docker: {e}")
        return False


def check_docker_image():
    """Check if sandbox Docker image is available."""
    print("\n" + "=" * 60)
    print("4. Checking Docker Image")
    print("=" * 60)
    try:
        import docker
        client = docker.from_env()
        
        image_name = "codecompletion-sandbox:latest"
        images = client.images.list(name=image_name)
        
        if images:
            print(f"✅ Image '{image_name}' is available")
            return True
        else:
            print(f"⚠️  Image '{image_name}' not found locally")
            print(f"   Build it from the sandbox Dockerfile:")
            print(f"   docker build -t {image_name} backend/sandbox/")
            return False
                
    except Exception as e:
        print(f"❌ Error checking Docker image: {e}")
        return False


def check_pytest():
    """Check if pytest is installed."""
    print("\n" + "=" * 60)
    print("5. Checking Pytest")
    print("=" * 60)
    try:
        import pytest
        print(f"✅ pytest is installed (version: {pytest.__version__})")
        return True
    except ImportError:
        print("❌ pytest not installed")
        print("   Install with: pip install pytest")
        return False


async def test_docker_sandbox():
    """Test Docker sandbox execution."""
    print("\n" + "=" * 60)
    print("6. Testing Docker Sandbox")
    print("=" * 60)
    try:
        # Add parent directory to path for imports
        import sys
        import os
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
        
        from backend.sandbox.docker_runner import DockerSandbox, DOCKER_AVAILABLE
        
        if not DOCKER_AVAILABLE:
            print("❌ Docker SDK not available")
            return False
        
        sandbox = DockerSandbox(timeout_seconds=10.0)
        
        code = """
def add(a: int, b: int) -> int:
    return a + b
"""
        
        tests = """
from solution import add

def test_add():
    assert add(2, 3) == 5
    assert add(0, 0) == 0
"""
        
        print("Running test execution in Docker container...")
        result = await sandbox.run_tests(code, tests)
        
        if result.passed:
            print(f"✅ Docker sandbox test passed")
            print(f"   Duration: {result.duration_ms:.0f}ms")
            print(f"   Container ID: {result.container_id}")
            return True
        else:
            print(f"❌ Docker sandbox test failed")
            print(f"   Output: {result.output}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing Docker sandbox: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_unified_sandbox():
    """Test unified sandbox."""
    print("\n" + "=" * 60)
    print("7. Testing Unified Sandbox")
    print("=" * 60)
    try:
        # Add parent directory to path for imports
        import sys
        import os
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
        
        from backend.sandbox.unified_runner import sandbox
        
        status = sandbox.get_status()
        print(f"Sandbox mode: {status['mode']}")
        print(f"Active runner: {status['active_runner']}")
        print(f"Docker available: {status['docker_available']}")
        print(f"Subprocess available: {status['subprocess_available']}")
        
        code = """
def multiply(a: int, b: int) -> int:
    return a * b
"""
        
        tests = """
from solution import multiply

def test_multiply():
    assert multiply(2, 3) == 6
    assert multiply(0, 5) == 0
"""
        
        print(f"\nRunning test with {status['active_runner']} runner...")
        result = await sandbox.run_tests(code, tests)
        
        if result.passed:
            print(f"✅ Unified sandbox test passed")
            print(f"   Duration: {result.duration_ms:.0f}ms")
            return True
        else:
            print(f"❌ Unified sandbox test failed")
            print(f"   Output: {result.output}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing unified sandbox: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main setup check routine."""
    print("\n" + "=" * 60)
    print("DOCKER SANDBOX SETUP VERIFICATION")
    print("=" * 60)
    
    results = []
    
    # Check Python version
    results.append(check_python_version())
    
    # Check Docker SDK
    results.append(check_docker_sdk())
    
    # Check Docker daemon
    docker_ok = check_docker_daemon()
    results.append(docker_ok)
    
    # Check Docker image (only if Docker is OK)
    if docker_ok:
        results.append(check_docker_image())
    else:
        results.append(False)
    
    # Check pytest
    results.append(check_pytest())
    
    # Test Docker sandbox (only if everything else is OK)
    if all(results):
        results.append(await test_docker_sandbox())
        results.append(await test_unified_sandbox())
    else:
        print("\n⚠️  Skipping sandbox tests due to previous failures")
        results.append(False)
        results.append(False)
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    checks = [
        "Python Version",
        "Docker SDK",
        "Docker Daemon",
        "Docker Image",
        "Pytest",
        "Docker Sandbox Test",
        "Unified Sandbox Test",
    ]
    
    for check, result in zip(checks, results):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{check:25} {status}")
    
    success_rate = sum(results) / len(results) * 100
    print(f"\nSuccess Rate: {success_rate:.0f}%")
    
    if all(results):
        print("\n🎉 All checks passed! Docker sandbox is ready to use.")
        print("\nNext steps:")
        print("1. Update backend/.env with desired sandbox configuration")
        print("2. Run your application: uvicorn backend.main:app --reload")
        print("3. Check sandbox status: http://localhost:8000/api/sandbox/status")
        return 0
    else:
        print("\n⚠️  Some checks failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("- Install Docker: pip install docker")
        print("- Start Docker Desktop")
        print("- Build sandbox image: docker build -t codecompletion-sandbox:latest backend/sandbox/")
        print("- Install pytest: pip install pytest")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
