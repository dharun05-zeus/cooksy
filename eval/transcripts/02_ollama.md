# Removing one restriction and adding another in one message

Parser: ollama (qwen3:4b). Covers: multi-turn follow-up, restriction removed, restriction added

**User:** Find vegetarian pasta recipes without mushrooms.

*parser: ollama (qwen3:4b), 5.3s; guard corrections: ["add_exclude += ['vegetarian']"]*

```text
1,168 recipes share at least one word with 'vegetarian pasta' and satisfy your constraints. The 5 most relevant:

1. Southwestern Vegetarian Pasta  [ar:1JismUWkQscNRlus8EuS2twFcreBd3u]
   11 ingredients, 3 steps; matched: vegetarian, pasta
   Evidence: none of its 11 ingredients contains 'mushrooms'; no vegetarian (meat, fish, shellfish) found in its 11 ingredient lines, including uncertain items
   Ingredients: 1 tablespoon vegetable oil; 1 onion, chopped; 1/2 green bell pepper, diced; 2 cloves garlic, chopped; 2 tablespoons chili powder; 1 teaspoon ground cumin; 1 (28 ounce) can diced tomatoes with juice; 1 (15 ounce) can chickpeas; 1 (10 ounce) package frozen corn kernels, thawed; 1 (12 ounce) package uncooked elbow macaroni; 1/2 cup shredded Monterey Jack cheese

2. Vegetarian White Bean 'Alfredo' with Linguine  [ar:MlZPouFciGWMdaDto8x4umEEaPeOMUe]
   7 ingredients, 2 steps; matched: vegetarian, pasta
   Evidence: none of its 7 ingredients contains 'mushrooms'; no vegetarian (meat, fish, shellfish) found in its 7 ingredient lines, including uncertain items
   Ingredients: 1 (16 ounce) package linguine pasta; 1/4 cup butter; 3 cloves garlic, minced; 2 cups cooked navy beans, rinsed and drained; 1 1/2 cups soy milk; 1 cup asparagus, cut into 1/2-inch pieces; salt and black pepper to taste

3. Easy Vegetarian Spinach Lasagna  [ar:ZlpIBwe2yjq8THm7S0OY7b/BP1Y3zAm]
   12 ingredients, 6 steps; matched: vegetarian, pasta
   Evidence: none of its 12 ingredients contains 'mushrooms'; no vegetarian (meat, fish, shellfish) found in its 12 ingredient lines, including uncertain items
   Ingredients: cooking spray; 9 lasagna noodles; 1 bunch fresh spinach; 1 (8 ounce) container ricotta cheese; 1/2 cup shredded mozzarella cheese; 1 egg, lightly beaten; 1 pinch ground nutmeg; 1 pinch dried basil; salt and ground black pepper to taste; 1 cup pasta sauce; 1/2 cup shredded mozzarella cheese; 1/4 cup grated Parmesan cheese

4. Vegetarian Four Cheese Lasagna  [ar:dZUU4MHgUSMVxBORhLFh0QDZl16UY8G]
   12 ingredients, 5 steps; matched: vegetarian, pasta
   Evidence: none of its 12 ingredients contains 'mushrooms'; no vegetarian (meat, fish, shellfish) found in its 12 ingredient lines, including uncertain items
   Ingredients: 2 cups peeled and diced pumpkin; 1 eggplant, sliced into 1/2 inch rounds; 5 tomatoes; 1 pint ricotta cheese; 9 ounces crumbled feta cheese; 2/3 cup pesto; 2 eggs, beaten; salt and pepper to taste; 1 (15 ounce) can tomato sauce; fresh pasta sheets; 1 1/3 cups shredded mozzarella cheese; 1 cup grated Parmesan cheese

5. Vegetarian, Tofu-Less Stir-Fry  [ar:uunA.qMKwI388W8D7Lbd3.nNm7kmohe]
   11 ingredients, 2 steps; matched: vegetarian, pasta
   Evidence: none of its 11 ingredients contains 'mushrooms'; no vegetarian (meat, fish, shellfish) found in its 11 ingredient lines, including uncertain items
   Ingredients: 1/4 cup frozen shelled edamame (green soybeans); 1/8 teaspoon salt; 1 tablespoon olive oil; 1 clove garlic, minced; 1 cup sliced yellow bell pepper; 1/2 cup sliced yellow onion; 1/2 cup bean sprouts; 1 tablespoon tamari soy sauce; 2 cups cooked pasta; 1 tablespoon sesame oil; 1 teaspoon toasted sesame seeds

Filters applied to the whole dataset: exact duplicates removed (same title and ingredient set); excludes 'mushroom' (any name containing it: mushroom, shiitake mushroom, condensed cream of mushroom soup, button mushroom, cremini mushroom, portobello mushroom and 470 more); excludes vegetarian (meat, fish, shellfish)
Note: Your constraints removed 2,325 of the 3,493 recipes matching the search words (uncertain cases are removed too).
Ask for 'the first one' (or any number) to see its full recipe.
Active constraints: no mushrooms, no vegetarian.
```

