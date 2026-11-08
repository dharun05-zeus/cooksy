# Substitution with strong evidence (PDF Task 3)

Parser: rules. Covers: substitution, restriction respected, other conflicts reported

**User:** Find chocolate chip cookies.

*parser: rules, 0.0s*

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

*parser: rules, 0.7s*

```text
Adapting: Easy Chocolate Chip Cookies  [ar:RBAW5pewzXTtgX.2bKuw8wv5WUm0rJW]
Removing: 1/2 cup butter, softened
Roles of butter in this baked dish (general cooking knowledge): fat (main), tenderness, flavor
Restrictions respected: no butter, no dairy
Original ingredients: 1 (18.25 ounce) package yellow cake mix; 1/2 cup butter, softened; 2 eggs; 1 teaspoon vanilla extract; 2 cups semisweet chocolate chips

Candidates from the dataset, ranked (evidence strength and role fit are rated separately):
  1. shortening: evidence strong (direct: 4 recipe(s) offer it as an alternative); role fit good (fat fully, tenderness fully; not flavor); quantity supported (same amount as the original)
       direct: Plum Dumplings [ar:6/NPCgFnySkuJAntnjd5N6dC3GD5xR6]: "2 tablespoons shortening or butter, softened"
       direct: Gingerbread [fn:DXQcLWSqBj0rRcKys32HlQkFORDNAqe]: "2/3 cup shortening or 5 1/3 ounces butter"
       direct: Jamaican Beef Patties [fn:KS3mYxwSO3h1X4Hgo9ROmum0xpFfzkO]: "1 cup cold butter or shortening"
       limitation: the recipes offer it as an option; none reports a tested result
  2. olive oil: evidence strong (direct: 15 recipe(s) offer it as an alternative); role fit good (fat fully, flavor fully; not tenderness); quantity supported (2/3 cup)
       direct: Brazilian Cheese Bread (Pao de Queijo) [ar:fX2MRtBMuIRMpCyFDkT5ihRMaPEQlQq]: "1/2 cup olive oil or butter"
       direct: Jimmy Dean Hearty Sausage Mini Quiches [ar:9krsTjPloFErugozlYeTE2/xo4uPEvq]: "1 tablespoon olive oil or butter"
       direct: Gorgonzola Bread [ar:r9eVGjt6H7lisY9MMsbOpjdykA741Nm]: "1/4 cup olive oil or melted butter"
       limitation: the recipes offer it as an option; none reports a tested result
  3. vegetable shortening: evidence strong (direct: 5 recipe(s) offer it as an alternative); role fit good (fat fully, tenderness fully; not flavor); quantity supported (same amount as the original)
       direct: Coconut Tamales [epi:Kfl8WWJjgBAr.5CNTIO/z09aPECRufu]: "1/3 cup vegetable shortening or butter, softened"
       direct: Cherry Pudding [fn:ElmOWBWfFgdTBhdWNA9ZAoeQbxl10iC]: "3 tablespoons vegetable shortening or butter, melted"
       direct: Baked Fish Fillets [fn:QCyTTT6kSAjWY9.1C7kzIv0IDLuo1K.]: "2 tablespoons vegetable shortening or butter"
       limitation: the recipes offer it as an option; none reports a tested result
  4. vegetable oil: evidence strong (direct: 8 recipe(s) offer it as an alternative); role fit good (fat fully; not tenderness, flavor); quantity supported (1/2 cup)
       direct: Vanilla Coconut Flour Cupcakes [ar:AQoeOlshZt4qsaMX.nfK.586MdemyOy]: "1/2 cup vegetable oil or melted butter"
       direct: Orange Pancakes `21' Club [epi:XdnNnC0kf.oF.y1luyA/Vbb6Tzpin.6]: "2 tablespoons vegetable oil or melted unsalted butter"
       direct: Sunny's Easy Breakfast Cottage Pie [fn:CRuUCcQg44E5K.sPzXkUj1YQ2c/HPvO]: "2 tablespoons vegetable oil or unsalted butter"
       limitation: the recipes offer it as an option; none reports a tested result
  5. oil: evidence strong (direct: 8 recipe(s) offer it as an alternative); role fit good (fat fully; not tenderness, flavor); quantity supported (same amount as the original)
       direct: Lemongrass-Panko Crusted Sea Bass [fn:2svFyH7VnjFvhN66OP5NjNvruPert6m]: "Oil or butter"
       direct: Yellow Snapper with Black Thai Sticky Rice, Corn Sauce, and Baby Bok Choy [fn:eIGzrykU9RBjPqWg7wjDrN7NXAhPDlG]: "Butter or oil, for sauteing"
       direct: The Porker [fn:XeFMyqS6aZ9sTAVlAqOYcxEaiTunbM.]: "2 tablespoons oil or butter"
       limitation: the recipes offer it as an option; none reports a tested result
  6. coconut oil: evidence moderate (direct: 2 recipe(s) offer it as an alternative); role fit good (fat fully, tenderness fully; not flavor); quantity supported (same amount as the original)
       direct: Buckwheat Crepes with Honeyed Ricotta and Sautéed Plums [epi:3zWG5z7wvpHiYRH6hj0OhbAuGdIo6HC]: "1 tablespoons coconut oil or butter"
       direct: Granola-Stuffed Baked Apples [fn:CjSwb2FJ2U0XM1IUaJqyXZZT4G/FsRK]: "2 tablespoons coconut oil or unsalted butter, cut into small pieces"
       indirect: Paleo Coconut Dark Chocolate Chip Cookies [ar:WAtclG48ne9euYclKjqvriVQRUpfmb.]: "1 1/2 teaspoons coconut oil, melted"
       limitation: the recipes offer it as an option; none reports a tested result
  Compared 300 baked 'chocolate chip cookie' recipes; 68 of them have no butter.
  Versions of this dish in the dataset made without butter: Super Easy Chocolate Chip Cookies [ar:RK7Vzzv28tg2cfgBqtEWzisPPmCFDeq]; Easy Chocolate Chip Cookie Dough Cheesecake [ar:iqk5XOpQOGCD.nbIzlczFga5PfoAyBO]; Chocolate Chip and Peppermint Cookie Bark [fn:0kI5vfNx7n0UbUz1tYmsW5BcVTHbqBW]
  Instruction note: "Cream sugar, shortening (may substitute 1/2 cup butter or margarine), eggs and vanilla thoroughly."  [ar:FMNsUfdxGnrJ59c/m6axYRV0.Z3UCOK]
  Instruction note: "Variations: • Add 2 cups crumbled goat cheese (8 oz) to potatoes along with butter and milk, and reduce salt to 3/4 teaspoon. • In place of butter, use 1/2 cup "  [epi:AXsAVcMc1UTpMW27zFmvku/dGi2Mgp2]
  Instruction note: "Squeeze roasted garlic from skins into potatoes along with butter and milk. • Add 2 cups crumbled goat cheese (8 oz) to potatoes along with butter and milk, and"  [epi:AXsAVcMc1UTpMW27zFmvku/dGi2Mgp2]
  Direct evidence: a recipe explicitly offers the ingredient as an alternative. Indirect evidence: a related recipe uses it without the removed ingredient but does not call it a replacement. The two are not equivalent.

