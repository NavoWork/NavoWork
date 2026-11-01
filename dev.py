"""One-command launcher for the NavoWork development stack.

`start.sh` (Linux/macOS), `start.command` (macOS Finder), `start.ps1` and
`start.bat` (Windows) all delegate here, so there is only one launcher to
maintain. First run creates `backend/.venv`, installs Python and npm
dependencies and copies `backend/.env.example` to `backend/.env`; later runs
apply migrations and start the API, LangGraph worker and Vite UI.
"""
from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "fontend"
VENV = BACKEND / ".venv"
IS_WINDOWS = os.name == "nt"
VENV_PYTHON = VENV / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")
VITE_BIN = ROOT / "node_modules" / "vite" / "bin" / "vite.js"
MIN_PYTHON = (3, 12)
MIN_NODE = (20, 0, 0)
API_HOST = "127.0.0.1"
API_PORT = 8000
UI_PORT = 5173
_STOP_REQUESTED = False


class SetupError(RuntimeError):
    """A failure that can be explained to the user without a traceback."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="启动 NavoWork 本地开发环境（API、Worker 和前端）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  ./start.sh                     Linux/macOS 首次启动并自动安装依赖\n"
            "  ./start.sh --setup-only        只准备环境，不启动服务\n"
            "  ./start.sh --no-install        跳过自动安装，依赖必须已存在\n"
            "  ./start.sh --skip-migrate      跳过数据库迁移\n"
        ),
    )
    parser.add_argument("--no-install", action="store_true", help="不自动创建虚拟环境或安装依赖")
    parser.add_argument("--setup-only", action="store_true", help="只准备运行环境，不启动服务")
    parser.add_argument("--skip-migrate", action="store_true", help="跳过数据库迁移")
    return parser.parse_args(argv)


def parse_version(value: str) -> tuple[int, int, int]:
    """Turn strings such as ``v24.22.2`` or ``3.13.1`` into a comparable tuple."""
    numbers: list[int] = []
    for piece in value.strip().lstrip("vV").split("."):
        digits = ""
        for char in piece:
            if not char.isdigit():
                break
            digits += char
        if not digits:
            break
        numbers.append(int(digits))
    while len(numbers) < 3:
        numbers.append(0)
    return numbers[0], numbers[1], numbers[2]


def probe(command: list[Path | str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str] | None:
    """Run a short check command without printing its output."""
    try:
        return subprocess.run(
            [str(part) for part in command],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def ensure_local_config() -> None:
    (BACKEND / "data").mkdir(parents=True, exist_ok=True)
    (BACKEND / "storage").mkdir(parents=True, exist_ok=True)
    env_file = BACKEND / ".env"
    example = BACKEND / ".env.example"
    if not env_file.exists() and example.exists():
        shutil.copyfile(example, env_file)
        print("==> 已从 backend/.env.example 创建 backend/.env", flush=True)


def python_meets_requirement(executable: Path) -> bool:
    result = probe(
        [
            executable,
            "-c",
            f"import sys; raise SystemExit(0 if sys.version_info >= {MIN_PYTHON!r} else 1)",
        ]
    )
    return result is not None and result.returncode == 0


def python_dependencies_installed() -> bool:
    result = probe(
        [VENV_PYTHON, "-c", "import fastapi, sqlalchemy, alembic, uvicorn, navowork_agent"],
        cwd=BACKEND,
    )
    return result is not None and result.returncode == 0


def ensure_python_dependencies(install: bool) -> None:
    if VENV_PYTHON.exists():
        if not python_meets_requirement(VENV_PYTHON):
            raise SetupError(
                "backend/.venv 无法使用，或其中的 Python 低于 3.12。请删除该目录后重新运行启动脚本：\n"
                "  Linux/macOS: rm -rf backend/.venv\n"
                "  Windows:     Remove-Item -Recurse -Force backend\\.venv"
            )
        if python_dependencies_installed():
            return

    if not install:
        raise SetupError(
            "Python 依赖尚未准备好。请去掉 --no-install 重新运行启动脚本，"
            "或按 README 手动创建 backend/.venv 并安装依赖。"
        )

    if not VENV_PYTHON.exists():
        print("==> 创建 Python 虚拟环境 backend/.venv ...", flush=True)
        result = subprocess.run([sys.executable, "-m", "venv", str(VENV)], cwd=ROOT, check=False)
        if result.returncode != 0 or not VENV_PYTHON.exists():
            raise SetupError(
                "创建 Python 虚拟环境失败。Linux 上请确认已安装 python3-venv，"
                "然后删除 backend/.venv 并重试。"
            )
        if not python_meets_requirement(VENV_PYTHON):
            raise SetupError("创建出的 backend/.venv 不是 Python 3.12+，请检查系统的 Python 安装。")

    print("==> 安装 Python 依赖（首次运行可能需要几分钟）...", flush=True)
    result = subprocess.run(
        [
            str(VENV_PYTHON),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-e",
            "agent-kit",
            "-e",
            "backend[test]",
        ],
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        raise SetupError("Python 依赖安装失败。请检查网络或 pip 源配置后重试。")
    if not python_dependencies_installed():
        raise SetupError("Python 依赖安装完成，但仍无法导入，请查看上方 pip 输出。")


def node_executable() -> str:
    executable = shutil.which("node")
    if not executable:
        raise SetupError(
            "未找到 Node.js 20+。请先安装 Node.js：\n"
            "  Linux/macOS: https://nodejs.org/ 或使用 nvm\n"
            "  Windows:     winget install OpenJS.NodeJS.LTS"
        )
    return executable


def ensure_node_runtime() -> str:
    executable = node_executable()
    result = probe([executable, "--version"])
    if result is None or result.returncode != 0:
        raise SetupError("无法执行 node --version，请检查 Node.js 安装。")
    version = result.stdout.strip()
    if parse_version(version) < MIN_NODE:
        raise SetupError(f"当前 Node.js 为 {version}，需要 20 或更高版本。")
    return version


def npm_executable() -> str:
    executable = shutil.which("npm")
    if not executable:
        raise SetupError("未找到 npm，请重新安装 Node.js 20+ 并确保 npm 在 PATH 中。")
    return executable


def frontend_dependencies_ready() -> bool:
    modules = ROOT / "node_modules"
    return (modules / ".package-lock.json").is_file() and VITE_BIN.is_file()


def ensure_frontend_dependencies(install: bool) -> None:
    if frontend_dependencies_ready():
        return
    if not install:
        raise SetupError("前端依赖尚未安装。请去掉 --no-install 重新运行，或执行 npm ci。")

    npm = npm_executable()
    command = [npm, "ci"] if (ROOT / "package-lock.json").exists() else [npm, "install"]
    print(f"==> 安装前端依赖（{Path(npm).name} {'ci' if command[-1] == 'ci' else 'install'}）...", flush=True)
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode != 0:
        raise SetupError("前端依赖安装失败。请检查网络或 npm 源配置后重试。")
    if not frontend_dependencies_ready():
        raise SetupError("前端依赖安装完成，但 node_modules 不完整，请查看上方 npm 输出。")


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
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("PYTHONUTF8", "1")
    env["VITE_API_MODE"] = "real"
    return env


def ensure_ports_free() -> None:
    for port in (API_PORT, UI_PORT):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)
            if sock.connect_ex((API_HOST, port)) != 0:
                continue
        if IS_WINDOWS:
            hint = f"netstat -ano | findstr :{port}"
        else:
            hint = f"lsof -nP -iTCP:{port} -sTCP:LISTEN"
        raise SetupError(f"端口 {port} 已被占用，请先停止占用该端口的进程（{hint}）。")


def migrate(env: dict[str, str]) -> None:
    print("==> 应用数据库迁移 ...", flush=True)
    result = subprocess.run(
        [str(VENV_PYTHON), "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        raise SetupError("数据库迁移失败，请检查 backend/.env 中的 DATABASE_URL。")


def install_signal_handlers() -> None:
    def request_stop(_signum: int, _frame: object) -> None:
        global _STOP_REQUESTED
        _STOP_REQUESTED = True

    for name in ("SIGHUP", "SIGINT", "SIGTERM", "SIGBREAK"):
        candidate = getattr(signal, name, None)
        if candidate is None:
            continue
        try:
            signal.signal(candidate, request_stop)
        except (OSError, ValueError):
            pass


def spawn(command: list[Path | str], cwd: Path, env: dict[str, str]) -> subprocess.Popen[bytes]:
    options: dict[str, object] = {}
    if IS_WINDOWS:
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        # Give each service its own process group so the launcher can stop the
        # complete npm/vite/uvicorn tree, not only the immediate child.
        options["start_new_session"] = True
    return subprocess.Popen([str(part) for part in command], cwd=cwd, env=env, **options)


def shutdown(children: list[tuple[str, subprocess.Popen[bytes]]]) -> None:
    running = [(label, child) for label, child in children if child.poll() is None]
    if not running:
        return
    print("==> 正在停止服务 ...", flush=True)
    for _label, child in running:
        try:
            if IS_WINDOWS:
                child.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                # Each service is a direct child, so signal only that process.
                # Vite then closes its own esbuild child without EPIPE noise.
                child.terminate()
        except (OSError, ValueError):
            pass

    deadline = time.monotonic() + 6
    for _label, child in running:
        try:
            child.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass

    for label, child in running:
        if child.poll() is not None:
            continue
        print(f"==> 强制结束 {label}（PID {child.pid}）", flush=True)
        if IS_WINDOWS:
            subprocess.run(
                ["taskkill", "/PID", str(child.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except OSError:
                pass

    for _label, child in running:
        try:
            child.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass


def start_services(env: dict[str, str]) -> int:
    global _STOP_REQUESTED
    _STOP_REQUESTED = False
    install_signal_handlers()

    commands: list[tuple[str, list[Path | str], Path]] = [
        (
            "API",
            [
                VENV_PYTHON,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                API_HOST,
                "--port",
                str(API_PORT),
            ],
            BACKEND,
        ),
        ("Worker", [VENV_PYTHON, "-m", "app.worker"], BACKEND),
        # Run Vite directly instead of through `npm run dev`: it is the same
        # command as fontend/package.json, but lets SIGTERM reach Vite first so
        # it can close its esbuild child cleanly.
        ("UI", [node_executable(), VITE_BIN, "--host", API_HOST], FRONTEND),
    ]

    children: list[tuple[str, subprocess.Popen[bytes]]] = []
    try:
        for label, command, directory in commands:
            print(f"==> 启动 {label} ...", flush=True)
            try:
                children.append((label, spawn(command, directory, env)))
            except OSError as exc:
                raise SetupError(f"无法启动 {label}：{exc}") from exc

        print(flush=True)
        print(f"  UI        http://{API_HOST}:{UI_PORT}", flush=True)
        print(f"  API       http://{API_HOST}:{API_PORT}", flush=True)
        print(f"  健康检查  http://{API_HOST}:{API_PORT}/health/live", flush=True)
        print(flush=True)
        print("按 Ctrl+C 停止全部服务。演示账号见 backend/.env。", flush=True)

        while not _STOP_REQUESTED:
            for label, child in children:
                code = child.poll()
                if code is not None:
                    print(
                        f"==> {label} 已退出（退出码 {code}），正在停止其他服务 ...",
                        flush=True,
                    )
                    return 1
            time.sleep(0.5)
        return 0
    finally:
        shutdown(children)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if sys.version_info < MIN_PYTHON:
        print(
            f"[NavoWork] 需要 Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+，"
            f"当前为 {sys.version.split()[0]}。",
            file=sys.stderr,
            flush=True,
        )
        return 1

    try:
        print("==> 检查 NavoWork 运行环境 ...", flush=True)
        ensure_local_config()
        ensure_node_runtime()
        ensure_python_dependencies(install=not args.no_install)
        ensure_frontend_dependencies(install=not args.no_install)

        if args.setup_only:
            print("==> 环境已就绪。运行 start.sh / start.bat 启动服务。", flush=True)
            return 0

        ensure_ports_free()
        env = local_env()
        if args.skip_migrate:
            print("==> 已跳过数据库迁移。", flush=True)
        else:
            migrate(env)
        return start_services(env)
    except SetupError as exc:
        print(f"\n[启动失败] {exc}", file=sys.stderr, flush=True)
        return 1
    except KeyboardInterrupt:
        print("\n已取消。", flush=True)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
