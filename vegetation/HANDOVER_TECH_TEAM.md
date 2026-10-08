# Handover to the Tech team: an automated Vegetation QA/QC dashboard

**Scope.** ODK submissions already land on the platform as raw tables. This document describes what runs after that: the joins, the rules, where the flags are stored, and what the dashboard shows. Everything was prototyped in `01_load_and_join.py` to `04_assemble_report.py` on the SAVMON LW baseline. The rule ids are the ones in `outputs/qa_summary.csv`.

Two principles to keep. **Flag, never fix**: the pipeline writes issues next to the data, people resolve them in the source, and the pipeline re-runs. **Keep three layers apart for species**: what was recorded, which entity it is, and what a reviewer later decided it is.

---

## 1. Source tables and how they join

ODK exports one table per form plus one per repeat group, linked by `KEY` / `PARENT_KEY`. Entity lists are lookup tables keyed by `__id`. Two columns are both called `plot_selection-selected_plot_uuid` and point to different lists. The registration form selects from `centroids`, the survey form from `vegplots`, and `vegplots.plot_uuid` links the two.

```
register_vegetation_plots  (1 row per registration)  -- selected_plot_uuid -> centroids.__id
herbaceous_veg_survey      (1 row per survey)        -- selected_plot_uuid -> vegplots.__id -> vegplots.plot_uuid -> centroids.__id
  └ quadrat_repeat          (20 rows per survey)      -- PARENT_KEY -> survey.KEY
      └ additional_species_repeat (0..n per quadrat)  -- PARENT_KEY -> quadrat.KEY
                                                       -- target_extra_name / select_reuse_* -> species_extra.__id
quadrat_repeat.herb_species-selected_herb_species_uuids  -- space-separated list of species.__id (explode to rows)
species_extra (group_type, unknown_index) -> species_extra_ids.species_number  (the identification supplied later; join on the number, never on the label)
```

Recommended normalized tables on the platform (PostgreSQL). Primary keys are UUIDs, never display names.

