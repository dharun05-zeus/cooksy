# Ingredient matching with a follow-up (PDF Task 2)

Parser: rules. Covers: multi-turn follow-up, explainable ranking

**User:** I have eggs, onions, tomatoes, and rice. Suggest five recipes using as many of these as possible, with no peanuts and at most six instruction steps. Prefer recipes that need the fewest additional ingredients.

*parser: rules, 0.5s*

```text
Your ingredients (as understood): egg, onion, tomato, rice
47,529 of 61,423 recipes using your ingredients satisfy your constraints. Top 5:

1. Curried Rice With Smoked Trout  [fn:Akk/zqCo1n3wzwavH0..w6QIF5363M2]
   Why here: uses 4 of your 4 ingredients, needs 6 more, 3 steps
   Matched: egg, onion, tomato, rice
   Extra required: olive oil, curry powder, cilantro, mixed green, lemon juice, smoked trout
   Staples assumed available: salt, black pepper

2. Omelet for Leftovers (Omurice)  [ar:ylwbZEdf8zK8ZA6pqy15Wll6YtZyG2G]
   Why here: uses 4 of your 4 ingredients, needs 7 more, 2 steps
   Matched: egg, onion, tomato, rice
   Extra required: butter, bell pepper, zucchini, mushroom, ketchup, bacon, paprika
   Staples assumed available: salt, black pepper

3. Imitation Meatloaf  [ar:q3kO3yCalJEVIp74kLkkcxHp6izs7zi]
   Why here: uses 4 of your 4 ingredients, needs 8 more, 3 steps
   Matched: egg, onion, tomato, rice
   Extra required: dry brown lentil, wheat germ, dry bread crumb, thyme, hot sauce, ketchup, soy sauce, mozzarella cheese

4. Sopa de Albondigas  [ar:EluceK82BeHBZiEFBnlazdnX3tReKky]
   Why here: uses 4 of your 4 ingredients, needs 8 more, 4 steps
   Matched: egg, onion, tomato, rice
   Extra required: chicken broth, ground chuck, hot pepper, garlic, cumin, pepper jack cheese, potato, cilantro
   Staples assumed available: salt, black pepper

5. Flank Steak with Black Beans and Rice  [fn:Yp5x0qV/NdaF8jYDOm3N1sE7i6Ps802]
   Why here: uses 4 of your 4 ingredients, needs 9 more, 2 steps
   Matched: egg, onion, tomato, rice
   Extra required: flank steak, vegetable oil, bay leaf, beef stock, olive oil, garlic, oregano, cumin, black bean

Ranking rule: most of your ingredients used → fewest extra ingredients needed → fewest instruction steps → recipe ID.
Hard constraints applied before ranking: exact duplicates removed (same title and ingredient set); excludes peanuts (peanut); at most 6 steps
Note: No quantities were given, so this is a name-level match; whether you have enough of each ingredient was not verified.
Active constraints: no peanuts, at most 6 steps.
```

**User:** Exclude eggs too.

*parser: rules, 0.3s*

```text
Your ingredients (as understood): onion, tomato, rice
23,572 of 36,305 recipes using your ingredients satisfy your constraints. Top 5:

1. Zucchini Saute  [ar:J/illFyDAANk7X1GwnmkQ4iMZPDTBmO]
   Why here: uses 3 of your 3 ingredients, needs 3 more, 2 steps
   Matched: onion, tomato, rice
   Extra required: vegetable oil, zucchini, bell pepper
   Staples assumed available: salt, black pepper, water

2. Mexican Rice I  [ar:tlxZ5TF3/OeA94/bLSh51tLF//pNk3.]
   Why here: uses 3 of your 3 ingredients, needs 3 more, 2 steps
   Matched: onion, tomato, rice
   Extra required: vegetable oil, cumin, chili powder
   Staples assumed available: salt, water
   Form: uses canned tomato

3. Black Beans and Rice  [fn:RwGqUrp5Mxzf/f5nCKmr0MofUtRB0Oy]
   Why here: uses 3 of your 3 ingredients, needs 3 more, 2 steps
   Matched: onion, tomato, rice
   Extra required: black bean, vegetable oil, okra
   Staples assumed available: salt

4. Vary Aminanana (Collard Greens and Rice)  [ar:wA.9BnVROfR6gjMSi2k5C7WoEoLYWOK]
   Why here: uses 3 of your 3 ingredients, needs 3 more, 3 steps
   Matched: onion, tomato, rice
   Extra required: olive oil, ginger root, collard green
   Staples assumed available: water, salt, black pepper

5. Mexican Rice  [fn:Pj3bu2i8t2GEOJE3h3991Rvnf.ud0CK]
   Why here: uses 3 of your 3 ingredients, needs 3 more, 3 steps
   Matched: onion, tomato, rice
   Extra required: vegetable oil, garlic, jalapeno pepper
   Staples assumed available: salt

Ranking rule: most of your ingredients used → fewest extra ingredients needed → fewest instruction steps → recipe ID.
Hard constraints applied before ranking: exact duplicates removed (same title and ingredient set); excludes peanuts (peanut); excludes eggs (egg); at most 6 steps
Note: 'eggs' is excluded by your constraints, so it is not counted as one of your ingredients.
Note: No quantities were given, so this is a name-level match; whether you have enough of each ingredient was not verified.
Active constraints: no peanuts, no eggs, at most 6 steps.
```
