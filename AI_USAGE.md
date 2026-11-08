# Use of AI tools

I led this project: I defined the requirements, made the design and technology decisions,
specified each feature, reviewed and tested every stage, and decided what was good enough to
ship. I used **Claude Code** (Anthropic's Claude) as an AI pair programmer to implement those
decisions.

## My role

**Problem framing and requirements**
- Analysed the assignment and turned it into hard constraints for the design: completely
  free to run, runnable on an interviewer's machine without my accounts or keys, every fact
  grounded in the dataset, and real use of an LLM rather than a keyword bot.

**Architecture and technology decisions**
- Compared the options (rules only, Gemini's free tier, a local model) and chose an
  LLM-first design in which the LLM interprets requests and code produces every fact.
- When my Gemini key turned out to be on a billed project, switched to a free local model
  (Qwen3 4B via Ollama). I later tried Groq as a hosted option too, then decided to keep
  only the local model: free quotas run out, and the interviewer should not need any
  account or API key.
- Had the plan critically evaluated against the assignment before any code was written,
  required every weakness to be fixed, and had the revised plan checked again. This shaped
  the evidence-based substitution design, the separate ingredient-normalization module and
  keeping all facts out of the LLM's hands.

**Feature specification**
- Split the work into four stages (data and statistics; search, matching and conversation;
  LLM and substitution; evaluation and delivery), each reviewed before the next began.
- After testing the assignment's banana bread example myself, judged that the substitution
  answer did not meet the brief and specified its rework: quantities only from the dataset
  (supported, estimated or explicitly unknown, never a silent 1:1), a role-by-role analysis
  of what each substitute can and cannot replace, a transparent ranking that keeps evidence
  strength separate from functional fit, a moisture check against the existing ingredients,
  labelled texture predictions, an adaptation status, and eight test scenarios.

**Quality: review and testing**
- Required full bug reviews of the first two stages before continuing and again before the
  final stage; these found real problems, such as substitutions replacing the wrong line in
  recipes with section headings.
- Set up and ran the system myself (Ollama, web UI), tested conversations by hand
  and reported the failures I found, each then fixed with a test: a restriction that stayed
  active after I allowed the ingredient again, a diet shown as "no vegetarian", and answers
  that were too long and technical.
- Asked for the data to be checked before deciding how to present things it lacks (cuisine
  labels, photos), so the assistant states the gap instead of guessing.
- Required a test of the setup from a fresh clone, which exposed that the dataset site
  refuses automated downloads; the README now documents the manual route.

**Product and user experience**
- Set the rule that the UI shows only what the system really has (no cooking times,
  ratings or nutrition, which the dataset does not contain).
- Provided the home-page mockup and the chef illustration, asked for the substitution
  answer to lead with a short plain summary, and for a larger chat panel.
- Asked for a final cleanup so the code stays simple enough for me to change on my own.

## What the AI tool did

Working from my specifications and feedback, Claude Code generated the implementation
(`src/`, `scripts/`, `eval/`), the unit tests and evaluation cases, profiled the raw dataset
for me to decide on its quirks, and drafted the documentation, which I reviewed. Bugs found
in my reviews and testing were fixed the same way.

## LLMs inside the application

The assistant itself uses an LLM at run time (see DESIGN.md §11):

- **Qwen3 4B via Ollama**, running locally; no API key or account.
- The LLM turns messages into structured requests, rewords the recipe steps a substitution
  changes, and (optionally) writes a short summary. Code chooses the substitute and its
  quantity.
- It never produces dataset facts: counts, rankings, recipe IDs and ingredient lists come from
  code, and LLM output is validated (JSON schema, guards, step checks, grounding check).

## Data

The Recipe Box dataset (eightportions.com, collected by Ryan Lee) is downloaded by
`scripts/download_data.py`; it is not redistributed in this repository.
