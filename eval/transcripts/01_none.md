# Search refined by a follow-up restriction (PDF Task 1)

Parser: rules. Covers: multi-turn follow-up, restriction applies to the active search

**User:** Find a penne pasta recipe.

*parser: rules, 0.0s*

```text
3,352 recipes share at least one word with 'penne pasta'. The 5 most relevant:

1. Penne Pasta with Spinach and Bacon  [ar:23to8XzUux0FF.g5ZFsqnxvhByMzfJ.]
   6 ingredients, 3 steps; matched: penne, pasta

2. Bacon and Parmesan Penne Pasta  [ar:hzvAPQudIHjif5vLsP8vv.H8aTThvAq]
   5 ingredients, 3 steps; matched: penne, pasta

3. Tuna Alfredo with Penne Pasta  [ar:Ds7VCz2ZVAvWeI/YBnNcA/lzUZGjb7G]
   6 ingredients, 2 steps; matched: penne, pasta

4. Creamy Penne Pasta  [ar:nvQzTEX.J7/2LmKnF8KjsR6aCqNHGxO]
   9 ingredients, 2 steps; matched: penne, pasta

5. Penne Pasta with Veggies  [ar:1y7j2vPKV2KEQbMJ7GgJw1Z5X/yKF/S]
   11 ingredients, 5 steps; matched: penne, pasta

Filters applied to the whole dataset: exact duplicates removed (same title and ingredient set)
Ask for 'the first one' (or any number) to see its full recipe.
```

**User:** I cannot have dairy.

*parser: rules, 0.0s*

```text
662 recipes share at least one word with 'penne pasta' and satisfy your constraints. The 5 most relevant:

1. Penne Pasta with Spinach and Bacon  [ar:23to8XzUux0FF.g5ZFsqnxvhByMzfJ.]
   6 ingredients, 3 steps; matched: penne, pasta
   Evidence: no dairy found in its 6 ingredient lines, including uncertain items
   Ingredients: 1 (12 ounce) package penne pasta; 2 tablespoons olive oil, divided; 6 slices bacon, chopped; 2 tablespoons minced garlic; 1 (14.5 ounce) can diced tomatoes; 1 bunch fresh spinach, rinsed and torn into bite-size pieces

2. Penne Pasta with Cannellini Beans and Escarole  [ar:zwRAInNlhnKD1jMf/HOm5a9oKhjC8Om]
   5 ingredients, 2 steps; matched: penne, pasta
   Evidence: no dairy found in its 5 ingredient lines, including uncertain items
   Ingredients: 1 (16 ounce) package dry penne pasta; 1 head escarole, chopped; 1 (15.5 ounce) can cannellini beans, with liquid; 1 (14.5 ounce) can diced tomatoes with garlic and onion, drained; salt and ground black pepper to taste

3. Pat's Simple Penne  [ar:9mPiUMSt4KndASd0tYPD7iKvkRhsO2i]
   5 ingredients, 4 steps; matched: penne, pasta
   Evidence: no dairy found in its 5 ingredient lines, including uncertain items
   Ingredients: 6 cups penne pasta; 1 pound bacon, cut into 1 inch pieces; 1 onion, thinly sliced; 3 1/2 (10.75 ounce) cans chicken broth; 1 pinch crushed red pepper flakes

4. Penne Pasta Salad with Sun Dried Tomatoes, Asparagus and Basil  [fn:ck/foCIv1g.W0SyPMLF5DWS/ZdeQBRi]
   7 ingredients, 2 steps; matched: penne, pasta
   Evidence: no dairy found in its 7 ingredient lines, including uncertain items
   Ingredients: 1 pound penne pasta; 1 cup fresh asparagus tips; 4 garlic cloves, minced; 1/4 cup olive oil; Salt and pepper, to taste; 1 bunch basil, chopped; 1 cup sun-dried tomatoes in oil

5. Italian Sausage Penne Pasta with Tomatoes and Peas and Sweet Corn Salad  [fn:Fa0AuDYa4SItG.bL1kA8votemAaTPZ6]
   12 ingredients, 2 steps; matched: penne, pasta
   Evidence: no dairy found in its 12 ingredient lines, including uncertain items
   Ingredients: 2 pounds sweet Italian sausage, roughly chopped; 3/4 cups olive oil, divided; 1 1/2 cups onion, diced and divided; 1 tablespoon dried oregano, crushed; 2 tablespoons garlic, chopped; 6 cups plus 6 whole tomatoes, chopped; 1/4 cup parsley, chopped; 1 cup basil, julienned and divided; 2 cups frozen peas; 2 pounds penne pasta; 3 ears corn, blanched; Salt and pepper

Filters applied to the whole dataset: exact duplicates removed (same title and ingredient set); excludes dairy
Note: Your constraints removed 2,690 of the 3,352 recipes matching the search words (uncertain cases are removed too).
Ask for 'the first one' (or any number) to see its full recipe.
Active constraints: no dairy.
```

**User:** Show me the ingredients for the first one.

*parser: rules, 0.0s*

```text
Penne Pasta with Spinach and Bacon  [ar:23to8XzUux0FF.g5ZFsqnxvhByMzfJ.]  (source: Allrecipes)

Ingredients (as listed in the dataset):
  - 1 (12 ounce) package penne pasta
  - 2 tablespoons olive oil, divided
  - 6 slices bacon, chopped
  - 2 tablespoons minced garlic
  - 1 (14.5 ounce) can diced tomatoes
  - 1 bunch fresh spinach, rinsed and torn into bite-size pieces

Not in the dataset: cooking times, servings and nutrition are not recorded, so they are not shown.
```
