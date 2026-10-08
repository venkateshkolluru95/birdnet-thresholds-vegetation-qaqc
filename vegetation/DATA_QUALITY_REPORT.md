# Herbaceous vegetation survey: data quality report

**Project:** Savanna Monitoring Pilot (SAVMON), area LW, baseline replicate `lw_baseline`, survey `savmon|lw|herbs|ho`.
**Data:** ODK exports of the Herbaceous Vegetation Survey form (32 submissions, 640 quadrats, 1,296 additional-species rows), the Register Vegetation Plots form (31 registrations), and the entity lists, including the identification list `species_extra_ids`. SOPs: Vegetation Plot Registration v2026.1 and Herbaceous Vegetation Surveys v2026.1.
**Rule followed:** nothing in the data was changed. Every problem is flagged with a rule id, a severity, its population and the exact record, in `outputs/qa_issues.csv`. Summaries use the retained population: the 30 submissions that ODK Central has not rejected. An identity recorded twice in one quadrat counts once. Frequency across quadrats is the abundance index, as the SOP states.

Code: [`01_load_and_join.py`](01_load_and_join.py) (join the exports and entity lists into five tidy tables), [`02_qa_checks.py`](02_qa_checks.py) (24 rules), [`03_report_tables_and_maps.py`](03_report_tables_and_maps.py) (tables, figures, maps, metrics), [`04_assemble_report.py`](04_assemble_report.py) (fills every number and table in this report from the outputs).

---

## Headline findings

1. **Species must be counted on entities, not labels.** 152 distinct labels were recorded, but they belong to 132 field identities: 28 from the project list, 44 typed names and 60 placeholders created in the field. 22 entities appear under two labels, their typed name and their `herb_###` placeholder. Of the 132 identities, 104 have a name from the list or from `species_extra_ids`, and 28 are still "Unknown". Every richness and diversity number below is computed on identities.
2. **The sampling design is incomplete in these exports.** All 30 primary savanna plots were visited: 29 surveyed, Plot 23 recorded not viable, backup Plot 46 surveyed. None of the 6 primary shrubland plots has a registration or a survey here.
3. **Two plots were submitted twice** (Plot 18 and Plot 21). The second copies are marked rejected in ODK Central and are excluded from summaries. The rule still lists them so nobody counts 32 surveys.
4. **Transect geometry often departs from the SOP numbers.** Straight A-to-B distances run from 22.6 to 65.6 m against a 50 m specification. One midpoint (Plot_14) is 33.6 m from its prescribed point against a 25 m limit. Every transect bears between 50 and 131 degrees, where the SOP says north-south unless rotated, and no rotation reason is recorded. In Plot_05, 19 of 20 quadrats lie 13 to 27 m from the registered transect, so the registration and the quadrat geopoints disagree.
5. **Typed names need a review queue.** 43 names were typed in the field, all with a space where the SOP asks for `Genus_species`. 10 differ from the GBIF spelling and 3 match only at genus or family. One already exists on the project list. The identification list adds a note to 6 identities, saying they duplicate another or should be excluded as woody; those are queued, not applied.
6. **The form's own end-of-survey count is the wrong quantity.** The "quadrats with species" number shown to the team differs from the rows in 22 of 30 retained submissions. The form's calculation tests the list-species field at the wrong nesting level, so it only counts quadrats with additional species. It equals that count in all 32 submissions.
7. **20 quadrats do not exhaust a plot.** On average 88 percent of a plot's identities are found by quadrat 15, and 29 of 30 plots added at least one identity in quadrats 16 to 20. Across plots the count is still rising at 30 plots.

Issue totals: 357 flagged rows in the retained population (21 errors, 277 warnings, 59 informational). 3 of 24 rules found nothing. Full catalogue in Section 5.

---

## a. Survey-level summary

| measure                                                        | value                    |
|:---------------------------------------------------------------|:-------------------------|
| Submissions received                                           | 32                       |
| Rejected in ODK review (excluded)                              | 2                        |
| Retained surveys (unreviewed, not rejected)                    | 30                       |
| Plots surveyed (primary / backup)                              | 29 / 1                   |
| Survey dates (device clock)                                    | 2026-05-19 to 2026-05-27 |
| Recorders                                                      | Grace (25), Sam (5)      |
| Quadrats in retained surveys                                   | 600                      |
| Quadrats with herbaceous species                               | 593                      |
| Species records (quadrat x identity, counted once per quadrat) | 2086                     |
| Distinct recorded labels                                       | 152                      |
| Distinct field identities (list + entity UUID)                 | 132                      |
| of which from the project list                                 | 28                       |
| of which typed names created in the field                      | 44                       |
| of which placeholders created in the field                     | 60                       |
| Identities with a name (list name or supplied identification)  | 104                      |
| Identities still 'Unknown'                                     | 28                       |
| Form-open time, retained surveys (minutes)                     | 2245                     |
| Nominal person-hours (minutes x team size / 60)                | 112.2                    |

