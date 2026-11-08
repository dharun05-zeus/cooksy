from recipebot.nlp.steps import count_steps


def test_one_step_per_line(lexicon):
    result = count_steps("Chop.\n\nBoil.\nServe.", lexicon.boilerplate_res)
    assert (result.steps, result.method) == (3, "line")


def test_single_paragraph_is_split_into_sentences(lexicon):
    result = count_steps("Slice it. Arrange it. Serve at 350 degrees.", lexicon.boilerplate_res)
    assert (result.steps, result.method) == (3, "sentence")


def test_boilerplate_is_not_a_step(lexicon):
    text = "Mix and bake.\nWatch how to make this recipe.\nPhotograph by Someone"
    result = count_steps(text, lexicon.boilerplate_res)
    assert (result.steps, result.method) == (1, "line")


def test_empty_instructions(lexicon):
    assert count_steps("", lexicon.boilerplate_res).steps == 0
