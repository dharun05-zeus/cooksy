# Design: Cooksy, a recipe assistant grounded in the Recipe Box dataset

## 1. Core principle

**The LLM reads the request; code produces every fact.** The LLM turns the user's message
into a validated JSON instruction and writes short explanations. Search, filtering,
counting, ranking and substitution evidence are computed by Python on the dataset. Every
answer cites recipe IDs and states its filters, the number of recipes it covers and the
method, and is checked for invented content before it is shown.

## 2. Stack

| Purpose | Choice | Why |
|---|---|---|
| Language | Python 3.13, managed by uv | reproducible installs from `uv.lock` |
| Data | pandas + Parquet, Pydantic for record shapes | ~125k rows fit in memory; readable code |
| Rules | YAML files in `config/` | normalization rules can be read and changed without code |
| Keyword search | bm25s | exact dish and ingredient terms |
| LLM | Ollama `qwen3:4b` (local, free) first; Gemini (google-genai) if a key is set | no quota or key needed for the interviewer; Gemini is faster when available |
| Interface | Typer + Rich CLI; web UI = FastAPI JSON API + one HTML/CSS/JS page (no build step) | full control of the layout; the same orchestrator behind both |

## 3. Architecture

```
User ──► CLI / web UI ──► Orchestrator (one turn)
                              1. LLM parser → StatePatch (JSON, schema-validated)
                              2. Session state ← apply patch (constraints persist)
                              3. Route: search | detail | stats | match | substitute | clarify
                              4. Engine runs on the full data (pandas)
                              5. Templates render the facts (IDs, counts, ingredient lists)
                              6. LLM writes a short explanation of those facts only
                              7. Grounding check (IDs, numbers, ingredients) → reply

Offline build (scripts/build_index.py):
  raw JSON → clean → parse + normalize lines → allergen flags → step counts
           → recipes.parquet + ingredients.parquet + build_report.json
```

## 4. Data decisions (Day 1, verified on the real files)

| Finding | Decision |
|---|---|
| 125,164 records; keys unique across files | ID = `{source}:{key}`, source ∈ `ar`, `epi`, `fn` |
| 517 records are `{}`; some lack a title, ingredients or instructions | kept and flagged; statistics use the complete recipes and state how many were excluded |
| Every Allrecipes ingredient line ends with `ADVERTISEMENT` | removed in a cleaned copy; the original text is kept unchanged |
| Section headings in ingredient lists ("For the sauce:") | flagged as headers, not counted as ingredients |
| ~15k instructions are one paragraph (after removing "Watch how to make this recipe.") | steps counted as sentences and labelled approximate |
| Same title and identical ingredient set appears more than once | flagged `duplicate_of`; statistics can remove them on request; search and matching always do |
| ~24 placeholder records (titles "Title", "QA"; instructions ";", "N/A", only a copyright line) | treated as missing title/instructions, so they are excluded as incomplete |

Originals (`title`, `ingredients_raw`, `instructions_raw`) are never modified.

## 5. Ingredient normalization

A line such as `2 (14.5 ounce) cans diced tomatoes, drained` is parsed into quantity 2,
unit `can`, amount 822 g, canonical `tomato`, form `canned`, prep `drained`.

1. **Clean**: remove artefacts and symbols, convert `½` to `1/2`.
2. **Quantity and unit**: numbers, mixed fractions, ranges (`2 to 3`), word numbers;
   units from `config/units.yaml`, converted to ml or g where possible. A package size in
   brackets is used for cans and packages.
3. **Name and prep**: the first comma-separated part that still names something is the
   name; the rest is preparation. Phrases like "to taste" and "for garnish" are cut.
4. **Alternatives**: "butter or margarine" keeps `butter` as the ingredient and records
   `margarine` as an alternative (used as direct substitution evidence on Day 3).
5. **Canonical name**: accents folded, form words (fresh, frozen, canned, dried) recorded,
   descriptors removed, last word singularized, synonyms applied (`scallion` → `green onion`).
6. **Base (family)**: varieties count as the same ingredient (`cherry tomato` → `tomato`),
   products do not (`tomato paste`, `garlic powder` stay separate).

Statistics support two explicit modes, and the answer always lists the names counted:
- **strict**: the ingredient and its varieties (fresh garlic, garlic cloves);
- **broad**: any name containing the word (also garlic powder, garlic salt).

**Validation against plain text search.** For "contains garlic AND onion" the engine counts
about 15,660 recipes (strict; the exact figure is in the evaluation report). A rough
plain-text regex over the same recipes finds about 16,500. The ~870-recipe difference was
inspected: it is mostly products the strict mode excludes on purpose (granulated garlic,
granulated onion), lines where onion is only the alternative ("shallot or onion"), brand
names ("Goya garlic") and ~30 unparseable lines. An earlier version also missed varieties
(pearl onion, elephant garlic) and "medium-sized onion"; these were added to the rules,
raising the count from 15,320.

