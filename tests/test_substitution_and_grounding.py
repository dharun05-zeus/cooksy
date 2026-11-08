import pandas as pd

from recipebot.dialogue.state import SessionState
from recipebot.engines.substitution import (
    UNKNOWN_QUANTITY,
    AdaptationPlan,
    AdaptedRecipe,
    Candidate,
    Evidence,
    Quantity,
    StepEdit,
    SubstitutionEngine,
    SubstitutionResult,
    format_amount,
)
from recipebot.llm.rules import RuleParser
from recipebot.render import payloads, templates
from recipebot.render.grounding import Grounder

ORIGINAL = ["1 cup margarine", "2 cups all-purpose flour", "1 egg"]  # fixture recipe fn:f3
STEPS = ["Mix the dough with the egg.", "Bake until golden."]
EGG_ROLES = {"egg": ["binding", "leavening", "moisture", "structure", "emulsification"]}


def _lines(rows: list[tuple]) -> pd.DataFrame:
    """Parsed ingredient lines: (line_no, text, base, dimension, amount_base)."""
    return pd.DataFrame(rows, columns=["line_no", "text", "base", "dimension", "amount_base"])


def _evidence(**kw) -> Evidence:
    base = dict(target="egg", target_lines=[(2, "1 egg")], target_names=["egg"],
                restricted=["egg"], roles={"egg": ["binding"]}, baked=True,
                candidates=[Candidate("applesauce", direct=3, strength="moderate")])
    base.update(kw)
    return Evidence(**base)


def _adapted(ingredients, instructions=None, substitute="applesauce") -> AdaptedRecipe:
    return AdaptedRecipe(substitute, ingredients,
                         instructions or ["Mix the dough with the applesauce.", "Bake until golden."],
                         changes=[])


def engine(bot) -> SubstitutionEngine:
    return bot.substitution


def judged(e: SubstitutionEngine, ev: Evidence, cand: Candidate) -> Candidate:
    e._judge(ev, cand, set())
    return cand


# ----- validation of the adapted recipe ---------------------------------------------

def test_valid_rewrite_passes(bot):
    adapted = _adapted(["1 cup margarine", "2 cups all-purpose flour",
                        "1/4 cup applesauce (estimated quantity)"])
    # applesauce is not in the 9-record fixture vocabulary, so only that check may fail
    errors = engine(bot).validate(adapted, ORIGINAL, STEPS, _evidence())
    assert all("does not appear in the dataset" in e for e in errors)


def test_rewrite_that_changes_an_unrelated_line_is_rejected(bot):
    adapted = _adapted(["1 cup butter", "2 cups all-purpose flour", "1/4 cup applesauce"])
    errors = engine(bot).validate(adapted, ORIGINAL, STEPS, _evidence())
    assert any("unchanged line was altered" in e for e in errors)


def test_rewrite_that_keeps_the_target_is_rejected(bot):
    adapted = _adapted(["1 cup margarine", "2 cups all-purpose flour", "1 egg"],
                       instructions=STEPS)
    errors = engine(bot).validate(adapted, ORIGINAL, STEPS, _evidence())
    assert any("restricted ingredient" in e for e in errors)
    assert any("still mentions the target" in e for e in errors)


def test_steps_are_checked_for_the_target_only(bot):
    # Replacing cream "without dairy": a step that mentions the recipe's parmesan is not a
    # failed rewrite (the remaining parmesan is reported separately).
    ev = _evidence(target="cream", target_lines=[(0, "1 cup heavy cream")],
                   target_names=["cream", "heavy cream"], restricted=["cream", "dairy"],
                   candidates=[Candidate("coconut milk", direct=2, strength="moderate")])
    original = ["1 cup heavy cream", "1/2 cup parmesan"]
    adapted = AdaptedRecipe("coconut milk", ["1 cup coconut milk", "1/2 cup parmesan"],
                            ["Simmer the coconut milk, then stir in the parmesan."], changes=[])
    errors = engine(bot).validate(adapted, original, ["Simmer the cream."], ev)
    assert not any("step" in e for e in errors)


# ----- evidence strength vs functional fit ------------------------------------------

