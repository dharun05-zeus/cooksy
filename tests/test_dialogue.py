"""Multi-turn conversations on the 9-record fixture dataset (see test_pipeline_and_stats.py)."""

import pytest

from recipebot.dialogue.state import SessionState, StatePatch, apply_patch
from recipebot.engines.matching import MatchRequest, PantryItem, match
from recipebot.llm.base import LLMUnavailable, inline_schema
from recipebot.llm.parser import MessageParser


def test_penne_then_no_dairy_refines_the_search(bot):
    bot.handle("Find a penne pasta recipe.")
    assert set(bot.state.last_results) == {"epi:e1", "ar:a3"}
    turn = bot.handle("I cannot have dairy.")
    assert bot.state.exclude == ["dairy"]
    assert bot.state.query == "penne pasta"  # same search, refined
    assert bot.state.last_results == ["epi:e1"]
    assert "Evidence: no dairy" in turn.reply
    assert "Active constraints: no dairy." in turn.reply


def test_constraint_persists_into_a_new_search(bot):
    bot.handle("I cannot have dairy.")
    bot.handle("Find penne.")
    assert bot.state.exclude == ["dairy"]
    assert "ar:a3" not in bot.state.last_results


def test_detail_by_position(bot):
    bot.handle("Find a penne pasta recipe.")
    first = bot.state.last_results[0]
    turn = bot.handle("Show me the ingredients for the first one.")
    assert f"[{first}]" in turn.reply
    assert "Ingredients (as listed in the dataset)" in turn.reply
    assert "Instructions" not in turn.reply


def test_detail_out_of_range(bot):
    bot.handle("Find a penne pasta recipe.")
    assert "There is no result number 9" in bot.handle("Show me the ninth one.").reply


def test_substitution_with_out_of_range_number_does_not_use_old_recipe(bot):
    bot.handle("Find a penne pasta recipe.")
    bot.handle("Show me the first one.")
    turn = bot.handle("Replace the cream in the ninth one.")
    assert "There is no result number 9" in turn.reply


def test_made_up_recipe_id_is_ignored(bot, monkeypatch):
    bot.handle("Find a penne pasta recipe.")
    monkeypatch.setattr(bot.parser, "parse", lambda *a, **k: StatePatch(
        intent="detail", recipe_id="ar:does-not-exist"))
    bot.handle("Show me the first one.")
    turn = bot.handle("show me ar:does-not-exist")
    assert turn.reply == "There is no recipe with ID ar:does-not-exist in the dataset."


def test_pdf_matching_conversation(bot):
    turn = bot.handle("I have eggs, onions, tomatoes, and rice. Suggest five recipes using as many "
                      "of these as possible, with no peanuts and at most six instruction steps. "
                      "Prefer recipes that need the fewest additional ingredients.")
    assert bot.state.preferences == []  # default order already prefers fewest extra second
    assert bot.state.last_results[0] == "fn:f1"  # uses onion and tomato
    assert "fn:f2" not in bot.state.last_results  # exact duplicate removed
    assert "Ranking rule: most of your ingredients used" in turn.reply
    turn = bot.handle("Exclude eggs too.")
    assert "fn:f3" not in bot.state.last_results  # the egg recipe is gone
    assert "'eggs' is excluded by your constraints" in turn.reply


def test_no_match_lists_violating_alternatives(store):
    # Only f3 (cookies) uses egg, and it has flour and 2 steps.
    request = MatchRequest(pantry=[PantryItem(name="egg")], exclude=["gluten"], max_steps=1)
    result = match(store, request)
    assert result.no_match
    assert result.alternatives[0].recipe_id == "fn:f3"
    assert result.alternatives[0].violations == ["contains gluten (gluten)", "2 steps (limit 1)"]


def test_all_pantry_items_excluded(store):
    result = match(store, MatchRequest(pantry=[PantryItem(name="flour")], exclude=["gluten"]))
    assert result.no_match
    assert "All the ingredients you listed are excluded" in result.notes[-1]


