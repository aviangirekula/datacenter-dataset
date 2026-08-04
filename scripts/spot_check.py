"""Print facilities with links so a human can verify our numbers independently.

Every other check in this repository is one I wrote checking work I wrote. This
one is different: it prints our value beside a link to the authority's own public
website, so a person can open the link and compare with their own eyes. Nothing
here asks the reader to trust the pipeline.

    ./.venv/bin/python scripts/spot_check.py             # 5 random facilities
    ./.venv/bin/python scripts/spot_check.py --n 10
    ./.venv/bin/python scripts/spot_check.py --state CA
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
P = REPO / "data" / "processed"
SEED = 7


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--state", help="restrict to one state, e.g. CA")
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    haz = pd.read_csv(P / "hazard_exposure.csv", low_memory=False)
    bld = pd.read_csv(P / "building_attributes.csv", low_memory=False)
    df = haz.merge(
        bld[["facility_id", "building_match", "building_dist_m", "footprint_sqft",
             "height_m", "flood_zone", "flood_sfha", "building_address"]],
        on="facility_id", how="left")
    if args.state:
        df = df[df["state"] == args.state.upper()]
    if df.empty:
        raise SystemExit("no facilities match")

    sample = df.sample(n=min(args.n, len(df)), random_state=args.seed)

    for _, r in sample.iterrows():
        lat, lon = float(r["latitude"]), float(r["longitude"])
        print("=" * 78)
        print(f"{r['name']}  ({r['state']})")
        if isinstance(r.get("building_address"), str):
            print(f"  building address on file : {r['building_address']}")
        print(f"  our coordinate           : {lat:.5f}, {lon:.5f}")
        print()
        print("  WHAT WE SAY")
        print(f"    earthquake, 2475 yr PGA : {r.get('haz_seismic_pga_g_2475yr_usgs')} g")
        print(f"    Ss (0.2 s) / S1 (1 s)   : {r.get('haz_seismic_sa_02s_g')} / "
              f"{r.get('haz_seismic_sa_1s_g')} g")
        print(f"    FEMA flood zone         : {r.get('flood_zone')}   "
              f"in regulatory floodplain: {r.get('flood_sfha')}")
        print(f"    lightning               : "
              f"{r.get('haz_lightning_flash_per_km2_yr'):.1f} flashes/km2/yr"
              if pd.notna(r.get("haz_lightning_flash_per_km2_yr")) else "")
        wf = r.get("haz_wildfire_max_severity_1000m")
        print(f"    wildfire within 1 km    : "
              f"{'class ' + str(int(wf)) if pd.notna(wf) else 'none nearby'}"
              f"   (4 = High, 5 = Very High)")
        bm = r.get("building_match")
        fp = r.get("footprint_sqft")
        hm = r.get("height_m")
        print(f"    building match          : {bm}"
              + (f", {fp:,.0f} sq ft" if pd.notna(fp) else "")
              + (f", {hm:.1f} m tall" if pd.notna(hm) else ", height unknown"))
        print()
        print("  CHECK IT YOURSELF")
        print("    Is the coordinate on the right building?")
        print(f"      https://www.google.com/maps/@{lat},{lon},18z/data=!3m1!1e3")
        print("    Does USGS report the same ground motion?")
        print(f"      https://www.usgs.gov/programs/earthquake-hazards/"
              f"seismic-design-maps  (enter {lat:.5f}, {lon:.5f},"
              f" ASCE 7-22, Risk Category III, Site Class BC)")
        print("    Does FEMA report the same flood zone?")
        print(f"      https://msc.fema.gov/portal/search?AddressQuery="
              f"{lat:.5f}%2C{lon:.5f}")
        print("    Is there really wildfire-prone land nearby?")
        print(f"      https://wildfirerisk.org/explore/  (search {lat:.5f}, {lon:.5f})")
        print()

    print("=" * 78)
    print("If the coordinate is on the right building, and USGS and FEMA report")
    print("what we report, the pipeline is doing what it claims. If any of them")
    print("disagree, that is a real defect worth chasing.")


if __name__ == "__main__":
    main()