One row per retained survey, that is one plot visit. Times are the device clock as recorded. The devices applied an offset of +02:00 while the project zone is +03:00, so wall-clock readings are one hour behind Nairobi time. `quadrats_with_species_form` is the number the ODK form displayed at the end; `quadrats_with_records` is the recount from the rows (Section 5, S04). `issues_direct` counts errors and warnings on the submission itself; `issues_quadrats` counts those on its quadrats and species rows.

| plot    | date       | start_device_clock   | recorder   |   team_size |   duration_min |   quadrats_with_herbs |   quadrats_with_species_form |   quadrats_with_records |   label_count |   identity_count |   identities_named |   identities_unknown |   issues_direct |   issues_quadrats |
|:--------|:-----------|:---------------------|:-----------|------------:|---------------:|----------------------:|-----------------------------:|------------------------:|--------------:|-----------------:|-------------------:|---------------------:|----------------:|------------------:|
| Plot_08 | 2026-05-19 | 10:42                | Sam        |           3 |            236 |                    20 |                           19 |                      20 |            31 |               26 |                 23 |                    3 |               2 |                 5 |
| Plot_12 | 2026-05-20 | 08:30                | Sam        |           3 |            165 |                    20 |                           20 |                      20 |            40 |               35 |                 31 |                    4 |               0 |                 5 |
| Plot_22 | 2026-05-20 | 12:53                | Sam        |           3 |             73 |                    20 |                           16 |                      20 |            21 |               20 |                 16 |                    4 |               1 |                 6 |
| Plot_03 | 2026-05-20 | 15:24                | Sam        |           3 |             59 |                    18 |                           18 |                      18 |            15 |               15 |                  8 |                    7 |               0 |                 3 |
| Plot_30 | 2026-05-21 | 08:10                | Grace      |           3 |            101 |                    20 |                           14 |                      20 |            25 |               24 |                 21 |                    3 |               1 |                 8 |
| Plot_10 | 2026-05-21 | 10:29                | Grace      |           3 |             63 |                    20 |                           18 |                      20 |            21 |               21 |                 20 |                    1 |               1 |                 4 |
| Plot_14 | 2026-05-21 | 12:03                | Grace      |           3 |             58 |                    20 |                           11 |                      20 |            19 |               18 |                 16 |                    2 |               1 |                 8 |
| Plot_09 | 2026-05-21 | 13:50                | Grace      |           3 |             82 |                    20 |                           19 |                      20 |            29 |               27 |                 23 |                    4 |               1 |                 2 |
| Plot_05 | 2026-05-22 | 08:27                | Grace      |           3 |            102 |                    19 |                           12 |                      19 |            17 |               16 |                 15 |                    1 |               1 |                19 |
| Plot_26 | 2026-05-22 | 11:05                | Grace      |           3 |            110 |                    20 |                           19 |                      20 |            23 |               24 |                 20 |                    4 |               1 |                 3 |
| Plot_27 | 2026-05-22 | 13:42                | Grace      |           3 |             67 |                    20 |                           19 |                      20 |            22 |               22 |                 19 |                    3 |               1 |                13 |
| Plot_19 | 2026-05-22 | 15:13                | Grace      |           3 |             60 |                    19 |                           16 |                      19 |            19 |               19 |                 18 |                    1 |               1 |                11 |
| Plot_46 | 2026-05-22 | 16:41                | Grace      |           3 |             33 |                    20 |                           14 |                      20 |             9 |                8 |                  7 |                    1 |               1 |                 5 |
| Plot_06 | 2026-05-23 | 08:37                | Grace      |           3 |             92 |                    20 |                           20 |                      20 |            26 |               24 |                 20 |                    4 |               0 |                 8 |
| Plot_17 | 2026-05-23 | 10:36                | Grace      |           3 |             44 |                    20 |                           20 |                      20 |            22 |               22 |                 16 |                    6 |               0 |                 2 |
| Plot_13 | 2026-05-23 | 11:46                | Grace      |           3 |             70 |                    20 |                           20 |                      20 |            12 |               13 |                 10 |                    3 |               0 |                 4 |
| Plot_01 | 2026-05-23 | 14:03                | Grace      |           3 |             70 |                    20 |                           19 |                      20 |            32 |               31 |                 29 |                    2 |               1 |                12 |
| Plot_28 | 2026-05-23 | 15:40                | Grace      |           3 |             64 |                    19 |                           19 |                      19 |            22 |               22 |                 18 |                    4 |               0 |                 2 |
| Plot_02 | 2026-05-24 | 09:06                | Grace      |           3 |            100 |                    19 |                           17 |                      19 |            19 |               18 |                 17 |                    1 |               1 |                 3 |
| Plot_24 | 2026-05-24 | 11:05                | Grace      |           3 |             38 |                    20 |                           19 |                      20 |            11 |               11 |                 10 |                    1 |               1 |                 0 |
| Plot_20 | 2026-05-24 | 12:09                | Grace      |           3 |             54 |                    20 |                           19 |                      20 |            17 |               17 |                 17 |                    0 |               1 |                 1 |
| Plot_15 | 2026-05-24 | 14:00                | Grace      |           3 |             60 |                    20 |                           17 |                      20 |            22 |               21 |                 20 |                    1 |               1 |                 6 |
| Plot_07 | 2026-05-24 | 15:38                | Grace      |           3 |             56 |                    20 |                           17 |                      20 |            18 |               18 |                 13 |                    5 |               1 |                 6 |
| Plot_04 | 2026-05-25 | 14:06                | Grace      |           3 |             56 |                    19 |                           18 |                      19 |            20 |               21 |                 15 |                    6 |               1 |                 5 |
| Plot_25 | 2026-05-25 | 15:20                | Grace      |           3 |             63 |                    20 |                           19 |                      20 |            31 |               31 |                 28 |                    3 |               1 |                 3 |
| Plot_18 | 2026-05-26 | 08:23                | Grace      |           3 |             53 |                    20 |                           20 |                      20 |            28 |               28 |                 23 |                    5 |               0 |                 2 |
| Plot_21 | 2026-05-26 | 09:44                | Grace      |           3 |             68 |                    20 |                           19 |                      20 |            30 |               30 |                 26 |                    4 |               1 |                 1 |
| Plot_29 | 2026-05-26 | 11:57                | Sam        |           3 |             42 |                    20 |                           19 |                      20 |            24 |               24 |                 22 |                    2 |               1 |                 6 |
| Plot_11 | 2026-05-26 | 15:31                | Grace      |           3 |             54 |                    20 |                           20 |                      20 |            25 |               25 |                 23 |                    2 |               0 |                 5 |
| Plot_16 | 2026-05-27 | 09:41                | Grace      |           3 |             51 |                    20 |                           19 |                      20 |            23 |               23 |                 20 |                    3 |               1 |                 0 |

