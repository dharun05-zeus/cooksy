"""Download the Recipe Box dataset and extract its three JSON files into data/raw.

Usage:
    uv run python scripts/download_data.py              # download from eightportions.com
    uv run python scripts/download_data.py --zip PATH   # use a copy you already have

The site may refuse automated downloads (HTTP 403). Then download recipes_raw.zip in a
browser from DATASET_PAGE and pass it with --zip; the checksum is verified either way.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from recipebot.config import get_settings, use_utf8_console
from recipebot.data.loader import SOURCE_FILES

DATASET_URL = "https://eightportions.com/recipes_raw.zip"
DATASET_PAGE = "https://eightportions.com/datasets/Recipes/"
# SHA-256 of recipes_raw.zip (53,355,492 bytes) as published, checked on 2026-11-06.
EXPECTED_SHA256 = "1ae20f3260313d501edf23c22c6f1875e87917f5a8e2ff13b40450719322c81b"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, target: Path) -> bool:
    """Download to a temporary file and rename it when complete, so an interrupted download
    is never mistaken for the dataset. Returns False (with instructions) if it fails."""
    print(f"Downloading {url} ...")
    partial = target.with_suffix(".part")
    try:
        with urllib.request.urlopen(url, timeout=60) as response, partial.open("wb") as out:
            shutil.copyfileobj(response, out)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        partial.unlink(missing_ok=True)
        reason = f"HTTP {exc.code}" if isinstance(exc, urllib.error.HTTPError) else str(exc)
        print(f"\nThe automatic download failed ({reason}); the site may refuse automated "
              "downloads.\nDownload it in a browser instead:\n"
              f"  1. open {DATASET_PAGE} and download recipes_raw.zip (about 53 MB)\n"
              "  2. run:  uv run python scripts/download_data.py --zip PATH/TO/recipes_raw.zip")
        return False
    partial.replace(target)
    return True


def extract(zip_path: Path, raw_dir: Path) -> None:
    wanted = set(SOURCE_FILES.values()) | {"LICENSE"}
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.namelist():
            name = Path(member).name
            # Extract only the files we expect, by name, so the archive cannot write elsewhere.
            if name in wanted:
                with archive.open(member) as src, (raw_dir / name).open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                print(f"  extracted {name}")


def main() -> int:
    use_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", type=Path, help="local copy of recipes_raw.zip")
    parser.add_argument("--skip-checksum", action="store_true")
    args = parser.parse_args()

    raw_dir = get_settings().raw_dir
    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path = raw_dir / "recipes_raw.zip"

    if args.zip:
        shutil.copyfile(args.zip, zip_path)
    elif not zip_path.exists() and not download(DATASET_URL, zip_path):
        return 2

    if not args.skip_checksum:
        actual = sha256_of(zip_path)
        if actual != EXPECTED_SHA256:
            print(f"Checksum mismatch: expected {EXPECTED_SHA256}, got {actual}.")
            print("The file may be corrupt or the dataset changed. Use --skip-checksum to proceed.")
            return 1
        print("Checksum OK.")

    extract(zip_path, raw_dir)
    missing = [f for f in SOURCE_FILES.values() if not (raw_dir / f).exists()]
    if missing:
        print(f"Missing after extraction: {missing}")
        return 1
    print(f"Dataset ready in {raw_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
