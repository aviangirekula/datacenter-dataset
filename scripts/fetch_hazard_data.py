"""Download and verify the raw hazard layers.

Every layer is recorded here with its canonical URL, byte size, checksum,
version, licence and target path, so the exposure table can be regenerated from
scratch by an independent researcher. Checksums are verified after download and
a mismatch is a hard failure.

    ./.venv/bin/python scripts/fetch_hazard_data.py            # fetch missing
    ./.venv/bin/python scripts/fetch_hazard_data.py --verify   # check only

Total download is about 1.3 GB; about 2.8 GB on disk after extraction.
Requires ``zstd`` for the Zenodo archive (``brew install zstd`` /
``apt install zstd``).
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parents[1]
DEST = REPO / "data" / "hazards"

# Access date for every layer below. Update when re-fetched.
ACCESSED = "2026-07-29"

LAYERS = [
    {
        "key": "mhtran_archive",
        "title": "MHTran processed multi-hazard data archive (supplies the "
                 "LIS/OTD lightning raster used here)",
        "citation": "Oughton, E. J., & Weigel, R. (2026). A Comparative "
                    "Multi-Hazard Risk Assessment of the US High-Voltage "
                    "Transmission Network (v1) [Data set]. Zenodo.",
        "doi": "10.5281/zenodo.20331026",
        "licence": "CC BY 4.0",
        "url": "https://zenodo.org/records/20331026/files/multi_hazard_data.tar.zst",
        "archive": DEST / "multi_hazard_data.tar.zst",
        "bytes": 928_677_951,
        "md5": "524e3f3576c226fc48a865b532ba7b3c",
        "extract": ["tar", "--use-compress-program=unzstd", "-xf"],
        "extract_into": DEST,
        "check_path": DEST / "data" / "hotspots" / "lightning_annual_rate_4326.tif",
        "note": "Only lightning_annual_rate_4326.tif is used. That file is a "
                "third-party reprojection of the NASA LIS/OTD climatology; the "
                "upstream NASA product should be cited alongside this archive.",
    },
    {
        "key": "seismic_pga",
        "title": "USGS NSHM 2023 uniform-hazard PGA maps, site class BC "
                 "(Vs30 760 m/s), 2%/5%/10% in 50 years",
        "citation": "Petersen, M. D., et al. (2023). 2023 US National Seismic "
                    "Hazard Model. US Geological Survey data release.",
        "doi": "10.5066/P9GNPCOD",
        "licence": "US Government public domain",
        "url": "https://www.sciencebase.gov/catalog/file/get/64ff886dd34ed30c2057b4d9"
               "?f=__disk__76%2Ff4%2Fb4%2F76f4b416aadf6f70680106a36acc31714473b4ff",
        "archive": DEST / "seismic" / "US_PGA_BC.zip",
        "bytes": 59_162_562,
        "md5": "bf67f42ad8ba4958460c121d75ba8609",
        "extract": ["unzip", "-o", "-q"],
        "extract_into": DEST / "seismic" / "pga_bc",
        "check_path": DEST / "seismic" / "pga_bc" / "US_PGA_10Pct50Yrs_BC_poly.shp",
        "note": "Source filename US_PGA_2Pct_5Pct_10Pct_50Yrs_BC.zip; one of 11 "
                "files on ScienceBase item 64ff886dd34ed30c2057b4d9. The item "
                "page rejects plain fetchers, hence the direct hashed file URL.",
    },
    {
        "key": "wildfire_whp",
        "title": "USFS Wildfire Hazard Potential for the United States, 270 m, "
                 "version 2023, 4th edition",
        "citation": "Dillon, G. K. (2023). Wildfire Hazard Potential for the "
                    "United States (270-m), version 2023, 4th Edition. Forest "
                    "Service Research Data Archive.",
        "doi": "10.2737/RDS-2015-0047-4",
        "licence": "US Government public domain",
        "url": "https://www.fs.usda.gov/rds/archive/products/RDS-2015-0047-4/"
               "RDS-2015-0047-4_Data.zip",
        "archive": DEST / "wildfire" / "WHP2023.zip",
        "bytes": 368_424_961,
        "md5": "0f9031e7223c7a1551c6c95c41450863",
        "extract": ["unzip", "-o", "-q"],
        "extract_into": DEST / "wildfire" / "whp",
        "check_path": DEST / "wildfire" / "whp" / "Data" / "whp2023_GeoTIF"
                      / "whp2023_cls_conus.tif",
        "note": "Source filename RDS-2015-0047-4_Data.zip.",
    },
]


def md5sum(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def verify(layer: dict) -> bool:
    ok = True
    ar, cp = layer["archive"], layer["check_path"]
    if cp.exists():
        print(f"  [present] {layer['key']}: {cp.relative_to(REPO)}")
    else:
        print(f"  [MISSING] {layer['key']}: expected {cp.relative_to(REPO)}")
        ok = False
    if ar.exists():
        size = ar.stat().st_size
        if size != layer["bytes"]:
            print(f"  [SIZE MISMATCH] {ar.name}: {size} != {layer['bytes']}")
            ok = False
        if layer["md5"]:
            got = md5sum(ar)
            status = "ok" if got == layer["md5"] else "MISMATCH"
            print(f"  [md5 {status}] {ar.name}: {got}")
            ok = ok and status == "ok"
    return ok


def fetch(layer: dict) -> None:
    ar = layer["archive"]
    ar.parent.mkdir(parents=True, exist_ok=True)
    if layer["check_path"].exists():
        print(f"  [skip] {layer['key']} already extracted")
        return
    if not ar.exists():
        print(f"  [get]  {layer['key']} -> {ar.relative_to(REPO)}")
        with requests.get(layer["url"], stream=True, timeout=120,
                          headers={"User-Agent": "datacenter-dataset/0.1"}) as r:
            r.raise_for_status()
            with open(ar, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
    if layer["md5"]:
        got = md5sum(ar)
        if got != layer["md5"]:
            raise SystemExit(f"checksum mismatch for {ar}: {got} != {layer['md5']}")
        print(f"  [md5]  verified {ar.name}")
    dest = layer["extract_into"]
    dest.mkdir(parents=True, exist_ok=True)
    cmd = [*layer["extract"], str(ar)]
    cmd += ["-d", str(dest)] if layer["extract"][0] == "unzip" else []
    print(f"  [tar]  extracting into {dest.relative_to(REPO)}")
    subprocess.run(cmd, check=True, cwd=dest if layer["extract"][0] != "unzip" else None)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="verify only, do not download")
    args = ap.parse_args()

    print(f"Hazard layers (accessed {ACCESSED}), destination {DEST.relative_to(REPO)}\n")
    all_ok = True
    for layer in LAYERS:
        print(f"{layer['key']}: {layer['title']}")
        print(f"  DOI {layer['doi']}  licence {layer['licence']}")
        if args.verify:
            all_ok &= verify(layer)
        else:
            fetch(layer)
        print()
    if args.verify and not all_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