![Effort timeline](figures/fig_v1_effort_timeline.png)

What the timeline shows. One team of three worked 2026-05-19 to 2026-05-27; Grace (25), Sam (5). Retained form-open time totals 2245 minutes, or 112.2 nominal person-hours, about 3.7 per plot. Form-open time includes interruptions and does not measure active work. The first survey, Plot 08 on 19 May, is the longest at about four hours. It also started with zero active placeholders, which is expected for the first survey of a campaign (rule S06). The two rejected submissions of 26 May lasted 25 to 26 minutes and record plots already surveyed that morning; the export does not say why they were rejected.

## b. Plot-level summary

Richness is the number of distinct field identities recorded in the plot's 20 quadrats. `label_count` is the number of distinct labels, for comparison. `identities_named` counts identities with a list name or a supplied identification. Shannon diversity is the natural-log entropy of the number of quadrats each identity occupied; it is not cover or abundance, which were not measured. `geometry_flags` counts the transect warnings and errors (P02 to P04) and `quadrats_off_transect` the Q02 flags for the plot.

| plot    | sample_status   | is_viable   | surveyed   | ecosystem_type   | canopy_structure   |   canopy_height_m | soil_type   | disturbance                                         |   transect_length_m |   polyline_length_m |   midpoint_offset_m |   midpoint_off_line_m |   bearing_a_to_b_deg |   geometry_flags |   quadrats_off_transect |   label_count |   identity_count |   identities_named |   mean_identities_per_quadrat |   shannon_identities |
|:--------|:----------------|:------------|:-----------|:-----------------|:-------------------|------------------:|:------------|:----------------------------------------------------|--------------------:|--------------------:|--------------------:|----------------------:|---------------------:|-----------------:|------------------------:|--------------:|-----------------:|-------------------:|------------------------------:|---------------------:|
| Plot_16 | primary         | yes         | True       | Scrub            | closed             |               2.0 | grey_sand   | wildlife_disturbance human_or_livestock_disturbance |                58.3 |                58.4 |                 3.5 |                   1.6 |                100.4 |                2 |                       0 |          23.0 |             23.0 |               20.0 |                           4.5 |                  2.8 |
| Plot_11 | primary         | yes         | True       | Scrub            | open               |               2.0 | grey_sand   | wildlife_disturbance                                |                42.5 |                48.2 |                11.6 |                  11.3 |                107.9 |                1 |                       4 |          25.0 |             25.0 |               23.0 |                           3.6 |                  3.0 |
| Plot_29 | primary         | yes         | True       | Scrub            | open               |               3.0 | white_sand  | wildlife_disturbance human_or_livestock_disturbance |                61.8 |                62.9 |                 8.3 |                   5.8 |                105.0 |                1 |                       5 |          24.0 |             24.0 |               22.0 |                           4.2 |                  2.8 |
| Plot_21 | primary         | yes         | True       | Scrub            | open               |               1.0 | beige_sand  | wildlife_disturbance                                |                44.8 |                46.0 |                13.8 |                   5.0 |                 97.8 |                1 |                       1 |          30.0 |             30.0 |               26.0 |                           4.7 |                  3.1 |
| Plot_18 | primary         | yes         | True       | Scrub            | open               |               3.0 | beige_sand  | wildlife_disturbance                                |                45.7 |                45.8 |                 2.6 |                   1.3 |                113.6 |                0 |                       1 |          28.0 |             28.0 |               23.0 |                           3.6 |                  3.0 |
| Plot_25 | primary         | yes         | True       | Scrub            | open               |               2.0 | beige_sand  | wildlife_disturbance                                |                42.8 |                42.9 |                 2.6 |                   1.4 |                 96.3 |                1 |                       3 |          31.0 |             31.0 |               28.0 |                           4.2 |                  3.2 |
| Plot_04 | primary         | yes         | True       | Forest           | open               |              10.0 | grey_sand   | wildlife_disturbance                                |                53.5 |                53.9 |                 5.7 |                   3.3 |                109.5 |                0 |                       5 |          20.0 |             21.0 |               15.0 |                           2.6 |                  2.8 |
| Plot_07 | primary         | yes         | True       | Scrub            | open               |               4.0 | beige_sand  | wildlife_disturbance                                |                52.3 |                54.0 |                 5.9 |                   6.5 |                 85.3 |                1 |                       6 |          18.0 |             18.0 |               13.0 |                           3.8 |                  2.5 |
| Plot_15 | primary         | yes         | True       | Scrub            | open               |               3.0 | beige_sand  | wildlife_disturbance human_or_livestock_disturbance |                60.4 |                69.7 |                15.2 |                  16.1 |                 95.8 |                3 |                       5 |          22.0 |             21.0 |               20.0 |                           2.0 |                  2.8 |
| Plot_20 | primary         | yes         | True       | Scrub            | open               |               2.0 | grey_sand   | none                                                |                45.1 |                46.6 |                 4.6 |                   5.8 |                104.9 |                0 |                       1 |          17.0 |             17.0 |               17.0 |                           2.8 |                  2.6 |
| Plot_24 | primary         | yes         | True       | Scrub            | open               |               3.0 | grey_sand   | none                                                |                50.6 |                52.1 |                 6.2 |                   6.2 |                 93.1 |                0 |                       0 |          11.0 |             11.0 |               10.0 |                           1.9 |                  1.8 |
| Plot_02 | primary         | yes         | True       | Scrub            | open               |               2.0 | grey_sand   | none                                                |                53.9 |                61.9 |                13.3 |                  15.1 |                102.7 |                1 |                       3 |          19.0 |             18.0 |               17.0 |                           2.5 |                  2.7 |
| Plot_28 | primary         | yes         | True       | Scrub            | closed             |               3.0 | beige_sand  | wildlife_disturbance human_or_livestock_disturbance |                40.2 |                40.4 |                 1.2 |                   1.6 |                117.9 |                2 |                       1 |          22.0 |             22.0 |               18.0 |                           3.1 |                  2.6 |
| Plot_01 | primary         | yes         | True       | Scrub            | open               |               3.0 | beige_sand  | none                                                |                63.2 |                63.4 |                11.4 |                   2.4 |                130.7 |                2 |                      12 |          32.0 |             31.0 |               29.0 |                           4.5 |                  3.1 |
| Plot_13 | primary         | yes         | True       | Scrub            | closed             |               2.0 | white_sand  | wildlife_disturbance                                |                56.1 |                60.4 |                14.0 |                  10.5 |                 78.4 |                2 |                       4 |          12.0 |             13.0 |               10.0 |                           3.3 |                  2.2 |
| Plot_17 | primary         | yes         | True       | Scrub            | open               |               4.0 | grey_sand   | wildlife_disturbance                                |                49.6 |                52.7 |                23.9 |                   8.6 |                 81.9 |                2 |                       2 |          22.0 |             22.0 |               16.0 |                           3.8 |                  2.7 |
| Plot_06 | primary         | yes         | True       | Scrub            | closed             |               3.0 | grey_sand   | none                                                |                48.4 |                48.5 |                 4.3 |                   1.2 |                106.2 |                0 |                       8 |          26.0 |             24.0 |               20.0 |                           4.0 |                  2.8 |
| Plot_46 | backup          | yes         | True       | Scrub            | open               |               1.0 | white_sand  | human_or_livestock_disturbance                      |                46.7 |                46.7 |                 6.2 |                   0.4 |                101.7 |                0 |                       2 |           9.0 |              8.0 |                7.0 |                           2.0 |                  1.7 |
| Plot_19 | primary         | yes         | True       | Scrub            | open               |               2.0 | beige_sand  | wildlife_disturbance human_or_livestock_disturbance |                22.6 |                23.0 |                 3.6 |                   2.0 |                 60.1 |                3 |                      10 |          19.0 |             19.0 |               18.0 |                           2.7 |                  2.6 |
| Plot_27 | primary         | yes         | True       | Scrub            | closed             |               4.0 | beige_sand  | wildlife_disturbance human_or_livestock_disturbance |                28.6 |                33.3 |                20.3 |                   4.0 |                 56.4 |                3 |                      13 |          22.0 |             22.0 |               19.0 |                           3.6 |                  2.9 |
| Plot_26 | primary         | yes         | True       | Scrub            | closed             |               3.0 | grey_sand   | wildlife_disturbance                                |                50.5 |                50.7 |                 7.7 |                   2.4 |                112.7 |                0 |                       3 |          23.0 |             24.0 |               20.0 |                           3.2 |                  2.9 |
| Plot_23 | primary         | no          | False      | nan              | nan                |             nan   | nan         | nan                                                 |               nan   |               nan   |               nan   |                 nan   |                nan   |                0 |                       0 |         nan   |            nan   |              nan   |                         nan   |                nan   |
| Plot_05 | primary         | yes         | True       | Scrub            | open               |               2.0 | beige_sand  | wildlife_disturbance                                |                46.0 |                47.3 |                20.0 |                   5.5 |                116.6 |                1 |                      19 |          17.0 |             16.0 |               15.0 |                           2.1 |                  2.3 |
| Plot_09 | primary         | yes         | True       | Scrub            | open               |               4.0 | grey_sand   | human_or_livestock_disturbance wildlife_disturbance |                45.7 |                46.5 |                 5.3 |                   4.1 |                 77.9 |                0 |                       2 |          29.0 |             27.0 |               23.0 |                           4.5 |                  2.9 |
| Plot_14 | primary         | yes         | True       | Scrub            | open               |               2.0 | grey_sand   | human_or_livestock_disturbance                      |                44.0 |                44.2 |                33.6 |                   1.6 |                 90.7 |                4 |                       7 |          19.0 |             18.0 |               16.0 |                           3.9 |                  2.2 |
| Plot_10 | primary         | yes         | True       | Scrub            | open               |               2.0 | beige_sand  | wildlife_disturbance human_or_livestock_disturbance |                57.5 |                57.9 |                10.2 |                   3.4 |                109.2 |                1 |                       3 |          21.0 |             21.0 |               20.0 |                           3.4 |                  2.6 |
| Plot_30 | primary         | yes         | True       | Scrub            | open               |               4.0 | beige_sand  | wildlife_disturbance human_or_livestock_disturbance |                50.9 |                52.9 |                14.5 |                   5.9 |                110.0 |                2 |                       7 |          25.0 |             24.0 |               21.0 |                           4.0 |                  2.8 |
| Plot_03 | primary         | yes         | True       | Scrub            | closed             |               4.0 | beige_sand  | wildlife_disturbance                                |                57.5 |                57.7 |                 5.3 |                   2.6 |                106.9 |                2 |                       3 |          15.0 |             15.0 |                8.0 |                           2.1 |                  2.4 |
| Plot_22 | primary         | yes         | True       | Scrub            | open               |               4.0 | grey_sand   | human_or_livestock_disturbance                      |                65.6 |                70.5 |                17.8 |                  12.1 |                 49.7 |                3 |                       5 |          21.0 |             20.0 |               16.0 |                           3.2 |                  2.8 |
| Plot_12 | primary         | yes         | True       | Scrub            | open               |               3.0 | beige_sand  | none                                                |                41.9 |                42.0 |                12.2 |                   0.7 |                122.8 |                2 |                       2 |          40.0 |             35.0 |               31.0 |                           5.2 |                  3.2 |
| Plot_08 | primary         | yes         | True       | Scrub            | open               |               3.0 | beige_sand  | none                                                |                47.6 |                50.2 |                 5.7 |                   8.0 |                111.9 |                0 |                       5 |          31.0 |             26.0 |               23.0 |                           5.2 |                  2.8 |

