# Substitution with strong evidence (PDF Task 3)

Parser: ollama (qwen3:4b). Covers: substitution, restriction respected, other conflicts reported

**User:** Find chocolate chip cookies.

*parser: ollama (qwen3:4b), 3.8s*

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

*parser: ollama (qwen3:4b), 35.4s; guard corrections: ["add_exclude += ['dairy']"]*

```text
Adapting: Easy Chocolate Chip Cookies  [ar:RBAW5pewzXTtgX.2bKuw8wv5WUm0rJW]
Replacing: 1/2 cup butter, softened
Role of butter in this baked dish: fat, tenderness, flavor (general cooking knowledge)
Restrictions respected: no butter, no dairy

Local evidence from the dataset:
  1. shortening: strong evidence; offered as an alternative to the target in 6 baked recipes; used by 17 same dish recipes without the target (25% of them vs 3% of those with it); good fit for the target's role
       direct: "2 tablespoons shortening or butter, softened"  [ar:6/NPCgFnySkuJAntnjd5N6dC3GD5xR6]
       direct: "2/3 cup shortening or 5 1/3 ounces butter"  [fn:DXQcLWSqBj0rRcKys32HlQkFORDNAqe]
       similar recipes without it: ar:25AEIq/dH3y9t71C0qtE1qnm/11w6KS, ar:FsrGslbv9un5DrnB4IRRPSt6.kzPLNe, ar:IRtTZxgr9mmoS7GuOCJrG3reogQxSkG
  2. vegetable oil: strong evidence; offered as an alternative to the target in 8 baked recipes; used by 8 same dish recipes without the target (12% of them vs 1% of those with it); good fit for the target's role
       direct: "1/2 cup vegetable oil or melted butter"  [ar:AQoeOlshZt4qsaMX.nfK.586MdemyOy]
       direct: "2 tablespoons vegetable oil or melted unsalted butter"  [epi:XdnNnC0kf.oF.y1luyA/Vbb6Tzpin.6]
       similar recipes without it: ar:FsrGslbv9un5DrnB4IRRPSt6.kzPLNe, ar:Ol9Um7HmhaSIyTbuvXoYiC/KS2Y769W, ar:RK7Vzzv28tg2cfgBqtEWzisPPmCFDeq
  3. oil: strong evidence; offered as an alternative to the target in 9 baked recipes; used by 3 same dish recipes without the target (4% of them vs 0% of those with it); good fit for the target's role
       direct: "Oil or butter, for greasing pan"  [epi:3TD/oyiSWgZi6EANk3S1ijarbx9ZrZi]
       direct: "Oil or butter"  [fn:2svFyH7VnjFvhN66OP5NjNvruPert6m]
       similar recipes without it: epi:T6QxNuxub8fQtdGKk.BZMtn84Y22Dni, fn:Gxx55Xd.Qyd7f9rez6CX.WHoxe1Pnxe, fn:yN9CEpJDTIvuq87leQOAt5k5585G3wu
  4. olive oil: strong evidence; offered as an alternative to the target in 15 baked recipes; good fit for the target's role
       direct: "1/2 cup olive oil or butter"  [ar:fX2MRtBMuIRMpCyFDkT5ihRMaPEQlQq]
       direct: "1 tablespoon olive oil or butter"  [ar:9krsTjPloFErugozlYeTE2/xo4uPEvq]
  5. vegetable shortening: strong evidence; offered as an alternative to the target in 5 baked recipes; used by 2 same dish recipes without the target (3% of them vs 1% of those with it); good fit for the target's role
       direct: "1/3 cup vegetable shortening or butter, softened"  [epi:Kfl8WWJjgBAr.5CNTIO/z09aPECRufu]
       direct: "3 tablespoons vegetable shortening or butter, melted"  [fn:ElmOWBWfFgdTBhdWNA9ZAoeQbxl10iC]
       similar recipes without it: ar:66i3iWBY07GBkuRSrmUnwi8HXTQSbD6, epi:CTGHouBjECFoRdSH2NyvtPs5mFeLtEK
  6. coconut oil: moderate evidence; offered as an alternative to the target in 2 baked recipes; used by 2 same dish recipes without the target (3% of them vs 0% of those with it); good fit for the target's role
       direct: "1 tablespoons coconut oil or butter"  [epi:3zWG5z7wvpHiYRH6hj0OhbAuGdIo6HC]
       direct: "2 tablespoons coconut oil or unsalted butter, cut into small pieces"  [fn:CjSwb2FJ2U0XM1IUaJqyXZZT4G/FsRK]
       similar recipes without it: ar:WAtclG48ne9euYclKjqvriVQRUpfmb., epi:PyfOR1IEfVF7jtYGhlgrlXiCwhm.dGW
  Compared 300 baked 'chocolate chip cookie' recipes; 68 of them have no butter.
  Versions of this dish in the dataset made without butter: Super Easy Chocolate Chip Cookies [ar:RK7Vzzv28tg2cfgBqtEWzisPPmCFDeq]; Easy Chocolate Chip Cookie Dough Cheesecake [ar:iqk5XOpQOGCD.nbIzlczFga5PfoAyBO]; Chocolate Chip and Peppermint Cookie Bark [fn:0kI5vfNx7n0UbUz1tYmsW5BcVTHbqBW]
  Instruction note: "Cream sugar, shortening (may substitute 1/2 cup butter or margarine), eggs and vanilla thoroughly."  [ar:FMNsUfdxGnrJ59c/m6axYRV0.Z3UCOK]
  Instruction note: "Variations: • Add 2 cups crumbled goat cheese (8 oz) to potatoes along with butter and milk, and reduce salt to 3/4 teaspoon. • In place of butter, use 1/2 cup "  [epi:AXsAVcMc1UTpMW27zFmvku/dGi2Mgp2]
  Instruction note: "Squeeze roasted garlic from skins into potatoes along with butter and milk. • Add 2 cups crumbled goat cheese (8 oz) to potatoes along with butter and milk, and"  [epi:AXsAVcMc1UTpMW27zFmvku/dGi2Mgp2]
  'Direct' = a recipe offers the swap itself; comparative evidence is indirect (those recipes may differ in other ways too).

Expected trade-offs of removing butter (predictions from its role, not dataset facts):
  - without the butter's fat, the bake may be less rich and less tender
  - without the butter's tenderness, the bake may be firmer or tougher
  - without the butter's flavor, the bake the flavor will change

Chosen substitute: shortening (strong evidence), chosen by the LLM (ollama (qwen3:4b)), from the evidenced candidates only, then checked by code.

Adapted ingredients (* = changed):
    1 (18.25 ounce) package yellow cake mix
  * 1/2 cup shortening, softened
    2 eggs
    1 teaspoon vanilla extract
    2 cups semisweet chocolate chips

Adapted instructions:
  1. Preheat oven to 350 degrees F (175 degrees C).
  2. Pour the cake mix into a large bowl. Stir in the shortening, eggs and vanilla with an electric mixer until well blended. Stir in the chocolate chips. Drop by rounded spoonfuls onto cookie sheets.
  3. Bake for 11 to 15 minutes in the preheated oven, until the edges are golden. Cool on baking sheets for a few minutes before removing to cool on wire racks.

Changes:
  - Substituted butter with shortening (evidence: strong role fit, used in 17 same dish recipes without butter)

Predicted effects (not verified by the dataset):
  - Slightly less rich flavor but similar tenderness and texture
  - May require a bit more mixing time due to different viscosity

WARNING: other ingredients in this recipe still break your restrictions and were not replaced: 1 (18.25 ounce) package yellow cake mix; 2 cups semisweet chocolate chips. Ask me to replace them too.
This is not a guarantee that the dish is safe for an allergy.
```
