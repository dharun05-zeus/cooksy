# Substitution with strong evidence (PDF Task 3)

Parser: ollama (qwen3:4b). Covers: substitution, restriction respected, other conflicts reported

**User:** Find chocolate chip cookies.

*parser: ollama (qwen3:4b), 4.0s*

```text
12,819 recipes share at least one word with 'chocolate chip cookies'. The 5 most relevant:

1. Easy Chocolate Chip Cookies  [ar:RBAW5pewzXTtgX.2bKuw8wv5WUm0rJW]
   5 ingredients, 3 steps; matched: chocolate, chip, cookie

2. Chocolate Chip Cookie Pie Crust  [fn:oQxof/DMNnvFoXWjv9idYb9V15P4jyG]
   4 ingredients, 2 steps; matched: chocolate, chip, cookie

3. Quick Chocolate Chip Cookie Cake  [ar:d6OkEkfpeougQEphCnBqf1cFPyIUVVu]
   4 ingredients, 3 steps; matched: chocolate, chip, cookie

4. Super Easy Chocolate Chip Cookies  [ar:RK7Vzzv28tg2cfgBqtEWzisPPmCFDeq]
   4 ingredients, 3 steps; matched: chocolate, chip, cookie

5. Quick Chocolate Chip Cookies  [fn:rdAmVvsjNefAmDh3favT2HJRuCF/eBi]
   8 ingredients, 5 steps; matched: chocolate, chip, cookie

Filters applied to the whole dataset: exact duplicates removed (same title and ingredient set)
Ask for 'the first one' (or any number) to see its full recipe.
```

**User:** I cannot have dairy. Replace the butter in the first one.

*parser: ollama (qwen3:4b), 25.3s; guard corrections: ["replacement 'dairy-free butter' removed (not in the message)", "add_exclude += ['dairy']"]*