![Richness by plot](figures/fig_v2_richness_by_plot.png)

Reading the plot table:

- Richness ranges from 8 identities (Plot_46) to 35 (Plot_12). Label counts are higher wherever an entity was recorded under both its typed name and its placeholder.
- Registration context, from the viable registered plots:

| field                                       | result among the viable registered plots                                                                                                               |
|:--------------------------------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------|
| Woody plants present                        | yes 30                                                                                                                                                 |
| Water nearby                                | no 30                                                                                                                                                  |
| Canopy structure                            | open 23, closed 7                                                                                                                                      |
| Canopy height (m)                           | 1 m: 2, 2 m: 10, 3 m: 10, 4 m: 7, 10 m: 1                                                                                                              |
| Soil type                                   | beige_sand 15, grey_sand 12, white_sand 3                                                                                                              |
| Ecosystem recorded                          | Scrub 29, Forest 1                                                                                                                                     |
| Disturbance recorded                        | none 7; wildlife 20; human or livestock 12; both 9                                                                                                     |
| Ground cover selections (overlapping)       | forbs 30, soil 28, grasses 22, non-dwarf_shrubs 18, litter 14, standing_npv 7                                                                          |
| Dominant woody species listed (overlapping) | Vachellia tortilis 16, Boscia coriacea 9, Terminalia brownii 9, Vachellia mellifera 2, Mundulea sericea 1, Combretum aculeatum 1, Combretum collinum 1 |

