"""Reproducible evaluation of the Recipe Intelligence Assistant.

Usage:
    uv run python eval/run_eval.py                    # with the LLM the app would use
    uv run python eval/run_eval.py --provider none    # no LLM (fallback parser), ~1 minute
    uv run python eval/run_eval.py --only parser,stats
    uv run python eval/run_eval.py --refresh-baseline # ask the one-shot LLM again
    uv run python eval/run_eval.py --report-only eval/results/ollama.json

Writes eval/results/<provider>.json, eval/transcripts/*.md and eval/REPORT.md.
Every check compares the assistant's output with something computed independently:
reference statistics in plain Python, constraints re-checked on each returned recipe,
and recipe IDs looked up in the dataset.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

import yaml

from recipebot.app import make_llm
from recipebot.config import get_settings, use_utf8_console
from recipebot.dialogue.orchestrator import Orchestrator
from recipebot.dialogue.state import SessionState, StatsRequest, resolve_intent
from recipebot.engines import stats as stats_engine
from recipebot.engines.matching import DEFAULT_ORDER, MatchRequest, match
from recipebot.engines.search import SearchIndex, search
from recipebot.engines.stats import RecipeFilter
from recipebot.engines.store import RecipeStore
from recipebot.engines.substitution import SubstitutionEngine
from recipebot.llm.parser import MessageParser
from recipebot.nlp.ingredient_parser import parse_line
from recipebot.nlp.text import fold
from recipebot.render import templates

EVAL_DIR = Path(__file__).parent
CASES = EVAL_DIR / "cases"
ID_PATTERN = re.compile(r"\b(?:ar|epi|fn):[A-Za-z0-9./]+")
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def load(name: str) -> list[dict]:
    return yaml.safe_load((CASES / f"{name}.yaml").read_text(encoding="utf-8"))


def cited_ids(text: str, store: RecipeStore) -> tuple[list[str], list[str]]:
    """(IDs found in the text, those that do not exist in the dataset). Real IDs can end
    in dots ("ar:...MSt.."), so a trailing full stop is ambiguous; any variant counts."""
    found = [i.rstrip(",;)") for i in ID_PATTERN.findall(text)]

    def exists(rid: str) -> bool:
        stem = rid.rstrip(".")
        return any(stem + "." * k in store.position for k in range(4))

    return found, [i for i in found if not exists(i)]


# ----- parser -----------------------------------------------------------------------

def _terms(store: RecipeStore, terms: list[str]) -> set[str]:
    """Normalize exclusion words: categories expand ("nuts" -> peanut, tree_nut), other
    words become their canonical ingredient name ("onions" -> onion)."""
    out: set[str] = set()
    for term in terms:
        cats = store.allergens.categories_for(term)
        out |= set(cats) if cats else {store.lexicon.canonicalize(term).canonical or fold(term)}
    return out


def _bases(store: RecipeStore, names: list[str]) -> set[str]:
    return {store.resolve(n, "strict").base for n in names}


def eval_parser(store: RecipeStore, parser: MessageParser) -> dict:
    rows = []
    for case in load("parser"):
        st = case.get("state", {})
        n = st.get("last_results", 0)
        state = SessionState(task=st.get("task"), exclude=st.get("exclude", []),
                             last_results=[f"x:{i}" for i in range(n)],
                             last_result_titles=[f"Recipe {i + 1}" for i in range(n)])
        started = time.perf_counter()
        patch = resolve_intent(state, parser.parse(case["message"], state))
        seconds = time.perf_counter() - started
        checks = []
        for field, want in case["expect"].items():
            got, ok = _parser_field(store, patch, field, want)
            checks.append({"field": field, "expected": want, "got": got, "ok": ok})
        rows.append({"message": case["message"], "passed": all(c["ok"] for c in checks),
                     "checks": checks, "source": parser.last_source,
                     "corrections": parser.last_corrections, "seconds": round(seconds, 1)})
    fields = Counter(c["field"] for r in rows for c in r["checks"])
    field_ok = Counter(c["field"] for r in rows for c in r["checks"] if c["ok"])
    return {
        "cases": rows,
        "passed": sum(r["passed"] for r in rows),
        "total": len(rows),
        "field_accuracy": {f: f"{field_ok[f]}/{n}" for f, n in sorted(fields.items())},
        "llm_used": sum(r["source"] != "rules" for r in rows),
        "guard_corrections": sum(bool(r["corrections"]) for r in rows),
        "median_seconds": statistics.median(r["seconds"] for r in rows),
    }


def _parser_field(store, patch, field, want):
    s, sub = patch.stats, patch.substitute
    if field == "intent":
        return patch.intent, patch.intent == want
    if field == "intent_in":
        return patch.intent, patch.intent in want
    if field == "query_has":
        q = fold(patch.query or "")
        return patch.query, all(w in q for w in want)
    if field in ("exclude", "remove_exclude"):
        got = patch.add_exclude if field == "exclude" else patch.remove_exclude
        return got, _terms(store, got) == _terms(store, want)
    if field == "pantry":
        got = [p.name for p in patch.pantry]
        return got, _bases(store, got) == _bases(store, want)
    if field in ("max_steps", "limit", "result_number"):
        got = getattr(patch, field)
        return got, got == want
    if field == "preferences":
        return patch.preferences, list(patch.preferences) == want
    if field == "stats_operation":
        got = s.operation if s else None
        return got, got == want
    if field == "stats_include":
        got = s.include_all if s else []
        return got, _bases(store, got) == _bases(store, want)
    if field in ("k", "order"):
        got = getattr(s, field) if s else None
        return got, got == want
    if field == "substitute_target":
        got = sub.target if sub else None
        return got, got is not None and _terms(store, [got]) == _terms(store, [want])
    if field == "recipe_query_has":
        q = fold(sub.recipe_query or "") if sub else ""
        return sub.recipe_query if sub else None, all(w in q for w in want)
    raise ValueError(f"unknown expectation field: {field}")


# ----- normalization ----------------------------------------------------------------

def eval_normalization(store: RecipeStore) -> dict:
    rows = []
    for case in load("normalization"):
        parsed = parse_line(case["line"], store.lexicon)
        got = parsed.base if parsed else ""
        rows.append({"name": case["line"], "passed": got == case["base"], "expected": case["base"],
                     "got": got, "was_wrong": case.get("was_wrong")})
    fixed = sum(1 for r in rows if r["was_wrong"] and r["passed"])
    return {"cases": rows, "passed": sum(r["passed"] for r in rows), "total": len(rows),
            "first_version_correct": sum(1 for r in rows if not r["was_wrong"]),
            "fixed_since": fixed}


# ----- statistics -------------------------------------------------------------------

def run_stats(store: RecipeStore, req: StatsRequest):
    f = RecipeFilter(include_all=req.include_all, include_any=req.include_any, exclude=req.exclude,
                     title_contains=req.title_contains, match_mode=req.match_mode)
    if req.operation == "count":
        return stats_engine.count(store, f)
    if req.operation == "percentage":
        return stats_engine.percentage(store, f)
    if req.operation == "top_ingredients":
        return stats_engine.top_ingredients(store, f, k=req.k, exclude_staples=req.exclude_staples)
    if req.operation == "ingredient_count_stats":
        return stats_engine.ingredient_count_stats(store, f)
    return stats_engine.rank_by_steps(store, f, k=req.k, order=req.order)


_COLUMNS: dict = {}


def _columns(store: RecipeStore) -> dict:
    """The recipe columns as plain Python lists, read once."""
    if not _COLUMNS:
        r = store.recipes
        _COLUMNS.update(
            complete=r["is_complete"].tolist(), bases=[set(b) for b in r["bases"]],
            canonicals=[set(c) for c in r["canonicals"]],
            flags=[set(a) | set(u) for a, u in zip(r["allergens"], r["allergens_uncertain"],
                                                    strict=True)],
            titles=[fold(t) for t in r["title"]])
    return _COLUMNS


def _reference_rows(store: RecipeStore, req: StatsRequest) -> list[int]:
    """Row positions matching the request, computed with plain Python sets."""
    cols = _columns(store)
    names = {}
    for term in req.include_all:
        resolved = store.resolve(term, req.match_mode)
        names[term] = (resolved.base, set(resolved.matched_names))
    excluded_cats = {c for t in req.exclude for c in (store.allergens.categories_for(t) or [])}
    rows = []
    for i in range(store.n):
        if not cols["complete"][i]:
            continue
        bases, canon = cols["bases"][i], cols["canonicals"][i]
        if req.match_mode == "strict":
            ok = all(base in bases for base, _ in names.values())
        else:
            ok = all(canon & matched for _, matched in names.values())
        if not ok:
            continue
        if cols["flags"][i] & excluded_cats:
            continue
        title = cols["titles"][i]
        if not all(re.search(rf"\b{re.escape(fold(w))}", title) for w in req.title_contains):
            continue
        rows.append(i)
    return rows


def eval_stats(store: RecipeStore) -> dict:
    rows = []
    complete = int(store.complete.sum())
    for case in load("stats"):
        req = StatsRequest(**case["request"])
        result = run_stats(store, req)
        ref_rows = _reference_rows(store, req)
        r = store.recipes
        if req.operation == "count":
            expected, got = len(ref_rows), result.value
        elif req.operation == "percentage":
            expected = (len(ref_rows), round(100 * len(ref_rows) / complete, 2))
            got = (result.numerator, result.value)
        elif req.operation == "ingredient_count_stats":
            counts = [int(r["ingredient_count"].iat[i]) for i in ref_rows]
            expected = (round(statistics.mean(counts), 2), float(statistics.median(counts)))
            got = (result.rows[0]["mean"], float(result.rows[0]["median"]))
        elif req.operation == "rank_by_steps":
            sign = 1 if req.order == "fewest" else -1
            ordered = sorted(ref_rows, key=lambda i: (sign * int(r["steps"].iat[i]),
                                                      r["recipe_id"].iat[i]))
            expected = [r["recipe_id"].iat[i] for i in ordered[:req.k]]
            got = [row["recipe_id"] for row in result.rows]
        else:
            counter = Counter(b for i in ref_rows for b in set(r["bases"].iat[i])
                              if not (req.exclude_staples and b in store.lexicon.staples))
            ranked = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:req.k]
            expected = [(name, n) for name, n in ranked]
            got = [(row["ingredient"], row["recipes"]) for row in result.rows]
        states_method = bool(result.method) and bool(result.filters or not case["request"].get(
            "include_all")) and result.denominator > 0
        rows.append({"name": case["name"], "passed": expected == got and states_method,
                     "expected": str(expected), "got": str(got), "answer": result.answer,
                     "explains_method": states_method})
    return {"cases": rows, "passed": sum(r["passed"] for r in rows), "total": len(rows)}


# ----- matching ---------------------------------------------------------------------

def eval_matching(store: RecipeStore) -> dict:
    rows = []
    for case in load("matching"):
        req = MatchRequest(**case["request"])
        result = match(store, req)
        problems = []
        cats = {c for t in req.exclude for c in (store.allergens.categories_for(t) or [])}
        names = {n for t in req.exclude if not store.allergens.categories_for(t)
                 for n in store.resolve(t, "broad").matched_names}
        order = list(dict.fromkeys([*req.preferences, *DEFAULT_ORDER]))
        keys = []
        for m in result.results:
            row = store.get(m.recipe_id)
            bases = list(row["bases"])
            flags = set(row["allergens"]) | set(row["allergens_uncertain"])
            if flags & cats:
                problems.append(f"{m.recipe_id} violates exclusion: {sorted(flags & cats)}")
            if set(row["canonicals"]) & names:
                problems.append(f"{m.recipe_id} contains an excluded ingredient")
            if req.max_steps is not None and int(row["steps"]) > req.max_steps:
                problems.append(f"{m.recipe_id} has {row['steps']} steps > {req.max_steps}")
            pantry = result.pantry
            if m.matched != [b for b in pantry if b in bases]:
                problems.append(f"{m.recipe_id} matched list is wrong")
            extra = [b for b in bases if b not in pantry and b not in store.lexicon.staples]
            if m.extra_required != extra:
                problems.append(f"{m.recipe_id} extra-required list is wrong")
            values = {"most_matched": -len(m.matched), "fewest_extra": len(m.extra_required),
                      "fewest_steps": m.steps}
            keys.append(tuple(values[k] for k in order) + (m.recipe_id,))
        if keys != sorted(keys):
            problems.append("results are not in the stated ranking order")
        if case.get("expect_no_match"):
            if not result.no_match:
                problems.append("expected no eligible recipe, but results were returned")
            if any(not alt.violations for alt in result.alternatives):
                problems.append("an alternative is not marked with the constraint it breaks")
        elif result.no_match:
            problems.append("no recipe returned")
        rows.append({"name": case["name"], "passed": not problems, "problems": problems,
                     "results": [f"{m.recipe_id} {m.title} ({m.reason})"
                                 for m in result.results or result.alternatives]})
    return {"cases": rows, "passed": sum(r["passed"] for r in rows), "total": len(rows)}


# ----- substitution -----------------------------------------------------------------

def eval_substitution(store, index, engine: SubstitutionEngine, llm) -> dict:
    rows = []
    for case in load("substitution"):
        hits = search(store, index, case["dish"], RecipeFilter(), k=40).hits
        has = [h for h in hits if engine.contains(h.recipe_id, case["target"])]
        lacks = [h for h in hits if not engine.contains(h.recipe_id, case["target"])]
        pick = (lacks if case.get("recipe_without_target") else has)[:1]
        if not pick:
            rows.append({"name": case["name"], "passed": False, "problems": ["no recipe found"]})
            continue
        started = time.perf_counter()
        restrictions = case.get("restrictions", [])
        result = engine.adapt(pick[0].recipe_id, case["target"], restrictions,
                              case.get("replacement"), llm)
        seconds = time.perf_counter() - started
        chosen_by = "LLM" if result.method == "llm" else "rules"
        text = templates.render_substitution(result, chosen_by)
        problems = _substitution_problems(store, engine, case, result, text)
        rows.append({
            "name": case["name"], "passed": not problems, "problems": problems,
            "recipe": f"{result.title} [{result.recipe_id}]", "method": result.method,
            "substitute": result.adapted.substitute if result.adapted else None,
            "strength": result.evidence.best_strength, "message": result.message,
            "validation_errors": result.validation_errors, "seconds": round(seconds, 1),
        })
    return {"cases": rows, "passed": sum(r["passed"] for r in rows), "total": len(rows),
            "llm_rewrites": sum(r.get("method") == "llm" for r in rows)}


def _substitution_problems(store, engine, case, result, text) -> list[str]:
    expect, problems = case["expect"], []
    _, missing = cited_ids(text, store)
    if missing:
        problems.append(f"cites recipe IDs that do not exist: {missing}")
    if expect == "no_target":
        return problems + ([] if "does not contain" in result.message else ["target not reported"])
    if expect == "refuse":
        return problems + ([] if "breaks your restrictions" in result.message
                           else ["a forbidden replacement was not refused"])
    adapted = result.adapted
    declined = result.message or adapted is None or adapted.substitute.lower() == "none"
    if expect == "adapt" and declined:
        return problems + [f"no adaptation: {result.message or 'LLM chose none'}"]
    if declined:
        return problems
    ev = result.evidence
    cats = {c for t in ev.restricted for c in (store.allergens.categories_for(t) or [])}
    original = result.original_ingredients
    targets = {pos for pos, _ in ev.target_lines}
    for pos, line in enumerate(original):
        if pos not in targets and line not in adapted.ingredients:
            problems.append(f"unchanged line altered: {line}")
    for line in adapted.ingredients:
        if line in original:
            continue
        hits = {h.category for h in store.allergens.classify(line)}
        parsed = parse_line(line.replace("(estimate)", ""), store.lexicon)
        if hits & cats or (parsed and parsed.base in ev.target_names):
            problems.append(f"new line contains a restricted ingredient: {line}")
    if adapted.substitute not in {c.name for c in ev.candidates}:
        problems.append(f"substitute {adapted.substitute} is not an evidenced candidate")
    best = next((c for c in ev.candidates if c.name == adapted.substitute), None)
    if best and best.strength in ("weak", "conflicting") and "Caution" not in text:
        problems.append("weak evidence was not flagged")
    return problems


# ----- conversations ----------------------------------------------------------------

def new_bot(store, index, llm, summaries=False) -> Orchestrator:
    return Orchestrator(store, index, MessageParser(llm), llm, summaries)


def eval_conversations(store, index, llm, provider: str) -> dict:
    out_dir = EVAL_DIR / "transcripts"
    out_dir.mkdir(exist_ok=True)
    rows = []
    for n, case in enumerate(load("conversations"), 1):
        bot = new_bot(store, index, llm)
        lines = [f"# {case['name']}", "", f"Parser: {bot.parser.name}. Covers: "
                 + ", ".join(case["covers"]), ""]
        problems = []
        for turn_no, turn in enumerate(case["turns"], 1):
            result = bot.handle(turn["user"])
            exp = turn.get("expect", {})
            for s in exp.get("reply_has", []):
                if s not in result.reply:
                    problems.append(f"turn {turn_no}: reply lacks '{s}'")
            any_of = exp.get("reply_has_any")
            if any_of and not any(s in result.reply for s in any_of):
                problems.append(f"turn {turn_no}: reply has none of {any_of}")
            for s in exp.get("reply_lacks", []):
                if s in result.reply:
                    problems.append(f"turn {turn_no}: reply should not contain '{s}'")
            st = exp.get("state", {})
            if "exclude_has" in st and not _terms(store, [st["exclude_has"]]) <= _terms(
                    store, bot.state.exclude):
                problems.append(f"turn {turn_no}: '{st['exclude_has']}' not in active exclusions")
            if "query_has" in st and st["query_has"] not in fold(bot.state.query):
                problems.append(f"turn {turn_no}: active query lost '{st['query_has']}'")
            if "max_steps" in st and bot.state.max_steps != st["max_steps"]:
                problems.append(f"turn {turn_no}: max_steps is {bot.state.max_steps}")
            _, missing = cited_ids(result.reply, store)
            if missing:
                problems.append(f"turn {turn_no}: cites non-existent IDs {missing}")
            lines += [f"**User:** {turn['user']}", "",
                      f"*parser: {result.parser}, {result.seconds}s"
                      + (f"; guard corrections: {result.corrections}" if result.corrections
                         else "") + "*", "", "```text", result.reply, "```", ""]
        (out_dir / f"{n:02d}_{provider}.md").write_text("\n".join(lines), encoding="utf-8")
        rows.append({"name": case["name"], "covers": case["covers"], "passed": not problems,
                     "problems": problems, "transcript": f"transcripts/{n:02d}_{provider}.md"})
    return {"cases": rows, "passed": sum(r["passed"] for r in rows), "total": len(rows)}


# ----- one-shot baseline ------------------------------------------------------------

ONE_SHOT_SYSTEM = "You are a helpful cooking assistant. Answer the question directly."


def eval_baseline(store, index, llm, refresh: bool) -> dict:
    cache_path = EVAL_DIR / "baseline" / "one_shot.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    rows = []
    for case in load("baseline"):
        if refresh or case["name"] not in cache:
            if llm is None:
                rows.append({"name": case["name"], "skipped": "no LLM and no saved answer"})
                continue
            # Plenty of room: Qwen3 reasons in its answer before concluding, and a cut-off
            # answer would not be a fair comparison.
            answer = llm.generate_text(ONE_SHOT_SYSTEM, case["question"], max_tokens=1200)
            cache[case["name"]] = {"model": llm.name, "date": str(date.today()),
                                   "answer": answer}
        one_shot = cache[case["name"]]
        system_reply = new_bot(store, index, llm).handle(case["assistant_message"]).reply
        rows.append({
            "name": case["name"], "question": case["question"],
            "one_shot_model": one_shot["model"], "one_shot_answer": one_shot["answer"],
            "one_shot_ok": _baseline_ok(store, case, one_shot["answer"]),
            "system_answer": system_reply[:1200],
            "system_ok": _baseline_ok(store, case, system_reply),
        })
    cache_path.parent.mkdir(exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
    scored = [r for r in rows if "skipped" not in r]
    outcomes = Counter(r["one_shot_ok"][2] for r in scored)
    return {"cases": rows, "one_shot_correct": outcomes["correct"],
            "one_shot_declined": outcomes["declined"],
            "one_shot_fabricated": outcomes["fabricated"],
            "system_correct": sum(r["system_ok"][0] for r in scored), "total": len(scored)}


def _baseline_ok(store, case, answer: str) -> tuple[bool, str, str]:
    """(correct?, explanation, outcome) with outcome correct | declined | fabricated."""
    if "number" in case:
        asked = {n.replace(",", "") for n in NUMBER.findall(case["question"])}
        values = [float(n.replace(",", "")) for n in NUMBER.findall(answer)
                  if n.replace(",", "") not in asked]
        tolerance = case["number"] * case["tolerance"] / 100
        if any(abs(v - case["number"]) <= tolerance for v in values):
            return True, "states the dataset value", "correct"
        if values:
            return False, (f"states numbers ({', '.join(f'{v:g}' for v in values[:4])}) but none "
                           f"within {case['tolerance']}% of the dataset value "
                           f"{case['number']}"), "fabricated"
        return False, "gives no value (it has no access to the data)", "declined"
    if case.get("ids_must_exist"):
        found, missing = cited_ids(answer, store)
        if not found:
            return False, "cites no recipe IDs (it has no access to the data)", "declined"
        if missing:
            return False, f"{len(missing)} of {len(found)} cited IDs do not exist", "fabricated"
        return True, f"all {len(found)} cited IDs exist", "correct"
    claim = re.search(rf"\d[\d,.]*\s*(?:k?cal|{case['must_not_claim']})", answer, re.I)
    if claim:
        return False, f"claims '{claim.group(0)}' though the dataset has no such data", "fabricated"
    return True, "does not invent the missing value", "correct"


# ----- report -----------------------------------------------------------------------

def _tail(answer: str, limit: int = 1100) -> str:
    """The end of a long answer is where the model states its conclusion."""
    answer = answer.strip()
    return answer if len(answer) <= limit else "[...] " + answer[-limit:]

def write_report(results: dict, provider: str) -> Path:
    r = results
    out = [
        "# Evaluation report", "",
        f"Generated by `eval/run_eval.py` on {r['date']} with: **{r['llm']}**.",
        "Re-run with `uv run python eval/run_eval.py` (add `--provider none` to run without an "
        "LLM in about a minute).", "", "## Summary", "",
        "| Area | Passed | What is checked |", "|---|---|---|",
    ]
    checks = {
        "normalization": "base ingredient of 60 random dataset lines vs. hand labels",
        "parser": "intent and slots of 40 labelled messages (many phrased unlike the prompt)",
        "stats": "every number equals an independent reference computation",
        "matching": "no constraint violated; matched/extra lists and ranking order re-derived",
        "substitution": "restriction respected, unchanged lines verbatim, evidence IDs exist, "
                        "weak evidence flagged",
        "conversations": "scripted multi-turn conversations, incl. the PDF examples",
    }
    for area, what in checks.items():
        if area in r:
            out.append(f"| {area} | {r[area]['passed']}/{r[area]['total']} | {what} |")
    if "baseline" in r and r["baseline"]["total"]:
        b = r["baseline"]
        out.append(f"| one-shot LLM vs assistant | {b['one_shot_correct']}/{b['total']} vs "
                   f"{b['system_correct']}/{b['total']} | same questions, answers checked "
                   f"against the dataset (one-shot: {b['one_shot_declined']} declined, "
                   f"{b['one_shot_fabricated']} gave unsupported numbers; see the discussion) |")
    if "normalization" in r:
        n = r["normalization"]
        out += ["", f"Normalization: the first parser version got {n['first_version_correct']}/"
                f"{n['total']} of these lines right; {n['fixed_since']} of its errors were fixed "
                "by general rules since (no line-specific rules)."]
    if "parser" in r:
        p = r["parser"]
        out += ["", f"Parser: LLM produced {p['llm_used']}/{p['total']} patches; guards "
                f"corrected {p['guard_corrections']}; median {p['median_seconds']} s per message.",
                "", "Field accuracy: " + ", ".join(f"{k} {v}" for k, v in
                                                   p["field_accuracy"].items())]
    out += ["", "## Failures", ""]
    any_failure = False
    for area in ("normalization", "parser", "stats", "matching", "substitution",
                 "conversations"):
        for case in r.get(area, {}).get("cases", []):
            if case.get("passed"):
                continue
            any_failure = True
            label = case.get("name") or case.get("message")
            details = case.get("problems") or [
                f"{c['field']}: expected {c['expected']}, got {c['got']}"
                for c in case.get("checks", []) if not c["ok"]] or [
                f"expected {case.get('expected')}, got {case.get('got')}"]
            out.append(f"- **{area}** — {label}: " + "; ".join(map(str, details)))
    if not any_failure:
        out.append("None.")
    if "baseline" in r and r["baseline"]["cases"]:
        out += ["", "## One-shot LLM vs the assistant", "",
                "The same LLM answered directly (no data access), and the assistant answered "
                "through its pipeline. Answers are checked against the dataset.", ""]
        for case in r["baseline"]["cases"]:
            if "skipped" in case:
                out.append(f"- {case['name']}: skipped ({case['skipped']})")
                continue
            out += [f"### {case['name']}", "", f"Question: {case['question']}", "",
                    f"**One-shot ({case['one_shot_model']}):** "
                    f"{case['one_shot_ok'][2].upper()}: {case['one_shot_ok'][1]}",
                    "", "```text", _tail(case["one_shot_answer"]), "```", "",
                    f"**Assistant:** {'correct' if case['system_ok'][0] else 'WRONG'}: "
                    f"{case['system_ok'][1]}", "", "```text",
                    case["system_answer"].strip()[:900], "```", ""]
    if "substitution" in r:
        out += ["", "## Substitution cases", "", "| Case | Recipe | Result | Evidence | By |",
                "|---|---|---|---|---|"]
        for c in r["substitution"]["cases"]:
            outcome = c.get("substitute") or (c.get("message") or "")[:60]
            out.append(f"| {c['name']} | {c.get('recipe', '')} | {outcome} | "
                       f"{c.get('strength', '')} | {c.get('method', '')} |")
    if "conversations" in r:
        out += ["", "## Conversations", "",
                "Full transcripts are in `eval/transcripts/`.", ""]
        for c in r["conversations"]["cases"]:
            out.append(f"- {'PASS' if c['passed'] else 'FAIL'} — [{c['name']}]({c['transcript']})"
                       f" ({', '.join(c['covers'])})")
    discussion = EVAL_DIR / "discussion.md"
    if discussion.exists():
        out += ["", discussion.read_text(encoding="utf-8")]
    path = EVAL_DIR / "REPORT.md"
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return path


def main() -> int:
    use_utf8_console()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--provider", help="auto | ollama | gemini | none")
    ap.add_argument("--only", help="comma-separated: parser,stats,matching,substitution,"
                                   "conversations,baseline")
    ap.add_argument("--refresh-baseline", action="store_true")
    ap.add_argument("--report-only", metavar="RESULTS",
                    help="rebuild REPORT.md from saved results, e.g. eval/results/ollama.json")
    args = ap.parse_args()
    if args.report_only:
        saved = json.loads(Path(args.report_only).read_text(encoding="utf-8"))
        print(f"Wrote {write_report(saved, Path(args.report_only).stem)}")
        return 0
    areas = (args.only.split(",") if args.only else
             ["normalization", "stats", "matching", "parser", "substitution", "conversations",
              "baseline"])

    settings = get_settings()
    store = RecipeStore.load(settings.processed_dir, settings.config_dir)
    index = SearchIndex.load_or_build(store, settings.processed_dir / "bm25")
    llm, description = make_llm(settings, args.provider)
    print(f"Parser: {description}")
    provider = llm.name.split()[0] if llm else "none"
    results_path = EVAL_DIR / "results" / f"{provider}.json"
    # Areas not re-run this time keep their previous results.
    previous = json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else {}
    results: dict = {**previous, "date": str(date.today()), "llm": description}
    engine = SubstitutionEngine(store, index, settings.config_dir)
    runners = {
        "normalization": lambda: eval_normalization(store),
        "stats": lambda: eval_stats(store),
        "matching": lambda: eval_matching(store),
        "parser": lambda: eval_parser(store, MessageParser(llm)),
        "substitution": lambda: eval_substitution(store, index, engine, llm),
        "conversations": lambda: eval_conversations(store, index, llm, provider),
        "baseline": lambda: eval_baseline(store, index, llm, args.refresh_baseline),
    }
    for area in areas:
        started = time.perf_counter()
        print(f"Running {area} ...", flush=True)
        results[area] = runners[area]()
        summary = {k: v for k, v in results[area].items() if k != "cases"}
        print(f"  {summary} ({time.perf_counter() - started:.0f}s)", flush=True)
    results_path.parent.mkdir(exist_ok=True)
    results_path.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str),
                            encoding="utf-8")
    print(f"Wrote {write_report(results, provider)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
