# Substitution with weak or conflicting evidence (PDF Task 3)

Parser: ollama (qwen3:4b). Covers: weak or conflicting evidence, declining to guess

**User:** Take this banana bread recipe and remove eggs. Use only ingredients that appear in the dataset.

*parser: ollama (qwen3:4b), 64.7s*

```text
Using 'Banana Banana Bread' [ar:kq.naD.8G19M4UU9dVvJgHtpfo.l/eC], the top match for 'banana bread' that contains eggs.
Adapting: Banana Banana Bread  [ar:kq.naD.8G19M4UU9dVvJgHtpfo.l/eC]
Replacing: 2 eggs, beaten
Role of egg in this baked dish: binding, leavening, moisture (general cooking knowledge)
Restrictions respected: no eggs

Local evidence from the dataset:
  1. applesauce: weak evidence; used by 1 same dish recipes without the target (11% of them vs 3% of those with it); good fit for the target's role
       similar recipes without it: ar:.GLWQH0bkiU3fRzwc68PqTCqGHJj2fy
  2. silken tofu: weak evidence; used by 1 same dish recipes without the target (11% of them vs 0% of those with it); good fit for the target's role
       similar recipes without it: ar:5S4TJwjeeH.L/gDoUxUR0jfxC/8Vd4u
  3. soy yogurt: weak evidence; used by 1 same dish recipes without the target (11% of them vs 0% of those with it); good fit for the target's role
       similar recipes without it: fn:p174TykunvO./PLjDpl03RBTaXiOEdu
  4. olive oil: moderate evidence; used by 12 bread recipes without the target (14% of them vs 2% of those with it); partial fit for the target's role
       similar recipes without it: ar:06n7WTw6RQSDCfROjZZs5Zee/ciX.Hm, ar:LL5BIYQHdnkUgqMUBwZyKR0x7QrnXX., ar:Xb0UYfwuDfuuRXtjGsuVcjbGXbOJNsq
  5. evaporated milk: weak evidence; offered as an alternative to the target in 1 baked recipes; partial fit for the target's role
       direct: "Canned evaporated milk or egg white"  [epi:DiKM3xoQccTZ7paC.XGMVpHMD8gchRm]
  6. milk: weak evidence; offered as an alternative to the target in 1 baked recipes
       direct: "Beaten egg or milk, for brushing, optional"  [fn:JLC5AaIxURarKNvxDd2ne2JWekCS4oC]
  Compared 183 baked 'banana bread' recipes; only 9 lack eggs, so also 300 baked 'bread' recipes (83 without it); 9 of them have no eggs.
  Versions of this dish in the dataset made without eggs: Microwave Tofu Banana Bread [ar:5S4TJwjeeH.L/gDoUxUR0jfxC/8Vd4u]; Banana Oat Bread Pudding [ar:/tgLkKTWsLuZ95S0LSm4WrrYcwKFuMi]; Rich and Delicious Banana Bread [ar:TJFqS5qmSUVcBw7c2Da99BzhmvnbgCm]
  Instruction note: "Prepare cake mix as directed, except substitute egg whites for eggs and applesauce for oil."  [ar:d8ca8qxARHeOTiYcQFQlp229RTttkw.]
  'Direct' = a recipe offers the swap itself; comparative evidence is indirect (those recipes may differ in other ways too).

Expected trade-offs of removing eggs (predictions from its role, not dataset facts):
  - without the egg's binding, the bake may hold together less well and be more crumbly
  - without the egg's leavening, the bake may rise less and be denser
  - without the egg's moisture, the bake may be drier

Chosen substitute: applesauce (weak evidence), chosen by the strongest evidence (rule-based rewrite).

Adapted ingredients (* = changed):
    2 cups all-purpose flour
    1 teaspoon baking soda
    1/4 teaspoon salt
    1/2 cup butter
    3/4 cup brown sugar
  * applesauce (amount not given by the dataset)
    2 1/3 cups mashed overripe bananas

Adapted instructions:
  1. Preheat oven to 350 degrees F (175 degrees C). Lightly grease a 9x5 inch loaf pan.
  2. In a large bowl, combine flour, baking soda and salt. In a separate bowl, cream together butter and brown sugar. Stir in applesauce and mashed bananas until well blended. Stir banana mixture into flour mixture; stir just to moisten. Pour batter into prepared loaf pan.
  3. Bake in preheated oven for 60 to 65 minutes, until a toothpick inserted into center of the loaf comes out clean. Let bread cool in pan for 10 minutes, then turn out onto a wire rack.

Changes:
  - replaced '2 eggs, beaten' with applesauce (weak evidence: used by 1 same dish recipes without the target (11% of them vs 3% of those with it); good fit for the target's role)

Predicted effects (not verified by the dataset):
  - applesauce can take over the binding and moisture role(s)
  - applesauce does not provide leavening, so the result may rise less and be denser

Caution: the evidence for applesauce is weak; treat this adaptation as untested.
Note: a simple rule-based rewrite is shown because replacement line '2 cups mashed overripe bananas' must contain only the substitute (applesauce), one ingredient per line.
This is not a guarantee that the dish is safe for an allergy.
```
