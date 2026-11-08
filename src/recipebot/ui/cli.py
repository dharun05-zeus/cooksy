"""Command-line chat.

    uv run recipebot chat                      # interactive
    uv run recipebot chat --provider rules     # offline, no API key
    uv run recipebot chat --script demo.txt    # run a scripted conversation (one message per line)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.rule import Rule

from recipebot.app import build_orchestrator
from recipebot.config import use_utf8_console
from recipebot.dialogue.orchestrator import HELP, Orchestrator

app = typer.Typer(add_completion=False, help="Evidence-grounded recipe assistant")
console = Console(highlight=False)


@app.callback()
def main() -> None:
    use_utf8_console()


def _say(text: str, style: str | None = None) -> None:
    console.print(text, markup=False, style=style)


def _run_turn(bot: Orchestrator, text: str, debug: bool) -> None:
    was_disabled = bot.parser.disabled_reason is not None
    with console.status("Thinking..."):
        turn = bot.handle(text)
    if bot.parser.disabled_reason and not was_disabled:
        _say(f"[The LLM is unavailable for this session ({bot.parser.disabled_reason[:160]}); "
             "using the offline fallback parser.]", style="yellow")
    if debug:
        patch = turn.patch.model_dump(exclude_defaults=True)
        _say(f"[parser: {turn.parser}, {turn.seconds}s] {json.dumps(patch)}", style="dim")
        if turn.corrections:
            _say(f"[guards corrected: {'; '.join(turn.corrections)}]", style="dim")
        if turn.grounding and turn.grounding.removed:
            for sentence, reason in turn.grounding.removed:
                _say(f"[grounding removed: \"{sentence[:80]}\" ({reason})]", style="dim")
        if bot.parser.last_error:
            _say(f"[LLM error, used fallback: {bot.parser.last_error}]", style="yellow")
    _say(turn.reply)


@app.command()
def chat(
    provider: Annotated[str | None, typer.Option(
        help="auto | gemini | rules (default: LLM_PROVIDER)")] = None,
    script: Annotated[Path | None, typer.Option(
        help="file with one user message per line")] = None,
    debug: Annotated[bool, typer.Option(
        help="show the parsed StatePatch for each turn")] = False,
) -> None:
    """Chat with the assistant."""
    with console.status("Loading 125,000 recipes and the search index..."):
        bot, description = build_orchestrator(provider)
    _say(f"Ready. Parser: {description}", style="green")

    if script:
        # utf-8-sig: Windows editors often add a byte-order mark to the first line
        for line in script.read_text(encoding="utf-8-sig").splitlines():
            if line.strip() and not line.startswith("#"):
                console.print(Rule())
                _say(f"You: {line.strip()}", style="bold cyan")
                _run_turn(bot, line.strip(), debug)
        return

    _say(HELP, style="dim")
    while True:
        try:
            text = console.input("\n[bold cyan]You:[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        if text in ("/quit", "/exit"):
            break
        if text == "/help":
            _say(HELP)
        elif text == "/state":
            _say(json.dumps(bot.state.model_dump(exclude_defaults=True), indent=2))
        elif text == "/reset":
            bot.reset()
            _say("Started a new session. All constraints were cleared.")
        elif text == "/debug":
            debug = not debug
            _say(f"debug {'on' if debug else 'off'}")
        else:
            _run_turn(bot, text, debug)


if __name__ == "__main__":
    app()
