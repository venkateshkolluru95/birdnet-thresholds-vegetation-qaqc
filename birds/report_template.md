# Bird challenge: from BirdNET predictions to observations

**Question asked.** BirdNET scores every 3-second clip with a confidence between 0 and 1 for a species. An ornithologist checked a sample of clips. Using a 99 percent probability-of-correctness cutoff, assign every clip in `birdnet_predictions.csv` a label in a new `observation` field.

**Short answer.** Two species get a threshold from the fitted curve: Abyssinian Nightjar {{m:nj_thr}} and Three-banded Plover {{m:pl_thr}}. The African Black-headed Oriole cannot have a curve, because every checked clip was correct, and gets an evidence-based threshold of {{m:or_thr}} instead. The Red-billed Firefinch gets no threshold, because the curve only reaches 99 percent above every clip that was ever checked. Applying these rules, {{m:n_obs}} of {{m:n_pred}} predictions become observations: {{m:n_obs_curve}} through a fitted curve and {{m:n_obs_empirical}} through the Oriole's counting rule. Each labeled row records which rule produced it. The labeled file is `outputs/birdnet_predictions_labeled.csv`.

Code: [`01_fit_thresholds.py`](01_fit_thresholds.py) (thresholds), [`02_label_predictions.py`](02_label_predictions.py) (labels and summaries) and [`03_assemble_report.py`](03_assemble_report.py) (fills every number in this report from the outputs). Every line is commented for a reader who does not code.

---

## 1. What the data contain

| File | Rows | What a row is |
|---|---|---|
| `birdnet_predictions.csv` | {{m:n_pred}} | One 3-second clip where BirdNET proposed one of four species, with its confidence. {{m:n_recorders}} recorders ({{m:rec_first}} to {{m:rec_last}} with gaps, all in Grid2), {{m:date_first}} to {{m:date_last}}, confidence {{m:conf_min}} to {{m:conf_max}}. |
| `validation_results.csv` | {{m:n_val}} | One clip an ornithologist listened to, with `outcome` = 1 (BirdNET correct) or 0 (wrong). BirdNET {{m:birdnet_version}} throughout. |

Validated clips per species, and how often BirdNET was right in each confidence band:

{{bands}}

Three things I noticed before fitting anything:

1. The validated clips cover the whole confidence range while the predictions pile up at low confidence (median confidence {{m:median_min}} to {{m:median_max}} by species). The coverage is uneven: {{m:ff_below02}} of the {{m:ff_n}} Firefinch clips sit below 0.2, and {{m:nj_above09}} of the {{m:nj_n}} Nightjar clips sit at or above 0.9. How the clips were chosen is not recorded. The curves therefore describe "how often BirdNET is right at a given confidence", not "how often it is right overall".
2. Only {{m:val_matched}} of the {{m:n_val}} validated clips carry a recording name, species and confidence that also appear in the predictions file. The other {{m:val_unmatched}} have recording times that are not on the hour, while every prediction file name is, so they cannot be matched by name. The files do not say why; it may be a naming offset or a larger pool of predictions. The thresholds are learned from the validated clips and applied to the file, which assumes both came from the same BirdNET version and settings. The predictions file does not record its version.
3. {{m:val_at_one}} validated clips ({{m:val_at_one_species}} only) and {{m:pred_at_one}} predictions carry a confidence of exactly 1.0. The logit transform, ln(c / (1 - c)), is infinite at 1.0. For the fit I clip confidences to the range 0.0001 to 0.9999 before transforming. Scanferla et al. (2025) dropped such clips instead; clipping keeps them in the fit. Predictions are compared with the threshold on the raw confidence scale, so they are never transformed.

## 2. Method

The method follows Wood and Kahl (2024). For each species:

