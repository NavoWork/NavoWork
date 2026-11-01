#!/usr/bin/env bash
# macOS Finder double-click launcher: opens Terminal and runs start.sh.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/start.sh" "$@"
