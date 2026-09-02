#!/usr/bin/env bash
#
# Rebuild the whole pipeline in dependency order, from raw layers to the poster.
#
#   ./run_all.sh              # everything
#   ./run_all.sh --verify     # check inputs are present and checksummed, then stop
#   ./run_all.sh --no-poster  # data and analysis only
#
# Expect several hours on a cold cache. Almost all of that is network: the two
# per-facility services (USGS ASCE 7-22 and the NSHM hazard curves) make one
# call per site for 2,696 sites. Every fetch step is resumable, so an
# interrupted run can be restarted with the same command and will skip whatever
# is already cached.
#
# WHAT THIS DOES NOT DO. It never deletes a cache. The fetchers append to
# JSONL caches with no locking, so running two copies of this script at once
# will duplicate rows. Run one at a time.
set -euo pipefail

cd "$(dirname "$0")"
PY=./.venv/bin/python
[ -x "$PY" ] || { echo "no virtualenv at $PY. Create it, then pip install -r requirements.txt" >&2; exit 1; }

VERIFY_ONLY=0
POSTER=1
for arg in "$@"; do
  case "$arg" in
    --verify)    VERIFY_ONLY=1 ;;
    --no-poster) POSTER=0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

# ---------------------------------------------------------------- raw layers
step "Hazard layers: download and checksum"
if [ "$VERIFY_ONLY" -eq 1 ]; then
  $PY scripts/fetch_hazard_data.py --verify
  step "Verify only, stopping here"
  exit 0
fi
$PY scripts/fetch_hazard_data.py
$PY scripts/fetch_hazard_data.py --verify

# ------------------------------------------------------- per-facility fetches
# Resumable and slow. Kept before the builders because every builder below
# reads their caches.
step "Buildings and FEMA flood (ArcGIS, resumable)"
$PY scripts/fetch_building_attributes.py

step "Seismic: USGS ASCE 7-22 per facility (resumable)"
$PY scripts/fetch_seismic_authoritative.py

step "Seismic: USGS NSHM hazard curves, 475/975/2475 yr (resumable)"
$PY scripts/fetch_seismic_nshm.py

# ------------------------------------------------------------------ builders
step "Building attributes, heights, flood join"
$PY scripts/build_building_attributes.py

step "Hazard exposure table"
$PY scripts/build_hazard_exposure.py

step "Water stress (WRI Aqueduct basin join)"
$PY scripts/build_water_stress.py

step "Storm exposure (SPC + IBTrACS, exact Poisson intervals)"
$PY scripts/build_storm_exposure.py

# ------------------------------------------------------------------ analyses
step "Footprint versus point sampling, and the storey control"
$PY scripts/build_footprint_hazard.py

step "Storm reporting-bias diagnostic"
$PY scripts/storm_bias_diagnostic.py

# coordinate_uncertainty imports dcdata directly, unlike every other script.
step "Positional-error Monte Carlo, 500 draws"
PYTHONPATH=src $PY scripts/coordinate_uncertainty.py --draws 500

step "Seismic external validation"
$PY scripts/validate_seismic.py --n 150

# -------------------------------------------------------------------- poster
if [ "$POSTER" -eq 1 ]; then
  step "Poster figures"
  $PY scripts/make_poster_figures.py

  # build_poster.py reads the ASSIP template from /tmp, which does not survive
  # a reboot. Restore it from Downloads rather than failing.
  TEMPLATE=/tmp/assip_template.pptx
  SRC="$HOME/Downloads/MentorLastName_FirstName_LastName_2026ASSIP_Poster.pptx"
  if [ ! -f "$TEMPLATE" ] && [ -f "$SRC" ]; then
    echo "  restoring $TEMPLATE from Downloads"
    cp "$SRC" "$TEMPLATE"
  fi
  if [ -f "$TEMPLATE" ]; then
    step "Poster"
    $PY scripts/build_poster.py
    $PY scripts/check_poster.py
    echo
    echo "  The PDF is exported from PowerPoint by hand. See docs/CONTEXT_HANDOFF.md."
  else
    echo "  [skip] poster: no template at $TEMPLATE and none in Downloads"
  fi
fi

step "Done"