1. Convert each validated clip's confidence to the logit scale. The logit spreads out the scores that pile up near 1, which makes the curve fit better; it does not change the logic.
2. Fit a logistic regression of `outcome` (1 or 0) on the logit confidence. This finds the S-shaped curve that agrees best with the yes/no marks (maximum likelihood); its height at any confidence is the estimated probability that a prediction at that confidence is correct. This is `glm(outcome ~ logit_score, family = binomial)` in R and `statsmodels.Logit` in Python; both maximise the same likelihood and agree to the solver's tolerance.
3. Solve the curve for the confidence at which the probability is 0.99: threshold = inverse-logit((logit(0.99) - intercept) / slope).
4. Put an uncertainty range on the threshold by refitting on 1,000 bootstrap resamples of the validated clips. A resample with no wrong clip has no curve, so the range is computed over the resamples that could be fitted, and that number is reported with it.
5. Count how many validated clips sit at or above the threshold and how many of those were correct, and compute the exact binomial 95 percent lower bound on that precision. This is the plain-counting evidence behind each threshold. It describes the validated clips, which were selected by the threshold itself and often share a recording, so it is a lower bound on what was checked, not a guarantee for every prediction.
6. Label: a prediction is an observation if its confidence is at or above its species' threshold.

Two situations the standard method cannot handle, and the rule I applied to each:

- **Every validated clip is correct (complete separation).** The S-curve needs some wrong clips on the left to know where the step is. With none, the fit keeps improving as the curve is pushed higher, there is no finite best curve, and the software reports non-convergence (Albert and Anderson 1984). Rather than force a curve, I use a counting rule, in the spirit of Tseng et al. (2025) who set thresholds from the observed precision of validated clips: the threshold is the lowest confidence that was validated, since every validated clip at or above it was correct. I then state how much precision that evidence supports (see Section 3). Firth-penalized regression or a Bayesian prior on the slope (Heinze and Schemper 2002; Gelman et al. 2008) would return finite coefficients by penalising very steep curves, and either can be attempted if a curve-based threshold is required for such species. The caveat is that the result then depends on the penalty as well as on the data, so the threshold it yields is an assumption rather than evidence of 99 percent precision. I did not find either method used for BirdNET thresholds in the papers I read.
- **The curve reaches 0.99 only above every validated clip.** A threshold with zero validated clips at or above it is an extrapolation of the curve, not evidence. I do not use such a threshold to create observations. Scanferla et al. (2025) met the related case, a fitted threshold above the maximum confidence of 1, for 16 of 72 species, mostly where BirdNET made errors across the whole range.

## 3. Results: one threshold per species

![Fitted curves](figures/fig1_precision_curves.png)

| Species | Validated (correct) | How the threshold was set | Threshold | Bootstrap 95% range (resamples fitted, of 1,000) | Validated clips at or above (correct) | 95% lower bound on precision among those clips |
|---|---|---|---|---|---|---|
| Abyssinian Nightjar | {{m:nj_n}} ({{m:nj_correct}}) | logistic curve (intercept {{m:nj_b0}}, slope {{m:nj_b1}}) | **{{m:nj_thr}}** | {{m:nj_lo}} to {{m:nj_hi}} ({{m:nj_fits}}) | {{m:nj_above}} ({{m:nj_correct_above}}) | at least {{m:nj_bound}} |
| African Black-headed Oriole | {{m:or_n}} ({{m:or_correct}}) | all clips correct; lowest validated confidence | **{{m:or_thr}}** | not applicable | {{m:or_above}} ({{m:or_correct_above}}) | at least {{m:or_bound}} |
| Three-banded Plover | {{m:pl_n}} ({{m:pl_correct}}) | logistic curve (intercept {{m:pl_b0}}, slope {{m:pl_b1}}) | **{{m:pl_thr}}** | {{m:pl_lo}} to {{m:pl_hi}} ({{m:pl_fits}}) | {{m:pl_above}} ({{m:pl_correct_above}}) | at least {{m:pl_bound}} |
| Red-billed Firefinch | {{m:ff_n}} ({{m:ff_correct}}) | curve reaches 0.99 only at {{m:ff_crossing}}, above every validated clip | **{{m:ff_thr}}** | {{m:ff_lo}} to {{m:ff_hi}} ({{m:ff_fits}}), for the unused crossing | {{m:ff_above}} ({{m:ff_correct_above}}) | {{m:ff_bound}} |

How to read each row:

