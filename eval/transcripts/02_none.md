# Removing one restriction and adding another in one message

Parser: rules. Covers: multi-turn follow-up, restriction removed, restriction added

**User:** Find vegetarian pasta recipes without mushrooms.

*parser: rules, 0.1s*

```text
1,028 recipes share at least one word with 'pasta' and satisfy your constraints. The 5 most relevant:

1. Reheating Pasta  [ar:VXH7q0f.zvkOk/Ouf/UNcTajeWgIQrC]
   2 ingredients, 6 steps; matched: pasta
   Evidence: none of its 2 ingredients contains 'mushrooms'; vegetarian: no meat, fish, shellfish found in its 2 ingredient lines, including uncertain items
   Ingredients: 8 ounces dry pasta; 3 tablespoons olive oil

2. How to Cook Pasta  [fn:kjkJhrV0MyFtnOGvmej5ktGxJ/wWd7i]
   1 ingredients, 2 steps; matched: pasta
   Evidence: none of its 1 ingredients contains 'mushrooms'; vegetarian: no meat, fish, shellfish found in its 1 ingredient lines, including uncertain items
   Ingredients: 1 pound pasta (your choice)

3. Homemade Pasta without a Pasta Machine  [ar:zwLWQ0v2wXlZd1RmfmuRGUnS4hINuwO]
   4 ingredients, 6 steps; matched: pasta
   Evidence: none of its 4 ingredients contains 'mushrooms'; vegetarian: no meat, fish, shellfish found in its 4 ingredient lines, including uncertain items
   Ingredients: 3 cups Italian-style tipo 00 flour; 3 eggs; 1 pinch salt; water, or as needed (optional)

4. Simple Pesto Pasta  [ar:TES5iV01pTIvz12YPfvJd3uPxw54GoO]
   4 ingredients, 2 steps; matched: pasta
   Evidence: none of its 4 ingredients contains 'mushrooms'; vegetarian: no meat, fish, shellfish found in its 4 ingredient lines, including uncertain items
   Ingredients: 1/2 (16 ounce) box dry fettuccine pasta; 1/4 cup butter, or to taste; 3 tablespoons minced garlic; 1/4 cup pesto

5. Pesto and Pasta  [fn:mNKBHMiOPqKMmmrnb/BdT50dcjL39xO]
   4 ingredients, 8 steps; matched: pasta
   Evidence: none of its 4 ingredients contains 'mushrooms'; vegetarian: no meat, fish, shellfish found in its 4 ingredient lines, including uncertain items
   Ingredients: 1/4 pound Rotelle pasta; 6 tablespoons pesto; 2 cups tomato sauce; 1/4 cup cream

Filters applied to the whole dataset: exact duplicates removed (same title and ingredient set); excludes 'mushroom' (any name containing it: mushroom, shiitake mushroom, condensed cream of mushroom soup, button mushroom, cremini mushroom, portobello mushroom and 470 more); vegetarian (excludes meat, fish, shellfish)
Note: Vegetarian: removed 46,639 recipes that contain meat, fish, shellfish and 2,012 where it is uncertain (e.g. margarine, chocolate); hard constraints remove uncertain cases too.
Note: Your constraints removed 2,190 of the 3,218 recipes matching the search words (uncertain cases are removed too).
Ask for 'the first one' (or any number) to see its full recipe.
Active constraints: no mushrooms, vegetarian.
```

**User:** Actually, mushrooms are okay. But exclude dairy.

*parser: rules, 0.0s*

```text
228 recipes share at least one word with 'pasta' and satisfy your constraints. The 5 most relevant:

1. Reheating Pasta  [ar:VXH7q0f.zvkOk/Ouf/UNcTajeWgIQrC]
   2 ingredients, 6 steps; matched: pasta
   Evidence: vegetarian: no meat, fish, shellfish found in its 2 ingredient lines, including uncertain items; no dairy found in its 2 ingredient lines, including uncertain items
   Ingredients: 8 ounces dry pasta; 3 tablespoons olive oil

2. How to Cook Pasta  [fn:kjkJhrV0MyFtnOGvmej5ktGxJ/wWd7i]
   1 ingredients, 2 steps; matched: pasta
   Evidence: vegetarian: no meat, fish, shellfish found in its 1 ingredient lines, including uncertain items; no dairy found in its 1 ingredient lines, including uncertain items
   Ingredients: 1 pound pasta (your choice)

3. Homemade Pasta without a Pasta Machine  [ar:zwLWQ0v2wXlZd1RmfmuRGUnS4hINuwO]
   4 ingredients, 6 steps; matched: pasta
   Evidence: vegetarian: no meat, fish, shellfish found in its 4 ingredient lines, including uncertain items; no dairy found in its 4 ingredient lines, including uncertain items
   Ingredients: 3 cups Italian-style tipo 00 flour; 3 eggs; 1 pinch salt; water, or as needed (optional)

4. Pasta and Beans (Pasta e Fagioli)  [fn:0rIkIsCBG2Njb3Y042H2uIpBDIqCHFe]
   7 ingredients, 9 steps; matched: pasta
   Evidence: vegetarian: no meat, fish, shellfish found in its 7 ingredient lines, including uncertain items; no dairy found in its 7 ingredient lines, including uncertain items
   Ingredients: 1/4 cup olive oil; 2 large cloves garlic, minced; 1/8 teaspoon hot red pepper flakes; 3 peeled plum tomatoes, crushed, from a can; 1/2 teaspoon salt; 2 1/2 to 3 cups cooked cannelloni beans, cooking water reserved; 1 pound cooked ditalini pasta, cooking water reserved

5. Pasta and Beans  [ar:HKOP45CaBPW0XwN77bZjJtVFtXVDV..]
   6 ingredients, 3 steps; matched: pasta
   Evidence: vegetarian: no meat, fish, shellfish found in its 6 ingredient lines, including uncertain items; no dairy found in its 6 ingredient lines, including uncertain items
   Ingredients: 1 1/2 tablespoons extra virgin olive oil; 1 onion, chopped; 2 tomatoes, chopped; 1 (15 ounce) can cannellini beans; 2 cups penne pasta; salt to taste

Filters applied to the whole dataset: exact duplicates removed (same title and ingredient set); vegetarian (excludes meat, fish, shellfish); excludes dairy
Note: Vegetarian: removed 51,127 recipes that contain meat, fish, shellfish and 2,079 where it is uncertain (e.g. margarine, chocolate); hard constraints remove uncertain cases too.
Note: No dairy: removed 41,656 recipes that contain it and 2,774 where it is uncertain (e.g. margarine, chocolate); hard constraints remove uncertain cases too.
Note: Your constraints removed 2,990 of the 3,218 recipes matching the search words (uncertain cases are removed too).
Ask for 'the first one' (or any number) to see its full recipe.
Active constraints: vegetarian, no dairy.
```