**Validation on a random sample.** 60 random ingredient lines were labelled by hand
(`eval/cases/normalization.yaml`). The first parser version named the base ingredient
correctly for 51; general rule fixes (label prefixes such as "Suggested garnishes:",
"unbleached"/brand words, "bag of", variety families) brought it to 59/60, without any
line-specific rules.

## 6. Allergens and hard constraints

`config/allergens.yaml` defines categories (dairy, egg, peanut, tree nut, gluten,
shellfish, fish, soy, meat, other animal products) with terms, exceptions and uncertain
items, plus diet words (vegan, vegetarian) mapped to categories.

- The **whole line** is checked, so `oil, such as peanut oil` is caught.
- Exceptions are removed first: peanut butter, coconut milk and cream of tartar are not dairy.
- Uncertain items (margarine, chocolate, plain "stock") and lines with markers such as
  "vegan" or "dairy-free" are marked **uncertain**.
- A hard constraint removes both definite and uncertain recipes, and the answer says how
  many of each were removed. Constraints are never relaxed silently.
- Ingredient exclusions are always broad: "no peanuts" also removes peanut oil.

This is a best-effort reading of recipe text, not a medical safety guarantee.

Diets are shown as the diet, not as an exclusion: "vegetarian" (excludes meat, fish,
shellfish), never "no vegetarian" (`constraint_label` in `nlp/allergens.py`).

## 7. Statistics engine

`engines/stats.py` exposes typed operations over a `RecipeFilter`
(include all/any, exclude, title words, sources, step limits, match mode, duplicates):
`count`, `percentage`, `top_ingredients`, `ingredient_count_stats`, `rank_by_steps`.
Each returns a `StatsResult` with the answer, filters, number of recipes analyzed, method,
notes (spelling corrections, uncertain exclusions, ties) and example recipe IDs.
The LLM only chooses the operation and fills in the filter.

**Step rule**: one non-empty instruction line is one step, excluding site boilerplate; a
recipe stored as a single paragraph is split into sentences (labelled approximate).
Rankings break ties by recipe ID, and the answer says how many recipes tie at the cutoff.

## 8. Search

BM25 (`bm25s`) over each recipe's title (repeated 3× so a dish name in the title outranks
one in an ingredient list) and its canonical ingredient names, with the same singularizing
tokenizer for documents and queries. Every recipe is scored, then the hard filters run on
the full dataset, so "no dairy" is never limited to the top few hits. Exact duplicates are
skipped; ties are broken by recipe ID. Each hit carries evidence from its own ingredient
list, and the answer says how many search matches the constraints removed. Words absent
from the whole dataset are reported rather than silently ignored.

## 9. Conversation state

The LLM returns a **StatePatch**, never a reply. `apply_patch` applies it with fixed rules:
- exclusions and the step limit are session-wide hard constraints, kept across new topics
  until removed or reset ("I cannot have dairy" keeps applying);
- a restriction with no new request refines the active task (search or match);
- "the second one" is resolved by code from the last result list;
- statistics do not silently inherit dietary constraints; the answer says they were not
  applied;
- an exclusion is lifted by saying so ("mushrooms are okay", "I can have nuts again"), also
  in the same message as a new one ("…but exclude dairy"); names match regardless of plural;
- after a substitution, "use applesauce instead" keeps the same recipe and target.

Parsers: the LLM with a JSON schema (validated with Pydantic, one retry), then guards
(section 11). On any LLM error a rule-based parser takes over, so a quota problem or a
stopped Ollama never breaks a turn; it also lets the assistant and its tests run offline.

## 10. Ingredient matching

Candidates are recipes using at least one pantry item (from the ingredient index); hard
constraints are applied before ranking. Ranking is lexicographic so each position has a
one-line reason: most of your ingredients used → fewest extra ingredients (staples excluded)
→ fewest steps → recipe ID. A stated preference moves its key to the front; "use as many as
possible, prefer fewest additional" is the default order. Each result lists matched, extra
required and unused ingredients, staples assumed, and forms (e.g. canned tomato).
Quantities are compared only when both sides convert to the same dimension; otherwise the
answer says sufficiency was not verified. An ingredient the user excludes is removed from
their pantry. With no eligible recipe, the answer says so and separately lists the closest
alternatives, each marked with the constraint it breaks.

## 11. The LLM layer

The LLM handles language and judgment; code handles facts.

