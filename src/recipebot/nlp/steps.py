"""Count instruction steps with one documented rule.

Rule:
1. Split the instructions on line breaks and drop empty lines and site boilerplate
   ("Watch how to make this recipe.", "Photograph by ...").
2. If two or more lines remain, each line is one step (method "line").
3. If only one block of text remains, split it into sentences and count each
   sentence as a step (method "sentence"). About 10,000 Food Network recipes are
   stored this way, so their counts are approximate and labelled as such.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'])")

Method = Literal["line", "sentence", "none"]


@dataclass(frozen=True)
class StepCount:
    steps: int
    method: Method
    sentences: int  # sentence count over all lines, an alternative measure


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(text) if s.strip()]


def instruction_lines(instructions: str, boilerplate: list[re.Pattern[str]]) -> list[str]:
    lines = []
    for line in instructions.splitlines():
        line = line.strip()
        if line and not any(p.search(line.lower()) for p in boilerplate):
            lines.append(line)
    return lines


def count_steps(instructions: str, boilerplate: list[re.Pattern[str]]) -> StepCount:
    lines = instruction_lines(instructions, boilerplate)
    sentences = sum(len(split_sentences(line)) for line in lines)
    if not lines:
        return StepCount(0, "none", 0)
    if len(lines) >= 2:
        return StepCount(len(lines), "line", sentences)
    parts = split_sentences(lines[0])
    if len(parts) > 1:
        return StepCount(len(parts), "sentence", sentences)
    return StepCount(1, "line", sentences)
