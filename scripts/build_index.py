"""Build the processed dataset from data/raw.

Usage:
    uv run python scripts/build_index.py
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from dataclasses import asdict

from recipebot.config import get_settings, use_utf8_console
from recipebot.data.pipeline import build
from recipebot.engines.search import SearchIndex
from recipebot.engines.store import RecipeStore


def main() -> int:
    use_utf8_console()
    settings = get_settings()
    print(f"Building from {settings.raw_dir} ...")
    report = build(settings.raw_dir, settings.processed_dir, settings.config_dir)
    print(json.dumps(asdict(report), indent=2))

    print("Building the BM25 search index ...")
    started = time.perf_counter()
    index_dir = settings.processed_dir / "bm25"
    shutil.rmtree(index_dir, ignore_errors=True)
    store = RecipeStore.load(settings.processed_dir, settings.config_dir)
    SearchIndex.load_or_build(store, index_dir)
    print(f"Search index ready in {time.perf_counter() - started:.0f}s")
    print(f"Wrote {settings.processed_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