| Step | LLM does | Code does |
|---|---|---|
| Understand the message | produces a StatePatch (JSON schema enforced) | validates it; guards fill dropped slots and drop invented ones |
| Substitution | rewords the steps that mention the replaced ingredient | finds evidence, ranks and selects the substitute, sets its quantity, builds the recipe, checks every step edit |
| Reply opening (optional) | writes 2–3 sentences from the engine's facts | grounding check removes unsupported sentences |

**Providers.** Ollama with `qwen3:4b` (local, free, no quota) is tried first, then Gemini if
a key is set; with neither, a fallback parser keeps the assistant working. A permanent
error (bad key, no credits, server down) switches the session to the fallback once, with
one warning, instead of failing every turn.

**Small-model engineering.** Measured on 9 test messages, Qwen3 4B with a bare schema
parsed 5 correctly: it dropped "no peanuts"/"at most six steps" from long requests, turned
"vegetarian" into "no dairy" and invented a step limit. Two changes fixed all 9: worked
examples in the prompt, and **guards** — high-precision patterns ("at most N steps",
"no X", "how many … contain A and B") that fill or correct slots the LLM got wrong. Each
correction is logged (`--debug`) so the evaluation can report how often the LLM needed help.
Thinking mode is off and output length is capped to keep CPU latency acceptable.

Guards added after real conversations went wrong, each with a test:
- an exclusion with no restriction word in the message is dropped ("pasta *with* cream" is
  not "no dairy");
- an ingredient the message allows again is never also re-added as excluded;
- a replacement the user did not name is dropped (Qwen once turned "replace the butter"
  into "use apricot mignonette"), so the substitute comes from the evidence;
- "exclude eggs too" restricts the recipes; it does not remove eggs from the pantry unless
  the message says the user lacks them.

**Grounding check** (`render/grounding.py`): each sentence the LLM writes is removed if it
cites a recipe ID, number or ingredient absent from the engine's facts, or claims cooking
times, servings or nutrition. Output that looks like the model's own planning notes is
discarded. The facts are always shown in full below, so nothing is lost. Summaries are on
by default for API models and off for local CPU models (about 30–50 s extra per turn).

## 12. Substitution

All in `engines/substitution.py`; cooking knowledge in `config/roles.yaml`, labelled as such.

1. **Target lines and roles.** Lines are found by allergen category ("dairy") or ingredient
   ("cream", including heavy cream). Roles depend on whether the recipe is baked; the first
   is the main role. Egg in a bake: binding (main), leavening, moisture, structure,
   emulsification.
2. **Direct evidence.** 30,593 "X or Y" ingredient lines and 1,274 instruction sentences
   about substituting, mined at build time. Counted in recipes of the same kind (baked or
   not): "butter or olive oil" in a sauté says little about cookies. Lines about a surface
   use ("beaten egg or milk, for brushing") are ignored unless the target line is one too.
3. **Indirect evidence.** Similar recipes = same kind, same last title word (the dish type)
   and another shared title word, ranked by BM25. Ingredients much more common in those
   *without* the target (share ≥ 1.5×) are candidates. If few same-dish recipes lack the
   target (9 of 183 banana breads lack eggs), a single same-dish recipe counts for an
   ingredient that provides the main role, and the comparison widens to the dish type. An
   ingredient with no known role is never a candidate on indirect evidence alone (recipes
   without cream also use more tomato).
4. **Strength and role fit, rated separately.** Strength comes from the evidence only:
   strong (≥ 5 direct, or direct plus a clear contrast), moderate, weak; *conflicting* if
   it may contain a restricted ingredient (egg substitute when removing egg); dropped if it
   does contain one. Role coverage lists each of the target's roles as provided fully,
   partly or not (applesauce: moisture fully, binding partly, no leavening). Fit: good
   (main role fully), partial, unknown, poor. A good fit never upgrades weak evidence.
5. **Quantity, from the dataset only.**
   - *supported*: an "X or Y" line gives both amounts ("2 large eggs or 1/2 cup egg
     substitute" gives 1/2 cup for 2 eggs), a note gives a ratio ("1/4 cup applesauce for
     each egg"), or lines offer it at the same amount ("1 cup butter or shortening");
   - *estimated*: a same-dish recipe without the target uses it, scaled to this recipe by
     flour, pasta or rice ("1 cup applesauce with 3 cups flour" → 2/3 cup for 2 cups);
   - *unknown*: "Quantity not established by the dataset." Never a guessed 1:1.
6. **Ranking (fixed, explained to the user).** 1) may break a restriction → last;
   2) must provide the main role to be selected; 3) evidence strength; 4) evidence type:
   direct, then same dish, then related; 5) roles covered; 6) supporting recipes;
   7) quantity: supported, estimated, unknown. The answer says why #1 beats each other
   candidate by the first rule that separates them, and says so when candidates tie or are
   equally weak. If no candidate provides the main role, no recipe is produced.
