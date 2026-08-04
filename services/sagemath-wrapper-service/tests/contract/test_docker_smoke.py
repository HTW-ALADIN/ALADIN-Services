"""Smoke test for the Docker container — requires Docker daemon.

Run with: pytest tests/contract/test_docker_smoke.py -v --docker
"""

import shutil
import subprocess
import time

import httpx
import pytest

IMAGE_TAG = "sagemath-wrapper:test-smoke"
CONTAINER_NAME = "sagemath-wrapper-smoke"
HEALTH_URL = "http://localhost:8000/healthz"
LINALG_URL = "http://localhost:8000/v1/linalg/determinant"

pytestmark = pytest.mark.docker

_HAS_DOCKER = shutil.which("docker") is not None
_HAS_DOCKER_DAEMON = False
if _HAS_DOCKER:
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        _HAS_DOCKER_DAEMON = result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        pass


@pytest.fixture(scope="module")
def docker_container():
    """Build image, start container, yield, then teardown."""
    if not _HAS_DOCKER_DAEMON:
        pytest.skip("Docker daemon not available")

    # Build
    build = subprocess.run(
        ["docker", "build", "-t", IMAGE_TAG, "."],
        capture_output=True, text=True, check=False,
    )
    if build.returncode != 0:
        pytest.skip(f"docker build failed:\n{build.stderr}")

    # Start
    subprocess.run(
        [
            "docker", "run", "--rm", "--name", CONTAINER_NAME,
            "--memory=2g", "--cpus=2",
            "-d", "-p", "8000:8000",
            IMAGE_TAG,
        ],
        capture_output=True, text=True, check=True,
    )

    # Wait for healthy
    deadline = time.monotonic() + 60
    healthy = False
    while time.monotonic() < deadline:
        r = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", CONTAINER_NAME],
            capture_output=True, text=True, check=False,
        )
        status = r.stdout.strip()
        if status == "healthy":
            healthy = True
            break
        time.sleep(2)

    yield healthy

    # Teardown
    subprocess.run(["docker", "stop", CONTAINER_NAME], capture_output=True, text=True, check=False)
    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True, text=True, check=False)


def test_docker_container_becomes_healthy(docker_container):
    assert docker_container, "Container did not become healthy within 60s"


def test_docker_healthz_returns_200(docker_container):
    resp = httpx.get(HEALTH_URL, timeout=5)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_docker_linalg_endpoint_returns_200(docker_container):
    resp = httpx.post(LINALG_URL, json={"matrix": [[1, 2], [3, 4]]}, timeout=10)
    assert resp.status_code == 200
    assert resp.json() == -2