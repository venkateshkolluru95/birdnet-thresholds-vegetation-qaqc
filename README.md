# BirdNET observation thresholds and vegetation survey QA/QC

Two small, fully commented Python pipelines and the reports written from them.

| Challenge | Start here | Code | Handover for the Tech team |
|---|---|---|---|
| Birds: turn BirdNET predictions into observations at 99 percent precision | [birds/REPORT.md](birds/REPORT.md) | [birds/01_fit_thresholds.py](birds/01_fit_thresholds.py) to [03_assemble_report.py](birds/03_assemble_report.py) | [birds/HANDOVER_TECH_TEAM.md](birds/HANDOVER_TECH_TEAM.md) |
| Vegetation: join and QA the herbaceous survey; data quality report | [vegetation/DATA_QUALITY_REPORT.md](vegetation/DATA_QUALITY_REPORT.md) | [vegetation/01_load_and_join.py](vegetation/01_load_and_join.py) to [04_assemble_report.py](vegetation/04_assemble_report.py) | [vegetation/HANDOVER_TECH_TEAM.md](vegetation/HANDOVER_TECH_TEAM.md) |

[DEVLOG.md](DEVLOG.md) records how the work unfolded.

## Results in one screen

**Birds.** Abyssinian Nightjar threshold 0.667 and Three-banded Plover 0.259, both from the logistic curve. African Black-headed Oriole 0.104: all 150 validated clips were correct, so no curve can be fitted and the lowest validated score is used, which certifies precision of at least 0.98. Red-billed Firefinch has no threshold, because the curve reaches 0.99 only above every validated clip. In total 21,331 of 29,491 predictions become observations. Output: `birds/outputs/birdnet_predictions_labeled.csv` with `observation`, `label_reason` and `threshold_method` columns.

**Vegetation.** 30 retained surveys over 29 primary and 1 backup savanna plot; the 6-plot shrubland stratum has no data in the exports. The 152 recorded labels resolve to 132 field identities, because 22 entities were recorded under two labels; 104 identities have a name and 28 are still unknown. The 24 rules flag 357 rows in the retained population, 21 of them errors. The main findings: two duplicate submissions, transect lengths from 23 to 66 m against a 50 m SOP, and one midpoint 34 m off its prescribed point. Every transect bears eastward, and the quadrats of Plot 05 lie 13 to 27 m from the registered transect. Ten typed names are spelled differently from GBIF, and the form's summary count measures the wrong quantity in 22 of 30 submissions. Nothing was corrected; every flag points to the exact record.

## How to run

```bash
pip install -r requirements.txt
python birds/01_fit_thresholds.py && python birds/02_label_predictions.py && python birds/03_assemble_report.py
python vegetation/01_load_and_join.py && python vegetation/02_qa_checks.py
python vegetation/03_report_tables_and_maps.py && python vegetation/04_assemble_report.py
```

Python 3.13. The scripts expect the input files under `data/raw/birds/` and `data/raw/vegetation/`. These are project data and are kept out of the repository; the derived outputs (thresholds, labeled predictions, cleaned tables, issues, figures) are included.

## Layout

```
birds/        01_fit_thresholds.py, 02_label_predictions.py, 03_assemble_report.py, report_template.md -> REPORT.md,
              HANDOVER_TECH_TEAM.md, outputs/, figures/
vegetation/   01_load_and_join.py, 02_qa_checks.py, 03_report_tables_and_maps.py, 04_assemble_report.py,
              report_template.md -> DATA_QUALITY_REPORT.md, HANDOVER_TECH_TEAM.md, outputs/, figures/
data/raw/     the input files (kept out of the repository)
```