- Disturbance was recorded in 23 of 30 viable plots: wildlife in 20, human or livestock in 12, both in 9. Every plot has woody plants and no nearby water. One plot was recorded as Forest inside the savanna stratum.
- Transect geometry: straight A-B distances 22.6 to 65.6 m against the 50 m SOP; the 45 to 55 and 40 to 60 m bands are analysis tolerances. Midpoint offsets reach 33.6 m against the 25 m limit; 1 exceed it and 5 sit between 15 and 25 m. Bearings run 50 to 131 degrees. 14 midpoints lie more than 5 m off the straight A-B line. All geometry is computed from recorded coordinates with reported accuracy of 5 m or better; it measures the coordinates, not the tape.

![Transect geometry](figures/fig_v4_transect_geometry.png)

## c. Assessment of sampling effort

### Design coverage

| stratum   | sample_status   |   prescribed |   registered |   viable |   surveyed |
|:----------|:----------------|-------------:|-------------:|---------:|-----------:|
| savanna   | backup          |           10 |            1 |        1 |          1 |
| savanna   | primary         |           30 |           30 |       29 |         29 |
| shrubland | backup          |            5 |            0 |        0 |          0 |
| shrubland | primary         |            6 |            0 |        0 |          0 |

The design prescribed 36 primary plots in two strata plus backups. The savanna stratum is complete in these exports: 29 primaries surveyed, Plot 23 recorded not viable because it falls on private property, backup Plot 46 surveyed. The shrubland stratum (Plots 31 to 36, backups 47 to 51) has no registration and no survey in the supplied files. Any area-level statement from this baseline describes the sampled savanna plots only. 19 of the 51 prescribed points have no survey year in the design list.

