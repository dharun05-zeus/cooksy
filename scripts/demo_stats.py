"""Answer the assignment's example statistics questions straight from the data.

Usage:
    uv run python scripts/demo_stats.py
"""

from __future__ import annotations

import sys
import time

from recipebot.config import get_settings, use_utf8_console
from recipebot.engines import stats
from recipebot.engines.stats import RecipeFilter
from recipebot.engines.store import RecipeStore


def show(question: str, result: stats.StatsResult) -> None:
    print("=" * 100)
    print(f"Q: {question}")
    print(result.explain())


def main() -> int:
    use_utf8_console()
    settings = get_settings()
    started = time.perf_counter()
    store = RecipeStore.load(settings.processed_dir, settings.config_dir)
    print(f"Loaded {store.n:,} records in {time.perf_counter() - started:.1f}s")

    both = RecipeFilter(include_all=["garlic", "onion"])
    show("How many recipes contain both garlic and onion? What percentage of the dataset is that?",
         stats.percentage(store, both))
    show("Same question, counting garlic and onion products too (garlic powder, green onion...)",
         stats.percentage(store, both.model_copy(update={"match_mode": "broad"})))
    show("Among recipes containing tomato, which five have the fewest instruction steps?",
         stats.rank_by_steps(store, RecipeFilter(include_all=["tomato"]), k=5))
    show("What are the most common ingredients (excluding staples)?",
         stats.top_ingredients(store, RecipeFilter(), k=10, exclude_staples=True))
    show("What is the average and median number of ingredients per recipe?",
         stats.ingredient_count_stats(store, RecipeFilter()))
    show("How many penne recipes have no dairy?",
         stats.count(store, RecipeFilter(title_contains=["penne"], exclude=["dairy"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
