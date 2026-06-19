"""Reverse-geocode coordinates to state/county via a Census TIGER spatial join.

Downloads (and caches) the public-domain TIGER/Line county shapefile, then
assigns each facility its containing county + state by point-in-polygon. This is
authoritative (geometry-derived) and lifts state/county coverage to ~100% within
CONUS.

Note: this fills *administrative* attributes only. It does NOT change
``geocode_precision`` — coordinate precision is a property of the coordinate, not
of which county it falls in.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point

from dcdata.schema import Facility

DEFAULT_COUNTY_URL = "https://www2.census.gov/geo/tiger/TIGER2024/COUNTY/tl_2024_us_county.zip"
USER_AGENT = "gmu-geoai-dc-dataset/0.1 (research)"

# FIPS state code -> USPS abbreviation (states + DC + territories).
STATEFP_TO_USPS = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO",
    "09": "CT", "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI",
    "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY",
    "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
    "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH",
    "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
    "54": "WV", "55": "WI", "56": "WY", "60": "AS", "66": "GU", "69": "MP",
    "72": "PR", "78": "VI",
}


class TigerReverseGeocoder:
    """Assign state/county to facilities via a TIGER county point-in-polygon join."""

    def __init__(self, county_url: str = DEFAULT_COUNTY_URL, cache_dir: str = "data/raw/tiger") -> None:
        self.county_url = county_url
        self.cache_dir = Path(cache_dir)

    def _county_shapefile(self) -> Path:
        """Return the path to the extracted county .shp, downloading if needed."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        existing = list(self.cache_dir.glob("*county*.shp"))
        if existing:
            return existing[0]
        zip_path = self.cache_dir / Path(self.county_url).name
        if not zip_path.exists():
            with requests.get(
                self.county_url, stream=True, timeout=300, headers={"User-Agent": USER_AGENT}
            ) as r:
                r.raise_for_status()
                with open(zip_path, "wb") as fh:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        fh.write(chunk)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(self.cache_dir)
        shps = list(self.cache_dir.glob("*county*.shp"))
        if not shps:
            raise FileNotFoundError("TIGER county shapefile not found after extraction")
        return shps[0]

    def load(self) -> gpd.GeoDataFrame:
        """Load the county layer (STATEFP, county NAME, GEOID) in WGS84."""
        gdf = gpd.read_file(self._county_shapefile())
        return gdf[["STATEFP", "NAME", "GEOID", "geometry"]].to_crs("EPSG:4326")

    def assign(self, facilities: list[Facility], counties: gpd.GeoDataFrame | None = None) -> dict:
        """Fill state/county on each facility from its containing county polygon.

        Returns stats about how many were filled and any disagreements with the
        state already present from the source (a useful coordinate-error signal).
        """
        if not facilities:
            return {"reverse_geocoded_state": 0, "reverse_geocoded_county": 0,
                    "admin_conflicts_with_source": 0, "points_outside_any_county": 0}

        gdf = counties if counties is not None else self.load()
        pts = gpd.GeoDataFrame(
            {"i": list(range(len(facilities)))},
            geometry=[Point(f.longitude, f.latitude) for f in facilities],
            crs="EPSG:4326",
        )
        joined = gpd.sjoin(pts, gdf, how="left", predicate="within").drop_duplicates(subset="i")

        filled_state = filled_county = conflicts = unmatched = 0
        for rec in joined.to_dict("records"):
            f = facilities[int(rec["i"])]
            statefp = rec.get("STATEFP")
            if statefp is None or (isinstance(statefp, float) and pd.isna(statefp)):
                unmatched += 1
                continue
            usps = STATEFP_TO_USPS.get(str(statefp).zfill(2))
            county = rec.get("NAME")
            if usps:
                if f.state and f.state != usps:
                    conflicts += 1
                f.state = usps
                filled_state += 1
            if isinstance(county, str) and county:
                f.county = county
                filled_county += 1
        return {
            "reverse_geocoded_state": filled_state,
            "reverse_geocoded_county": filled_county,
            "admin_conflicts_with_source": conflicts,
            "points_outside_any_county": unmatched,
        }
