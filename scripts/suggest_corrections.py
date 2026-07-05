"""For the truly-uncertain points (not on any confirmed building), find the
nearest INDEPENDENT (non-OSM) building and propose a SUGGESTED corrected
coordinate to speed the human Google Earth pass. Suggestions are NOT verified
truth -- each must be confirmed visually. Flags ambiguous cases (many buildings
nearby). Writes data/processed/corrections_suggested.csv."""
import json, subprocess
import pandas as pd
from shapely.geometry import shape, Point
from shapely.strtree import STRtree
from pyproj import Geod

GRID, BUF_BBOX = 0.4, 0.004
GEOD = Geod(ellps="WGS84")
TMP = "/tmp/_ov_fix.geojson"

df = pd.read_csv("data/processed/datacenters_conus.csv")
v = pd.read_csv("data/processed/independent_verification.csv")
m = df.merge(v, on="facility_id", how="left")
m["verified"] = m["independent_building_verified"] == True
target = m[(~m["verified"]) & (m["coordinate_precision"] != "building")].copy()  # the 462
target["cx"] = (target.longitude / GRID).round().astype(int)
target["cy"] = (target.latitude / GRID).round().astype(int)
groups = list(target.groupby(["cx", "cy"]))
print(f"suggesting corrections for {len(target)} uncertain points across {len(groups)} cells")

def independent(f):
    s = f["properties"].get("sources") or []
    return any("openstreetmap" not in str(x.get("dataset", "")).lower() for x in s)

rows = []
for i, (_, sub) in enumerate(groups, 1):
    w, e = sub.longitude.min() - BUF_BBOX, sub.longitude.max() + BUF_BBOX
    s_, n = sub.latitude.min() - BUF_BBOX, sub.latitude.max() + BUF_BBOX
    geoms, cents = [], []
    try:
        subprocess.run(["./.venv/bin/overturemaps", "download", f"--bbox={w},{s_},{e},{n}",
                        "-f", "geojson", "--type=building", "-o", TMP],
                       check=True, capture_output=True, timeout=300)
        feats = json.load(open(TMP)).get("features", [])
        geoms = [shape(f["geometry"]) for f in feats if independent(f)]
        cents = [g.representative_point() for g in geoms]
    except Exception:
        pass
    tree = STRtree(cents) if cents else None
    for _, r in sub.iterrows():
        p = Point(r.longitude, r.latitude)
        rec = {"facility_id": r.facility_id, "name": r.get("name"),
               "orig_lat": r.latitude, "orig_lon": r.longitude,
               "suggested_lat": "", "suggested_lon": "", "dist_m": "",
               "n_buildings_within_60m": "", "ambiguous": "", "note": ""}
        if tree is not None and cents:
            j = int(tree.nearest(p))
            c = cents[j]
            _, _, dist = GEOD.inv(r.longitude, r.latitude, c.x, c.y)
            near = 0
            for cc in cents:
                _, _, d2 = GEOD.inv(r.longitude, r.latitude, cc.x, cc.y)
                if d2 <= 60: near += 1
            rec.update(suggested_lat=round(c.y, 6), suggested_lon=round(c.x, 6),
                       dist_m=round(dist, 1), n_buildings_within_60m=near,
                       ambiguous=(near > 1),
                       note=("SUGGESTION - confirm on Google Earth" if dist <= 80
                             else "no building nearby - manual"))
        else:
            rec["note"] = "no independent buildings found - manual"
        rows.append(rec)
    if i % 15 == 0 or i == len(groups):
        print(f"  {i}/{len(groups)} cells", flush=True)

out = pd.DataFrame(rows)
out["google_earth"] = out.apply(
    lambda r: f"https://earth.google.com/web/@{r.orig_lat},{r.orig_lon},0a,150d,35y", axis=1)
out.to_csv("data/processed/corrections_suggested.csv", index=False)
snap = int((out["note"] == "SUGGESTION - confirm on Google Earth").sum())
amb = int((out["ambiguous"] == True).sum())
print(f"DONE. {len(out)} uncertain | {snap} have a nearby-building suggestion "
      f"({amb} ambiguous) | {len(out)-snap} no clear building -> manual")
