#!/bin/sh
# Downloads the OpenStreetMap extract once. Re-downloads only if OSRM_PBF_URL changes.
set -eu

DATA=/data
PBF="$DATA/region.osm.pbf"
MARKER="$DATA/region.url"

if [ -s "$PBF" ] && [ "$(cat "$MARKER" 2>/dev/null)" = "$OSRM_PBF_URL" ]; then
    echo "osrm-download: $PBF already present, skipping"
    exit 0
fi

echo "osrm-download: fetching $OSRM_PBF_URL"
rm -f "$DATA"/region.osrm* "$MARKER"
curl -fL --retry 3 --retry-delay 5 -o "$PBF.part" "$OSRM_PBF_URL"
mv "$PBF.part" "$PBF"
echo "$OSRM_PBF_URL" > "$MARKER"
echo "osrm-download: done ($(du -h "$PBF" | cut -f1))"
