"""Plain-text answers built only from engine results, so every fact shown comes from data."""

from __future__ import annotations

from recipebot.data.models import SOURCE_NAMES
from recipebot.engines.matching import MatchedRecipe, MatchResult
from recipebot.engines.search import SearchResult
from recipebot.engines.stats import StatsResult
from recipebot.engines.store import RecipeStore
from recipebot.engines.substitution import RANKING_RULE, Candidate, Evidence, SubstitutionResult
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


# What each role does, in everyday words, for the short answer.
PLAIN_ROLE = {
    "binding": "hold the batter together", "leavening": "help it rise",
    "moisture": "keep it moist", "structure": "give it structure",
    "emulsification": "keep the batter smooth", "fat": "add fat and tenderness",
    "richness": "add richness", "thickening": "thicken it", "tenderness": "keep it tender",
    "flavor": "add flavor", "tang": "add tang", "sweetness": "sweeten it",
}


def _does(phrase: str) -> str:
    """ "hold the batter together" -> "holds the batter together"."""
    verb, _, rest = phrase.partition(" ")
    return f"{verb}s {rest}".strip()
CONFIDENCE = {"strong": "high", "moderate": "medium"}
HEADLINE = {"supported": "supported by the dataset", "experimental": "experimental",
            "incomplete": "experimental, amount unknown", "not_adapted": "no reliable swap found"}


def _amount(c: Candidate, short: bool = False) -> str:
    q = c.quantity
    if q.same_as_original:
        return "same amount" if short else "same amount as the original (the dataset offers this)"
    if q.status == "supported":
        return f"{q.text}" if short else f"{q.text} (amount from the dataset)"
    if q.status == "estimated":
        return f"about {q.text}, estimated" if short else f"about {q.text} (estimated)"
    return "amount unknown" if short else "the dataset doesn't say how much to use"


def _why(c: Candidate, ev: Evidence) -> str:
    if c.strength == "none":
        source = "you asked for it; no recipe in the dataset supports it"
    elif c.direct:
        source = (f"{c.direct} recipe{'s' if c.direct > 1 else ''} in the dataset offer it as an "
                  f"alternative to {ev.noun}")
    elif c.comparative_scope == "same dish":
        n = c.comparative_support
        source = (f"{'only ' if n == 1 else ''}{n} {ev.dish or 'similar'} recipe"
                  f"{'s' if n > 1 else ''} without {ev.target} use{'s' if n == 1 else ''} it")
    else:
        source = f"{c.comparative_support} similar recipes without {ev.target} use it"
    main = ev.main_roles[0] if ev.main_roles else ""
    how = c.coverage.get(main)
    role = PLAIN_ROLE.get(main, main)
    if how == "full":
        source += f", and it {_does(role)} like {ev.noun} does"
    elif how == "partial":
        source += f"; it only partly {_does(role)}"
    elif main and c.coverage:
        source += f", but it does not {role}"
    return source


def _expect(result: SubstitutionResult) -> str:
    ev, c, m = result.evidence, result.chosen, result.moisture
    parts = []
    if "leavening" in ev.all_roles and c.coverage.get("leavening") != "full":
        parts.append("less rise and a denser result")
    main = ev.main_roles[0] if ev.main_roles else ""
    if main == "binding" and c.coverage.get("binding") != "full":
        parts.append("it may crumble more")
    if main == "fat" and c.coverage.get("fat") != "full":
        parts.append("it may be less rich")
    if m and m.risk in ("high", "possible"):
        wetter = m.ratio is not None and m.baseline is not None and m.ratio > m.baseline
        parts.append(f"it may turn gummy: this recipe is already wetter than most {ev.dish} "
                     "recipes" if wetter else f"it may turn gummy if you add too much {c.name}")
    elif m and m.risk == "none" and "moisture" in ev.all_roles:
        parts.append("it may be drier")
    if not parts:
        parts = [f"{p.lower()}: {t}" for p, t in result.texture[:2]] or ["no change predicted"]
    text = "; ".join(parts)
    return text[0].upper() + text[1:] + "."


