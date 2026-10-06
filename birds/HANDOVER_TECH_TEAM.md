# Handover to the Tech team: turning BirdNET predictions into observations automatically

**Scope.** The SD-card upload and the BirdNET run already work. This document describes what has to happen after BirdNET writes its predictions so that every clip gets an `observation` label without a scientist touching it, and so that the thresholds behind those labels are versioned, auditable and refreshed when new validations arrive.

Everything below was prototyped in `01_fit_thresholds.py` and `02_label_predictions.py` on the sample data; the numbers in this document come from that run.

---

## 1. The logic in one paragraph

For each species, a small logistic regression relates "the ornithologist said the prediction was correct" (1/0) to the logit of BirdNET's confidence. Solving the fitted curve for a 0.99 probability gives the species' confidence threshold. A prediction at or above its species' threshold is an observation. Where a curve cannot be fitted because every validated clip was correct, the threshold is the lowest validated confidence, and the table records how much precision that evidence certifies. Where the curve reaches 0.99 only above every validated clip, the species gets no threshold and no observations until more clips are validated.

## 2. Tables

### 2.1 `birdnet_predictions` (exists; the ML pipeline writes it)

One row per clip per species. Columns used: `prediction_id`, `recording_file`, `begin_time_s`, `end_time_s`, `species_code`, `common_name`, `confidence`, `recorder_id`, `project_id`, `birdnet_version`, `birdnet_sensitivity`. If `birdnet_version` and `birdnet_sensitivity` are not stored today, please add them: thresholds are only valid for the model version and settings they were derived from.

### 2.2 `validation_results` (exists; written when an ornithologist reviews clips)

One row per reviewed clip: `validation_id`, `prediction_id` (foreign key into predictions; today the link is only through the filename, which matched 263 of 551 rows in the sample), `species_code`, `confidence`, `outcome` (1 correct, 0 wrong), `validator`, `validated_at`, `birdnet_version`.

### 2.3 `species_thresholds` (new; one row per species per fitting run)

| column | type | meaning |
|---|---|---|
| threshold_id | serial | primary key |
| project_id, site_id | fk | scope the threshold applies to (thresholds do not transfer between sites or seasons without re-validation) |
| species_code | text | BirdNET class |
| birdnet_version, birdnet_sensitivity | text, numeric | model and setting the validations were produced with |
| target_precision | numeric | 0.99 in the current spec |
| method | text | `logistic_curve`, `empirical_all_correct`, `none_unsupported`, `none_unreachable` |
| intercept, slope | numeric | fitted curve (null for empirical) |
| threshold_confidence | numeric | the cutoff on BirdNET's 0 to 1 scale; null when no threshold |
| ci95_low, ci95_high | numeric | bootstrap range |
| n_validated, n_correct | int | evidence behind the fit |
| n_validated_above, n_correct_above | int | clips at or above the threshold and how many were correct |
| precision_lower_bound_95 | numeric | exact binomial lower bound; the number to show auditors |
| fitted_at, fitted_by, validation_max_date | timestamp, text, date | provenance |
| is_current | bool | exactly one current row per (project, site, species, birdnet_version) |

### 2.4 `bird_observations` (new; a view, not a table)

Applying thresholds is a join plus a CASE, so it should be a view that is always consistent with the current thresholds:

```sql
CREATE VIEW bird_observations AS
SELECT p.*,
       t.threshold_confidence,
       CASE WHEN t.threshold_confidence IS NOT NULL
             AND p.confidence >= t.threshold_confidence THEN p.common_name END AS observation,
       CASE WHEN t.threshold_id IS NULL                    THEN 'no_threshold_for_species'
            WHEN p.confidence >= t.threshold_confidence     THEN 'at_or_above_threshold'
            ELSE                                                 'below_threshold' END AS label_reason
FROM birdnet_predictions p
LEFT JOIN species_thresholds t
       ON t.species_code    = p.species_code
      AND t.project_id      = p.project_id
      AND t.birdnet_version = p.birdnet_version
      AND t.is_current
      AND t.threshold_confidence IS NOT NULL;
```

If dashboards need a materialized table for speed, refresh it whenever `species_thresholds` changes.

## 3. The fitting job (Python 3.13, runs in the existing pipeline)

Inputs: all `validation_results` rows for one (project, site, birdnet_version). Steps, exactly as in `01_fit_thresholds.py`:

