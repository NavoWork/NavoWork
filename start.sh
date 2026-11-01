#!/usr/bin/env bash
# NavoWork launcher for Linux and macOS.
#
# First run creates backend/.venv, installs dependencies and starts the API,
# worker and Vite UI. Pass --setup-only, --no-install or --skip-migrate through
# to dev.py; run `./start.sh --help` for details.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

find_python() {
    local candidate
    for candidate in python3.13 python3.12 python3 python; do
        if ! command -v "$candidate" >/dev/null 2>&1; then
            continue
        fi
        if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' >/dev/null 2>&1; then
            command -v "$candidate"
            return 0
        fi
    done
    return 1
}

if ! PYTHON="$(find_python)"; then
    cat >&2 <<'EOF'
[NavoWork] 未找到 Python 3.12+。

  macOS:          brew install python@3.12
  Ubuntu/Debian:  sudo apt install python3.12 python3.12-venv
  其他 Linux:     使用发行版的包管理器，或从 https://www.python.org/downloads/ 安装。

安装完成后重新运行 ./start.sh。
EOF
    exit 1
fi

exec "$PYTHON" "$SCRIPT_DIR/dev.py" "$@"
