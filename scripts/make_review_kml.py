"""Build a Google Earth KML (+ tracking CSV) of ONLY the facilities that need a
manual look: independent_building_verified is False (not on an independent
building) or blank (check failed). Targets the manual pass instead of all rows."""
import csv
import pandas as pd

df = pd.read_csv("data/processed/datacenters_conus.csv")
ver = pd.read_csv("data/processed/independent_verification.csv")
m = df.merge(ver, on="facility_id", how="left")

# ⚠️ pile = not independently confirmed (False) or could-not-check (blank/NaN)
need = m[m["independent_building_verified"] != True].copy()

def esc(s):
    s = "" if pd.isna(s) else str(s)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# --- KML ---
parts = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
         '<name>Data centers needing manual review</name>',
         '<Style id="rev"><IconStyle><color>ff0000ff</color>'
         '<Icon><href>http://maps.google.com/mapfiles/kml/paddle/red-circle.png</href></Icon>'
         '</IconStyle></Style>']
for _, r in need.iterrows():
    status = "check-failed" if pd.isna(r["independent_building_verified"]) else "not-on-independent-building"
    desc = (f"Operator: {esc(r.get('operator_company'))}<br/>"
            f"Status: {esc(r.get('status'))}<br/>"
            f"Type: {esc(r.get('facility_type'))}<br/>"
            f"Coordinate precision: {esc(r.get('coordinate_precision'))}<br/>"
            f"Source: {esc(r.get('source_name'))}<br/>"
            f"Verification: {status}")
    parts.append(f"<Placemark><name>{esc(r.get('name')) or esc(r['facility_id'])}</name>"
                 f"<styleUrl>#rev</styleUrl><description><![CDATA[{desc}]]></description>"
                 f"<Point><coordinates>{r['longitude']},{r['latitude']},0</coordinates></Point></Placemark>")
parts.append("</Document></kml>")
open("data/processed/needs_review.kml", "w").write("\n".join(parts))

# --- tracking CSV for the human pass ---
cols = ["facility_id", "name", "operator_company", "status", "facility_type",
        "coordinate_precision", "source_name", "latitude", "longitude"]
t = need[cols].copy()
t["reason"] = need["independent_building_verified"].apply(
    lambda v: "check-failed" if pd.isna(v) else "not-on-independent-building")
t["google_maps"] = need.apply(
    lambda r: f"https://www.google.com/maps/search/?api=1&query={r['latitude']},{r['longitude']}", axis=1)
for c in ["verified", "corrected_lat", "corrected_lon", "reviewer_notes"]:
    t[c] = ""
t.to_csv("data/processed/needs_review_tracking.csv", index=False)

print(f"needs review: {len(need)} of {len(m)}")
print("  not-on-independent-building:", int((need['independent_building_verified'] == False).sum()))
print("  check-failed:", int(need['independent_building_verified'].isna().sum()))
print("wrote data/processed/needs_review.kml + needs_review_tracking.csv")