def test_candidate_filtering(bot):
    e = engine(bot)
    dairy = _evidence(target="dairy", restricted=["dairy"])
    butter, margarine = Candidate("butter", direct=9), Candidate("margarine", direct=9)
    e._judge(dairy, butter, set())
    e._judge(dairy, margarine, set())
    assert butter.strength == "excluded"
    assert margarine.strength == "conflicting"
    cream = _evidence(target="cream", target_names=["cream", "heavy cream"], restricted=["cream"])
    coconut = Candidate("coconut cream", direct=2)
    e._judge(cream, coconut, set())
    assert coconut.strength == "moderate"


def test_role_coverage_separates_full_partial_and_missing_roles(bot):
    ev = _evidence(roles=EGG_ROLES)
    applesauce = judged(engine(bot), ev, Candidate("applesauce", comparative_support=1,
                                                   comparative_scope="same dish"))
    assert applesauce.coverage == {"binding": "partial", "leavening": "none", "moisture": "full",
                                   "structure": "none", "emulsification": "none"}
    # binding (the main role) only partly: a partial fit, never a complete replacement
    assert applesauce.fit == "partial" and applesauce.covers_main
    assert "binding partly" in applesauce.coverage_text()
    assert "not leavening" in applesauce.coverage_text()


def test_good_fit_does_not_make_the_evidence_strong(bot):
    ev = _evidence(roles=EGG_ROLES)
    tofu = judged(engine(bot), ev, Candidate("silken tofu", comparative_support=1,
                                             comparative_scope="same dish"))
    assert tofu.fit == "good"
    assert tofu.strength == "weak"


# ----- scenario 1-3, 5, 7: ranking and selection --------------------------------------

def _ranked(e: SubstitutionEngine, ev: Evidence, cands: list[Candidate]) -> Evidence:
    for c in cands:
        e._judge(ev, c, set())
    ev.candidates = sorted(cands, key=e._rank_key)
    e._explain_ranking(ev)
    return ev


def test_strong_direct_evidence_with_a_dataset_quantity_is_supported(bot):
    e = engine(bot)
    ev = _ranked(e, _evidence(roles=EGG_ROLES), [
        Candidate("egg replacer", direct=6, quantity=Quantity("supported", "1/2 cup", 118.0,
                                                               "volume", "from 6 lines")),
        Candidate("applesauce", comparative_support=1, comparative_scope="same dish")])
    chosen = e.select(ev)
    assert chosen.name == "egg replacer" and chosen.strength == "strong"
    assert e.status(chosen) == "supported"
    assert "egg replacer ranks above applesauce: egg replacer has strong evidence" \
        in ev.ranking_notes[0]


def test_weak_evidence_is_experimental_and_flagged(bot):
    e = engine(bot)
    ev = _ranked(e, _evidence(roles=EGG_ROLES), [
        Candidate("applesauce", comparative_support=1, comparative_scope="same dish",
                  quantity=Quantity("estimated", "2/3 cup", 158.0, "volume", "scaled"))])
    chosen = e.select(ev)
    assert chosen.strength == "weak"
    assert e.status(chosen) == "experimental"


def test_conflicting_evidence_is_never_selected(bot):
    e = engine(bot)
    ev = _evidence(roles=EGG_ROLES, restricted=["egg"])
    # "egg substitute" may contain egg: strong direct evidence, but conflicting
    ev = _ranked(e, ev, [Candidate("egg substitute", direct=4),
                         Candidate("silken tofu", comparative_support=1,
                                   comparative_scope="same dish")])
    sub = next(c for c in ev.candidates if c.name == "egg substitute")
    assert sub.strength == "conflicting"
    assert ev.candidates[-1] is sub  # ranks last despite more evidence
    assert e.select(ev).name == "silken tofu"
    assert any("Conflicting evidence: egg substitute" in u for u in ev.uncertainty)


def test_equally_ranked_candidates_are_reported_as_a_tie(bot):
    e = engine(bot)
    ev = _ranked(e, _evidence(roles=EGG_ROLES), [
        Candidate("soy yogurt", comparative_support=1, comparative_scope="same dish"),
        Candidate("applesauce", comparative_support=1, comparative_scope="same dish")])
    assert e.select(ev).name == "applesauce"  # alphabetical only
    assert "listed first only alphabetically" in ev.ranking_notes[0]
    assert any("tied with soy yogurt" in u for u in ev.uncertainty)


