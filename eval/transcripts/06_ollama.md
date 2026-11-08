# Substitution with weak or conflicting evidence (PDF Task 3)

Parser: ollama (qwen3:4b). Covers: weak or conflicting evidence, declining to guess

**User:** Take this banana bread recipe and remove eggs. Use only ingredients that appear in the dataset.

*parser: ollama (qwen3:4b), 41.9s*

```text
Using 'Banana Banana Bread' [ar:kq.naD.8G19M4UU9dVvJgHtpfo.l/eC], the top match for 'banana bread' that contains eggs.
Adapting: Banana Banana Bread  [ar:kq.naD.8G19M4UU9dVvJgHtpfo.l/eC]
Replacing: 2 eggs, beaten
Role of egg in this baked dish: binding, leavening, moisture (general cooking knowledge)
Restrictions respected: no eggs

Local evidence from the dataset:
  1. olive oil: moderate evidence; used by 12 bread recipes without the target (14% of them vs 2% of those with it); partial fit for the target's role
       similar recipes without it: ar:06n7WTw6RQSDCfROjZZs5Zee/ciX.Hm, ar:LL5BIYQHdnkUgqMUBwZyKR0x7QrnXX., ar:Xb0UYfwuDfuuRXtjGsuVcjbGXbOJNsq
  2. evaporated milk: weak evidence; offered as an alternative to the target in 1 baked recipes; partial fit for the target's role
       direct: "Canned evaporated milk or egg white"  [epi:DiKM3xoQccTZ7paC.XGMVpHMD8gchRm]
  3. milk: weak evidence; offered as an alternative to the target in 1 baked recipes
       direct: "Beaten egg or milk, for brushing, optional"  [fn:JLC5AaIxURarKNvxDd2ne2JWekCS4oC]
  4. egg substitute: conflicting evidence; offered as an alternative to the target in 4 baked recipes; good fit for the target's role; may contain eggs (uncertain)
       direct: "2 large eggs or 1/2 cup egg substitute"  [epi:cTG4e2s8RON5swgZSMmn6Omhx7Q9MGi]
       direct: "1/4 cup egg substitute or 2 large egg whites"  [epi:LSm1hzr0Vqt1sNp2f5ml93JmmG7Qm2C]
  Compared 183 baked 'banana bread' recipes; only 9 lack eggs, so also 300 baked 'bread' recipes (83 without it); 9 of them have no eggs.
  Versions of this dish in the dataset made without eggs: Microwave Tofu Banana Bread [ar:5S4TJwjeeH.L/gDoUxUR0jfxC/8Vd4u]; Banana Oat Bread Pudding [ar:/tgLkKTWsLuZ95S0LSm4WrrYcwKFuMi]; Rich and Delicious Banana Bread [ar:TJFqS5qmSUVcBw7c2Da99BzhmvnbgCm]
  Instruction note: "Note: If desired, 1 whole egg may be substituted for the 2 egg yolks to make 2 3/4 cups frosting."  [ar:l9irZcqyQrcp645oqrGM/oZwnLN2COW]
  Instruction note: "Prepare cake mix as directed, except substitute egg whites for eggs and applesauce for oil."  [ar:d8ca8qxARHeOTiYcQFQlp229RTttkw.]
  Instruction note: "In a separate bowl combine the egg replacer and water (2 eggs' worth) and mix in sour cream substitute and vanilla."  [ar:/BG0.sjOLhOu1XAuh8Wq0XSUVZIqsXK]
  'Direct' = a recipe offers the swap itself; comparative evidence is indirect (those recipes may differ in other ways too).

None of the evidenced candidates fits this ingredient's role well enough, so I am not proposing an adaptation.
```
