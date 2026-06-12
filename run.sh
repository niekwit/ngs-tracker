#!/usr/bin/env bash
# Launch the NGS Tracker web app.
# Activate the ngs-tracker conda env before running, or let conda run handle it.
#
# Environment variables (all optional):
#   NGS_PORT    — port to listen on  (default: 5000)
#   NGS_HOST    — host to bind to    (default: 127.0.0.1)
#               Set to 0.0.0.0 to expose on the local network.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