| table | grain | key columns |
|---|---|---|
| `veg_survey` | one submission | submission_key (pk), plot_entity_id (fk vegplots), survey_entity_id (fk surveys), replicate, recorder, start_utc, end_utc, device_utc_offset, submission_utc, review_state, population (retained/rejected), form_version, device_id, active_placeholders_at_start |
| `veg_quadrat` | one quadrat | quadrat_key (pk), submission_key (fk), quadrat_number, herbs_present, all_unknown_unidentifiable, geom (PostGIS point, SRID 4326), gps_accuracy_m, image, comment |
| `veg_species_record` | one entry in one quadrat | record_key (pk: the additional row's KEY, or quadrat_key + species id), quadrat_key (fk), source (project_list / additional_species), entry_mode, entity_id, identity_key (source + entity_id), label_raw (never edited) |
| `species_identification` | one field entity | identity_key (pk), entity_label, species_number, supplied_name, supplied_note, entity_review_status, effective_date, approved_taxon_id (null until a reviewer decides), duplicate_of (null until decided), eligible (null until decided) |
| `veg_plot` | one registration | registration_key (pk), plot_entity_id (fk vegplots), centroid_entity_id (fk centroids), is_viable, stratum, sample_status, context fields (ecosystem, canopy structure and height, soil, water, ground cover, disturbance, dominant woody), geom_a, geom_mid, geom_b, transect (A-mid-B linestring), straight_ab_m, polyline_m, midpoint_off_line_m, midpoint_offset_m, bearing_deg |
| `design_centroid` | one prescribed point | centroid_id (pk), plot_name, stratum, sample_status, design_year, geom, replacement_of (null unless recorded) |
| `veg_qa_issue` | one flagged item | issue_id (pk), run_id, rule_id, rule_version, config_version, severity, level, population, item_key (source record uuid), rule_variant (for example the endpoint in P04), plot_name, detail, first_seen, last_seen, resolved_at |
| `veg_qa_run` | one execution of one rule | run_id, rule_id, status (pass / findings / not_applicable / not_run / failed_execution), n_evaluated, n_flagged, started_at |

Three transforms are not plain joins: the explode of the space-separated species list, the three-way `coalesce` for the additional-species label and id, and the `species_number` join to the identification list. All are in `01_load_and_join.py` with comments. Validate joins before aggregating: key uniqueness, orphans, unresolved ids, and a row-count check after each step. The script asserts 2,243 = 947 list ids + 1,296 additional rows.

## 2. The species identity model

One field entity can be recorded under two labels: its typed name and its `herb_###` placeholder. In this baseline 22 of 104 entities were. One typed name can also be created twice as two entities, which happened twice. So:

- **Richness, diversity and accumulation are computed on `identity_key`** (source list + entity UUID). Label counts are kept beside them as a diagnostic, never as the result.
- **`species_extra_ids` is joined on `species_number`** (herb_016, wood_003), which is unique; its labels are not. The supplied name is attached as a dated lookup; the recorded label is never overwritten. A supplied name is not an approval: `entity_review_status` is still pending for all 104 herb entities.
- **Reviewer decisions get their own columns** (`approved_taxon_id`, `duplicate_of`, `eligible`, `effective_date`) and a history. The supplied notes ("duplicate of herb_011", "woody but below 40 cm, exclude") are queued for that decision, not applied.
- When an approved mapping changes, every metric that depends on identities (richness, Shannon, accumulation) is recomputed for the affected plots.

## 3. The rules

Each rule is a few lines in one of five functions, one per level. They read the normalized tables and append rows to `veg_qa_issue`. Thresholds live in two dictionaries. `SOP` holds the numbers the SOPs state: 20 quadrats, 5 m GPS, 25 m midpoint limit, 50 m transect, 25 m half-lengths and the `Genus_species` pattern. `CONFIG` holds the tolerances the SOPs do not give: the 45 to 55 and 40 to 60 m bands, 7.5 m half-length tolerance, 15 m midpoint warning, 20 degrees orientation, 10 and 25 m quadrat distance, and 30 to 180 minutes of survey duration. `CONFIG` values are for the biometrics team to confirm.

| id | level | rule | severity | this baseline (retained / all exports) |
|---|---|---|---|---|
| S01 | survey | same plot submitted more than once for the same survey | error unless resolved by review state | 2 / 4 (info) |
| S02 | survey | submission rejected in ODK Central, excluded from summaries | info | 0 / 2 |
| S03 | survey | quadrat count not 20 or numbers not 1 to 20 once each (SOP) | error | pass |
| S04 | survey | form's end-of-survey species count differs from a recount of rows | warning | 22 / 23 |
| S05 | survey | form-open time outside 30 to 180 minutes (CONFIG) | warning | 1 / 3 |
| S06 | survey | zero active placeholders at start: expected on the campaign's first survey (info), freshness check on a later one (warning) | info / warning | 1 / 1 |
| P01 | plot | registered as not viable (reason recorded) | info | 1 |
| P02 | plot | midpoint more than 25 m from prescribed point (SOP); 15 to 25 m is a warning inside the limit | error / warning | 6 (1 error) |
| P03 | plot | straight A-B distance outside 45 to 55 m (warning) or 40 to 60 m (error) | error / warning | 16 (6 errors) |
| P04 | plot | endpoint not about 25 m from the midpoint (warning, one row per endpoint); recorded midpoint more than 5 m off the straight A-B line (info) | warning / info | 18 + 14 |
| P05 | plot | transect more than 20 degrees off north-south and no rotation reason recorded | info | 30 |
| P06 | plot | backup plot surveyed (replacement link not recorded) | info | 1 |
| P07 | design | prescribed primary plots with no registration in the exports, by stratum | error if whole stratum | 1 (shrubland, 6 plots) |
| Q01 | quadrat | geopoint, accuracy or photo missing; GPS accuracy worse than 5 m | error / warning | pass |
| Q02 | quadrat | more than 10 m (warning) or 25 m (error) from the registered A-mid-B transect, the geometry the map draws | warning / error | 142 / 147 (13 errors) |
| Q03 | quadrat | no herbaceous species present | info | 7 |
| Q04 | quadrat | "additional species" answer disagrees with the rows beneath it | warning | 9 / 10 |
| Q05 | quadrat | same identity entered twice in a quadrat (by entity id, so an alias pair counts as the same identity) | warning | 6 / 7 |
| Q06 | quadrat | form species count differs from number of ids | error | pass |
| Q07 | quadrat | additional-species row with nothing chosen (keyed by the row's own KEY) | warning | 1 |
| X01 | species | typed name not in `Genus_species` format (SOP; the form's hint shows a space) | warning | 43 |
| X02 | species | typed name already on the project species list | warning | 1 |
| X03 | species | typed name not an exact GBIF backbone match (fuzzy = warning, higher rank = info, lookup failed = warning and retried next run) | warning / info | 10 + 3 |
| X04 | species | same entity recorded under two labels | warning | 22 |

Every rule writes a run row even when it finds nothing. The summary then shows pass, findings, not applicable, not run or failed execution. A rule that crashed must never look like a pass.

Checks that are cheap in SQL (S01 to S06, Q03 to Q07, X01, X02, X04) can be views. The geometry rules (P02 to P05, Q02) are PostGIS queries on the geography type: `ST_Distance`, `ST_Length`, `ST_Azimuth`, `ST_ClosestPoint`, with the method and SRID recorded. X03 is one HTTP call per new typed name to `https://api.gbif.org/v1/species/match`. It runs outside the row-level transaction, is cached on success and retried on failure.

## 4. When it runs, and what re-runs

- On every new or edited submission, or a review-state change: re-run the survey and quadrat rules for that submission. Upsert into `veg_qa_issue` on (rule_id, item_key, rule_variant), set `resolved_at` on issues that no longer fire, and write the run rows.
- On a registration or design-centroid change: re-run P02 to P05 for that plot and Q02 for every quadrat of that plot.
- On an entity-list change (species, species_extra, species_extra_ids, vegplots, centroids): re-run the X rules and P07.
- On an approved identification change: recompute richness, Shannon and accumulation for the affected plots.
- Nightly: full re-run and the design-coverage rule, so nothing drifts.

## 5. The dashboard (Vegetation QA/QC)

One page per project area and replicate, in uKweli's existing React stack:

1. **Status strip.** Submissions received, rejected, retained; quadrats; open issues by severity for the retained population; rules passing, with findings, not run; last run time.
2. **Design coverage.** The stratum-by-status table and a map of prescribed points by status: surveyed, backup surveyed, not viable, registered not surveyed, primary without registration, unused backup. The registered A-mid-B transects and the quadrat points are toggles; `figures/map_transects.png` is the wireframe. Click a plot to see its registration photos, context, geometry measures and open issues.
3. **Survey table.** One row per retained submission: device clock, duration, upload delay, recorder, quadrats with herbs, identities (named and unknown), and issues on the submission and on its quadrats. Each row links to the issue list.
4. **Issue queue.** Filterable by rule, severity, population, plot, and open or resolved. Each row links to the ODK Central submission so a data manager corrects the source. Issues are never edited in the dashboard.
5. **Species review queue.** Aliases (X04), the supplied notes from the identification list, typed names with their GBIF suggestion (X03), names already on the list (X02), and identities still Unknown with their quadrat photos. Decisions are recorded in `species_identification` with a date and a reviewer. The dashboard shows what is pending.
6. **Effort panel.** The timeline on the device clock with the offset stated, person-hours and the accumulation curves. This lets the biometrics team judge the design before computing Pillar Metrics.

## 6. What the baseline taught us that should change upstream

- **Recompute every summary from rows.** The form's `quadrats_with_species` tests the list-species field at the wrong nesting level and only counts quadrats with additional species. It is wrong in 22 of 30 retained submissions. Fix the XPath in the next form version and never trust an in-form calculate.
- **Make the reuse selectors required** when their branch is active, and require a completed child row when "additional species present" is yes. One blank row and nine yes-without-rows cases came from these gaps.
- **Agree the canonical name convention** between the SOP (`Genus_species`) and the form, whose hint shows a space. Then enforce it with a constraint, keep the raw text and derive the normalized form.
- **Record the rotation reason** when a transect is not north-south, or change the SOP if eastward layout is the practice.
- **Compare quadrat geopoints with the registered transect at upload.** Alert the team the same day if they disagree by more than 25 m, while they can still check on site.
- **Set and record the device time zone**; the devices applied +02:00 in a +03:00 project.
- **Record replacements**, that is which backup replaced which primary, and the design year for every prescribed point. 19 of 51 years are blank.

## 7. Tests to ship

- Join integrity: every quadrat has a parent survey and every additional row a parent quadrat. Every selected species id resolves in `species`, every entity id in `species_extra`, and every `species_number` once in `species_extra_ids`. Row counts reconcile at each step.
- One synthetic failing row per rule. Add one case each for: an entity under two labels, a blank reuse row, a yes-without-child quadrat, two P04 findings on one plot (both must survive the upsert), a rejected submission (must stay out of retained counts), a midpoint off the A-B line, and an identification update that changes a plot's richness.
- Regression: the SAVMON LW baseline must reproduce `outputs/qa_summary.csv` (357 retained rows, 21 errors) and `outputs/metrics.json`. When a rule changes, the expected file is re-versioned, not forced.
- Geometry sanity: a known 50 m line measures 50 m after the UTM 37N transformation; the polyline and straight-line distances agree for a straight transect.
