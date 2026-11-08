# Substitution with weak or conflicting evidence (PDF Task 3)

Parser: ollama (qwen3:4b). Covers: weak or conflicting evidence, quantity not invented, follow-up with a requested replacement

**User:** Take this banana bread recipe and remove eggs. Use only ingredients that appear in the dataset.

*parser: ollama (qwen3:4b), 18.4s*

```text
Using 'Banana Banana Bread' [ar:kq.naD.8G19M4UU9dVvJgHtpfo.l/eC], the top match for 'banana bread' that contains eggs.
Adapting: Banana Banana Bread  [ar:kq.naD.8G19M4UU9dVvJgHtpfo.l/eC]
Removing: 2 eggs, beaten
Roles of egg in this baked dish (general cooking knowledge): binding (main), leavening, moisture, structure, emulsification
Restrictions respected: no eggs
Original ingredients: 2 cups all-purpose flour; 1 teaspoon baking soda; 1/4 teaspoon salt; 1/2 cup butter; 3/4 cup brown sugar; 2 eggs, beaten; 2 1/3 cups mashed overripe bananas

Candidates from the dataset, ranked (evidence strength and role fit are rated separately):
  1. silken tofu: evidence weak (indirect: used by 1 same-dish recipe(s) without it); role fit good (binding fully, moisture fully, structure partly, emulsification partly; not leavening); quantity unknown
       indirect: Microwave Tofu Banana Bread [ar:5S4TJwjeeH.L/gDoUxUR0jfxC/8Vd4u]: "1/2 (12 ounce) package silken tofu"
       limitation: indirect (a single recipe): those recipes use it and lack the target, but may differ in other ways and do not call it a replacement
  2. applesauce: evidence weak (indirect: used by 1 same-dish recipe(s) without it); role fit partial (binding partly, moisture fully; not leavening, structure, emulsification); quantity estimated (2/3 cup)
       indirect: Vegan Zucchini Banana Bread Muffins [ar:.GLWQH0bkiU3fRzwc68PqTCqGHJj2fy]: "1 cup applesauce"
       limitation: indirect (a single recipe): those recipes use it and lack the target, but may differ in other ways and do not call it a replacement
  3. soy yogurt: evidence weak (indirect: used by 1 same-dish recipe(s) without it); role fit partial (binding partly, moisture fully; not leavening, structure, emulsification); quantity estimated (3/4 cup)
       indirect: Vegan Banana Bread [fn:p174TykunvO./PLjDpl03RBTaXiOEdu]: "1/2 cup plain soy milk yogurt"
       limitation: indirect (a single recipe): those recipes use it and lack the target, but may differ in other ways and do not call it a replacement
  4. olive oil: evidence moderate (indirect: used by 12 bread recipe(s) without it); role fit partial (moisture fully; not binding, leavening, structure, emulsification); quantity unknown
       indirect: Appetizing Bread [ar:06n7WTw6RQSDCfROjZZs5Zee/ciX.Hm]: "1 cup extra virgin olive oil"
       indirect: Roasted Garlic Bread [ar:LL5BIYQHdnkUgqMUBwZyKR0x7QrnXX.]: "2 tablespoons olive oil"
       indirect: Ciabatta Bread [ar:Xb0UYfwuDfuuRXtjGsuVcjbGXbOJNsq]: "1 tablespoon olive oil"
       limitation: indirect: those recipes use it and lack the target, but may differ in other ways and do not call it a replacement
  5. evaporated milk: evidence weak (direct: 1 recipe(s) offer it as an alternative); role fit partial (moisture fully; not binding, leavening, structure, emulsification); quantity unknown
       direct: Pumpkin Turnovers [epi:DiKM3xoQccTZ7paC.XGMVpHMD8gchRm]: "Canned evaporated milk or egg white"
       limitation: offered as an alternative in a single recipe only
  6. egg substitute: evidence conflicting (direct: 4 recipe(s) offer it as an alternative); role fit good (binding fully, leavening fully, moisture fully, structure fully, emulsification fully); quantity supported (1/2 cup)
       direct: Quick-and-Easy Cheese Blintz Casserole [epi:cTG4e2s8RON5swgZSMmn6Omhx7Q9MGi]: "2 large eggs or 1/2 cup egg substitute"
       direct: Carrot Cake [epi:LSm1hzr0Vqt1sNp2f5ml93JmmG7Qm2C]: "1/4 cup egg substitute or 2 large egg whites"
       direct: Elvis Woulda Loved It [fn:yTnmJN90fdLXlp2nrQ85lmQsEJU.TV2]: "3/4 cup egg substitute or 3 whole eggs"
       limitation: may contain a restricted ingredient, so it is never chosen automatically
  Compared 183 baked 'banana bread' recipes; only 9 lack eggs, so also 300 baked 'bread' recipes (83 without it); 9 of them have no eggs.
  Versions of this dish in the dataset made without eggs: Microwave Tofu Banana Bread [ar:5S4TJwjeeH.L/gDoUxUR0jfxC/8Vd4u]; Banana Oat Bread Pudding [ar:/tgLkKTWsLuZ95S0LSm4WrrYcwKFuMi]; Rich and Delicious Banana Bread [ar:TJFqS5qmSUVcBw7c2Da99BzhmvnbgCm]
  Instruction note: "Prepare cake mix as directed, except substitute egg whites for eggs and applesauce for oil."  [ar:d8ca8qxARHeOTiYcQFQlp229RTttkw.]
  Direct evidence: a recipe explicitly offers the ingredient as an alternative. Indirect evidence: a related recipe uses it without the removed ingredient but does not call it a replacement. The two are not equivalent.

Ranking rules: 1) candidates that may break a restriction rank last; 2) a candidate must provide the ingredient's main role to be selected; 3) evidence strength; 4) evidence type: direct, then same dish, then related recipes; 5) how many of the ingredient's roles it covers; 6) number of supporting recipes; 7) quantity: from the dataset, estimated, unknown.
  - silken tofu ranks above applesauce: both have weak same dish evidence, but silken tofu covers more of the egg's roles (binding fully, moisture fully, structure partly, emulsification partly; not leavening) than applesauce (binding partly, moisture fully; not leavening, structure, emulsification).
  - silken tofu ranks above soy yogurt: both have weak same dish evidence, but silken tofu covers more of the egg's roles (binding fully, moisture fully, structure partly, emulsification partly; not leavening) than soy yogurt (binding partly, moisture fully; not leavening, structure, emulsification).
  - silken tofu ranks above olive oil: olive oil does not provide the egg's main role (binding).
  - silken tofu ranks above evaporated milk: evaporated milk does not provide the egg's main role (binding).

Expected trade-offs of removing eggs (predictions from its role, not dataset facts):
  - without the egg's binding, the bake may hold together less well and be more crumbly
  - without the egg's leavening, the bake may rise less and be denser
  - without the egg's moisture, the bake may be drier
  - without the egg's structure, the bake may be more fragile and softer
  - without the egg's emulsification, the bake may be less smooth, as the batter can separate

Adaptation status: Incomplete experimental adaptation (quantity not established by the dataset).
Selected replacement: silken tofu (evidence weak, role fit good), selected by the ranking rules in code; steps reworded by the LLM (ollama (qwen3:4b)) and checked by code.
Replacement quantity (unknown): Quantity not established by the dataset. Microwave Tofu Banana Bread [ar:5S4TJwjeeH.L/gDoUxUR0jfxC/8Vd4u] uses "1/2 (12 ounce) package silken tofu", but its size cannot be compared with this recipe's, so the amount is not scaled.
This is an incomplete experimental adaptation: the silken tofu amount is not established, so the list below is not a complete recipe.

Adapted ingredients (* = changed):
    2 cups all-purpose flour
    1 teaspoon baking soda
    1/4 teaspoon salt
    1/2 cup butter
    3/4 cup brown sugar
  * silken tofu (quantity not established by the dataset)
    2 1/3 cups mashed overripe bananas

Adapted instructions:
  1. Preheat oven to 350 degrees F (175 degrees C). Lightly grease a 9x5 inch loaf pan.
  2. In a large bowl, combine flour, baking soda and salt. In a separate bowl, cream together butter and brown sugar. Stir in silken tofu and mashed bananas until well blended. Stir banana mixture into flour mixture; stir just to moisten. Pour batter into prepared loaf pan.
  3. Bake in preheated oven for 60 to 65 minutes, until a toothpick inserted into center of the loaf comes out clean. Let bread cool in pan for 10 minutes, then turn out onto a wire rack.
Baking (from the original recipe, not re-tested): 350 degrees F (175 degrees C); 60 to 65 minutes

Changes:
  - replaced '2 eggs, beaten' with 'silken tofu (quantity not established by the dataset)'
  - quantity (unknown): Quantity not established by the dataset. Microwave Tofu Banana Bread [ar:5S4TJwjeeH.L/gDoUxUR0jfxC/8Vd4u] uses "1/2 (12 ounce) package silken tofu", but its size cannot be compared with this recipe's, so the amount is not scaled.
  - step(s) 2: eggs replaced with silken tofu; everything else as in the original

Moisture check (risk: high):
  - Wet ingredients already in this recipe: 2 1/3 cups mashed overripe bananas.
  - By volume they are 117% of the flour; the median across 56 'banana bread' recipes in the dataset is 80% (eggs are not counted: the dataset gives no volume for them).
  - The amount of silken tofu is not established, and it decides how wet the batter gets.
  - Excess-moisture risk: a wetter batter can bake up gummy, dense or underbaked in the centre. Check doneness with a toothpick; the original baking time was not tested with this change.

Predicted texture changes (predictions, not verified by the dataset):
  - Binding: silken tofu provides binding, so this may stay close to the original
  - Rise: silken tofu does not provide leavening, so the result may rise less and be denser
  - Moisture: may stay moist or become wetter than the original, depending on the amount of silken tofu
  - Structure: potentially weaker than the original: silken tofu provides only some structure
  - Batter consistency: potentially weaker than the original: silken tofu provides only some emulsification
  - Density: may become denser, since the egg's leavening is not fully replaced
  - Crumb: may become softer or gummy, more so with more silken tofu

Limitations:
  - No recipe in the dataset explicitly recommends silken tofu for eggs. The evidence is indirect: recipes that use silken tofu and no eggs may differ in other ways too.
  - The evidence rests on a single recipe.
  - Quantity not established by the dataset. The ingredient list is incomplete: test a small batch before relying on it.
  - Baking temperature and time are those of the original recipe; they were not re-tested with the substitute.
  - Texture predictions come from the ingredient's roles (general cooking knowledge), not from results recorded in the dataset.
  - silken tofu, applesauce, soy yogurt all have equally weak evidence; the order between them rests on role coverage and quantity, not on stronger data.
  - Conflicting evidence: egg substitute is supported by the dataset but may contain a restricted ingredient, so it ranks last and is never chosen automatically.

Caution: the evidence for silken tofu is weak; treat this adaptation as untested.
This is not a guarantee that the dish is safe for an allergy.
```

