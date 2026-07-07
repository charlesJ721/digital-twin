#!/bin/bash
# Run DT v2 framework extraction beside the legacy cron path without mutating data.
set -euo pipefail
cd "${DT_PROJECT_ROOT:-$HOME/Projects/digital-twin}"
python3 -m framework.pipeline --config "${DT_CONFIG:-config.yaml}" --shadow-legacy "$HOME/.hermes/scripts/dt-dimension-extraction.py"