### Effort

30 retained surveys, 600 quadrats, 2245 form-open minutes, about 112.2 person-hours with three people throughout, roughly 3.7 per plot. Quadrats were never skipped: every submission holds exactly 20, 593 of 600 contained herbaceous species, and every quadrat has a photo and a geopoint with reported accuracy of 5 m or better. The 20 one-square-metre quadrats sample 20 m² of each 250 m² belt transect.

### Does 20 quadrats per plot capture the plot?

![Species accumulation](figures/fig_v3_species_accumulation.png)

Left panel: for each plot, the share of the identities found by quadrat 20 that had already been found after 1, 2, ... 15 quadrats, in the recorded order. The mean reaches 88 percent at quadrat 15 (median 90, lowest 75). 29 of 30 plots recorded at least one new identity in quadrats 16 to 20 (table below). The curve shows that identities were still accumulating at the end of the transect; it does not say how many taxa the whole transect holds. Right panel: distinct identities across plots, averaged over 200 random plot orders with the plot as the sampling unit (Colwell et al. 2012). It rises from 123 after 25 plots to 132 after 30 with no sign of flattening. The 200 orders give an average, not a confidence interval. The fixed design records most, but not all, of what is present. That is acceptable for a change-detection baseline if the next replicate repeats the same effort, placement and identification practice.