```text
Easy Chocolate Chip Cookies without butter: supported by the dataset, high confidence  [ar:RBAW5pewzXTtgX.2bKuw8wv5WUm0rJW]
- Swap: replace 1/2 cup butter, softened with shortening; same amount as the original (the dataset offers this)
- Why: 4 recipes in the dataset offer it as an alternative to butter, and it adds fat and tenderness like butter does.
- Other options: olive oil (2/3 cup), vegetable shortening (same amount)
- Expect: Richness and tenderness: shortening provides fat, so this may stay close to the original; tenderness: shortening provides tenderness, so this may stay close to the original.
- Bake: as the original, 350 degrees F (175 degrees C); 11 to 15 minutes. Check with a toothpick.
- Still to replace: 1 (18.25 ounce) package yellow cake mix; 2 cups semisweet chocolate chips

Adapted recipe (* = changed):
    1 (18.25 ounce) package yellow cake mix
  * 1/2 cup shortening, softened (quantity from the dataset)
    2 eggs
    1 teaspoon vanilla extract
    2 cups semisweet chocolate chips
Steps:
  1. Preheat oven to 350 degrees F (175 degrees C).
  2. Pour the cake mix into a large bowl. Stir in the shortening, eggs and vanilla with an electric mixer until well blended. Stir in the chocolate chips. Drop by rounded spoonfuls onto cookie sheets.
  3. Bake for 11 to 15 minutes in the preheated oven, until the edges are golden. Cool on baking sheets for a few minutes before removing to cool on wire racks.

DETAILS
Selected replacement: shortening (strong evidence, good role fit), selected by the ranking rules in code; steps reworded by the LLM (ollama (qwen3:4b)) and checked by code.
Amount (supported): 3 dataset line(s) offer shortening at the same amount, e.g. "2 tablespoons shortening or butter, softened" [ar:6/NPCgFnySkuJAntnjd5N6dC3GD5xR6]
What butter does here (cooking knowledge): fat (main), tenderness, flavor.
Why this choice (ranking rules: 1) candidates that may break a restriction rank last; 2) a candidate must provide the ingredient's main role to be selected; 3) evidence strength; 4) evidence type: direct, then same dish, then related recipes; 5) how many of the ingredient's roles it covers; 6) number of supporting recipes; 7) quantity: from the dataset, estimated, unknown):
  - shortening ranks above olive oil: shortening has more supporting recipes (21 vs 15).
  - shortening ranks above vegetable shortening: shortening has more supporting recipes (21 vs 7).
  - shortening ranks above vegetable oil: both have strong direct evidence, but shortening covers more of the butter's roles (fat fully, tenderness fully; not flavor) than vegetable oil (fat fully; not tenderness, flavor).
  - shortening ranks above oil: both have strong direct evidence, but shortening covers more of the butter's roles (fat fully, tenderness fully; not flavor) than oil (fat fully; not tenderness, flavor).
Evidence from the dataset, ranked (strength and role fit rated separately):
  1. shortening: strong evidence, good fit, same amount (direct: 4 recipe(s) offer it as an alternative; e.g. Plum Dumplings [ar:6/NPCgFnySkuJAntnjd5N6dC3GD5xR6])
  2. olive oil: strong evidence, good fit, 2/3 cup (direct: 15 recipe(s) offer it as an alternative; e.g. Brazilian Cheese Bread (Pao de Queijo) [ar:fX2MRtBMuIRMpCyFDkT5ihRMaPEQlQq])
  3. vegetable shortening: strong evidence, good fit, same amount (direct: 5 recipe(s) offer it as an alternative; e.g. Coconut Tamales [epi:Kfl8WWJjgBAr.5CNTIO/z09aPECRufu])
  4. vegetable oil: strong evidence, good fit, 1/2 cup (direct: 8 recipe(s) offer it as an alternative; e.g. Vanilla Coconut Flour Cupcakes [ar:AQoeOlshZt4qsaMX.nfK.586MdemyOy])
  5. oil: strong evidence, good fit, same amount (direct: 8 recipe(s) offer it as an alternative; e.g. Lemongrass-Panko Crusted Sea Bass [fn:2svFyH7VnjFvhN66OP5NjNvruPert6m])
  6. coconut oil: moderate evidence, good fit, same amount (direct: 2 recipe(s) offer it as an alternative; e.g. Buckwheat Crepes with Honeyed Ricotta and Sautéed Plums [epi:3zWG5z7wvpHiYRH6hj0OhbAuGdIo6HC])
  Compared 300 baked 'chocolate chip cookie' recipes; 68 of them have no butter.
  Versions of this dish in the dataset made without butter: Super Easy Chocolate Chip Cookies [ar:RK7Vzzv28tg2cfgBqtEWzisPPmCFDeq]; Easy Chocolate Chip Cookie Dough Cheesecake [ar:iqk5XOpQOGCD.nbIzlczFga5PfoAyBO]; Chocolate Chip and Peppermint Cookie Bark [fn:0kI5vfNx7n0UbUz1tYmsW5BcVTHbqBW]
  Instruction note: "Cream sugar, shortening (may substitute 1/2 cup butter or margarine), eggs and vanilla thoroughly."  [ar:FMNsUfdxGnrJ59c/m6axYRV0.Z3UCOK]
  Instruction note: "Variations: • Add 2 cups crumbled goat cheese (8 oz) to potatoes along with butter and milk, and reduce salt to 3/4 teaspoon. • In place of butter, use 1/2 cup "  [epi:AXsAVcMc1UTpMW27zFmvku/dGi2Mgp2]
  Instruction note: "Squeeze roasted garlic from skins into potatoes along with butter and milk. • Add 2 cups crumbled goat cheese (8 oz) to potatoes along with butter and milk, and"  [epi:AXsAVcMc1UTpMW27zFmvku/dGi2Mgp2]
  Direct evidence: a recipe explicitly offers the ingredient as an alternative. Indirect evidence: a related recipe uses it without the removed ingredient but does not call it a replacement. The two are not equivalent.
Predicted texture changes (predictions, not verified by the dataset):
  - Richness and tenderness: shortening provides fat, so this may stay close to the original
  - Tenderness: shortening provides tenderness, so this may stay close to the original
  - Flavor: shortening does not provide flavor, so the result may taste different
Limitations:
  - Baking temperature and time are those of the original recipe; they were not re-tested with the substitute.
  - Texture predictions come from the ingredient's roles (general cooking knowledge), not from results recorded in the dataset.
This is not a guarantee that the dish is safe for an allergy.
```
