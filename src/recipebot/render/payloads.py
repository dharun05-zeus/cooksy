"""Engine results as plain dicts (JSON) for the web UI. Same facts as the text templates."""

from __future__ import annotations

from recipebot.data.models import SOURCE_NAMES
from recipebot.engines.matching import MatchedRecipe, MatchResult
from recipebot.engines.search import SearchResult
from recipebot.engines.stats import StatsResult
from recipebot.engines.store import RecipeStore
from recipebot.engines.substitution import RANKING_RULE, SubstitutionResult
from recipebot.nlp.steps import instruction_lines, split_sentences
from recipebot.render.templates import EVIDENCE_TYPES, substitution_summary


def recipe(store: RecipeStore, recipe_id: str) -> dict | None:
    row = store.get(recipe_id)
    if row is None:
        return None
    steps = instruction_lines(row["instructions_raw"], store.lexicon.boilerplate_res)
    if row["steps_method"] == "sentence" and steps:
        steps = split_sentences(steps[0])
    return {
        "id": recipe_id,
        "title": row["title"],
        "source": SOURCE_NAMES.get(row["source"], row["source"]),
        "ingredients": store.display_ingredients(recipe_id),
        "steps": steps,
        "steps_method": row["steps_method"],
        "allergens": list(row["allergens"]),
        "allergens_uncertain": list(row["allergens_uncertain"]),
    }


def search(result: SearchResult, store: RecipeStore) -> dict:
    return {
        "type": "search",
        "query": result.query,
        "total": result.total_matches,
        "filters": result.filters,
        "notes": result.notes,
        "results": [
            {"id": h.recipe_id, "title": h.title, "steps": h.steps,
             "ingredient_count": h.ingredient_count, "matched_terms": h.matched_terms,
             "evidence": h.evidence, "ingredients": store.display_ingredients(h.recipe_id)}
            for h in result.hits
        ],
    }


def _matched(m: MatchedRecipe) -> dict:
    return {"id": m.recipe_id, "title": m.title, "steps": m.steps,
            "steps_method": m.steps_method, "reason": m.reason, "matched": m.matched,
            "extra_required": m.extra_required, "unused": m.unused,
            "staples_used": m.staples_used, "quantity_notes": m.quantity_notes,
            "form_notes": m.form_notes, "violations": m.violations}


def match(result: MatchResult) -> dict:
    return {
        "type": "match",
        "pantry": result.pantry,
        "eligible": result.eligible,
        "candidates": result.candidates,
        "ranking_rule": result.ranking_rule,
        "filters": result.filters,
        "notes": result.notes,
        "no_match": result.no_match,
        "results": [_matched(m) for m in result.results],
        "alternatives": [_matched(m) for m in result.alternatives],
    }


def stats(result: StatsResult) -> dict:
    return {"type": "stats", **result.model_dump()}


def _quantity(q) -> dict:
    return {"status": q.status, "text": q.text, "basis": q.basis}


def substitution(result: SubstitutionResult, chosen_by: str) -> dict:
    """What the substitution card shows (app.js `substitutionCard`); the full text answer,
    with every detail, is sent alongside."""
    ev, adapted, chosen = result.evidence, result.adapted, result.chosen
    original = {line.strip() for line in result.original_ingredients}
    return {
        "type": "substitution",
        "summary": substitution_summary(result),
        "recipe": {"id": result.recipe_id, "title": result.title},
        "target": ev.target,
        "target_lines": [text for _, text in ev.target_lines],
        "original_ingredients": result.original_ingredients,
        "status": result.status,
        "chosen_by": chosen_by,
        "baking": result.baking,
        "adapted": None if adapted is None or chosen is None else {
            "substitute": chosen.name,
            "quantity": _quantity(chosen.quantity),
            "ingredients": [{"text": line, "changed": line.strip() not in original}
                            for line in adapted.ingredients],
            "instructions": adapted.instructions,
        },
        # why this choice
        "ranking_rule": RANKING_RULE,
        "ranking_notes": ev.ranking_notes,
        "uncertainty": ev.uncertainty,
        # evidence
        "candidates": [
            {"name": c.name, "strength": c.strength, "fit": c.fit, "direct": c.direct > 0,
             "support": c.support, "coverage_text": c.coverage_text(),
             "quantity": _quantity(c.quantity), "supporting": c.supporting,
             "limitation": c.limitation()}
            for c in ev.candidates
        ],
        "comparison_scope": ev.comparison_scope,
        "same_dish_without": [{"id": i, "title": t} for i, t in ev.same_dish_without],
        "notes": [{"id": i, "sentence": s} for i, s in ev.notes],
        "evidence_types": EVIDENCE_TYPES,
        # predictions and limits
        "texture": [{"property": p, "prediction": t} for p, t in result.texture],
        "moisture": None if result.moisture is None else {
            "risk": result.moisture.risk, "notes": result.moisture.notes},
        "expected_effects": ev.expected_effects,
        "limitations": result.limitations,
    }