**User:** Use applesauce instead.

*parser: ollama (qwen3:4b), 25.4s*

```text
Adapting: Banana Banana Bread  [ar:kq.naD.8G19M4UU9dVvJgHtpfo.l/eC]
Removing: 2 eggs, beaten
Roles of egg in this baked dish (general cooking knowledge): binding (main), leavening, moisture, structure, emulsification
Restrictions respected: no eggs
Original ingredients: 2 cups all-purpose flour; 1 teaspoon baking soda; 1/4 teaspoon salt; 1/2 cup butter; 3/4 cup brown sugar; 2 eggs, beaten; 2 1/3 cups mashed overripe bananas

Candidates from the dataset, ranked (evidence strength and role fit are rated separately):
  1. applesauce: evidence weak (indirect: used by 1 same-dish recipe(s) without it); role fit partial (binding partly, moisture fully; not leavening, structure, emulsification); quantity estimated (2/3 cup)
       indirect: Vegan Zucchini Banana Bread Muffins [ar:.GLWQH0bkiU3fRzwc68PqTCqGHJj2fy]: "1 cup applesauce"
       limitation: indirect (a single recipe): those recipes use it and lack the target, but may differ in other ways and do not call it a replacement
  2. silken tofu: evidence weak (indirect: used by 1 same-dish recipe(s) without it); role fit good (binding fully, moisture fully, structure partly, emulsification partly; not leavening); quantity unknown
       indirect: Microwave Tofu Banana Bread [ar:5S4TJwjeeH.L/gDoUxUR0jfxC/8Vd4u]: "1/2 (12 ounce) package silken tofu"
       limitation: indirect (a single recipe): those recipes use it and lack the target, but may differ in other ways and do not call it a replacement
  3. soy yogurt: evidence weak (indirect: used by 1 same-dish recipe(s) without it); role fit partial (binding partly, moisture fully; not leavening, structure, emulsification); quantity estimated (3/4 cup)
       indirect: Vegan Banana Bread [fn:p174TykunvO./PLjDpl03RBTaXiOEdu]: "1/2 cup plain soy milk yogurt"
       limitation: indirect (a single recipe): those recipes use it and lack the target, but may differ in other ways and do not call it a replacement
  4. olive oil: evidence moderate (indirect: used by 12 bread recipe(s) without it); role fit partial (moisture fully; not binding, leavening, structure, emulsification); quantity unknown
       indirect: Appetizing Bread [ar:06n7WTw6RQSDCfROjZZs5Zee/ciX.Hm]: "1 cup extra virgin olive oil"
       indirect: Roasted Garlic Bread [ar:LL5BIYQHdnkUgqMUBwZyKR0x7QrnXX.]: "2 tablespoons olive oil"
       indirect: Ciabatta Bread [ar:Xb0UYfwuDfuuRXtjGsuVcjbGXbOJNsq]: "1 tablespoon olive oil"
       limitation: indirect: those recipes use it and lack the target, but may differ in other ways and do not call it a replacement
  5. evaporated milk: evidence weak (direct: 1 recipe(s) offer it as an alternative); role fit partial (moisture fully; not binding, leavening, structure, emulsification); quantity unknown
       direct: Pumpkin Turnovers [epi:DiKM3xoQccTZ7paC.XGMVpHMD8gchRm]: "Canned evaporated milk or egg white"
       limitation: offered as an alternative in a single recipe only
  6. egg substitute: evidence conflicting (direct: 4 recipe(s) offer it as an alternative); role fit good (binding fully, leavening fully, moisture fully, structure fully, emulsification fully); quantity supported (1/2 cup)
       direct: Quick-and-Easy Cheese Blintz Casserole [epi:cTG4e2s8RON5swgZSMmn6Omhx7Q9MGi]: "2 large eggs or 1/2 cup egg substitute"
       direct: Carrot Cake [epi:LSm1hzr0Vqt1sNp2f5ml93JmmG7Qm2C]: "1/4 cup egg substitute or 2 large egg whites"
       direct: Elvis Woulda Loved It [fn:yTnmJN90fdLXlp2nrQ85lmQsEJU.TV2]: "3/4 cup egg substitute or 3 whole eggs"
       limitation: may contain a restricted ingredient, so it is never chosen automatically
  Compared 183 baked 'banana bread' recipes; only 9 lack eggs, so also 300 baked 'bread' recipes (83 without it); 9 of them have no eggs.
  Versions of this dish in the dataset made without eggs: Microwave Tofu Banana Bread [ar:5S4TJwjeeH.L/gDoUxUR0jfxC/8Vd4u]; Banana Oat Bread Pudding [ar:/tgLkKTWsLuZ95S0LSm4WrrYcwKFuMi]; Rich and Delicious Banana Bread [ar:TJFqS5qmSUVcBw7c2Da99BzhmvnbgCm]
  Instruction note: "Prepare cake mix as directed, except substitute egg whites for eggs and applesauce for oil."  [ar:d8ca8qxARHeOTiYcQFQlp229RTttkw.]
  Direct evidence: a recipe explicitly offers the ingredient as an alternative. Indirect evidence: a related recipe uses it without the removed ingredient but does not call it a replacement. The two are not equivalent.

Ranking rules: 1) candidates that may break a restriction rank last; 2) a candidate must provide the ingredient's main role to be selected; 3) evidence strength; 4) evidence type: direct, then same dish, then related recipes; 5) how many of the ingredient's roles it covers; 6) number of supporting recipes; 7) quantity: from the dataset, estimated, unknown.
  - You asked for applesauce, so the ranking rules were not used to choose it; its evidence and role coverage are shown as for any other candidate.

Expected trade-offs of removing eggs (predictions from its role, not dataset facts):
  - without the egg's binding, the bake may hold together less well and be more crumbly
  - without the egg's leavening, the bake may rise less and be denser
  - without the egg's moisture, the bake may be drier
  - without the egg's structure, the bake may be more fragile and softer
  - without the egg's emulsification, the bake may be less smooth, as the batter can separate

Adaptation status: Experimental adaptation (weak evidence or estimated quantity).
Selected replacement: applesauce (evidence weak, role fit partial), selected by you (requested); steps rewritten by replacing the name.
Replacement quantity (estimated): 2/3 cup; estimated from Vegan Zucchini Banana Bread Muffins [ar:.GLWQH0bkiU3fRzwc68PqTCqGHJj2fy], which uses "1 cup applesauce" with 3 cups flour; scaled to this recipe's 2 cups flour

Adapted ingredients (* = changed):
    2 cups all-purpose flour
    1 teaspoon baking soda
    1/4 teaspoon salt
    1/2 cup butter
    3/4 cup brown sugar
  * 2/3 cup applesauce (estimated quantity)
    2 1/3 cups mashed overripe bananas

Adapted instructions:
  1. Preheat oven to 350 degrees F (175 degrees C). Lightly grease a 9x5 inch loaf pan.
  2. In a large bowl, combine flour, baking soda and salt. In a separate bowl, cream together butter and brown sugar. Stir in applesauce and mashed bananas until well blended. Stir banana mixture into flour mixture; stir just to moisten. Pour batter into prepared loaf pan.
  3. Bake in preheated oven for 60 to 65 minutes, until a toothpick inserted into center of the loaf comes out clean. Let bread cool in pan for 10 minutes, then turn out onto a wire rack.
Baking (from the original recipe, not re-tested): 350 degrees F (175 degrees C); 60 to 65 minutes

Changes:
  - replaced '2 eggs, beaten' with '2/3 cup applesauce (estimated quantity)'
  - quantity (estimated): estimated from Vegan Zucchini Banana Bread Muffins [ar:.GLWQH0bkiU3fRzwc68PqTCqGHJj2fy], which uses "1 cup applesauce" with 3 cups flour; scaled to this recipe's 2 cups flour
  - step(s) 2: eggs replaced with applesauce; everything else as in the original

Moisture check (risk: high):
  - Wet ingredients already in this recipe: 2 1/3 cups mashed overripe bananas.
  - By volume they are 117% of the flour; the median across 56 'banana bread' recipes in the dataset is 80% (eggs are not counted: the dataset gives no volume for them).
  - With 2/3 cup applesauce (estimated) it would be about 150%.
  - Excess-moisture risk: a wetter batter can bake up gummy, dense or underbaked in the centre. Check doneness with a toothpick; the original baking time was not tested with this change.

Predicted texture changes (predictions, not verified by the dataset):
  - Binding: potentially weaker than the original: applesauce provides only some binding
  - Rise: applesauce does not provide leavening, so the result may rise less and be denser
  - Moisture: may stay moist or become wetter than the original, depending on the amount of applesauce
  - Structure: applesauce does not provide structure, so the result may be more fragile and softer
  - Batter consistency: applesauce does not provide emulsification, so the result may be less smooth, as the batter can separate
  - Density: may become denser, since the egg's leavening is not fully replaced
  - Crumb: may become softer or gummy, more so with more applesauce

Limitations:
  - No recipe in the dataset explicitly recommends applesauce for eggs. The evidence is indirect: recipes that use applesauce and no eggs may differ in other ways too.
  - The evidence rests on a single recipe.
  - The quantity is an estimate scaled from another recipe, not an amount the dataset gives for this substitution.
  - Baking temperature and time are those of the original recipe; they were not re-tested with the substitute.
  - Texture predictions come from the ingredient's roles (general cooking knowledge), not from results recorded in the dataset.

Caution: the evidence for applesauce is weak; treat this adaptation as untested.
Note: some LLM step rewrites were not used (step 2 rewrite adds numbers ['2', '3']); those steps use the rule-based rewrite.
This is not a guarantee that the dish is safe for an allergy.
```
