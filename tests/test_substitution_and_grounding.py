from recipebot.engines.substitution import (
    AdaptationPlan,
    AdaptedRecipe,
    Candidate,
    Evidence,
    LineEdit,
    StepEdit,
    SubstitutionEngine,
)
from recipebot.render.grounding import Grounder

ORIGINAL = ["1 cup margarine", "2 cups all-purpose flour", "1 egg"]  # fixture recipe fn:f3
STEPS = ["Mix the dough with the egg.", "Bake until golden."]


def _evidence(**kw) -> Evidence:
    base = dict(target="egg", target_lines=[(2, "1 egg")], target_names=["egg"],
                restricted=["egg"], roles={"egg": ["binding"]}, baked=True,
                candidates=[Candidate("applesauce", direct=3, strength="moderate")])
    base.update(kw)
    return Evidence(**base)


def _adapted(ingredients, instructions=None, substitute="applesauce") -> AdaptedRecipe:
    return AdaptedRecipe(substitute=substitute, ingredients=ingredients,
                         instructions=instructions or ["Mix the dough with the applesauce.",
                                                       "Bake until golden."],
                         changes=[], predicted_effects=[])


def engine(bot) -> SubstitutionEngine:
    return bot.substitution


def test_valid_rewrite_passes(bot):
    adapted = _adapted(["1 cup margarine", "2 cups all-purpose flour", "1/4 cup applesauce (estimate)"])
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


def test_replacement_line_must_hold_only_the_substitute(bot):
    adapted = _adapted(["1 cup margarine", "2 cups all-purpose flour", "2 cups flour, 1/4 cup applesauce"])
    errors = engine(bot).validate(adapted, ORIGINAL, STEPS, _evidence())
    assert any("must contain only the substitute" in e for e in errors)


def test_substitute_must_be_an_evidenced_candidate(bot):
    adapted = _adapted(ORIGINAL[:2] + ["1 banana"], substitute="banana")
    errors = engine(bot).validate(adapted, ORIGINAL, STEPS, _evidence())
    assert any("not one of the candidates" in e for e in errors)


def test_steps_are_checked_for_the_target_only(bot):
    # Replacing cream "without dairy": a step that mentions the recipe's parmesan is not a
    # failed rewrite (the remaining parmesan is reported separately).
    ev = _evidence(target="cream", target_lines=[(0, "1 cup heavy cream")],
                   target_names=["cream", "heavy cream"], restricted=["cream", "dairy"],
                   candidates=[Candidate("coconut milk", direct=2, strength="moderate")])
    original = ["1 cup heavy cream", "1/2 cup parmesan"]
    adapted = AdaptedRecipe(substitute="coconut milk",
                            ingredients=["1 cup coconut milk", "1/2 cup parmesan"],
                            instructions=["Simmer the coconut milk, then stir in the parmesan."],
                            changes=[], predicted_effects=[])
    errors = engine(bot).validate(adapted, original, ["Simmer the cream."], ev)
    assert not any("step" in e for e in errors)


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


def test_plan_edits_only_target_lines(bot):
    plan = AdaptationPlan(
        substitute="applesauce",
        ingredient_edits=[LineEdit(number=3, text="1/4 cup applesauce (estimate)"),
                          LineEdit(number=1, text="1 cup butter")],  # not a target: ignored
        step_edits=[StepEdit(number=1, text="Mix the dough with the applesauce.")],
        changes=[], predicted_effects=[])
    adapted = engine(bot).apply_plan(plan, ORIGINAL, STEPS, _evidence())
    assert adapted.ingredients == ["1 cup margarine", "2 cups all-purpose flour",
                                   "1/4 cup applesauce (estimate)"]
    assert adapted.instructions == ["Mix the dough with the applesauce.", "Bake until golden."]


def test_fallback_rewrite(bot):
    adapted = engine(bot)._fallback(ORIGINAL, STEPS, _evidence())
    assert adapted.ingredients[2] == "applesauce (amount not given by the dataset)"
    assert adapted.ingredients[:2] == ORIGINAL[:2]
    assert adapted.instructions[0] == "Mix the dough with the applesauce."
    # roles.yaml: applesauce provides binding, so the egg's binding role is covered
    assert adapted.predicted_effects == ["applesauce can take over the binding role(s)"]


def test_fallback_keeps_measured_amounts(bot):
    ev = _evidence(target="butter", target_lines=[(0, "1/2 cup butter, softened")],
                   target_names=["butter"], restricted=["butter"],
                   candidates=[Candidate("shortening", direct=6, strength="strong", fit="good")])
    adapted = engine(bot)._fallback(["1/2 cup butter, softened"], ["Cream the butter."], ev)
    assert adapted.ingredients == ["1/2 cup shortening, softened (estimate: same amount as the original)"]
    assert adapted.instructions == ["Cream the shortening."]


def test_fallback_declines_unclear_evidence(bot):
    unclear = _evidence(candidates=[Candidate("olive oil", comparative_support=12,
                                              strength="moderate", fit="partial")])
    assert not engine(bot).fallback_allowed(unclear)
    assert engine(bot).fallback_allowed(_evidence(candidates=[Candidate("applesauce", fit="good",
                                                                        strength="weak")]))


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
