import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

playwright = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Error, sync_playwright


def _wait_for_http(url: str, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return
        except (urllib.error.URLError, ConnectionError) as exc:
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def _post_json(url: str, payload: dict[str, str]) -> None:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        if response.status >= 400:
            raise RuntimeError(f"Unexpected status {response.status} for {url}")


@pytest.mark.skipif(shutil.which("npm") is None, reason="npm is required for the UI smoke test")
def test_dashboard_log_smoke(tmp_path):
    backend_port = 8765
    frontend_port = 5173
    env = os.environ.copy()
    env["VITE_GENESISDB_USE_MOCK_DATA"] = "false"
    env["VITE_GENESISDB_WS_URL"] = f"ws://127.0.0.1:{backend_port}/ws"

    backend_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "src.visualization.server:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(backend_port),
    ]
    frontend_cmd = [
        "npm",
        "run",
        "dev",
        "--",
        "--host",
        "127.0.0.1",
        "--port",
        str(frontend_port),
    ]

    backend_proc = subprocess.Popen(
        backend_cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=os.getcwd(),
    )
    frontend_proc = subprocess.Popen(
        frontend_cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=os.path.join(os.getcwd(), "ui"),
    )

    try:
        _wait_for_http(f"http://127.0.0.1:{backend_port}/health")
        _wait_for_http(f"http://127.0.0.1:{frontend_port}")

        with sync_playwright() as playwright_instance:
            try:
                browser = playwright_instance.chromium.launch()
            except Error as exc:
                if "Executable doesn't exist" in str(exc):
                    pytest.skip("Playwright browser binaries are not installed")
                raise
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{frontend_port}", wait_until="networkidle")
            page.get_by_role("button", name="Logs").click()
            page.get_by_text("Connected").wait_for(timeout=10_000)

            _post_json(
                f"http://127.0.0.1:{backend_port}/logs",
                {"message": "ui smoke log", "level": "info"},
            )

            page.get_by_text("ui smoke log").wait_for(timeout=10_000)
            browser.close()
    finally:
        for proc in (frontend_proc, backend_proc):
            if proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