def test_candidate_without_the_main_role_is_not_selected(bot):
    e = engine(bot)
    # olive oil: more evidence, but no binding, the egg's main role
    ev = _ranked(e, _evidence(roles=EGG_ROLES), [
        Candidate("olive oil", comparative_support=12, share_without=0.14, share_with=0.02,
                  comparative_scope="bread recipes"),
        Candidate("applesauce", comparative_support=1, comparative_scope="same dish")])
    assert e.select(ev).name == "applesauce"
    assert any("olive oil does not provide the egg's main role (binding)" in n
               for n in ev.ranking_notes)


def test_no_reliable_substitute_produces_no_recipe(bot):
    e = engine(bot)
    ev = _ranked(e, _evidence(roles=EGG_ROLES), [
        Candidate("olive oil", comparative_support=12, share_without=0.14, share_with=0.02,
                  comparative_scope="bread recipes")])
    assert e.select(ev) is None
    message = e._no_choice(ev)
    assert "No candidate can be selected" in message and "not producing an adapted recipe" in message


def test_no_evidence_in_the_dataset_declines(bot):
    # The 9-record fixture has nothing to replace the egg with in Margarine Cookies.
    result = engine(bot).adapt("fn:f3", "egg", [])
    assert result.adapted is None and result.status == "not_adapted"
    assert "would rather not guess" in result.message
    text = templates.render_substitution(result, "rules")
    assert text.startswith("Margarine Cookies without egg") and "would rather not guess" in text
    assert "Adapted recipe" not in text


# ----- scenario 4: quantities -------------------------------------------------------

def test_direct_lines_give_a_supported_quantity(bot):
    e = engine(bot)
    ev = _evidence(target_lines=[(2, "2 eggs, beaten")])
    ev.recipe_lines = _lines([(2, "2 eggs, beaten", "egg", "count", 2.0)])
    cand = Candidate("egg substitute", direct=1,
                     direct_lines=[("r1", "2 large eggs or 1/2 cup egg substitute")])
    q = e._direct_quantity(cand, ev, e._target_amount(ev))
    assert q.status == "supported" and q.text == "1/2 cup"


def test_same_amount_lines_keep_the_original_measure(bot):
    e = engine(bot)
    ev = _evidence(target="butter", target_lines=[(0, "1/2 cup butter, softened")],
                   target_names=["butter"], restricted=["butter"])
    ev.recipe_lines = _lines([(0, "1/2 cup butter, softened", "butter", "volume", 118.3)])
    cand = Candidate("shortening", direct=6, strength="strong", fit="good",
                     direct_lines=[("r1", "1 cup butter or shortening")])
    cand.quantity = e._direct_quantity(cand, ev, e._target_amount(ev))
    assert cand.quantity.same_as_original
    adapted = e.build(["1/2 cup butter, softened"], ["Cream the butter."], ev, cand)
    assert adapted.ingredients == ["1/2 cup shortening, softened (quantity from the dataset)"]
    assert adapted.instructions == ["Cream the shortening."]


def test_same_dish_quantity_is_scaled_by_flour_and_labelled_estimated(bot):
    e = engine(bot)
    ev = _evidence()
    ev.recipe_lines = _lines([(0, "2 cups all-purpose flour", "flour", "volume", 473.2)])
    theirs = _lines([(0, "3 cups all-purpose flour", "flour", "volume", 709.8),
                     (1, "1 cup applesauce", "applesauce", "volume", 236.6)])
    theirs["recipe_id"] = "r1"
    cand = Candidate("applesauce", comparative_support=1, comparative_scope="same dish",
                     comparative_examples=["r1"])
    q = e._estimated_quantity(cand, ev, {"r1": theirs})
    assert q.status == "estimated" and q.text == "2/3 cup"
    assert "scaled to this recipe's 2 cups flour" in q.basis


def test_unscalable_or_missing_quantity_is_not_invented(bot):
    e = engine(bot)
    ev = _evidence()
    ev.recipe_lines = _lines([(0, "2 cups all-purpose flour", "flour", "volume", 473.2)])
    theirs = _lines([(0, "2 ripe bananas", "banana", "count", 2.0),
                     (1, "1/2 (12 ounce) package silken tofu", "silken tofu", "mass", 170.1)])
    cand = Candidate("silken tofu", comparative_support=1, comparative_scope="same dish",
                     comparative_examples=["r1"])
    q = e._estimated_quantity(cand, ev, {"r1": theirs})
    assert q.status == "unknown" and q.text == ""
    assert q.basis.startswith(UNKNOWN_QUANTITY) and "not scaled" in q.basis
    # Comparative evidence from other dishes never gives a quantity.
    other = Candidate("olive oil", comparative_support=9, comparative_scope="bread recipes")
    assert e._estimated_quantity(other, ev, {}).status == "unknown"


