# Development log

## 1. Reading before coding

Read the task description twice and both SOPs, and wrote down every number the SOPs commit to: 50 m by 5 m transect, midpoint within 25 m of the prescribed point, endpoints 25 m either side, north-south layout unless rotated for obstacles, 20 quadrats at 5 m spacing, GPS accuracy 5 m or better, species typed as `Genus_species`. Those numbers became the `RULES` dictionary in the vegetation checks. Read Wood and Kahl (2024) for the bird method and noted the three things it insists on: scores are not probabilities, use the logit scale, validate across the whole score range.

## 2. First look at the bird data

Printed headers, counted rows, binned the validated clips by confidence and printed correct/checked per bin. That one table split the four species into four different problems: a clean step (Nightjar), all correct (Oriole), all correct but one (Plover), almost all wrong (Firefinch). Also noticed confidence values of exactly 1.0 (no finite logit) and that only 263 of 551 validated clips match a row in the predictions file (validated from a larger pool).

## 3. Method question: what if every validated clip is correct?

A logistic regression has no finite answer when the outcome is always 1 (complete separation). Checked what the BirdNET literature does before choosing: Scanferla et al. 2025 report the 0.99 target as unreliable and unreachable for 16 of 72 species; Tseng et al. 2025 use a model-free rule (lowest confidence with observed precision at or above the target); Thompson et al. 2025 pool species in a mixed model. Decision: Wood and Kahl's curve where it exists, the empirical rule where it cannot, and the rule-of-three bound to say what the evidence certifies.

