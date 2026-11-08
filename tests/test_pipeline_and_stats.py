"""End-to-end checks on a hand-built 9-record dataset whose answers were worked out by hand.

Records: a1 garlic+onion soup, a2 empty, a3 penne with cream, e1 penne with garlic and
canned tomatoes, e2 no ingredients, e3 peanut noodles with green onion, f1 tomato salad
(one-paragraph instructions), f2 exact duplicate of f1, f3 margarine cookies.
Complete recipes: a1, a3, e1, e3, f1, f2, f3 = 7.
"""

import json

import pytest

from recipebot.engines import stats
from recipebot.engines.stats import RecipeFilter


def test_build_report_counts(built_dir):
    report = json.loads((built_dir / "build_report.json").read_text())
    assert report["total_records"] == 9
    assert report["empty_records"] == 1
    assert report["no_ingredients"] == 1
    assert report["complete_recipes"] == 7
    assert report["exact_duplicates"] == 1
    assert report["header_lines"] == 2


def test_line_numbers_match_the_displayed_list(store):
    # f1 starts with the heading "For the dressing:", so its tomato line is display line 3
    display = store.display_ingredients("fn:f1")
    lines = store.lines(["fn:f1"])
    tomato = lines[lines["base"] == "tomato"].iloc[0]
    assert display[int(tomato["line_no"])] == "2 large tomatoes, sliced"


def test_originals_are_preserved(store):
    row = store.get("ar:a1")
    assert row["title"] == "Garlic Onion Soup"
    assert list(row["ingredients_raw"])[0] == "2 cloves garlic, minced ADVERTISEMENT"
    assert row["instructions_raw"].startswith("Chop the vegetables.")


def test_garlic_and_onion_count_and_percentage(store):
    result = stats.percentage(store, RecipeFilter(include_all=["garlic", "onion"]))
    assert (result.numerator, result.denominator, result.value) == (1, 7, pytest.approx(14.29))
    assert result.sample_ids == ["ar:a1"]


def test_strict_vs_broad_onion(store):
    strict = stats.count(store, RecipeFilter(include_all=["onion"]))
    broad = stats.count(store, RecipeFilter(include_all=["onion"], match_mode="broad"))
    assert strict.value == 3  # a1, f1, f2 (red onion is an onion variety)
    assert broad.value == 4  # + e3 green onion


def test_fewest_steps_with_tomato(store):
    result = stats.rank_by_steps(store, RecipeFilter(include_all=["tomato"]), k=5)
    assert [r["recipe_id"] for r in result.rows] == ["fn:f1", "fn:f2", "epi:e1"]
    assert [r["steps"] for r in result.rows] == [3, 3, 4]
    assert result.rows[0]["counted_by"] == "sentence"


def test_exclude_dairy_removes_uncertain_too(store):
    result = stats.count(store, RecipeFilter(exclude=["dairy"]))
    # a3 contains cream; f3 has margarine (uncertain) → both removed
    assert result.value == 5
    assert any("uncertain" in note for note in result.notes)


def test_penne_without_dairy(store):
    result = stats.count(store, RecipeFilter(title_contains=["penne"], exclude=["dairy"]))
    assert result.sample_ids == ["epi:e1"]


def test_exclude_peanuts_is_broad(store):
    result = stats.count(store, RecipeFilter(exclude=["peanuts"]))
    assert "epi:e3" not in result.sample_ids
    assert result.value == 6


def test_ingredient_count_stats(store):
    result = stats.ingredient_count_stats(store, RecipeFilter())
    assert result.rows[0]["mean"] == pytest.approx(24 / 7, abs=0.01)
    assert result.rows[0]["median"] == 3


def test_duplicates_can_be_removed(store):
    result = stats.count(store, RecipeFilter(include_all=["tomato"], exclude_duplicates=True))
    assert result.value == 2


def test_unknown_ingredient_says_so(store):
    result = stats.count(store, RecipeFilter(include_all=["dragonfruit"]))
    assert result.value == 0
    assert any("does not appear" in note for note in result.notes)
