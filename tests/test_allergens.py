import pytest


def statuses(allergens, line):
    return {hit.category: hit.status for hit in allergens.classify(line)}


@pytest.mark.parametrize(
    "line,category,expected",
    [
        ("1 cup heavy cream", "dairy", "contains"),
        ("2 tablespoons butter", "dairy", "contains"),
        ("1 cup buttermilk", "dairy", "contains"),
        ("1 tablespoon peanut butter", "dairy", None),
        ("1 cup coconut milk", "dairy", None),
        ("1/2 teaspoon cream of tartar", "dairy", None),
        ("2 cups butternut squash", "dairy", None),
        ("2 tablespoons vegan butter", "dairy", "uncertain"),
        ("1 cup margarine", "dairy", "uncertain"),
        ("3 large eggs", "egg", "contains"),
        ("1/2 cup mayonnaise", "egg", "contains"),
        ("1 eggplant, cubed", "egg", None),
        ("1 tablespoon peanut butter", "peanut", "contains"),
        ("2 tablespoons oil, such as peanut oil", "peanut", "contains"),
        ("1/2 cup pine nuts", "peanut", None),
        ("1/2 cup pine nuts", "tree_nut", "contains"),
        ("1 teaspoon nutmeg", "tree_nut", None),
        ("2 cups vegetable broth", "meat", None),
        ("2 cups chicken broth", "meat", "contains"),
        ("2 cups stock", "meat", "uncertain"),
        ("2 cups rice flour", "gluten", None),
        ("2 cups all-purpose flour", "gluten", "contains"),
        ("1 cup oyster mushrooms", "shellfish", None),
        ("2 ribs celery", "meat", None),
    ],
)
def test_classify(allergens, line, category, expected):
    assert statuses(allergens, line).get(category) == expected


def test_category_aliases(allergens):
    assert allergens.categories_for("vegan") == ["meat", "fish", "shellfish", "dairy", "egg", "animal_product"]
    assert allergens.categories_for("Nuts") == ["peanut", "tree_nut"]
    assert allergens.categories_for("tomato") is None
