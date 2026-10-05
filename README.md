# BirdNET observation thresholds and vegetation survey QA/QC

## The two challenges

**Birds.** BirdNET scores every 3-second clip with a confidence between 0 and 1, but that number is not a probability and means different things for different species. An ornithologist has checked 551 clips. Following Wood and Kahl (2024), I will fit, per species, a logistic regression of "prediction was correct" on the logit of the confidence, solve the curve for a 0.99 probability, and label every prediction in `birdnet_predictions.csv` with a new `observation` field. Then a handover note for the Tech team describing how to run this automatically.

**Vegetation.** Herbaceous surveys of 20 quadrats per 50 m by 5 m belt transect, recorded in ODK. Four export tables and eleven entity lists need to be joined, checked against the two SOPs, and summarised in a data quality report (survey level, plot level, sampling effort, transect map). Errors are flagged, never fixed. Then a handover note describing an automated QA/QC dashboard.

## Plan

1. Read the task description, both SOPs and the Wood and Kahl paper; list every number the SOPs commit to.
2. Inspect every file before writing analysis code: row counts, keys, how the tables link, where the odd values are.
3. Birds: thresholds script, labeling script, report, handover.
4. Vegetation: join script, checks script, report script, data quality report, handover.
5. Every script carries a plain-language header and a comment on each line or block, stating what is computed and at what level (clip, species, quadrat, plot, survey).

[DEVLOG.md](DEVLOG.md) records the work as it happens.

## Data

The input files live under `data/raw/birds/` and `data/raw/vegetation/`. They belong to the project and are not committed. Derived outputs will be.

## Environment

Python 3.13; packages in `requirements.txt`.

```bash
pip install -r requirements.txt
```