def test_quantity_check(store):
    request = MatchRequest(pantry=[PantryItem(name="egg", quantity=2), PantryItem(name="flour")])
    result = match(store, request)
    cookies = next(r for r in result.results if r.recipe_id == "fn:f3")
    assert cookies.quantity_notes == ["egg: needs 1, you have 2 → enough"]


def test_stats_through_chat(bot):
    turn = bot.handle("How many recipes contain both garlic and onion? What percentage of the dataset is that?")
    assert "1 of 7 recipes (14.29%)" in turn.reply


def test_reset_clears_constraints(bot):
    bot.handle("I cannot have dairy.")
    bot.handle("reset")
    assert bot.state == SessionState()


def test_unsupported_attribute_is_refused(bot):
    bot.handle("Find a penne pasta recipe.")
    turn = bot.handle("How many calories are in the first one?")
    assert "does not record nutrition" in turn.reply


def test_rule_parser_edge_cases(bot):
    rules = bot.parser.rules
    assert rules.parse("I have no idea what to cook", SessionState()).add_exclude == []
    assert rules.parse("Find soup with less than 5 steps", SessionState()).max_steps == 4
    assert rules.parse("Find soup under 1 step", SessionState()).max_steps is None
    assert rules.parse("show me the last one", SessionState()).result_number is None


def test_patch_rules():
    state = apply_patch(SessionState(), StatePatch(intent="search", query="curry", add_exclude=["nuts"]))
    state = apply_patch(state, StatePatch(intent="search", new_topic=True, query="soup"))
    assert (state.query, state.exclude) == ("soup", ["nuts"])
    state = apply_patch(state, StatePatch(intent="search", remove_exclude=["NUTS"]))
    assert state.exclude == []


class _FailingClient:
    name = "fake"

    def generate_json(self, system, prompt, schema):
        raise RuntimeError("quota exceeded")


class _FixedClient:
    name = "fake"

    def generate_json(self, system, prompt, schema):
        return StatePatch(intent="search", new_topic=True, query="tomato salad")


def test_llm_failure_falls_back_to_rules():
    parser = MessageParser(_FailingClient())
    patch = parser.parse("Find a penne pasta recipe.", SessionState())
    assert (parser.last_source, patch.query) == ("rules", "penne pasta")
    assert "quota exceeded" in parser.last_error


def test_llm_patch_is_used_when_valid():
    parser = MessageParser(_FixedClient())
    assert parser.parse("anything", SessionState()).query == "tomato salad"
    assert parser.last_source == "fake"


class _NoCreditsClient:
    name = "fake"
    calls = 0

    def generate_json(self, system, prompt, schema):
        self.calls += 1
        raise LLMUnavailable("Gemini error 402: credits depleted")


def test_permanent_llm_error_disables_llm_for_the_session():
    client = _NoCreditsClient()
    parser = MessageParser(client)
    parser.parse("Find penne.", SessionState())
    parser.parse("Find soup.", SessionState())
    assert client.calls == 1  # the second turn did not wait on the API again
    assert parser.disabled_reason and parser.last_source == "rules"


def test_exclusion_refines_match_even_if_labelled_search(bot, monkeypatch):
    bot.handle("I have eggs, onions and tomatoes.")
    monkeypatch.setattr(bot.parser, "parse",
                        lambda *a, **k: StatePatch(intent="search", add_exclude=["eggs"]))
    turn = bot.handle("Exclude eggs too.")
    assert bot.state.task == "match"
    assert "Your ingredients (as understood): onion, tomato" in turn.reply


def test_excluding_an_unknown_ingredient_says_so(store):
    from recipebot.engines import stats
    from recipebot.engines.stats import RecipeFilter

    result = stats.count(store, RecipeFilter(exclude=["dragonfruit"]))
    assert result.value == 7
    assert any("removed nothing" in n for n in result.notes)


