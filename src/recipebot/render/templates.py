"""Plain-text answers built only from engine results, so every fact shown comes from data."""

from __future__ import annotations

from recipebot.data.models import SOURCE_NAMES
from recipebot.engines.matching import MatchedRecipe, MatchResult
from recipebot.engines.search import SearchResult
from recipebot.engines.stats import StatsResult
from recipebot.engines.store import RecipeStore
from recipebot.engines.substitution import RANKING_RULE, SubstitutionResult
from recipebot.nlp.steps import instruction_lines, split_sentences


def _constraints_footer(constraints: str) -> list[str]:
    return [f"Active constraints: {constraints}."] if constraints else []


def render_search(result: SearchResult, store: RecipeStore, constraints: str) -> str:
    if not result.hits:
        lines = [f"No recipes found for '{result.query}'"
                 + (" that satisfy your constraints." if constraints else ".")]
        lines += [f"Note: {n}" for n in result.notes]
        return "\n".join(lines + _constraints_footer(constraints))
    lines = [f"{result.total_matches:,} recipes share at least one word with '{result.query}'"
             + (" and satisfy your constraints" if constraints else "")
             + f". The {len(result.hits)} most relevant:"]
    for i, hit in enumerate(result.hits, 1):
        lines.append(f"\n{i}. {hit.title}  [{hit.recipe_id}]")
        lines.append(f"   {hit.ingredient_count} ingredients, {hit.steps} steps; "
                     f"matched: {', '.join(hit.matched_terms) or '-'}")
        if hit.evidence:
            ingredients = store.display_ingredients(hit.recipe_id)
            lines.append("   Evidence: " + "; ".join(hit.evidence))
            lines.append("   Ingredients: " + "; ".join(ingredients[:12])
                         + (" ..." if len(ingredients) > 12 else ""))
    if result.filters:
        lines.append("\nFilters applied to the whole dataset: " + "; ".join(result.filters))
    lines += [f"Note: {n}" for n in result.notes]
    lines.append("Ask for 'the first one' (or any number) to see its full recipe.")
    return "\n".join(lines + _constraints_footer(constraints))


def render_recipe(store: RecipeStore, recipe_id: str, show: list[str]) -> str:
    row = store.get(recipe_id)
    if row is None:
        return f"Recipe {recipe_id} is not in the dataset."
    show = show or ["ingredients", "instructions"]
    source = SOURCE_NAMES.get(row["source"], row["source"])
    lines = [f"{row['title']}  [{recipe_id}]  (source: {source})"]
    if "ingredients" in show:
        lines.append("\nIngredients (as listed in the dataset):")
        lines += [f"  - {x}" for x in store.display_ingredients(recipe_id)]
    if "instructions" in show:
        steps = instruction_lines(row["instructions_raw"], store.lexicon.boilerplate_res)
        if row["steps_method"] == "sentence" and steps:
            steps = split_sentences(steps[0])
        lines.append(f"\nInstructions ({row['steps']} steps, counted by {row['steps_method']}):")
        lines += [f"  {i}. {s}" for i, s in enumerate(steps, 1)]
    lines.append("\nNot in the dataset: cooking times, servings and nutrition are not recorded, "
                 "so they are not shown.")
    return "\n".join(lines)


def render_stats(result: StatsResult, session_constraints: str) -> str:
    text = result.explain()
    if session_constraints:
        text += (f"\nNote: your active constraints ({session_constraints}) were not applied "
                 "to this statistic; ask for them explicitly if you want them included.")
    return text


def _matched_block(i: int, m: MatchedRecipe) -> list[str]:
    lines = [f"\n{i}. {m.title}  [{m.recipe_id}]",
             f"   Why here: {m.reason}",
             f"   Matched: {', '.join(m.matched) or '-'}",
             f"   Extra required: {', '.join(m.extra_required) or 'none'}"]
    if m.unused:
        lines.append(f"   Not used from your list: {', '.join(m.unused)}")
    if m.staples_used:
        lines.append(f"   Staples assumed available: {', '.join(m.staples_used)}")
    if m.steps_method == "sentence":
        lines.append("   (steps counted as sentences: instructions are one paragraph)")
    lines += [f"   Quantity: {q}" for q in m.quantity_notes]
    lines += [f"   Form: {f}" for f in m.form_notes]
    lines += [f"   VIOLATES: {v}" for v in m.violations]
    return lines


EVIDENCE_TYPES = ("Direct evidence: a recipe explicitly offers the ingredient as an alternative. "
                  "Indirect evidence: a related recipe uses it without the removed ingredient "
                  "but does not call it a replacement. The two are not equivalent.")


