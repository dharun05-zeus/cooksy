"""Read the three Recipe Box JSON files."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from recipebot.data.models import RawRecipe

SOURCE_FILES: dict[str, str] = {
    "ar": "recipes_raw_nosource_ar.json",
    "epi": "recipes_raw_nosource_epi.json",
    "fn": "recipes_raw_nosource_fn.json",
}


def iter_raw_recipes(raw_dir: Path) -> Iterator[RawRecipe | tuple[str, str]]:
    """Yield every record from all three files.

    Empty records (the dataset has a few hundred `{}` entries) are yielded as
    `(source, key)` so the build can count them instead of silently dropping them.
    """
    for source, filename in SOURCE_FILES.items():
        path = raw_dir / filename
        if not path.exists():
            raise FileNotFoundError(
                f"{path} is missing. Run `uv run python scripts/download_data.py` first."
            )
        records = json.loads(path.read_text(encoding="utf-8"))
        for key, record in records.items():
            if not isinstance(record, dict) or not record:
                yield (source, key)
                continue
            yield RawRecipe(
                source=source,
                source_key=key,
                title=record.get("title"),
                ingredients=record.get("ingredients"),
                instructions=record.get("instructions"),
            )