def test_guard_drops_exclusion_with_no_restriction_in_message():
    from recipebot.llm.parser import apply_guards

    llm = StatePatch(intent="search", new_topic=True, query="pasta", add_exclude=["dairy"])
    fixed, notes = apply_guards(llm, StatePatch(intent="search"), "Find a pasta recipe with heavy cream.")
    assert fixed.add_exclude == [] and notes
    kept, _ = apply_guards(llm, StatePatch(intent="search"), "pasta, my son is lactose intolerant")
    assert kept.add_exclude == ["dairy"]


def test_allowing_one_ingredient_and_excluding_another_in_one_message(bot):
    bot.handle("Find vegetarian pasta recipes without mushrooms.")
    assert set(bot.state.exclude) == {"mushrooms", "vegetarian"}
    bot.handle("Actually, mushrooms are okay. But exclude dairy.")
    assert set(bot.state.exclude) == {"vegetarian", "dairy"}


@pytest.mark.parametrize("message, allowed", [
    ("mushrooms are okay", ["mushrooms"]),
    ("actually, dairy is fine now", ["dairy"]),
    ("but red onions are fine after all", ["red onions"]),
    ("i can have nuts again", ["nuts"]),
    ("allow eggs again", ["eggs"]),
    ("that is fine", []),
])
def test_allowed_again_phrasings(message, allowed):
    from recipebot.llm.rules import allowed_again

    assert allowed_again(message) == allowed


def test_removing_an_exclusion_ignores_plural():
    state = apply_patch(SessionState(), StatePatch(intent="search", add_exclude=["mushrooms"]))
    state = apply_patch(state, StatePatch(intent="search", remove_exclude=["Mushroom"]))
    assert state.exclude == []


def test_guard_stops_the_llm_re_adding_an_allowed_ingredient():
    from recipebot.llm.parser import apply_guards

    # What Qwen returned for "Actually, mushrooms are okay. But exclude dairy."
    llm = StatePatch(intent="search", query="vegetarian pasta", add_exclude=["mushrooms", "dairy"])
    rules = StatePatch(intent="search", remove_exclude=["mushrooms"], add_exclude=["dairy"])
    fixed, _ = apply_guards(llm, rules, "Actually, mushrooms are okay. But exclude dairy.")
    assert fixed.remove_exclude == ["mushrooms"] and fixed.add_exclude == ["dairy"]


def test_guard_drops_an_invented_replacement():
    from recipebot.dialogue.state import SubstituteRequest
    from recipebot.llm.parser import apply_guards

    text = "I cannot have dairy. Replace the butter in the first one."
    llm = StatePatch(intent="substitute", result_number=1, add_exclude=["dairy"],
                     substitute=SubstituteRequest(target="butter", replacement="dairy-free butter"))
    fixed, _ = apply_guards(llm, StatePatch(intent="substitute"), text)
    assert fixed.substitute.replacement is None
    named = llm.model_copy(update={"substitute": SubstituteRequest(target="butter",
                                                                   replacement="shortening")})
    kept, _ = apply_guards(named, StatePatch(intent="substitute"),
                           "Replace the butter with shortening.")
    assert kept.substitute.replacement == "shortening"


def test_guard_keeps_pantry_when_an_item_is_only_excluded():
    from recipebot.llm.parser import apply_guards

    llm = StatePatch(intent="match", add_exclude=["eggs"], remove_pantry=["eggs"])
    fixed, _ = apply_guards(llm, StatePatch(intent="match", add_exclude=["eggs"]),
                            "Exclude eggs too.")
    assert fixed.remove_pantry == [] and fixed.add_exclude == ["eggs"]
    kept, _ = apply_guards(llm, StatePatch(intent="match"), "I don't have eggs after all.")
    assert kept.remove_pantry == ["eggs"]


def test_schema_has_no_refs():
    assert "$ref" not in str(inline_schema(StatePatch))
