"""Shapes of a raw recipe record as it appears in the dataset files."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator

Source = Literal["ar", "epi", "fn"]

SOURCE_NAMES: dict[str, str] = {"ar": "Allrecipes", "epi": "Epicurious", "fn": "Food Network"}


class RawRecipe(BaseModel):
    """One record exactly as stored in a source file. Nothing here is modified."""

    source: Source
    source_key: str
    title: str = ""
    ingredients: list[str] = []
    instructions: str = ""

    @property
    def recipe_id(self) -> str:
        """Stable ID: the dataset's own key, prefixed with the source file it came from."""
        return f"{self.source}:{self.source_key}"

    @field_validator("title", "instructions", mode="before")
    @classmethod
    def _none_to_empty(cls, value: object) -> str:
        return "" if value is None else str(value)

    @field_validator("ingredients", mode="before")
    @classmethod
    def _ingredients_list(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return [str(item) for item in value if item is not None]
