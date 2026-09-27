#!/bin/sh
# Builds the OSRM routing graph (walking profile, MLD algorithm) once.
set -eu

DATA=/data
GRAPH="$DATA/region.osrm.mldgr"
MARKER="$DATA/region.url"  # rewritten by download.sh whenever a new extract arrives
if [ -s "$GRAPH" ] && { [ ! -e "$MARKER" ] || [ "$GRAPH" -nt "$MARKER" ]; }; then
    echo "osrm-prepare: routing graph is up to date, skipping"
    exit 0
fi

INPUT="$DATA/region.osm.pbf"
[ -s "$INPUT" ] || INPUT="$DATA/region.osm"  # plain XML works too (used in tests)

echo "osrm-prepare: extracting $INPUT with the foot profile (this can take a few minutes)"
osrm-extract -p /opt/foot.lua "$INPUT"
osrm-partition "$DATA/region.osrm"
osrm-customize "$DATA/region.osrm"
echo "osrm-prepare: done"