| plot    |   identities_after_20 |   share_found_by_quadrat_15 |   new_identities_in_last_5_quadrats |
|:--------|----------------------:|----------------------------:|------------------------------------:|
| Plot_05 |                    16 |                        0.75 |                                   4 |
| Plot_01 |                    31 |                        0.77 |                                   7 |
| Plot_18 |                    28 |                        0.79 |                                   6 |
| Plot_30 |                    24 |                        0.79 |                                   5 |
| Plot_24 |                    11 |                        0.82 |                                   2 |
| Plot_21 |                    30 |                        0.83 |                                   5 |
| Plot_29 |                    24 |                        0.83 |                                   4 |
| Plot_02 |                    18 |                        0.83 |                                   3 |
| Plot_19 |                    19 |                        0.84 |                                   3 |
| Plot_27 |                    22 |                        0.86 |                                   3 |
| Plot_16 |                    23 |                        0.87 |                                   3 |
| Plot_08 |                    26 |                        0.88 |                                   3 |
| Plot_06 |                    24 |                        0.88 |                                   3 |
| Plot_46 |                     8 |                        0.88 |                                   1 |
| Plot_07 |                    18 |                        0.89 |                                   2 |
| Plot_04 |                    21 |                        0.90 |                                   2 |
| Plot_15 |                    21 |                        0.90 |                                   2 |
| Plot_17 |                    22 |                        0.91 |                                   2 |
| Plot_12 |                    35 |                        0.91 |                                   3 |
| Plot_28 |                    22 |                        0.91 |                                   2 |
| Plot_13 |                    13 |                        0.92 |                                   1 |
| Plot_26 |                    24 |                        0.92 |                                   2 |
| Plot_11 |                    25 |                        0.92 |                                   2 |
| Plot_20 |                    17 |                        0.94 |                                   1 |
| Plot_25 |                    31 |                        0.94 |                                   2 |
| Plot_14 |                    18 |                        0.94 |                                   1 |
| Plot_10 |                    21 |                        0.95 |                                   1 |
| Plot_22 |                    20 |                        0.95 |                                   1 |
| Plot_09 |                    27 |                        0.96 |                                   1 |
| Plot_03 |                    15 |                        1.00 |                                   0 |

### Where effort would help most

- Register and survey the six shrubland primaries, or record that the stratum is dropped and why.
- Resolve the 28 identities still "Unknown" from the vouchers and photos. Act on the 6 notes in the identification list and merge the 22 alias pairs in the identification layer.
- Re-establish the transects whose recorded geometry fails the SOP numbers before the next replicate, comparing the registration points with the quadrat geopoints and the photos on site.

## d. Map of transect locations

![Transect map](figures/map_transects.png)

Left: all 51 prescribed locations in UTM 37N, by their status in these exports. The rings mark the shrubland stratum, which has no data. Primary points without a registration are shown apart from unused backups. Right: Plot_05 at full resolution, the plot with the most quadrats flagged by rule Q02 (19 of 20, at 13 to 27 m from the registered transect, drawn in black). The quadrats form an east-west band around the prescribed centroid (star) while the registered transect runs further south. The dashed circle is the 25 m limit for relocating the midpoint, drawn for scale. Both coordinate sets were recorded with 5 m accuracy or better and disagree by more than that; which one reflects where the tape lay needs the photos or a site visit. The same pattern, less extreme, accounts for most of the 142 retained quadrats flagged by Q02.

---

## 5. Issue catalogue

Every rule is a few lines in `02_qa_checks.py`, named after what it tests. The SOP numbers sit in one `SOP` dictionary and the analysis tolerances in a separate `CONFIG` dictionary. Each issue row carries its population (retained, rejected or shared) and the exact record. Rules that found nothing are listed with status pass.

