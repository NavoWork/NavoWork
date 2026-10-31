"""Start the local API, LangGraph worker and Vite UI with one command."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
PYTHON = BACKEND / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def local_env() -> dict[str, str]:
    env = os.environ.copy()
    source = BACKEND / ".env"
    if source.exists():
        for raw in source.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    env.setdefault("APP_ENV", "demo")
    env["VITE_API_MODE"] = "real"
    return env


def main() -> int:
    if not PYTHON.exists() or not (ROOT / "node_modules").exists():
        print("先运行：python -m venv backend/.venv；backend/.venv/Scripts/python -m pip install -e 'backend[test]'；npm ci")
        return 1
    env = local_env()
    subprocess.run([str(PYTHON), "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env, check=True)
    npm = "npm.cmd" if os.name == "nt" else "npm"
    commands = [
        ("API", [str(PYTHON), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"], BACKEND),
        ("Worker", [str(PYTHON), "-m", "app.worker"], BACKEND),
        ("UI", [npm, "run", "dev"], ROOT),
    ]
    children: list[subprocess.Popen] = []
    try:
        for label, command, directory in commands:
            children.append(subprocess.Popen(command, cwd=directory, env=env))
            print(f"{label} started (PID {children[-1].pid})", flush=True)
        print("打开 http://127.0.0.1:5173；按 Ctrl+C 停止全部服务。", flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()


if __name__ == "__main__":
    raise SystemExit(main())