def substitution_summary(result: SubstitutionResult) -> dict:
    """The short answer: a headline and up to five plain rows. Every fact in it is also in
    the details below it, with its source."""
    ev, c = result.evidence, result.chosen
    title = f"{result.title} without {ev.target}"
    if not ev.target_lines or (result.message and not ev.candidates and not c):
        return {"headline": title if ev.target_lines else result.title, "status": result.status,
                "confidence": "", "rows": [["Answer", result.message]]}
    if c is None or result.adapted is None:
        rows = [["Answer", "No swap is suggested: none of the options in the dataset can do "
                           f"what {ev.noun} does here."]]
        if ev.candidates and ev.candidates[0].strength != "excluded":
            best = ev.candidates[0]
            rows.append(["Closest option", f"{best.name}: {_why(best, ev)}."])
        elif result.message:
            rows = [["Answer", result.message]]
        if ev.expected_effects:
            rows.append(["Leaving it out", "; ".join(ev.expected_effects[:2]) + "."])
        return {"headline": f"{title}: {HEADLINE['not_adapted']}", "status": result.status,
                "confidence": "", "rows": rows}
    confidence = CONFIDENCE.get(c.strength, "low")
    swap = f"replace {' + '.join(t for _, t in ev.target_lines)} with {c.name}; {_amount(c)}"
    rows = [["Swap", swap + (" (your choice)" if result.requested else "")],
            ["Why", _why(c, ev) + "."]]
    others = [o for o in ev.candidates if o is not c and o.covers_main
              and o.strength not in ("conflicting", "excluded")][:2]
    if others:
        rows.append(["Other options", ", ".join(f"{o.name} ({_amount(o, True)})"
                                                for o in others)])
    rows.append(["Expect", _expect(result)])
    if ev.baked:
        rows.append(["Bake", (f"as the original, {result.baking}" if result.baking
                              else "as the original recipe says") + ". Check with a toothpick."])
    if result.remaining_conflicts:
        rows.append(["Still to replace", "; ".join(result.remaining_conflicts)])
    return {"headline": f"{title}: {HEADLINE[result.status]}, {confidence} confidence",
            "status": result.status, "confidence": confidence, "rows": rows}


def render_substitution(result: SubstitutionResult, chosen_by: str) -> str:
    """Short answer first, then the adapted recipe, then the details that back it up."""
    ev = result.evidence
    summary = substitution_summary(result)
    lines = [f"{summary['headline']}  [{result.recipe_id}]"]
    lines += [f"- {label}: {text}" for label, text in summary["rows"]]
    if not ev.target_lines:
        return "\n".join(lines)
    adapted, chosen = result.adapted, result.chosen
    if adapted is not None and chosen is not None:
        if result.status == "incomplete":
            lines.append(f"\nIncomplete recipe: the {chosen.name} amount is not established by "
                         "the dataset, so test a small batch first.")
        lines.append("\nAdapted recipe (* = changed):")
        original = {line.strip() for line in result.original_ingredients}
        lines += [f"  {' ' if line.strip() in original else '*'} {line}"
                  for line in adapted.ingredients]
        lines.append("Steps:")
        lines += [f"  {i}. {s}" for i, s in enumerate(adapted.instructions, 1)]

    lines.append("\nDETAILS")
    if chosen is not None:
        q = chosen.quantity
        lines.append(f"Selected replacement: {chosen.name} ({chosen.strength} evidence, "
                     f"{chosen.fit} role fit), selected by {chosen_by}.")
        lines.append(f"Amount ({q.status}): {q.basis}")
    roles = [", ".join([f"{rs[0]} (main)", *rs[1:]]) for rs in ev.roles.values() if rs]
    if roles:
        lines.append(f"What {ev.noun} does here (cooking knowledge): {'; '.join(roles)}.")
    if ev.ranking_notes or ev.uncertainty:
        lines.append(f"Why this choice (ranking rules: {RANKING_RULE}):")
        lines += [f"  - {note}" for note in ev.ranking_notes + ev.uncertainty]

    lines.append("Evidence from the dataset, ranked (strength and role fit rated separately):")
    for i, c in enumerate(ev.candidates, 1):
        top = c.supporting[0] if c.supporting else None
        source = f"; e.g. {top['title']} [{top['id']}]" if top else ""
        lines.append(f"  {i}. {c.name}: {c.strength} evidence, {c.fit} fit, "
                     f"{_amount(c, True)} ({c.evidence_type()}{source})")
    if not ev.candidates:
        lines.append("  none found")
    lines.append(f"  Compared {ev.comparison_scope or f'{ev.neighbours} similar recipes'}; "
                 f"{ev.neighbours_without} of them have no {ev.target}.")
    if ev.same_dish_without:
        lines.append(f"  Versions of this dish in the dataset made without {ev.target}: "
                     + "; ".join(f"{title} [{rid}]" for rid, title in ev.same_dish_without))
    for rid, sentence in ev.notes:
        lines.append(f"  Instruction note: \"{sentence[:160]}\"  [{rid}]")
    lines.append(f"  {EVIDENCE_TYPES}")

    if chosen is None:
        if ev.expected_effects:
            lines.append(f"Expected trade-offs of removing {ev.target} (predictions, not "
                         "dataset facts):")
            lines += [f"  - {effect}" for effect in ev.expected_effects]
        if result.message and summary["rows"][0][1] != result.message:
            lines.append(result.message)
        return "\n".join(lines)
    if result.texture:
        lines.append("Predicted texture changes (predictions, not verified by the dataset):")
        lines += [f"  - {prop}: {text}" for prop, text in result.texture]
    if result.moisture and result.moisture.notes:
        lines.append(f"Moisture check (risk: {result.moisture.risk}):")
        lines += [f"  - {n}" for n in result.moisture.notes]
    if result.limitations:
        lines.append("Limitations:")
        lines += [f"  - {x}" for x in result.limitations]
    if chosen.strength in ("weak", "conflicting", "none"):
        lines.append(f"Caution: the evidence for {chosen.name} is {chosen.strength}; "
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
