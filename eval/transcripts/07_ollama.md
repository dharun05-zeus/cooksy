# Unsupported attribute (PDF Task 1)

Parser: ollama (qwen3:4b). Covers: refusing to fabricate

**User:** Find banana bread.

*parser: ollama (qwen3:4b), 3.5s*

```text
12,305 recipes share at least one word with 'banana bread'. The 5 most relevant:

1. Banana Banana Bread  [ar:kq.naD.8G19M4UU9dVvJgHtpfo.l/eC]
   7 ingredients, 3 steps; matched: banana, bread

2. Healthier Banana Banana Bread  [ar:zPU0I27hBx09bNpfvQEjNTyHl/X7uwK]
   8 ingredients, 3 steps; matched: banana, bread

3. Country Banana Bread  [ar:LCKlIJX8Jjf51FQPJqTQGydT1/m4zRi]
   4 ingredients, 3 steps; matched: banana, bread

4. The Best Banana Bread  [ar:pW/G7uT3a0khPJWk/AzOieElj4cz2ku]
   6 ingredients, 3 steps; matched: banana, bread

5. Almond Butter and Finger Bananas on Fruit Bread  [epi:D2lLtfmm2Br05Jy8UDxsv3vJryjgEEG]
   3 ingredients, 2 steps; matched: banana, bread

Filters applied to the whole dataset: exact duplicates removed (same title and ingredient set)
Ask for 'the first one' (or any number) to see its full recipe.
```

**User:** How many calories are in the first one?

*parser: ollama (qwen3:4b), 8.9s; guard corrections: ['intent clarify -> stats']*

```text
The dataset does not record nutrition (calories, fat, protein, carbohydrates), so I cannot answer that without guessing. Each recipe has only a title, an ingredient list and instructions; I can show those, or answer questions about them.
```
