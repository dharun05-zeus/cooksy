# Aggregate statistics (PDF Task 1)

Parser: ollama (qwen3:4b). Covers: aggregate statistics, stated filters and denominator

**User:** How many recipes contain both garlic and onion? What percentage of the dataset is that?

*parser: ollama (qwen3:4b), 6.7s*

```text
Answer: 15,657 of 122,910 recipes (12.74%).
Filters: contains 'garlic' (same ingredient or its varieties: garlic, garlic clove, cloves garlic, bulb garlic, unpeeled garlic clove, pureed garlic and 6 more); contains 'onion' (same ingredient or its varieties: onion, red onion, yellow onion, white onion, sweet onion, spanish onion and 15 more)
Recipes analyzed: 122,910
Method: numerator / denominator × 100, where the denominator is all complete recipes.
Example recipe IDs: ar:..6gl/0GIzSugrbvy6kHyxEHMMP4h9K, ar:..G2iuRLT7oseNmkKbjqAgbdB1G5IBC, ar:..M776r8BHroHcCXw3vInfs25LDkWw2, ar:..VDFobAHiAa0127h.N784Y2pnZyBZK, ar:./EObbt769KyfBTxJ.hIRe5275W4a9C
Note: Dataset: 122,910 complete recipes (title, ingredients and instructions present) out of 125,164 records; 2,254 incomplete records excluded (517 empty).
```

**User:** Among recipes containing tomato, which five have the fewest instruction steps?

*parser: ollama (qwen3:4b), 10.3s*

```text
Answer: Fewest instruction steps among 11,710 matching recipes.
Filters: contains 'tomato' (same ingredient or its varieties: tomato, plum tomato, cherry tomato, roma tomato, grape tomato, beefsteak tomato and 2 more)
Recipes analyzed: 11,710
Method: Step = one non-empty instruction line, excluding site boilerplate; a recipe stored as one paragraph is split into sentences. Sorted by steps, then ID.
  rank: 1 | recipe_id: ar:/0wx00RefE0VHzlff/GBszObKmj63Pi | title: Tomato Basil Smoothie | steps: 1 | counted_by: line
  rank: 2 | recipe_id: ar:3yxgq0iAqrlm2lHnLoxwJ8vQTHCd/Cm | title: Mediterranean Zucchini and Chickpea Salad | steps: 1 | counted_by: line
  rank: 3 | recipe_id: ar:5s.4S6mTsQWRNXHDFGWe6ea03Oac48C | title: Momma's Marinara Sauce | steps: 1 | counted_by: line
  rank: 4 | recipe_id: ar:9T2HkniyS.3VZB9NmFvzrfA39fMSt.. | title: Black Bean and White Corn Salad | steps: 1 | counted_by: line
  rank: 5 | recipe_id: ar:BqfGsVgk7WHPebuzDH3IIRDAo0Vy8Hy | title: Refreshing Mango Chutney | steps: 1 | counted_by: line
Note: Dataset: 122,910 complete recipes (title, ingredients and instructions present) out of 125,164 records; 2,254 incomplete records excluded (517 empty).
Note: 47 recipes have 1 step(s); the 5 shown are the first by recipe ID (deterministic tie-break).
```
