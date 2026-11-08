"""The LLM writes a short, natural opening for a reply, from the engine's facts only."""

from __future__ import annotations

import re

from recipebot.llm.base import LLMClient

WRITER_SYSTEM = """\
You write the first 2-3 sentences of a recipe assistant's reply.
Use ONLY the FACTS below; they come from a recipe dataset. The full details are shown to
the user right after your text, so summarize and highlight, do not repeat lists.
- Answer the user's question directly; mention recipe titles and IDs exactly as written.
- Keep every number exactly as in the facts. Do not add new numbers.
- Never add cooking times, servings, nutrition or ingredients that the facts do not state.
- If the facts say nothing matched or the evidence is weak, say so plainly.
Plain text, no lists, no markdown."""


_META = re.compile(r"\b(sentences?|the facts|user message|constraints:|steps:|i should|"
                   r"let me|first sentence|second sentence)\b", re.I)


def write_summary(llm: LLMClient, user_text: str, facts: str) -> str:
    prompt = f"User message: {user_text}\n\nFACTS:\n{facts[:3500]}\n\nYour 2-3 sentences:"
    return clean_summary(llm.generate_text(WRITER_SYSTEM, prompt))


def clean_summary(text: str) -> str:
    """Small models sometimes write their plan ("The first sentence should...") instead of
    the summary. Such output is discarded; the factual answer is shown on its own."""
    text = text.strip()
    if not text or "\n\n" in text or _META.search(text) or text.count(".") > 5:
        return ""
    return text
