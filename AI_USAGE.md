# Use of AI tools

> Author: please review this file and adjust it so it describes your own process exactly.

## AI coding assistant

This project was built with **Claude Code** (Anthropic's Claude) as a pair programmer.

| Where | What the AI did | What I did |
|---|---|---|
| Planning | Proposed and critiqued architectures; compared LLM options (local Qwen vs. Gemini vs. Groq) against the assignment and my constraints (free, runs on an interviewer's machine) | Chose the approach: LLM-first, a free local model, every fact computed by code |
| Data analysis | Profiled the three JSON files and surfaced quirks (the `ADVERTISEMENT` suffix, one-paragraph instructions, placeholder records, duplicates) | Decided how each should be handled |
| Code | Wrote most of the code in `src/`, `scripts/` and `eval/` | Directed the work, reviewed it, ran it, and asked for changes and bug fixes |
| Testing | Wrote unit tests and the fixture dataset, and found bugs by running real cases (e.g. substitution evidence drawn from banana drinks for banana bread, line numbers shifted by section headings) | Reviewed the failures and the fixes |
| Evaluation | Wrote the evaluation cases and labelled the 60-line normalization sample | Reviewed the labels and the cases |
| Documentation | Drafted README, DESIGN and this file | Edited them |

I can explain every part of the system: the data pipeline, ingredient normalization, BM25
search, the matching and ranking rules, the substitution evidence, the LLM guards and the
grounding check.

## LLMs inside the application

The assistant itself uses an LLM at run time (see DESIGN.md §11):

- **Qwen3 4B via Ollama** (default, local), or **Gemini** if an API key is configured.
- The LLM converts messages into structured requests, chooses substitutes from evidenced
  candidates and writes the edits, and (optionally) writes a short summary.
- It never produces dataset facts: counts, rankings, recipe IDs and ingredient lists come from
  code, and LLM output is validated (JSON schema, guards, substitution validation, grounding
  check).

## Data

The Recipe Box dataset (eightportions.com, collected by Ryan Lee) is downloaded by
`scripts/download_data.py`; it is not redistributed in this repository.