7. **Adaptation, built by code.** Only the target lines change (extra target lines are
   removed with a stated reason); every other line is verbatim. The LLM may reword the
   steps that mention the target; an edit that adds a number (amount, time, temperature) or
   still names the target is rejected and that step keeps the rule-based rewrite.
8. **Moisture check.** Wet ingredients (those that provide moisture) per volume of flour,
   compared with the median of the same dish's recipes: Banana Banana Bread's 2 1/3 cups of
   banana are 117% of its flour against a median of 80% across 56 banana breads, so adding
   a wet substitute is flagged as a risk of a gummy or underbaked centre.
9. **Texture predictions.** One row per role (binding, rise, moisture, structure, batter)
   plus density and crumb, from what the substitute provides; labelled predictions.
10. **Status.** *supported* (strong/moderate evidence and a dataset quantity),
    *experimental* (weak evidence or estimated quantity), *incomplete* (quantity unknown:
    the list is not a complete recipe), *not adapted*. Baking temperature and time are
    quoted from the original and marked not re-tested.
11. **Presentation.** A five-line plain summary first (Swap, Why, Other options, Expect,
    Bake), then the adapted recipe, then the details: amount source, ranking reasons,
    every candidate with its evidence type and supporting recipes, moisture numbers,
    texture table and limitations.

Results on the assignment's examples: chocolate-chip cookies without butter, no dairy →
shortening (strong, same amount offered by the dataset); pasta with cream, no dairy →
olive oil (moderate; coconut milk has one direct line); banana bread without eggs → silken
tofu, weak evidence, quantity unknown, labelled an incomplete experimental adaptation, with
applesauce (about 2/3 cup, estimated) and soy yogurt as equally weak alternatives.

## 13. Web UI

`recipebot web` serves a single page (`src/recipebot/ui/web/`) and a small JSON API
(`ui/server.py`), one conversation per browser session.

- **Chat** messages go through the parser (LLM), exactly like the CLI.
- **Buttons and forms** (diet tiles, "What can I cook?", statistics presets, "Adapt this
  recipe") send a structured StatePatch to `/api/action`. That skips the LLM, so they are
  instant and deterministic, and they update the same conversation state, so a chat
  follow-up such as "exclude eggs too" works after a form.
- Each turn returns the engine result as JSON (`render/payloads.py`), drawn as cards; the
  full text answer is one click away. A substitution card shows the short summary and folds
  the recipe, ranking, evidence, texture and limitations below it.
- The home page: hero with feature pills that open their pages, a search box with voice
  input (the browser's own speech recognition, hidden where unsupported; the words go into
  the box to be checked before sending), example prompts and diet cards that set a
  constraint for the whole conversation. Layout adapts with container queries, so it fits
  whether the chat panel is open or not; the chat panel takes about 42% of the window.
- The UI only shows what the dataset has: no cooking times, servings, ratings, nutrition,
  cuisine labels or recipe photos (two-thirds of records name a picture file, but the
  images are a separate multi-GB download and are not used). The recipe card's tabs are
  Ingredients, Steps and Allergen check. All dataset text is HTML-escaped before display.
- The page and its files are sent with `Cache-Control: no-cache`, so a browser shows an
  updated UI after a change instead of a cached one.

## 14. Evaluation

`eval/run_eval.py` checks each part against something computed independently and writes
`eval/REPORT.md`: normalization (hand-labelled sample), parser (40 labelled messages,
many phrased unlike the prompt examples), statistics (vs. a plain-Python reference),
matching (constraints, lists and ranking re-derived per result), substitution (properties
of the adapted recipe), eight scripted conversations covering the assignment's required
cases, and a one-shot comparison where the same LLM answers without the pipeline. 151 unit
tests (`pytest`) cover the parser rules, guards, state, engines, substitution scenarios
(strong, weak, conflicting, missing quantity, ties, moisture risk, no reliable substitute,
follow-ups) and the web API.

## 15. Not implemented

- **Web search for weak substitution evidence** (optional in the brief). When local
  evidence is weak the assistant labels it weak, or declines; adding a clearly labelled
  external source is the natural next step.
- **Cuisine questions.** The dataset has no cuisine field; only 4.3% of titles name one
  ("Mexican", "Thai"). Answering them as title matches, labelled as such, would be honest;
  inferring cuisine from ingredients would not be a dataset fact.
- **Semantic (embedding) search.** BM25 handles dish and ingredient names well; vague
  requests ("something cozy") depend on the LLM turning them into keywords.