- **Nightjar** is the clearest case. Every wrong clip sits below {{m:nj_max_wrong_ceiling}} (the highest is {{m:nj_max_wrong}}) and the curve climbs through 0.99 at {{m:nj_thr}}. The bootstrap range is wide ({{m:nj_lo2}} to {{m:nj_hi2}}) because only {{m:nj_in_bend}} clips were validated between 0.3 and 0.6, exactly where the curve bends. Validating more clips in that band is the first thing to do; whether the range narrows depends on what they show.
- **Oriole** is the species BirdNET gets right at every score we have evidence for, down to 0.10. A curve cannot be fitted; the evidence says "no errors in {{m:or_n}} clips". With zero errors in n clips the 95 percent upper bound on the error rate is about 3/n (the rule of three, Hanley and Lippman-Hand 1983), so {{m:or_n}} clips support precision of at least {{m:or_bound2}}, not 0.99. Supporting 0.99 this way would need {{m:n_for_99}} validated clips with no errors, drawn afresh from above the threshold. I apply {{m:or_thr}} as the threshold because that is what the data support, and I label the table accordingly rather than claiming 0.99. These {{m:or_obs}} observations rest on a counting rule, not on a fitted 0.99 curve, and the labeled file says so in its `threshold_method` column.
- **Plover** has a single wrong clip, at confidence {{m:pl_wrong_conf}}, and that one clip decides the curve. The fitted threshold ({{m:pl_thr}}) sits just below it, which is why the bootstrap range is so wide ({{m:pl_lo2}} to {{m:pl_hi2}}), why {{m:pl_fails}} of the 1,000 resamples had no wrong clip and no curve, and why {{m:pl_wrong}} of the {{m:pl_above}} validated clips above the threshold is wrong. Re-checking that one clip is the first thing to do. If it turns out to be correct, the Plover becomes an all-correct case like the Oriole and gets a counting-rule threshold.
- **Firefinch** is the opposite case. Only {{m:ff_correct}} of {{m:ff_n}} validated clips were correct and only one of those had a high score. The curve technically reaches 0.99 at confidence {{m:ff_crossing}}, but no validated clip sits that high, so there is no evidence at that score. No Firefinch prediction is labeled as an observation. If Firefinch matters to the project, the fix is to validate its high-confidence clips specifically (there are only {{m:ff_pred_above05}} predictions above 0.5 in this dataset) or to accept a lower precision target for this species.

**The main limitation, which applies to every species:** with 150 validated clips, none of the four thresholds can be shown to reach 99 percent precision with 95 percent confidence. The best is the {{m:best_bound_species}} at {{m:best_bound}}. The 0.99 target is at the edge of what 150 clips can prove; Scanferla et al. (2025) reached the same conclusion and recommend 0.90 or 0.95 as targets that the usual sample sizes can support. I kept 0.99 because that is what the specification asks for, and I report the lower bound next to it so nobody mistakes one for the other.

## 4. Results: the labeled predictions

![Predictions versus observations](figures/fig2_predictions_vs_observations.png)

{{results}}

The output file keeps every original column, in the original row order, with the same {{m:n_pred}} rows (the script checks this), and adds {{m:n_cols_added}} columns:

- `threshold_confidence` and `threshold_method`: the cutoff applied to the row and how it was set (fitted curve, or the counting rule for the Oriole), so a reader can see which rule produced each observation.
- `observation`: the species common name when the clip passes its species threshold, otherwise empty.
- `label_reason`: `at_or_above_threshold` ({{m:n_obs}} clips), `below_threshold` ({{m:n_below}}) or `no_threshold_for_species` ({{m:n_no_thr}}, all {{m:no_thr_species}}). A fourth value, `invalid_input`, is reserved for rows with a missing species or a confidence outside 0 to 1; {{m:n_invalid}} rows carry it in this file. An empty `observation` is therefore never ambiguous, and it never means the species was absent: it means the prediction was not accepted.

"Share kept" is not recall. The validation set contains only clips that BirdNET flagged, so it says nothing about calls BirdNET missed; precision and recall have different denominators (Knight et al. 2017). The Nightjar keeps {{m:nj_share}} percent of its predictions, which is a statement about how many predictions survive the cutoff, not about how many Nightjar calls were detected.

Per-recorder counts for all {{m:n_recorders}} recorders and all four species, including zeros, are in `outputs/summary_by_recorder.csv`. {{m:n_rec_zero}} recorders have no observation of any species; that is a statement about accepted predictions, not about absence. {{m:n_double_segments}} segments of 3 seconds carry predictions for two different species at once; both rows are labeled independently, which is correct because two birds can call in the same 3 seconds.

