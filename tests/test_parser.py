import pytest

from recipebot.nlp.ingredient_parser import parse_line

# (line, canonical, base, extra, alternatives)
CASES = [
    ("4 skinless, boneless chicken breast halves ADVERTISEMENT", "chicken breast half", "chicken", (), ()),
    ("1 onion, finely diced ADVERTISEMENT", "onion", "onion", (), ()),
    ("2 (14.5 ounce) cans diced tomatoes, drained", "tomato", "tomato", (), ()),
    ("1½ cups all-purpose flour", "all-purpose flour", "flour", (), ()),
    ("1 teaspoon ground white or black pepper, or to taste", "white pepper", "white pepper", (), ("black pepper",)),
    ("2 cups chicken or vegetable stock", "chicken stock", "chicken stock", (), ("vegetable stock",)),
    ("1/2 cup butter or margarine, softened", "butter", "butter", (), ("margarine",)),
    ("2 cloves garlic, minced", "garlic", "garlic", (), ()),
    ("3 garlic cloves", "garlic clove", "garlic", (), ()),
    ("1 small clove garlic, smashed", "garlic", "garlic", (), ()),
    ("Kosher salt and freshly ground black pepper", "salt", "salt", ("black pepper",), ()),
    ("1 bunch scallions, thinly sliced", "green onion", "green onion", (), ()),
    ("1 teaspoon crushed red pepper flakes", "red pepper flake", "red pepper flake", (), ()),
    ("1 pound ground beef", "ground beef", "ground beef", (), ()),
    ("2 teaspoons ground cumin", "cumin", "cumin", (), ()),
    ("1 1/2 cups cherry tomatoes, halved", "cherry tomato", "tomato", (), ()),
    ("3 large eggs, lightly beaten", "egg", "egg", (), ()),
    ("2 egg yolks", "egg yolk", "egg", (), ()),
    ("1 cup heavy whipping cream", "heavy cream", "cream", (), ()),
    ("1 cup fresh or frozen blackberries", "blackberry", "blackberry", (), ()),
    ("1/2 cup packed light or dark brown sugar", "brown sugar", "brown sugar", (), ()),
    ("Zest and juice of 1 orange", "orange zest", "orange zest", ("orange juice",), ()),
    ("3 cloves", "clove", "clove", (), ()),
    ("1/4 cup fresh basil leaves", "basil leaf", "basil", (), ()),
    ("1/2 cup grated Parmesan cheese", "parmesan", "parmesan", (), ()),
    ("2 tablespoons sugar or brown sugar", "sugar", "sugar", (), ("brown sugar",)),
    ("1 medium-sized onion, chopped", "onion", "onion", (), ()),
    ("1 cup pearl onions, peeled", "pearl onion", "onion", (), ()),
    ("1 teaspoon garlic powder", "garlic powder", "garlic powder", (), ()),
]


@pytest.mark.parametrize("line,canonical,base,extra,alternatives", CASES)
def test_canonical_names(lexicon, line, canonical, base, extra, alternatives):
    parsed = parse_line(line, lexicon)
    assert parsed.canonical == canonical
    assert parsed.base == base
    assert parsed.extra == extra
    assert parsed.alternatives == alternatives


def test_header_line(lexicon):
    assert parse_line("For the sauce:", lexicon).is_header


def test_advertisement_only_line_is_dropped(lexicon):
    assert parse_line("ADVERTISEMENT", lexicon) is None


@pytest.mark.parametrize(
    "line,quantity,unit,amount,dimension",
    [
        ("1 1/2 cups sugar", 1.5, "cup", 354.9, "volume"),
        ("1-1/2 cups milk", 1.5, "cup", 354.9, "volume"),
        ("200g spaghetti", 200, "gram", 200, "mass"),
        ("2 (14.5 ounce) cans diced tomatoes", 2, "can", 822.15, "mass"),
        ("1 15-ounce can black beans, rinsed", 1, "can", 425.25, "mass"),
        ("3 large eggs", 3, None, 3, "count"),
    ],
)
def test_quantities(lexicon, line, quantity, unit, amount, dimension):
    parsed = parse_line(line, lexicon)
    assert parsed.quantity == pytest.approx(quantity)
    assert parsed.unit == unit
    assert parsed.amount_base == pytest.approx(amount, rel=1e-3)
    assert parsed.dimension == dimension


def test_range_keeps_upper_bound(lexicon):
    parsed = parse_line("2 to 3 tablespoons olive oil", lexicon)
    assert (parsed.quantity, parsed.quantity_max) == (2, 3)


def test_canned_form_is_recorded(lexicon):
    assert parse_line("1 (14.5 ounce) can diced tomatoes", lexicon).form == "canned"
