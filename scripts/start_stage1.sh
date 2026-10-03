#!/usr/bin/env bash
set -euo pipefail
export EAR_MALECNS_ROOT=/mnt/h/ear-malecns
export EAR_MALECNS_PROJECT="$EAR_MALECNS_ROOT/project/ear_malecns_manual_project"
mountpoint -q /mnt/h || { echo 'H drive is not mounted'; exit 1; }
test -d "$EAR_MALECNS_PROJECT" || { echo 'H-drive project missing'; exit 1; }
export PIP_CACHE_DIR="$EAR_MALECNS_PROJECT/downloads/pip-cache"
export TMPDIR="$EAR_MALECNS_PROJECT/downloads/tmp"
export MPLCONFIGDIR="$EAR_MALECNS_PROJECT/downloads/matplotlib"
mkdir -p "$PIP_CACHE_DIR" "$TMPDIR" "$MPLCONFIGDIR"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate ear-malecns
cd "$EAR_MALECNS_PROJECT"
python scripts/06_stage1.py "$@"
