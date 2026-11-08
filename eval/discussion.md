## Discussion: what worked, what failed, and why

### What worked

- **Statistics** match an independent reference computation exactly, and every answer
  states its filters, the exact ingredient names counted, the denominator (122,910 complete
  recipes; 2,254 incomplete records excluded) and the method.
- **Hard constraints held.** Across all matching cases, no returned recipe violates an
  exclusion (uncertain items included) or a step limit. The two no-match cases say so and
  list the closest alternatives separately, each marked with the constraint it breaks.
- **The parser** (Qwen3 4B, local, CPU) passed 40/40 labelled messages, but only with help:
  guards corrected 11 of the 40 LLM outputs. Without the LLM, the fallback parser alone passes
  27/40, so the LLM is what makes free-form phrasing work. Median 5.7 s per message.
- **Substitution** passed its property checks in all 6 cases: restrictions respected,
  unchanged lines kept verbatim, every cited recipe ID exists, weak evidence flagged, a
  forbidden requested replacement refused. Code ranks the candidates and picks the
  substitute; Qwen only rewords the affected steps (accepted in 3 of the 4 adaptations).
  Results:
  - chocolate-chip cookies without butter, no dairy → shortening: strong evidence, and
    dataset lines offer it at the same amount, so the adaptation is *supported*;
  - pasta with cream, no dairy → olive oil: moderate evidence (used by many same-dish
    recipes without cream); coconut milk has only one direct line;
  - pancakes without milk → cream: strong evidence ("milk or cream" lines);
  - banana bread without eggs → silken tofu, *incomplete experimental adaptation*. Only 9
    of 183 banana breads in the dataset lack eggs; silken tofu, applesauce and soy yogurt
    each appear in one of them (weak evidence). Silken tofu ranks first because it covers
    the egg's main role (binding) fully. Its amount cannot be scaled from its recipe, so
    the answer says "quantity not established by the dataset" instead of guessing, and
    offers applesauce (about 2/3 cup, estimated from a same-dish recipe by flour) as an
    alternative. It also warns that this recipe is already wetter than most banana breads
    (117% of the flour by volume vs a median of 80%), so a wet substitute risks a gummy
    centre.
- **Conversations**: all 8 pass, including two added after manual testing found bugs: an
  exclusion lifted in the same message as a new one ("mushrooms are okay, but exclude
  dairy") and a follow-up with a requested replacement ("use applesauce instead").
- **Every recipe ID** in every reply of every conversation exists in the dataset.

### Where a one-shot LLM answer is wrong, and how the system handles it

The same Qwen3 4B model answered the questions directly, without the pipeline. Reading its
answers (not only the automatic score):

- *"How many recipes contain both garlic and onion, and what percentage?"* It says it cannot
  access the data, then estimates **"~30–40%"** and claims onion appears in **~70%** and
  garlic in **~60%** of recipes. The dataset says **12.74%** (15,657 of 122,910 recipes); onion
  is in 25.0% and garlic in 26.3%. The estimate is about three times too high and its
  supporting figures are invented. The assistant computes the count over the full dataset,
  states that varieties (red onion, garlic cloves) count and products (garlic powder) do not,
  and reports the denominator.
- *"How many calories are in a slice of Banana Banana Bread?"* It gives "100–150 calories",
  which does not come from the data: the dataset records no nutrition. The assistant
  answers that the dataset does not record nutrition and declines to guess.
- *"Average number of ingredients?"* It mostly declines, but cites a made-up "Recipe 1000"
  dataset with "~12 ingredients". The assistant answers 10.36 (median 9), with its method.
- The two questions asking for recipe IDs were declined honestly; the assistant returned
  five existing IDs each.

The automatic check scores 0/5 for the one-shot model (2 declined, 3 with unsupported
numbers) and 5/5 for the assistant.

### What failed, and why (including problems found and fixed while building)

1. **Normalization (59/60).** "1 whole rind from 1 wedge Parmesan" is still parsed as
   `rind from wedge parmesan`. The rules handle "X of Y" containers but not "rind from".
   It is left as a known failure rather than special-cased. The first parser version scored
   51/60; the fixes were general (label prefixes, brand and processing words, containers,
   variety families).
2. **The small LLM drops and invents details.** With a bare schema Qwen3 4B parsed 5 of 9
   early test messages correctly: it dropped "no peanuts" and "at most six steps" from long
   requests, turned "vegetarian" into "no dairy", invented a step limit for "quick", and
   read "pasta *with* heavy cream" as "no dairy". Worked examples in the prompt and the guards
   fixed these, and it is still not deterministic: "Exclude eggs too" passed in one run and
   failed in the next, which led to one more guard. The guards are high-precision patterns,
   so a phrasing that is unusual for both the LLM and the patterns can still be misread.
3. **Substitution evidence was noisy at first.** Similar recipes for banana bread included
   banana drinks, which suggested banana liqueur as an egg replacement. Recipes without cream
   also use more tomato, which made tomato look like a cream substitute. Fixes: compare only
   the same dish (widening with a note when too few), and require comparative-only
   candidates to fill the ingredient's role. A misspelling ("creme fraeche") briefly let a
   dairy product through as a dairy-free option.
4. **A line-numbering bug.** In 2,128 recipes with section headings ("For the sauce:"), the
   substituted line could be off by one. It was found in review, fixed at build time, and
   verified on all 1,273,583 ingredient lines.
5. **The first substitution answers did not meet the brief.** For banana bread without
   eggs, the first version either declined outright or proposed applesauce with no amount
   and a 1:1 assumption elsewhere, and the LLM chose the substitute. It was reworked so
   that code ranks candidates by stated rules (evidence strength kept separate from
   functional fit), quantities come only from the dataset or are marked unknown, a moisture
   check compares the recipe with others of the same dish, and the LLM only rewords steps.
   A step edit that adds a number or still names the ingredient is rejected and that step
   keeps the rule-based rewrite (Qwen once added "2 cups mashed bananas" to the replacement).
6. **LLM slips found by using the product.** Manual testing found failures the test sets
   had not covered, each now fixed with a guard and a test: Qwen re-added "mushrooms" as an
   exclusion in "mushrooms are okay, but exclude dairy"; it invented a replacement
   ("apricot mignonette", then "dairy-free butter") for "replace the butter"; and for
   "exclude eggs too" it removed eggs from the user's ingredient list instead of only
   excluding them. A display bug also showed the vegetarian diet as "no vegetarian".
7. **Latency.** On a laptop CPU: about 5–10 s per message and 15–50 s per substitution.
   LLM-written summaries are therefore off for local models.

### Limits of this evaluation

- The statistics reference uses the same ingredient normalization as the engine, so it
  checks filtering and counting logic, not normalization. Normalization is measured
  separately on the hand-labelled sample.
- The test sets are small (40 parser messages, 60 lines, 6 substitutions) and were written
  by the same people who built the system. Many parser messages are deliberately phrased
  unlike the prompt examples, but overfitting to them is still possible.
- The normalization labels were made with an AI assistant and reviewed by the author.
- LLM outputs vary between runs; the numbers above are from one run with Qwen3 4B.
