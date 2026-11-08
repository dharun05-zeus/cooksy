# Use of AI tools

I built this project with **Claude Code** (Anthropic's Claude) as an AI pair programmer.
I owned the requirements, the key decisions, the review of each stage and the testing;
the AI wrote the code and drafted the documentation under my direction.

## My role

- **Requirements and constraints.** I analysed the assignment and set the constraints the
  design had to meet: completely free to run, runnable on an interviewer's machine without my
  accounts or keys, every fact grounded in the dataset, and a result that shows real use of an
  LLM rather than a keyword bot.
- **Technology decisions.** I compared the options (rules only, Gemini's free tier, a local
  model) and decided on an LLM-first design. When my Gemini key turned out to be on a billed
  project, I chose a free local model (Qwen3 4B through Ollama) as the default, so the
  interviewer needs no API key or quota.
- **Critical review of the plan.** Before any code was written I asked for the plan to be
  evaluated against the assignment, then required every weakness found to be fixed and the
  revised plan checked again. This led to the evidence-based substitution design, the
  separate ingredient-normalization module, and keeping all facts out of the LLM's hands.
- **Planning and direction.** I split the work into four stages (data and statistics;
  search, matching and conversation; LLM and substitution; evaluation and delivery) and
  reviewed each stage before starting the next.
- **Quality control.** I asked for a full bug review of the first two stages before
  continuing, and for another before the final stage. These reviews found and fixed real
  problems, for example substitutions replacing the wrong line in recipes with section
  headings.
- **Testing.** I set up the LLM (Ollama and an API key), ran the assistant, and checked its
  answers, its speed on my laptop, and the evaluation report.
- **User interface design.** I chose the visual design of the web UI and specified that it
  must show only features the system really has (no cooking times, ratings or nutrition,
  which the dataset does not contain). I provided the home-page mockup that the hero,
  feature pills and diet cards follow, supplied the chef illustration, and asked for a
  larger chat panel.
- **Specification of the substitution feature.** After testing the assignment's banana
  bread example myself, I judged that the answer did not meet the brief and wrote a detailed
  specification for reworking it: quantities only from the dataset (supported, estimated or
  explicitly unknown, never a silent 1:1), a role-by-role analysis of what each substitute
  can and cannot replace, a transparent ranking that keeps evidence strength separate from
  functional fit, a moisture check against the existing ingredients, labelled texture
  predictions, an adaptation status, and eight test scenarios.
- **Finding problems by using the product.** I tested conversations by hand and reported
  the failures, which were then fixed with tests: a removed restriction that stayed active
  ("mushrooms are okay"), a diet shown as "no vegetarian", answers that were too long and
  technical (now a short summary first), and missing cuisine and photo data, which I asked
  to be checked against the dataset before deciding how to present it.

## The AI assistant's role

| Area | What the AI did |
|---|---|
| Code | Wrote the code in `src/`, `scripts/` and `eval/` to my specifications, and fixed the bugs found in review |
| Data analysis | Profiled the three JSON files and reported quirks (the `ADVERTISEMENT` suffix, one-paragraph instructions, placeholder records, duplicates) for me to decide on |
| Tests and evaluation | Wrote the unit tests, the evaluation cases and the evaluation runner, and labelled the 60-line normalization sample |
| Documentation | Drafted the README, DESIGN and the evaluation discussion |
| Web UI | Implemented the page to my mockup (layout, icons, responsive behaviour) and made the chef image's background transparent |

## LLMs inside the application

The assistant itself uses an LLM at run time (see DESIGN.md §11):

- **Qwen3 4B via Ollama** (default, local), or **Gemini** if an API key is configured.
- The LLM turns messages into structured requests, rewords the recipe steps a substitution
  changes, and (optionally) writes a short summary. Code chooses the substitute and its
  quantity.
- It never produces dataset facts: counts, rankings, recipe IDs and ingredient lists come from
  code, and LLM output is validated (JSON schema, guards, substitution checks, grounding check).

## Data

The Recipe Box dataset (eightportions.com, collected by Ryan Lee) is downloaded by
`scripts/download_data.py`; it is not redistributed in this repository.
