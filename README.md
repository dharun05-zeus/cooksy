# Cooksy

**Cooksy** is a conversational recipe assistant over the
[Recipe Box](https://eightportions.com/datasets/Recipes/) dataset (~125,000 recipes) that
**searches, analyzes, matches and adapts recipes**, with every fact grounded in the dataset.

- **Search and Q&A**: dish names, ingredients or descriptions; follow-ups like "I cannot have
  dairy" refine the current search; "show me the second one".
- **Statistics** computed over the full filtered dataset (counts, percentages, top
  ingredients, average/median ingredient counts, ranking by steps), each with its filters,
  denominator and method.
- **Ingredient matching**: "I have eggs, onions, tomatoes and rice…" ranked with a rule you
  can read, showing matched, missing and extra ingredients; constraints are never relaxed
  silently.
- **Evidence-based substitution**: replacements backed by recipes in the dataset (cited by
  ID, labelled direct or indirect), ranked by stated rules, with a quantity taken from the
  dataset or marked unknown (never guessed), a moisture check against similar recipes,
  predicted texture changes, and an adapted recipe. The answer opens with a short plain
  summary; the evidence is folded below it.

The LLM understands the request and rewords recipe steps; **code computes every fact**,
chooses substitutes, and checks the LLM's output. See [DESIGN.md](DESIGN.md) for the architecture and decisions,
[eval/REPORT.md](eval/REPORT.md) for the evaluation, and [AI_USAGE.md](AI_USAGE.md).

## Setup (about 10 minutes)

Requires Python 3.11–3.13 and [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
uv sync
```

```bash
uv run python scripts/download_data.py
```

```bash
uv run python scripts/build_index.py
```

The download is 53 MB (checksum-verified); the build takes 3–5 minutes and writes
`data/processed/`.

If the download step reports a failure (the dataset site can refuse automated downloads with
HTTP 403), download `recipes_raw.zip` in a browser from the
[dataset page](https://eightportions.com/datasets/Recipes/) and pass it to the script; the
checksum is still verified:

```bash
uv run python scripts/download_data.py --zip PATH/TO/recipes_raw.zip
```

### LLM (free, local): Ollama + Qwen3 4B

1. Install [Ollama](https://ollama.com/download) and start it.
2. Download the model (about 2.5 GB):

```bash
ollama pull qwen3:4b
```

The app finds it automatically; no API key or account is needed. On a laptop CPU expect
about 5–10 s per message and up to a minute for a substitution (the first message also
loads the model); a GPU is much faster. Another installed model can be used by setting
`OLLAMA_MODEL` in a `.env` file (see `.env.example`).

**Without Ollama** the assistant still runs with a built-in fallback parser for common
phrasings and says so at startup; every answer is still computed from the dataset.

## Use

Web UI (then open http://localhost:8000):

```bash
uv run recipebot web
```

Chat on the right; diet cards, "What can I cook?" and statistics forms on the left run
instantly without the LLM and share the same conversation. The search box on the home page
also takes voice input in browsers that support it (Chrome, Edge, Safari). If the page looks
outdated after an update, press Ctrl+F5 once.

Command line:

```bash
uv run recipebot chat
```

Replay the assignment's example conversations (`--debug` shows how each message was parsed):

```bash
uv run recipebot chat --script examples/pdf_conversations.txt --debug
```

```bash
uv run recipebot chat --script examples/substitution_conversations.txt --debug
```

In the CLI: `/state` shows active constraints, `/reset` starts over, `/quit` exits.

Things to try: *"Find a penne pasta recipe"* → *"I cannot have dairy"* → *"Show me the first
one"*; *"How many recipes contain both garlic and onion? What percentage is that?"*;
*"I have tempeh and kimchi. Suggest recipes with at most one step."* (no match);
*"Find chocolate chip cookies"* → *"I cannot have dairy. Replace the butter in the first one."*;
*"Take this banana bread recipe and remove eggs."* → *"Use applesauce instead."*;
*"Find vegetarian pasta without mushrooms."* → *"Actually, mushrooms are okay. But exclude dairy."*

## Evaluation and tests

```bash
uv run python eval/run_eval.py
```

```bash
uv run python eval/run_eval.py --provider none
```

The second form runs without an LLM in about a minute (the parser then uses the fallback)
and writes `eval/REPORT_offline.md` (not committed); the LLM run writes `eval/REPORT.md`. Raw results and
conversation transcripts go to `eval/results/` and `eval/transcripts/`. Unit tests:

```bash
uv run pytest
```

## Project layout

```
config/            rules as data: units, synonyms, allergens, ingredient roles, staples
scripts/           download_data.py, build_index.py
src/recipebot/
  data/            loading the 3 JSON files, the build pipeline
  nlp/             ingredient parser, normalization, allergen check, step counting
  engines/         store, search (BM25), statistics, matching, substitution
  llm/             Ollama client, message parser + guards, fallback parser
  dialogue/        session state and the orchestrator (one turn)
  render/          answer templates and the grounding check
  ui/              CLI, web API (FastAPI) and the web page (ui/web/)
eval/              evaluation cases, runner, report, transcripts
tests/             unit tests on a 9-record fixture dataset
```



## Limitations

- The dataset has no cooking times, servings, nutrition or cuisine labels; questions about
  them are answered with "the dataset does not record …". Recipe photos are not shown: about
  two-thirds of records name a picture file, but the images are a separate, much larger
  download.
- Substitution amounts come only from the dataset, so many are "not established" (the
  answer then labels the recipe an incomplete experimental adaptation). Texture effects are
  predictions from a hand-written role table, not tested results.
- Allergen and diet checks read recipe text with word lists; they are conservative
  (uncertain items are excluded) but are **not a medical safety guarantee**.
- Ingredient normalization is rule-based (59/60 on a random sample); brand names and unusual
  phrasings can still be misread.
- A 4B model on a CPU is slow and makes parsing mistakes on some phrasings; guards catch many
  (see the report). A larger Ollama model (e.g. `qwen3:8b`) improves both, given the hardware.
- Voice input uses the browser's speech recognition; in Chrome that sends the audio to
  Google. Typing works everywhere.
