#!/usr/bin/env bash
# Launch the NGS Tracker web app.
# Activate the ngs-tracker conda env before running, or let conda run handle it.
#
# Environment variables (all optional):
#   NGS_PORT    — port to listen on  (default: 5000)
#   NGS_HOST    — host to bind to    (default: 127.0.0.1)
#               Set to 0.0.0.0 to expose on the local network.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

conda run -n ngs-tracker python "$SCRIPT_DIR/app.py"