**User:** Actually, mushrooms are okay. But exclude dairy.

*parser: ollama (qwen3:4b), 11.4s*

```text
315 recipes share at least one word with 'vegetarian pasta' and satisfy your constraints. The 5 most relevant:

1. Vegetarian, Tofu-Less Stir-Fry  [ar:uunA.qMKwI388W8D7Lbd3.nNm7kmohe]
   11 ingredients, 2 steps; matched: vegetarian, pasta
   Evidence: no vegetarian (meat, fish, shellfish) found in its 11 ingredient lines, including uncertain items; no dairy found in its 11 ingredient lines, including uncertain items
   Ingredients: 1/4 cup frozen shelled edamame (green soybeans); 1/8 teaspoon salt; 1 tablespoon olive oil; 1 clove garlic, minced; 1 cup sliced yellow bell pepper; 1/2 cup sliced yellow onion; 1/2 cup bean sprouts; 1 tablespoon tamari soy sauce; 2 cups cooked pasta; 1 tablespoon sesame oil; 1 teaspoon toasted sesame seeds

2. Vegetarian Dashi  [fn:/PExjBcOe2zIQx6cmsln.2zQWdL5agG]
   3 ingredients, 4 steps; matched: vegetarian
   Evidence: no vegetarian (meat, fish, shellfish) found in its 3 ingredient lines, including uncertain items; no dairy found in its 3 ingredient lines, including uncertain items
   Ingredients: 1 small piece (4 to 5 square inch) kombu (dried, cultivated kelp or seaweed); 2 cups water; 1 cup vegetable stock

3. Al's Quick Vegetarian Spaghetti  [ar:9B8BIcDQ11ZH0D.at3b.2E3QfecQCfe]
   6 ingredients, 2 steps; matched: vegetarian
   Evidence: no vegetarian (meat, fish, shellfish) found in its 6 ingredient lines, including uncertain items; no dairy found in its 6 ingredient lines, including uncertain items
   Ingredients: 1 pound uncooked spaghetti; 1 cup broccoli florets; 1 (15 ounce) can whole kernel corn, drained; 1 cup fresh sliced mushrooms; 1 cup sliced carrots; 2 (8 ounce) cans tomato sauce

4. Vegetarian Dipping Sauce  [epi:aXLWEF8ptI0beFOoSaU.qglNhAbRyiC]
   4 ingredients, 2 steps; matched: vegetarian
   Evidence: no vegetarian (meat, fish, shellfish) found in its 4 ingredient lines, including uncertain items; no dairy found in its 4 ingredient lines, including uncertain items
   Ingredients: 1/4 cup superfine sugar; 3/4 cup boiling water; 3 tablespoons freshly squeezed lemon juice; 3 tablespoons light soy sauce

5. Vegetarian Ribs  [ar:2A3VpW2Kxo0RIA42hMemG6mku/sdRJu]
   9 ingredients, 7 steps; matched: vegetarian
   Evidence: no vegetarian (meat, fish, shellfish) found in its 9 ingredient lines, including uncertain items; no dairy found in its 9 ingredient lines, including uncertain items
   Ingredients: 2 cups gluten; 1/3 cup nutritional yeast; 2 tablespoons paprika; 1 tablespoon salt; 2 cups water; 1/2 cup smooth peanut butter; 1 large onion, minced; 1/2 cup olive oil; 2 cups barbeque sauce

Filters applied to the whole dataset: exact duplicates removed (same title and ingredient set); excludes vegetarian (meat, fish, shellfish); excludes dairy
Note: Your constraints removed 3,178 of the 3,493 recipes matching the search words (uncertain cases are removed too).
Ask for 'the first one' (or any number) to see its full recipe.
Active constraints: no vegetarian, no dairy.
```