def test_unknown_quantity_is_explicit_in_the_recipe(bot):
    e = engine(bot)
    ev = _evidence(roles=EGG_ROLES)
    cand = judged(e, ev, Candidate("applesauce", comparative_support=1,
                                   comparative_scope="same dish"))
    adapted = e.build(ORIGINAL, STEPS, ev, cand)
    assert adapted.ingredients[2] == "applesauce (quantity not established by the dataset)"
    assert adapted.ingredients[:2] == ORIGINAL[:2]  # nothing else changed
    assert adapted.instructions[0] == "Mix the dough with the applesauce."
    assert e.status(cand) == "incomplete"
    assert any(UNKNOWN_QUANTITY in c for c in adapted.changes)


def test_extra_target_lines_are_removed_openly(bot):
    e = engine(bot)
    ev = _evidence(target_lines=[(0, "2 eggs"), (1, "1 egg yolk")], target_names=["egg", "egg yolk"],
                   roles=EGG_ROLES)
    cand = judged(e, ev, Candidate("applesauce", comparative_support=1,
                                   comparative_scope="same dish"))
    adapted = e.build(["2 eggs", "1 egg yolk", "1 cup flour"], [], ev, cand)
    assert adapted.ingredients == ["applesauce (quantity not established by the dataset)",
                                   "1 cup flour"]
    assert any(c.startswith("removed '1 egg yolk'") for c in adapted.changes)


def test_format_amount():
    assert format_amount(236.6, "volume") == "1 cup"
    assert format_amount(158.0, "volume") == "2/3 cup"
    assert format_amount(552.0, "volume") == "2 1/3 cups"
    assert format_amount(29.6, "volume") == "2 tablespoons"
    assert format_amount(4.9, "volume") == "1 teaspoon"


# ----- scenario 6: moisture and texture ---------------------------------------------

def test_excess_moisture_risk_is_detected(bot, monkeypatch):
    e = engine(bot)
    ev = _evidence(roles=EGG_ROLES, dish="banana bread")
    ev.recipe_lines = _lines([(0, "2 cups all-purpose flour", "flour", "volume", 473.2),
                              (1, "2 1/3 cups mashed overripe bananas", "banana", "volume", 552.0),
                              (2, "1 egg", "egg", "count", 1.0)])
    monkeypatch.setattr(e, "_baseline", lambda ev, skip: (0.8, 56))
    cand = judged(e, ev, Candidate("applesauce", comparative_support=1,
                                   comparative_scope="same dish"))
    cand.quantity = Quantity("estimated", "2/3 cup", 158.0, "volume", "scaled")
    check = e._moisture(ev, cand)
    assert check.existing == ["2 1/3 cups mashed overripe bananas"]
    assert round(check.ratio, 2) == 1.17 and round(check.after, 2) == 1.5
    assert check.risk == "high"
    assert any("gummy, dense or underbaked" in n for n in check.notes)
    texture = dict(e._texture(ev, cand, check))
    assert "wetter" in texture["Moisture"]
    assert texture["Binding"].startswith("potentially weaker")
    assert "does not provide leavening" in texture["Rise"]
    assert "denser" in texture["Density"] and "gummy" in texture["Crumb"]


def test_dry_substitute_has_no_moisture_risk(bot):
    e = engine(bot)
    ev = _evidence(roles=EGG_ROLES)
    ev.recipe_lines = _lines([(0, "2 cups flour", "flour", "volume", 473.2)])
    cand = judged(e, ev, Candidate("egg replacer", direct=3))
    check = e._moisture(ev, cand)
    assert check.risk == "none" and "drier" in check.notes[0]


def test_baking_time_comes_from_bake_sentences_only():
    steps = ["Preheat oven to 350 degrees F (175 degrees C).",
             "Bake for 60 to 65 minutes. Let cool in the pan for 10 minutes."]
    assert SubstitutionEngine._baking(steps) == "350 degrees F (175 degrees C); 60 to 65 minutes"


# ----- the LLM only rewords steps ---------------------------------------------------

