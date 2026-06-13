#!/usr/bin/env bash
# Launch the NGS Tracker web app.
# Activate the ngs-tracker conda env before running, or let conda run handle it.
#
# Usage:
#   ./run.sh           — normal mode, uses ~/.ngs-tracker/settings.json
#   ./run.sh demo      — demo mode: regenerates demo.db and starts with that
#                        database; the real settings.json is left untouched
#
# Environment variables (all optional):
#   NGS_PORT    — port to listen on  (default: 5000)
#   NGS_HOST    — host to bind to    (default: 127.0.0.1)
#               Set to 0.0.0.0 to expose on the local network.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "${1:-}" = "demo" ]; then
    DEMO_DB="$SCRIPT_DIR/demo.db"
    DEMO_STORAGE="/tmp/ngs-tracker-demo-files"
    mkdir -p "$DEMO_STORAGE"
    echo "Demo mode: regenerating demo database..."
    conda run -n ngs-tracker python "$SCRIPT_DIR/create_demo_db.py" --out "$DEMO_DB"
    export NGS_DB_PATH="$DEMO_DB"
    export NGS_STORAGE_PATH="$DEMO_STORAGE"
    echo "Starting NGS Tracker in DEMO mode — http://127.0.0.1:${NGS_PORT:-5000}"
fi

RESTART_FLAG="$HOME/.ngs-tracker/.restart"

while true; do
    conda run -n ngs-tracker python "$SCRIPT_DIR/app.py"
    if [ -f "$RESTART_FLAG" ]; then
        rm -f "$RESTART_FLAG"
        echo "Restarting NGS Tracker..."
    else
        break
    fi
done
