"""Merge building-verification results into the dataset -> datacenters_final.csv.
Keeps the original coordinate (provenance) and sets latitude/longitude to the
confirmed on-building coordinate where a VERIFIED/CANDIDATE result exists."""
import os
import pandas as pd

base = pd.read_csv("data/processed/datacenters_conus.csv")
vstat = pd.read_csv("data/processed/datacenters_conus_verified.csv")[["facility_id", "coordinate_status"]]
rp = "data/processed/building_verification_results.csv"
res = pd.read_csv(rp) if os.path.exists(rp) else pd.DataFrame(
    columns=["facility_id","status","confirmed_lat","confirmed_lon","evidence","source_url","confidence","checked_date","verification_method"])
res = res.rename(columns={"status":"verification_status","evidence":"verification_evidence",
    "source_url":"verification_source","confidence":"verification_confidence","checked_date":"verification_date"})

df = base.merge(vstat, on="facility_id", how="left").merge(
    res[["facility_id","verification_status","confirmed_lat","confirmed_lon",
         "verification_evidence","verification_source","verification_confidence",
         "verification_date","verification_method"]], on="facility_id", how="left")

df["original_lat"] = df["latitude"]
df["original_lon"] = df["longitude"]
mask = df["verification_status"].isin(["VERIFIED","CANDIDATE"]) & df["confirmed_lat"].notna()
df.loc[mask, "latitude"] = df.loc[mask, "confirmed_lat"]
df.loc[mask, "longitude"] = df.loc[mask, "confirmed_lon"]
df["verification_status"] = df["verification_status"].fillna("pending")
df.to_csv("data/processed/datacenters_final.csv", index=False)

print("datacenters_final.csv written:", len(df), "rows")
print("coordinates updated to a confirmed on-building point:", int(mask.sum()))
print("\nverification_status counts:")
print(df["verification_status"].value_counts().to_string())
