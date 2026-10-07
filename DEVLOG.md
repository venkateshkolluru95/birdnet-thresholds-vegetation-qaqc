# Development log

## 1. Reading before coding

I read the task description twice, then both SOPs. I wrote down every number the SOPs commit to: a 50 m by 5 m transect, a midpoint within 25 m of the prescribed point, endpoints 25 m either side, a north-south layout unless rotated, 20 quadrats at 5 m spacing, GPS accuracy of 5 m or better, and species typed as `Genus_species`. Those numbers became the `SOP` dictionary in the checks.

I then read Wood and Kahl (2024) for the bird method. Three points mattered: scores are not probabilities, the logit scale should be used, and validation must cover the whole score range.

## 2. First look at the bird data

I printed the headers, counted the rows, and binned the validated clips by confidence. That one table split the four species into four different problems. The Nightjar has a clean step. The Oriole is correct everywhere. The Plover is correct everywhere but once. The Firefinch is almost always wrong.

Two more things stood out. Some confidence values are exactly 1.0, which has no finite logit. And only 263 of the 551 validated clips match a row in the predictions file, so they were drawn from a larger pool.

## 3. Method question: what if every validated clip is correct?

A logistic regression has no finite answer when the outcome is always 1. I checked what the BirdNET literature does before choosing. Scanferla et al. (2025) report the 0.99 target as unreachable for 16 of 72 species. Tseng et al. (2025) use a counting rule: the lowest confidence at which observed precision meets the target. Thompson et al. (2025) pool species in a mixed model.

Decision: Wood and Kahl's curve where it exists, the counting rule where it cannot, and the rule-of-three bound to state what the evidence certifies.

## 4. Bird code

The scripts gave Nightjar 0.667, Plover 0.259, Oriole 0.104 by the counting rule, and Firefinch no threshold. The Firefinch curve reaches 0.99 at 0.998, but no validated clip sits that high, so I added a rule: a threshold with no validated clip above it is not used.

## 5. First look at the vegetation data

I worked out the KEY / PARENT_KEY chain and which entity list each id points to. I read the two form definitions to understand the fixed 20-quadrat repeat and the placeholder logic. The mechanics were clean: 640 quadrats, every id resolves, every GPS reading within 5 m.

The problems were in the content. Plots 18 and 21 were submitted twice. Plot 23 was not viable and backup 46 was surveyed. The six shrubland primaries have no registration in the exports. Transects run 23 to 66 m and all bear eastward. Typed names use spaces and some are misspelled.

The species rows decided the design. The same field entity can carry two labels: its typed name when first created and its `herb_###` placeholder when reused. So species are counted on the entity UUID, not on the label. The identification list `species_extra_ids` keys on the placeholder number, so it is joined on that number and attached as a lookup.

## 6. Vegetation code

Four scripts: join, checks, report tables and maps, report assembly. Each rule is a few lines with the SOP sentence in its docstring. The SOP numbers sit in one dictionary and my own tolerances in another. Every issue row carries its population (retained, rejected, shared) and the exact record. Rules that find nothing are listed as pass.

Three findings came from the code rather than from reading. The form's end-of-survey species count differs from the rows in most submissions. Its calculation tests the list-species field at the wrong nesting level, so it only counts quadrats with additional species; this matches all 32 submissions exactly. Fourteen of 30 recorded midpoints lie more than 5 m off the straight A-B line, so quadrat distances are measured against the A-mid-B transect. And the quadrats of Plot 05 sit 13 to 27 m from the registered transect, which only became obvious on the zoomed map.

A fuzzy match of typed names against the project list found almost nothing, because the misspelled genera are not on the list. Typed names are matched against the GBIF backbone instead, with the result cached.
