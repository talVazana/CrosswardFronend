import pathlib
import socket
import subprocess
import sys
import time

from fastapi.testclient import TestClient

from app.main import app

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
REQUIREMENTS = BACKEND_DIR / "requirements.txt"


def test_get_health_returns_200_and_status_ok():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_unknown_path_returns_404():
    client = TestClient(app)
    response = client.get("/unknown")
    assert response.status_code == 404


def test_get_health_without_auth_headers_returns_200():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert "www-authenticate" not in response.headers


def test_requirements_lists_fastapi_uvicorn_pytest():
    lines = [
        line.strip()
        for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert "fastapi" in lines
    assert "uvicorn" in lines
    assert "pytest" in lines


def test_uvicorn_starts_without_error():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(BACKEND_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    started = False
    deadline = time.time() + 15
    try:
        while time.time() < deadline:
            if process.poll() is not None:
                break
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    started = True
                    break
            except OSError:
                time.sleep(0.2)
        assert process.poll() is None, (
            "uvicorn exited early:\n" + (process.stdout.read() if process.stdout else "")
        )
        assert started, "uvicorn did not start listening within 15s"
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