| check_id   | rule                                                      |   n_all_exports |   n_retained | severities    | status   |
|:-----------|:----------------------------------------------------------|----------------:|-------------:|:--------------|:---------|
| S01        | duplicate submission for plot                             |               4 |            2 | info          | findings |
| S02        | rejected submission (excluded from summaries)             |               2 |            0 | info          | findings |
| S03        | quadrat count or numbering not 1 to 20                    |               0 |            0 | nan           | pass     |
| S04        | form's end-of-survey species count differs from recount   |              23 |           22 | warning       | findings |
| S05        | survey duration outside 30 to 180 minutes                 |               3 |            1 | warning       | findings |
| S06        | no active placeholders at survey start                    |               1 |            1 | info          | findings |
| P01        | plot registered as not viable                             |               1 |            1 | info          | findings |
| P02        | midpoint offset from prescribed point                     |               6 |            6 | error/warning | findings |
| P03        | straight A-B distance vs 50 m                             |              16 |           16 | error/warning | findings |
| P04        | endpoint half-lengths and midpoint off the A-B line       |              32 |           32 | info/warning  | findings |
| P05        | transect not north-south                                  |              30 |           30 | info          | findings |
| P06        | backup plot surveyed                                      |               1 |            1 | info          | findings |
| P07        | prescribed primary plots with no registration             |               1 |            1 | error         | findings |
| Q01        | quadrat geopoint, accuracy or photo missing or inaccurate |               0 |            0 | nan           | pass     |
| Q02        | quadrat off the registered transect                       |             147 |          142 | error/warning | findings |
| Q03        | no herbaceous species in quadrat                          |               7 |            7 | info          | findings |
| Q04        | additional-species answer disagrees with rows             |              10 |            9 | warning       | findings |
| Q05        | same identity entered twice in a quadrat                  |               7 |            6 | warning       | findings |
| Q06        | form species count differs from IDs                       |               0 |            0 | nan           | pass     |
| Q07        | additional-species row with no species chosen             |               1 |            1 | warning       | findings |
| X01        | typed name not in Genus_species format                    |              43 |           43 | warning       | findings |
| X02        | typed name already on the project species list            |               1 |            1 | warning       | findings |
| X03        | typed name not an exact GBIF match                        |              13 |           13 | info/warning  | findings |
| X04        | same entity recorded under two labels                     |              22 |           22 | warning       | findings |

Notes on the rules that need interpretation:

- **S04, form count differs from recount.** The form's calculation tests the list-species field at the wrong nesting level, so it only counts quadrats with additional species. It equals that count in all 32 submissions. Nothing is wrong with the rows; the form should be corrected in its next version.
- **S06, placeholders.** Zero active placeholders at the start of the first survey is expected. A later survey showing zero would need the device's sync history before concluding anything.
- **P04, midpoint off the A-B line.** 14 recorded midpoints are more than 5 m off the straight line between A and B, up to 16.1 m. Q02 therefore measures quadrats against the A-mid-B transect, which is also what the maps draw.
- **P05, not north-south (30 of 30).** The SOP allows rotation to avoid obstacles but asks for north-south first and gives no field for the reason. The flag means "reason not recorded".
- **Q02, quadrat off the registered transect.** With reported accuracy of up to 5 m on the quadrat and on each registration point, about 10 m of apparent offset is within noise. Offsets of 20 m or more are not. Severity splits at 25 m. The retained count is 142 of 600 quadrats, 13 of them beyond 25 m.
- **X01, spaces instead of underscores (43 names).** The form constraint only blocks commas, semicolons and brackets, and its hint shows a space. The SOP's `Genus_species` format is never enforced. A space does not make the identification wrong.
- **X03, GBIF match.** Each typed name was matched against the GBIF backbone, the source of `species.csv`. 10 names matched with a spelling difference and 3 only at a higher rank. A match is a suggestion for review, not an identification. `outputs/gbif_name_check.csv` is the review queue.
- **X04, one entity under two labels.** 22 entities were recorded under their typed name and under their `herb_###` placeholder. They count as one identity everywhere in this report. The identification list also carries 6 notes (duplicate of another placeholder, or woody and to be excluded). All are queued for the identification layer; none is applied to the data.

## References

- Colwell RK, Chao A, Gotelli NJ, Lin S-Y, Mao CX, Chazdon RL, Longino JT (2012). Models and estimators linking individual-based and sample-based rarefaction, extrapolation and comparison of assemblages. Journal of Plant Ecology 5: 3-21.
- Lehmann CER, Archibald S, Vorontsova MS, Hempson GP, Wieczorkowski JD (2022). "Manisa bozaka" or "Counting grass": Global Grassy Group guide to understanding and measuring the functional and taxonomic composition of ground layer plants. Protocol Exchange.
