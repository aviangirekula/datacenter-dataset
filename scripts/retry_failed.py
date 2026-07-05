"""Retry independent verification for facilities the first pass couldn't check
(blank/None). Re-downloads their areas (smaller per-cell bbox, longer timeout)
and updates data/processed/independent_verification.csv in place."""
import json, subprocess
import pandas as pd
from shapely.geometry import shape, Point
from shapely.strtree import STRtree

GRID, BUF_BBOX, BUF_PT = 0.4, 0.003, 0.0002
TMP = "/tmp/_ov_retry.geojson"

ver = pd.read_csv("data/processed/independent_verification.csv")
df = pd.read_csv("data/processed/datacenters_conus.csv")
failed_ids = set(ver[ver["independent_building_verified"].isna()]["facility_id"])
if not failed_ids:
    print("nothing to retry"); raise SystemExit
sub_all = df[df["facility_id"].isin(failed_ids)].copy()
sub_all["cx"] = (sub_all.longitude / GRID).round().astype(int)
sub_all["cy"] = (sub_all.latitude / GRID).round().astype(int)
groups = list(sub_all.groupby(["cx", "cy"]))
print(f"retrying {len(failed_ids)} facilities across {len(groups)} cells")

def independent(f):
    s = f["properties"].get("sources") or []
    return any("openstreetmap" not in str(x.get("dataset", "")).lower() for x in s)

fixed = {}
for i, (_, sub) in enumerate(groups, 1):
    w, e = sub.longitude.min() - BUF_BBOX, sub.longitude.max() + BUF_BBOX
    s_, n = sub.latitude.min() - BUF_BBOX, sub.latitude.max() + BUF_BBOX
    try:
        subprocess.run(["./.venv/bin/overturemaps", "download", f"--bbox={w},{s_},{e},{n}",
                        "-f", "geojson", "--type=building", "-o", TMP],
                       check=True, capture_output=True, timeout=300)
        feats = json.load(open(TMP)).get("features", [])
        geoms = [shape(f["geometry"]) for f in feats if independent(f)]
        tree = STRtree(geoms) if geoms else None
        for _, r in sub.iterrows():
            if tree is None:
                fixed[r.facility_id] = False; continue
            p = Point(r.longitude, r.latitude).buffer(BUF_PT)
            fixed[r.facility_id] = bool(any(geoms[k].intersects(p) for k in tree.query(p)))
    except Exception:
        pass  # leave as NaN
    if i % 10 == 0 or i == len(groups):
        print(f"  {i}/{len(groups)} cells", flush=True)

ver["independent_building_verified"] = ver.apply(
    lambda r: fixed.get(r["facility_id"], r["independent_building_verified"]), axis=1)
ver.to_csv("data/processed/independent_verification.csv", index=False)
still = int(ver["independent_building_verified"].isna().sum())
print(f"retry done. recovered {len(fixed)} | still-failed {still}")
