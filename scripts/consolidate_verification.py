"""Consolidate coordinate-quality into the dataset + a targeted review kit.
Adds per-facility: independent_building_verified, coordinate_status, and a
suggested coordinate for the fixable ones. Honest labels only -- nothing is
called 'verified to the exact building'; that stays a human step."""
import pandas as pd

df = pd.read_csv("data/processed/datacenters_conus.csv")
v = pd.read_csv("data/processed/independent_verification.csv")
c = pd.read_csv("data/processed/corrections_suggested.csv")
m = df.merge(v, on="facility_id", how="left").merge(
    c[["facility_id", "suggested_lat", "suggested_lon", "dist_m", "ambiguous", "note"]],
    on="facility_id", how="left")

def status(r):
    if r["independent_building_verified"] == True:
        return "independently_confirmed_on_building"   # strongest (two datasets agree)
    if r["coordinate_precision"] == "building":
        return "on_osm_building_single_source"          # building-accurate, one source
    if str(r.get("note")) == "SUGGESTION - confirm on Google Earth":
        return "ambiguous_candidate" if r.get("ambiguous") == True else "candidate_building_suggested"
    return "no_building_found_manual"

m["coordinate_status"] = m.apply(status, axis=1)
m["needs_human_check"] = ~m["coordinate_status"].isin(["independently_confirmed_on_building"])

keep = ["facility_id", "name", "operator_company", "status", "coordinate_precision",
        "coordinate_status", "independent_building_verified", "needs_human_check",
        "latitude", "longitude", "suggested_lat", "suggested_lon", "dist_m",
        "state", "county", "source_name"]
m[keep].to_csv("data/processed/datacenters_conus_verified.csv", index=False)

print("coordinate_status breakdown (all", len(m), "):")
print(m["coordinate_status"].value_counts().to_string())

# --- review kit: the location-uncertain 462 (candidate / ambiguous / no-building) ---
fix = m[m["coordinate_status"].isin(
    ["candidate_building_suggested", "ambiguous_candidate", "no_building_found_manual"])].copy()

def esc(s):
    return "" if pd.isna(s) else str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

parts = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
         '<name>Data centers to locate (targeted)</name>',
         '<Style id="orig"><IconStyle><color>ff0000ff</color><Icon><href>http://maps.google.com/mapfiles/kml/paddle/red-circle.png</href></Icon></IconStyle></Style>',
         '<Style id="cand"><IconStyle><color>ff00ff00</color><Icon><href>http://maps.google.com/mapfiles/kml/paddle/grn-blank.png</href></Icon></IconStyle></Style>']
for _, r in fix.iterrows():
    desc = (f"Operator: {esc(r.operator_company)}<br/>Status: {esc(r['status'])}<br/>"
            f"Coordinate status: {esc(r.coordinate_status)}<br/>Source: {esc(r.source_name)}")
    parts.append(f"<Placemark><name>{esc(r['name']) or esc(r.facility_id)}</name><styleUrl>#orig</styleUrl>"
                 f"<description><![CDATA[{desc} (current pin)]]></description>"
                 f"<Point><coordinates>{r.longitude},{r.latitude},0</coordinates></Point></Placemark>")
    if pd.notna(r.suggested_lat):
        parts.append(f"<Placemark><name>{esc(r['name'])} [candidate]</name><styleUrl>#cand</styleUrl>"
                     f"<description><![CDATA[Suggested nearest building (~{r.dist_m} m) - CONFIRM on Google Earth]]></description>"
                     f"<Point><coordinates>{r.suggested_lon},{r.suggested_lat},0</coordinates></Point></Placemark>")
parts.append("</Document></kml>")
open("data/processed/needs_review.kml", "w").write("\n".join(parts))

tcols = ["facility_id","name","operator_company","status","coordinate_status",
         "latitude","longitude","suggested_lat","suggested_lon","dist_m"]
t = fix[tcols].copy()
t["google_earth"] = fix.apply(lambda r: f"https://earth.google.com/web/@{r.latitude},{r.longitude},0a,180d,35y", axis=1)
for col in ["confirmed_lat","confirmed_lon","verified_by","verified_date","notes"]:
    t[col] = ""
t.to_csv("data/processed/needs_review_tracking.csv", index=False)
print(f"\nreview kit: {len(fix)} location-uncertain points -> needs_review.kml + needs_review_tracking.csv")
print("  (candidate suggestions pre-filled where available)")
