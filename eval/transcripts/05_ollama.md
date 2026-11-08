# No eligible recipe (PDF Task 2)

Parser: ollama (qwen3:4b). Covers: no-match case, constraint never relaxed silently

**User:** I have tempeh and kimchi. Suggest recipes with at most one instruction step.

*parser: ollama (qwen3:4b), 12.0s; guard corrections: ['max_steps None -> 1']*

```text
Your ingredients (as understood): tempeh, kimchi
No eligible recipe found: none of the 75 recipes using your ingredients satisfies every constraint.

Closest alternatives. Each one BREAKS a constraint, as marked:

1. Tempeh Bacon  [ar:KyxzkaK.QVekCjgqTHjj0kl8HnKwphy]
   Why here: uses 1 of your 2 ingredients, needs 2 more, 3 steps
   Matched: tempeh
   Extra required: vegetable oil, tamari
   Not used from your list: kimchi
   (steps counted as sentences: instructions are one paragraph)
   VIOLATES: 3 steps (limit 1)

2. Mom's Kimchi Egg  [ar:jSKrHo7n0GCc5trqtQ57DarWpvVzlF2]
   Why here: uses 1 of your 2 ingredients, needs 2 more, 3 steps
   Matched: kimchi
   Extra required: vegetable oil, egg
   Not used from your list: tempeh
   (steps counted as sentences: instructions are one paragraph)
   VIOLATES: 3 steps (limit 1)

3. Caramelized Kimchi Relish  [epi:0vdS2vG8NHhGdmAfRVPwSV7J3Ez/v/.]
   Why here: uses 1 of your 2 ingredients, needs 2 more, 3 steps
   Matched: kimchi
   Extra required: sugar, cider vinegar
   Not used from your list: tempeh
   VIOLATES: 3 steps (limit 1)

Ranking rule: most of your ingredients used → fewest extra ingredients needed → fewest instruction steps → recipe ID.
Hard constraints applied before ranking: exact duplicates removed (same title and ingredient set); at most 1 steps
Note: No quantities were given, so this is a name-level match; whether you have enough of each ingredient was not verified.
Active constraints: at most 1 steps.
```