Ranking rules: 1) candidates that may break a restriction rank last; 2) a candidate must provide the ingredient's main role to be selected; 3) evidence strength; 4) evidence type: direct, then same dish, then related recipes; 5) how many of the ingredient's roles it covers; 6) number of supporting recipes; 7) quantity: from the dataset, estimated, unknown.
  - shortening ranks above olive oil: shortening has more supporting recipes (21 vs 15).
  - shortening ranks above vegetable shortening: shortening has more supporting recipes (21 vs 7).
  - shortening ranks above vegetable oil: both have strong direct evidence, but shortening covers more of the butter's roles (fat fully, tenderness fully; not flavor) than vegetable oil (fat fully; not tenderness, flavor).
  - shortening ranks above oil: both have strong direct evidence, but shortening covers more of the butter's roles (fat fully, tenderness fully; not flavor) than oil (fat fully; not tenderness, flavor).

Expected trade-offs of removing butter (predictions from its role, not dataset facts):
  - without the butter's fat, the bake may be less rich and less tender
  - without the butter's tenderness, the bake may be firmer or tougher
  - without the butter's flavor, the bake may taste different

Adaptation status: Supported adaptation (dataset evidence and quantity; not tested in a kitchen).
Selected replacement: shortening (evidence strong, role fit good), selected by the ranking rules in code; steps rewritten by replacing the name.
Replacement quantity (supported): same amount as the original; 3 dataset line(s) offer shortening at the same amount, e.g. "2 tablespoons shortening or butter, softened" [ar:6/NPCgFnySkuJAntnjd5N6dC3GD5xR6]

Adapted ingredients (* = changed):
    1 (18.25 ounce) package yellow cake mix
  * 1/2 cup shortening, softened (quantity from the dataset)
    2 eggs
    1 teaspoon vanilla extract
    2 cups semisweet chocolate chips

Adapted instructions:
  1. Preheat oven to 350 degrees F (175 degrees C).
  2. Pour the cake mix into a large bowl. Stir in the shortening, eggs and vanilla with an electric mixer until well blended. Stir in the chocolate chips. Drop by rounded spoonfuls onto cookie sheets.
  3. Bake for 11 to 15 minutes in the preheated oven, until the edges are golden. Cool on baking sheets for a few minutes before removing to cool on wire racks.
Baking (from the original recipe, not re-tested): 350 degrees F (175 degrees C); 11 to 15 minutes

Changes:
  - replaced '1/2 cup butter, softened' with '1/2 cup shortening, softened (quantity from the dataset)'
  - quantity (supported): 3 dataset line(s) offer shortening at the same amount, e.g. "2 tablespoons shortening or butter, softened" [ar:6/NPCgFnySkuJAntnjd5N6dC3GD5xR6]
  - step(s) 2: butter replaced with shortening; everything else as in the original

Predicted texture changes (predictions, not verified by the dataset):
  - Richness and tenderness: shortening provides fat, so this may stay close to the original
  - Tenderness: shortening provides tenderness, so this may stay close to the original
  - Flavor: shortening does not provide flavor, so the result may taste different

WARNING: other ingredients in this recipe still break your restrictions and were not replaced: 1 (18.25 ounce) package yellow cake mix; 2 cups semisweet chocolate chips. Ask me to replace them too.

Limitations:
  - Baking temperature and time are those of the original recipe; they were not re-tested with the substitute.
  - Texture predictions come from the ingredient's roles (general cooking knowledge), not from results recorded in the dataset.
This is not a guarantee that the dish is safe for an allergy.
```