def test_llm_step_edits_cannot_add_numbers_or_keep_the_target(bot):
    e = engine(bot)
    ev = _evidence()
    steps = ["Mix the dough with the egg.", "Stir in the egg.", "Bake until golden."]
    adapted = _adapted(ORIGINAL, instructions=["Mix the dough with the applesauce.",
                                               "Stir in the applesauce.", "Bake until golden."])
    plan = AdaptationPlan(step_edits=[
        StepEdit(number=1, text="Mix the dough with 1/4 cup applesauce."),  # new numbers
        StepEdit(number=2, text="Gently fold in the applesauce."),  # fine
        StepEdit(number=3, text="Bake for 40 minutes."),  # not a step that mentions egg
    ])
    errors, used = e.apply_step_edits(plan, steps, [0, 1], ev, adapted)
    assert used == 1 and any("adds numbers" in x for x in errors)
    assert adapted.instructions == ["Mix the dough with the applesauce.",
                                    "Gently fold in the applesauce.", "Bake until golden."]


# ----- rendering --------------------------------------------------------------------

def test_render_and_payload_label_status_quantity_and_predictions(bot):
    e = engine(bot)
    ev = _evidence(roles=EGG_ROLES)
    cand = judged(e, ev, Candidate("applesauce", comparative_support=1,
                                   comparative_scope="same dish"))
    ev.candidates = [cand]
    result = SubstitutionResult("fn:f3", "Margarine Cookies", ev, chosen=cand,
                                adapted=e.build(ORIGINAL, STEPS, ev, cand), method="fallback",
                                original_ingredients=ORIGINAL, status=e.status(cand),
                                texture=e._texture(ev, cand, None))
    text = templates.render_substitution(result, "the ranking rules in code")
    # the short answer comes first, in plain words
    assert text.startswith("Margarine Cookies without egg: experimental, amount unknown, "
                           "low confidence")
    assert "- Swap: replace 1 egg with applesauce; the dataset doesn't say how much to use" in text
    assert text.index("- Swap:") < text.index("Adapted recipe") < text.index("DETAILS")
    assert "Incomplete recipe" in text
    assert "Amount (unknown): " + UNKNOWN_QUANTITY in text
    assert "Predicted texture changes (predictions, not verified by the dataset)" in text
    assert "Caution: the evidence for applesauce is weak" in text
    assert "Indirect evidence: a related recipe uses it" in text
    data = payloads.substitution(result, "rules")
    assert data["summary"]["confidence"] == "low"
    assert data["summary"]["rows"][0][0] == "Swap"
    assert data["status"] == "incomplete"
    assert data["adapted"]["quantity"]["status"] == "unknown"
    assert data["candidates"][0]["fit"] == "partial" and data["candidates"][0]["direct"] is False


# ----- scenario 8: follow-up about the selected replacement -------------------------

def test_follow_up_use_another_replacement():
    state = SessionState(focus_recipe_id="fn:f3", last_substitute_target="eggs")
    patch = RuleParser().parse("Use soy yogurt instead.", state)
    assert patch.intent == "substitute"
    assert patch.substitute.target == "eggs" and patch.substitute.replacement == "soy yogurt"
    # without an earlier substitution there is nothing to apply it to
    assert RuleParser().parse("Use soy yogurt instead.", SessionState()).intent != "substitute"


def test_substitution_remembers_its_target(bot):
    bot.handle("Find margarine cookies.")
    bot.handle("Remove the egg from the first one.")
    assert bot.state.last_substitute_target == "egg"
    assert bot.state.focus_recipe_id == "fn:f3"


# ----- grounding ----------------------------------------------------------------------

def test_grounding_removes_unsupported_sentences():
    grounder = Grounder({"garlic", "onion", "chicken"})
    facts = "Answer: 15,656 of 122,910 recipes (12.74%). Example: ar:abc garlic onion"
    text = ("About 15,656 recipes use garlic and onion. That is 12.74% of the dataset. "
            "The top one is ar:xyz. It takes 20 minutes. Many also use chicken. "
            "Roughly 40% of them are soups.")
    kept, report = grounder.check(text, facts, {"ar:abc"})
    assert kept == "About 15,656 recipes use garlic and onion. That is 12.74% of the dataset."
    reasons = " | ".join(r for _, r in report.removed)
    assert "ar:xyz" in reasons and "minutes" in reasons and "chicken" in reasons and "40" in reasons