## 5. Decisions made along the way

| Decision | Choice | Why |
|---|---|---|
| x-axis of the regression | logit of confidence | Wood and Kahl recommend it; the raw 0 to 1 scale compresses the high scores. The threshold is converted back to confidence for use. |
| Confidence of exactly 1.0 | clipped to 0.9999 before the logit, in the validation table only | logit(1) is infinite; dropping the {{m:val_at_one}} clips would waste evidence. Predictions are compared on the raw scale and are not transformed. |
| BirdNET sensitivity setting | assumed default (1.0) | BirdNET's sensitivity setting (0.5 to 1.5) controls how sharply the raw score is squashed into the 0 to 1 confidence, and Wood and Kahl's logit formula divides by it. The setting used was not supplied. Dividing every x by a constant only rescales the slope; the threshold is unchanged once converted back to the confidence scale. This holds as long as the validated clips and the predictions were produced with the same setting, which the files do not record. |
| Species with all validations correct | lowest validated confidence, with the precision lower bound stated and the rule recorded in `threshold_method` | A curve does not exist; forcing one with penalties makes the result depend on the penalty. The counting rule follows the logic of Tseng et al. (2025). The stricter alternative, assigning no Oriole observations until 0.99 is shown, was considered and rejected: it would discard 150 of 150 correct validations, and by the same standard no species in this dataset qualifies, since even the Nightjar's {{m:nj_above}} clips above its threshold support only {{m:nj_bound2}}. The sample size, not the method, is what limits the bound, and the report says so. |
| Threshold above every validated clip | not used | An extrapolated threshold has no evidence behind it. |
| Precision target | 0.99 as specified | Reported alongside the lower bound from the validated clips so the two are not confused. |
| Uncertainty | 1,000 bootstrap resamples | The threshold is a ratio of two fitted coefficients. A formula for its standard error exists (the delta method), but resampling the validated clips needs no formula, shows which thresholds rest on few clips, and reports how many resamples had no curve at all. Clips from the same recording are resampled as if independent, so the ranges may be too narrow. |

## 6. What I would do next with the same data

- Validate more Nightjar clips between 0.3 and 0.6, and have the single wrong Plover clip re-checked. Both address the thresholds' weakest evidence more directly than any change of method.
- Validate Firefinch clips above 0.5 specifically, since the current sample has almost none.
- Decide with the biometrics team whether 0.99 is the right target given sample sizes, or whether 0.95 with a documented bound is more useful for the Pillar Metrics.
- At platform scale, with hundreds of species, fit one mixed model with species as a grouping factor (Thompson et al. 2025) so species with few validations borrow strength from the others. This is described in the handover document.

## References

- Wood CM, Kahl S (2024). Guidelines for appropriate use of BirdNET scores and other detector outputs. Journal of Ornithology 165: 777-782.
- Tseng S, Hodder DP, Otter KA (2025). Setting BirdNET confidence thresholds: species-specific vs. universal approaches. Journal of Ornithology. doi:10.1007/s10336-025-02260-w.
- Scanferla J, Brambilla M, et al. (2025). Determining species-specific thresholds to improve precision in passive acoustic monitoring. Ecological Informatics 91: 103423.
- Thompson MC, Ducey MJ, Gunn JS, Rowe RJ (2025). A post-processing framework for assessing BirdNET identification accuracy and community composition. Ibis 167: 530-542.
- Albert A, Anderson JA (1984). On the existence of maximum likelihood estimates in logistic regression models. Biometrika 71: 1-10.
- Heinze G, Schemper M (2002). A solution to the problem of separation in logistic regression. Statistics in Medicine 21: 2409-2419.
- Gelman A, Jakulin A, Pittau MG, Su Y-S (2008). A weakly informative default prior distribution for logistic and other regression models. Annals of Applied Statistics 2: 1360-1383.
- Hanley JA, Lippman-Hand A (1983). If nothing goes wrong, is everything all right? Interpreting zero numerators. JAMA 249: 1743-1745.
- Knight EC, Hannah KC, Foley GJ, Scott CD, Brigham RM, Bayne E (2017). Recommendations for acoustic recognizer performance assessment with application to five common automated signal recognition programs. Avian Conservation and Ecology 12(2): 14.