1. `conf = clip(confidence, 0.0001, 0.9999)`; `x = log(conf / (1 - conf))`.
2. Per species: `n`, `n_correct`.
   - If `n_correct == n`: `method = empirical_all_correct`, `threshold = min(confidence)`.
   - If `n_correct == 0`: `method = none_unreachable`, threshold null.
   - Otherwise fit `statsmodels.Logit(outcome, [1, x])`; if the optimizer does not converge, treat as `none_unreachable`. Solve `t = (logit(0.99) - b0) / b1`; `threshold = 1 / (1 + exp(-t))`; if `threshold > 0.9999` or `slope <= 0`, method `none_unreachable`.
3. Count validated clips at or above the threshold; if zero, `method = none_unsupported`, threshold null.
4. `precision_lower_bound_95 = scipy.stats.beta.ppf(0.05, k, n_above - k + 1)` (equals `0.05 ** (1 / n_above)` when all correct).
5. Bootstrap 1,000 resamples for `ci95_low/high` (skip resamples that fail; record how many succeeded).
6. Insert rows; set `is_current` on the new rows and clear it on the previous ones, inside one transaction.

Runtime is seconds; the job can run synchronously after each validation batch. Dependencies: pandas, numpy, scipy, statsmodels. The biometrics team can reproduce any row in R with `glm(outcome ~ logit_score, family = binomial)`; the coefficients are identical.

## 4. When to run it

| Trigger | Action |
|---|---|
| New validations committed for a species (suggest: at least 20 new clips, or any new clip for a species with fewer than 150) | refit that species |
| New BirdNET version or changed sensitivity/overlap settings | all existing thresholds become non-current for that version; new validations are required |
| New project or site | no thresholds inherited; validation campaign first (Wood and Kahl: thresholds are site and season specific) |
| Monthly | re-run as a check; alert if any species' threshold moves outside its previous CI |

## 5. Validation sampling the platform should support

The quality of every threshold depends on where the validated clips sit on the confidence axis. The platform should draw validation clips for the ornithologist, not leave it to hand selection:

- stratified across confidence bins (for example 10 bins of 0.1) with a floor per bin, plus an extra draw above 0.7, as Wood and Kahl recommend;
- a per-species target of about 300 clips with none wrong above the threshold if 0.99 is to be certified at 95 percent confidence (rule of three: 3/n); 150 clips certify about 0.98;
- store `prediction_id` with each validation so clips always link back to their prediction row.

## 6. Edge cases the code must handle (all seen in the sample)

| Case | Seen in | Handling |
|---|---|---|
| All validated clips correct (complete separation) | Oriole 150/150 | empirical threshold; lower bound reported, not 0.99 |
| One wrong clip decides the fit | Plover 149/150 | wide CI reported; flag for re-review of that clip |
| Threshold above all validated clips | Firefinch | no threshold; dashboard shows "needs high-confidence validation" |
| Confidence exactly 1.0 | predictions file | clip to 0.9999 before logit |
| Species present in predictions but with no validations | none here, common in production | `no_threshold_for_species`; never silently treated as observations |
| Same 3-second segment, two species | 3 segments | label each row independently |
| Validation clips not matching a prediction row | 288 of 551 | fit still valid; store `prediction_id` going forward |

## 7. Monitoring after launch

- Keep validating a small random sample of **observations** (say 20 per species per month). Observed precision should stay at or above the certified bound; if it falls below, re-fit.
- Show recall honestly: the Nightjar keeps 31 percent of its predictions, the Oriole 98 percent. If an analysis needs recall (vocal activity rates, density), a lower target or an aggregation rule (for example two or more observations in the same hour, as in Kelly et al. 2023) should be offered as a second view, not by lowering the observation threshold.
- Dashboard tiles: per species, the threshold, its CI, certified precision, number of validations, date of last refit, and the share of predictions kept.

## 8. Tests to ship with the job

- Unit: a synthetic validation set with known intercept and slope must return the known threshold within tolerance.
- Unit: all-correct input returns `empirical_all_correct` and `threshold = min(confidence)`; all-wrong input returns no threshold.
- Schema: confidence within [0, 1]; species codes in validations exist in predictions; no duplicate `prediction_id` per species; `outcome` only 0/1.
- Regression: the four species in the sample must reproduce the thresholds in `outputs/species_thresholds.csv` (0.667, 0.104, 0.259, none).

## 9. Decisions that need a scientist, not a developer

1. Keep 0.99 as the target, or report 0.95 and 0.99 side by side (Scanferla et al. 2025 found 0.99 unreliable at usual sample sizes).
2. Minimum validation sample before a species may have observations at all (suggest 100).
3. Whether to move to a single mixed model across species (Thompson et al. 2025) once the platform has 50 or more species with validations; it stabilizes species with few validations by borrowing strength from the rest, at the cost that each species' threshold then depends on the other species' data and must be audited as one model.
4. Whether thresholds are per site or per project area, and how often seasonal re-validation is required.
