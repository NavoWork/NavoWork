"""Exercise one event loop with more requests than the database pool can hold."""
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


def test_parallel_workspace_reads_do_not_block_api(tmp_path):
    # A subprocess bounds a regression that blocks the event loop itself;
    # asyncio.wait_for cannot time out while synchronous pool checkout blocks it.
    script = textwrap.dedent('''
        import asyncio
        import httpx
        from app.main import app

        async def exercise():
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://test"
                ) as client:
                    login = await client.post("/api/v1/auth/session", json={
                        "email": "demo@navowork.local", "password": "ChangeMe123!"
                    })
                    assert login.status_code == 200, login.text
                    base = "/api/v1/workspaces/ws_demo/inquiries/inq_demo_bag/"
                    paths = [(base + tail, 200) for tail in (
                        "messages", "revisions", "material-bundles", "canvas"
                    )] + [(base + "missing", 404), ("/health/live", 200)]
                    for _ in range(3):
                        responses = await asyncio.gather(*[
                            client.get(path) for path, _ in paths * 10
                        ])
                        for response, (_, expected) in zip(responses, paths * 10):
                            assert response.status_code == expected, response.text
                    assert (await client.get("/health/ready")).status_code == 200

        asyncio.run(exercise())
    ''')
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp_path / 'parallel.sqlite3'}",
           "STORAGE_ROOT": str(tmp_path / "storage"), "APP_ENV": "demo",
           "MODEL_API_KEY": "", "DEMO_EMAIL": "demo@navowork.local",
           "DEMO_PASSWORD": "ChangeMe123!"}
    try:
        result = subprocess.run(
            [sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1],
            env=env, capture_output=True, text=True, timeout=15,
        )
    except subprocess.TimeoutExpired:
        pytest.fail("Concurrent workspace reads blocked the API for more than 15 seconds")
    assert result.returncode == 0, result.stdout + result.stderr