def render_substitution(result: SubstitutionResult, chosen_by: str) -> str:
    ev = result.evidence
    lines = [f"Adapting: {result.title}  [{result.recipe_id}]"]
    if not ev.target_lines:
        return "\n".join(lines + [result.message])
    lines.append("Removing: " + "; ".join(text for _, text in ev.target_lines))
    for name, roles in ev.roles.items():
        if roles:
            dish = "baked dish" if ev.baked else "dish"
            lines.append(f"Roles of {name} in this {dish} (general cooking knowledge): "
                         + ", ".join([f"{roles[0]} (main)", *roles[1:]]))
    lines.append("Restrictions respected: " + ", ".join(f"no {r}" for r in ev.restricted))
    if result.original_ingredients:
        lines.append("Original ingredients: " + "; ".join(result.original_ingredients))

    lines.append("\nCandidates from the dataset, ranked (evidence strength and role fit are "
                 "rated separately):")
    if ev.candidates:
        for i, c in enumerate(ev.candidates, 1):
            q = c.quantity
            lines.append(f"  {i}. {c.name}: evidence {c.strength} ({c.evidence_type()}); "
                         f"role fit {c.fit} ({c.coverage_text()}); quantity {q.status}"
                         + (f" ({q.text})" if q.text else ""))
            for s in c.supporting[:3]:
                line = f": \"{s['line']}\"" if s["line"] else ""
                lines.append(f"       {s['kind']}: {s['title']} [{s['id']}]{line}")
            lines.append(f"       limitation: {c.limitation()}")
    else:
        lines.append("  none found")
    lines.append(f"  Compared {ev.comparison_scope or f'{ev.neighbours} similar recipes'}; "
                 f"{ev.neighbours_without} of them have no {ev.target}.")
    if ev.same_dish_without:
        lines.append(f"  Versions of this dish in the dataset made without {ev.target}: "
                     + "; ".join(f"{title} [{rid}]" for rid, title in ev.same_dish_without))
    for rid, sentence in ev.notes:
        lines.append(f"  Instruction note: \"{sentence[:160]}\"  [{rid}]")
    lines.append(f"  {EVIDENCE_TYPES}")
    if ev.ranking_notes:
        lines.append(f"\nRanking rules: {RANKING_RULE}.")
        lines += [f"  - {note}" for note in ev.ranking_notes]
    if ev.expected_effects:
        lines.append(f"\nExpected trade-offs of removing {ev.target} (predictions from its role, "
                     "not dataset facts):")
        lines += [f"  - {effect}" for effect in ev.expected_effects]

    if result.message:
        lines += ["", f"Adaptation status: {result.status_label}.", result.message]
        lines += [f"Uncertainty: {u}" for u in ev.uncertainty]
        return "\n".join(lines)
    adapted, chosen = result.adapted, result.chosen
    if adapted is None or chosen is None:
        return "\n".join(lines + ["", "No adapted recipe is produced."])
    q = chosen.quantity
    lines += ["", f"Adaptation status: {result.status_label}.",
              f"Selected replacement: {chosen.name} (evidence {chosen.strength}, role fit "
              f"{chosen.fit}), selected by {chosen_by}.",
              f"Replacement quantity ({q.status}): " + (f"{q.text}; " if q.text else "") + q.basis]
    if result.status == "incomplete":
        lines.append(f"This is an incomplete experimental adaptation: the {chosen.name} amount "
                     "is not established, so the list below is not a complete recipe.")
    lines.append("\nAdapted ingredients (* = changed):")
    original = {line.strip() for line in result.original_ingredients}
    for line in adapted.ingredients:
        lines.append(f"  {' ' if line.strip() in original else '*'} {line}")
    lines.append("\nAdapted instructions:")
    lines += [f"  {i}. {s}" for i, s in enumerate(adapted.instructions, 1)]
    lines.append("Baking (from the original recipe, not re-tested): "
                 + (result.baking or "not given in the recipe"))
    if adapted.changes:
        lines.append("\nChanges:")
        lines += [f"  - {c}" for c in adapted.changes]
    if result.moisture and result.moisture.notes:
        lines.append(f"\nMoisture check (risk: {result.moisture.risk}):")
        lines += [f"  - {n}" for n in result.moisture.notes]
    if result.texture:
        lines.append("\nPredicted texture changes (predictions, not verified by the dataset):")
        lines += [f"  - {prop}: {text}" for prop, text in result.texture]
    if result.remaining_conflicts:
        lines.append("\nWARNING: other ingredients in this recipe still break your restrictions "
                     "and were not replaced: " + "; ".join(result.remaining_conflicts)
                     + ". Ask me to replace them too.")
    if result.limitations:
        lines.append("\nLimitations:")
        lines += [f"  - {x}" for x in result.limitations]
    if chosen.strength in ("weak", "conflicting", "none"):
        lines.append(f"\nCaution: the evidence for {chosen.name} is {chosen.strength}; "
                     "treat this adaptation as untested.")
    if result.validation_errors:
        lines.append("Note: some LLM step rewrites were not used ("
                     + "; ".join(result.validation_errors[:2]) + "); those steps use the "
                     "rule-based rewrite.")
    lines.append("This is not a guarantee that the dish is safe for an allergy.")
    return "\n".join(lines)


def render_match(result: MatchResult, constraints: str) -> str:
    lines = [f"Your ingredients (as understood): {', '.join(result.pantry) or 'none'}"]
    if result.no_match:
        lines.append(f"No eligible recipe found: none of the {result.candidates:,} recipes "
                     "using your ingredients satisfies every constraint.")
        if result.alternatives:
            lines.append("\nClosest alternatives. Each one BREAKS a constraint, as marked:")
            for i, m in enumerate(result.alternatives, 1):
                lines += _matched_block(i, m)
    else:
        lines.append(f"{result.eligible:,} of {result.candidates:,} recipes using your "
                     f"ingredients satisfy your constraints. Top {len(result.results)}:")
        for i, m in enumerate(result.results, 1):
            lines += _matched_block(i, m)
    lines.append(f"\nRanking rule: {result.ranking_rule}.")
    if result.filters:
        lines.append("Hard constraints applied before ranking: " + "; ".join(result.filters))
    lines += [f"Note: {n}" for n in result.notes]
    return "\n".join(lines + _constraints_footer(constraints))
