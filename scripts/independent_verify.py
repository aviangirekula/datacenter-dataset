"""Independently verify every facility coordinate against non-OSM building
footprints (Overture -> Microsoft ML / Google / Esri). Writes
data/processed/independent_verification.csv with one row per facility.
Optional arg: max number of cells (for testing)."""
import json, subprocess, sys
import pandas as pd
from shapely.geometry import shape, Point
from shapely.strtree import STRtree

GRID, BUF_BBOX, BUF_PT = 0.4, 0.003, 0.0002
TMP = "/tmp/_ov_cell.geojson"
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else None

df = pd.read_csv("data/processed/datacenters_conus.csv")
df["cx"] = (df.longitude / GRID).round().astype(int)
df["cy"] = (df.latitude / GRID).round().astype(int)
groups = list(df.groupby(["cx", "cy"]))
if LIMIT:
    groups = groups[:LIMIT]

def independent(f):
    s = f["properties"].get("sources") or []
    return any("openstreetmap" not in str(x.get("dataset", "")).lower() for x in s)

results = {}
for i, ((cx, cy), sub) in enumerate(groups, 1):
    w, e = sub.longitude.min() - BUF_BBOX, sub.longitude.max() + BUF_BBOX
    s_, n = sub.latitude.min() - BUF_BBOX, sub.latitude.max() + BUF_BBOX
    try:
        subprocess.run(
            ["./.venv/bin/overturemaps", "download", f"--bbox={w},{s_},{e},{n}",
             "-f", "geojson", "--type=building", "-o", TMP],
            check=True, capture_output=True, timeout=240)
        feats = json.load(open(TMP)).get("features", [])
        geoms = [shape(f["geometry"]) for f in feats if independent(f)]
        tree = STRtree(geoms) if geoms else None
        for _, r in sub.iterrows():
            if tree is None:
                results[r.facility_id] = False; continue
            p = Point(r.longitude, r.latitude).buffer(BUF_PT)
            results[r.facility_id] = bool(any(geoms[k].intersects(p) for k in tree.query(p)))
    except Exception:
        for _, r in sub.iterrows():
            results[r.facility_id] = None
    if i % 20 == 0 or i == len(groups):
        conf = sum(1 for v in results.values() if v)
        print(f"{i}/{len(groups)} cells | checked {len(results)} | confirmed {conf}", flush=True)

out = pd.DataFrame([{"facility_id": k, "independent_building_verified": v} for k, v in results.items()])
out.to_csv("data/processed/independent_verification.csv", index=False)
tot = len(out); conf = int((out.independent_building_verified == True).sum())
no = int((out.independent_building_verified == False).sum()); err = int(out.independent_building_verified.isna().sum())
print(f"DONE. total {tot} | independently confirmed {conf} ({round(100*conf/max(tot,1))}%) | not-on-independent {no} | check-failed {err}")
