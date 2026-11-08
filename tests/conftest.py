from __future__ import annotations

from pathlib import Path

import pytest

from recipebot.config import PROJECT_ROOT
from recipebot.data.pipeline import build
from recipebot.dialogue.orchestrator import Orchestrator
from recipebot.engines.search import SearchIndex
from recipebot.engines.store import RecipeStore
from recipebot.llm.parser import MessageParser
from recipebot.nlp.allergens import AllergenLexicon
from recipebot.nlp.lexicon import Lexicon

CONFIG_DIR = PROJECT_ROOT / "config"
FIXTURE_RAW = Path(__file__).parent / "fixtures" / "raw"


@pytest.fixture(scope="session")
def lexicon() -> Lexicon:
    return Lexicon(CONFIG_DIR)


@pytest.fixture(scope="session")
def allergens() -> AllergenLexicon:
    return AllergenLexicon(CONFIG_DIR)


@pytest.fixture(scope="session")
def built_dir(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("processed")
    build(FIXTURE_RAW, out, CONFIG_DIR)
    return out


@pytest.fixture(scope="session")
def store(built_dir: Path) -> RecipeStore:
    return RecipeStore.load(built_dir, CONFIG_DIR)


@pytest.fixture(scope="session")
def index(store: RecipeStore) -> SearchIndex:
    return SearchIndex.build(store)


@pytest.fixture
def bot(store: RecipeStore, index: SearchIndex) -> Orchestrator:
    """A fresh conversation using the offline rule parser."""
    return Orchestrator(store, index, MessageParser(None))
