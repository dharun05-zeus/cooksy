"""Web chat UI.

    uv run streamlit run src/recipebot/ui/streamlit_app.py

Same assistant as the CLI: one conversation (and its constraints) per browser session.
"""

from __future__ import annotations

import json

import streamlit as st

from recipebot.app import Components, load_components
from recipebot.dialogue.orchestrator import Orchestrator

EXAMPLES = [
    "Find a penne pasta recipe.",
    "I cannot have dairy.",
    "How many recipes contain both garlic and onion? What percentage of the dataset is that?",
    "Among recipes containing tomato, which five have the fewest instruction steps?",
    "I have eggs, onions, tomatoes, and rice. Suggest five recipes with no peanuts and at most "
    "six instruction steps.",
    "Take this banana bread recipe and remove eggs.",
]

st.set_page_config(page_title="Recipe Intelligence Assistant", page_icon="🍲", layout="wide")


@st.cache_resource(show_spinner="Loading 125,000 recipes and the search index...")
def components() -> Components:
    return load_components()


def bot() -> Orchestrator:
    if "bot" not in st.session_state:
        st.session_state.bot = components().new_conversation()
        st.session_state.turns = []
    return st.session_state.bot


def send(text: str) -> None:
    with st.spinner("Thinking... (a local model on a CPU can take 5-60 seconds)"):
        turn = bot().handle(text)
    st.session_state.turns.append(turn)


def sidebar() -> None:
    b = bot()
    st.sidebar.title("Recipe Intelligence Assistant")
    st.sidebar.caption(f"LLM: {components().description}")
    st.sidebar.subheader("Active constraints")
    s = b.state
    st.sidebar.write(s.constraints_text() or "none")
    if s.task == "search" and (s.query or s.include):
        st.sidebar.write(f"Search: {s.query} {' '.join(s.include)}".strip())
    if s.task == "match" and s.pantry:
        st.sidebar.write("Your ingredients: " + ", ".join(p.name for p in s.pantry))
    if st.sidebar.button("Start over"):
        b.reset()
        st.session_state.turns = []
        st.rerun()
    st.sidebar.subheader("Try")
    for example in EXAMPLES:
        if st.sidebar.button(example, use_container_width=True):
            send(example)
            st.rerun()
    st.session_state.debug = st.sidebar.toggle("Show how each message was parsed")
    st.sidebar.caption("Every fact comes from the Recipe Box dataset. Cooking times, servings "
                       "and nutrition are not in the dataset.")


def main() -> None:
    bot()
    sidebar()
    for turn in st.session_state.turns:
        with st.chat_message("user"):
            st.write(turn.user)
        with st.chat_message("assistant"):
            if st.session_state.get("debug"):
                with st.expander(f"parser: {turn.parser}, {turn.seconds}s"):
                    st.code(json.dumps(turn.patch.model_dump(exclude_defaults=True), indent=1),
                            language="json")
                    if turn.corrections:
                        st.write("Guard corrections:", turn.corrections)
                    if turn.grounding and turn.grounding.removed:
                        st.write("Removed by the grounding check:", turn.grounding.removed)
            st.text(turn.reply)
    if text := st.chat_input("Ask about recipes, ingredients you have, or substitutions"):
        send(text)
        st.rerun()


main()
