"""
WHAT THIS FILE DOES, IN PLAIN LANGUAGE
--------------------------------------
Turns report_template.md into REPORT.md. Every number quoted in the report's prose is a
placeholder, {{m:name}}, filled here from the raw files and the outputs of 01 and 02; the two
tables are {{bands}} and {{results}}. Nothing in the report is typed by hand, so re-running
01, 02 and 03 after new validations regenerates the numbers and the prose together. If a
placeholder is left unfilled the script stops with an error and writes nothing.
"""

import os
import re
import sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, "birds")
OUT = os.path.join(HERE, "outputs")

pred = pd.read_csv(os.path.join(ROOT, "data", "raw", "birds", "birdnet_predictions.csv"))
val = pd.read_csv(os.path.join(ROOT, "data", "raw", "birds", "validation_results.csv"))
thr = pd.read_csv(os.path.join(OUT, "species_thresholds.csv")).set_index("species")
lab = pd.read_csv(os.path.join(OUT, "birdnet_predictions_labeled.csv"))
by_rec = pd.read_csv(os.path.join(OUT, "summary_by_recorder.csv"))
n_raw_cols = len(pred.columns)                          # remembered before any helper column is added below

M = {}                                                  # every number the prose quotes
def n(x):                                               # 29491 -> "29,491"
    return f"{int(x):,}"

# ---------------------------------------------------------------------------
# 1. Facts about the two input files
# ---------------------------------------------------------------------------
dates = pd.to_datetime(pred["begin_path"].str.extract(r"_(\d{8})_")[0], format="%Y%m%d")
recorders = sorted(pred["folder"].unique())
med = pred.groupby("common_name")["confidence"].median()
M.update({"n_pred": n(len(pred)), "n_val": n(len(val)), "n_recorders": len(recorders), "rec_first": recorders[0], "rec_last": recorders[-1],
          "date_first": dates.min().strftime("%-d %B"), "date_last": dates.max().strftime("%-d %B %Y"),
          "conf_min": f"{pred.confidence.min():.2f}", "conf_max": f"{pred.confidence.max():.2f}", "birdnet_version": val["vBirdNET"].iloc[0],
          "median_min": f"{med.min():.2f}", "median_max": f"{med.max():.2f}",
          "val_at_one": int((val.confidence == 1).sum()), "val_at_one_species": " and ".join(val.loc[val.confidence == 1, "commonName"].str.split().str[-1].unique()),
          "pred_at_one": int((pred.confidence == 1).sum())})

# validated clips per species in five confidence bands: "correct / checked"
edges = [(0.1, 0.2), (0.2, 0.3), (0.3, 0.4), (0.4, 0.9), (0.9, 1.01)]
species = sorted(val["commonName"].unique())
lines = ["| Confidence band | " + " | ".join(species) + " |", "|---|" + "---|" * len(species)]
for lo, hi in edges:
    cells = [val[(val.commonName == s) & (val.confidence >= lo) & (val.confidence < hi)] for s in species]
    lines.append(f"| {lo:.1f} to {min(hi, 1.0):.1f} | " + " | ".join(f"{int(c.outcome.sum())} / {len(c)}" for c in cells) + " |")
lines.append("| **Total** | " + " | ".join(f"**{int(val[val.commonName == s].outcome.sum())} / {len(val[val.commonName == s])}**" for s in species) + " |")
bands_table = "\n".join(lines)

ff = val[val.commonName == "Red-billed Firefinch"]; nj = val[val.commonName == "Abyssinian Nightjar"]; pl = val[val.commonName == "Three-banded Plover"]
M.update({"ff_n": len(ff), "ff_below02": int((ff.confidence < 0.2).sum()), "nj_n": len(nj), "nj_above09": int((nj.confidence >= 0.9).sum())})

# validated clips whose recording name, species and confidence also appear in the predictions file. Validation
# confidences have 3 decimals and predictions 4, so "same confidence" means within half a thousandth.
pred["recording"] = pred["begin_path"].str.split("/").str[-1].str.replace(".WAV", "", regex=False)      # RBS64_20230629_060000
val["recording"] = val["filename"].str.replace(".wav", "", regex=False).str.split("_").str[2:].str.join("_")   # drop the "0.264_6_" prefix
cand = val.merge(pred[["recording", "common_name", "confidence"]], left_on=["recording", "commonName"], right_on=["recording", "common_name"], how="left")
closest = (cand["confidence_y"] - cand["confidence_x"]).abs().groupby(cand["filename"]).min()
matched = int((closest <= 0.0005 + 1e-9).sum())
M.update({"val_matched": matched, "val_unmatched": len(val) - matched})

# ---------------------------------------------------------------------------
# 2. Facts about the thresholds (outputs of 01)
# ---------------------------------------------------------------------------
for s, short in [("Abyssinian Nightjar", "nj"), ("African Black-headed Oriole", "or"), ("Three-banded Plover", "pl"), ("Red-billed Firefinch", "ff")]:
    r = thr.loc[s]
    M.update({f"{short}_thr": "none" if pd.isna(r.threshold_confidence) else f"{r.threshold_confidence:.3f}",
              f"{short}_lo": f"{r.threshold_ci95_low:.3f}" if pd.notna(r.threshold_ci95_low) else "", f"{short}_hi": f"{r.threshold_ci95_high:.3f}" if pd.notna(r.threshold_ci95_high) else "",
              f"{short}_lo2": f"{r.threshold_ci95_low:.2f}" if pd.notna(r.threshold_ci95_low) else "", f"{short}_hi2": f"{r.threshold_ci95_high:.2f}" if pd.notna(r.threshold_ci95_high) else "",
              f"{short}_fits": n(r.bootstrap_fits_ok), f"{short}_fails": n(1000 - r.bootstrap_fits_ok), f"{short}_b0": f"{r.intercept:.2f}" if pd.notna(r.intercept) else "", f"{short}_b1": f"{r.slope:.2f}" if pd.notna(r.slope) else "",
              f"{short}_n": int(r.n_validated), f"{short}_correct": int(r.n_correct), f"{short}_above": int(r.validated_at_or_above_threshold), f"{short}_correct_above": int(r.correct_at_or_above_threshold),
              f"{short}_bound": f"{r.precision_lower_bound_95:.3f}" if pd.notna(r.precision_lower_bound_95) else "not estimable",
              f"{short}_bound2": f"{r.precision_lower_bound_95:.2f}" if pd.notna(r.precision_lower_bound_95) else ""})
ff_r = thr.loc["Red-billed Firefinch"]
M.update({"ff_crossing": f"{1 / (1 + np.exp(-(np.log(0.99 / 0.01) - ff_r.intercept) / ff_r.slope)):.3f}",   # where the Firefinch curve reaches 0.99
          "ff_pred_above05": int((pred[pred.common_name == "Red-billed Firefinch"].confidence > 0.5).sum()),
          "nj_max_wrong": f"{nj[nj.outcome == 0].confidence.max():.3f}", "nj_max_wrong_ceiling": f"{np.ceil(nj[nj.outcome == 0].confidence.max() * 10) / 10:.1f}",
          "nj_in_bend": int(((nj.confidence >= 0.3) & (nj.confidence < 0.6)).sum()),
          "pl_wrong_conf": f"{pl[pl.outcome == 0].confidence.iloc[0]:.3f}", "pl_wrong": int((pl.outcome == 0).sum()),
          "n_for_99": int(np.ceil(np.log(0.05) / np.log(0.99))),   # clean clips needed for a 0.99 lower bound: 299
          "best_bound": f"{thr.precision_lower_bound_95.max():.2f}", "best_bound_species": thr.precision_lower_bound_95.idxmax().split()[-1]})

# ---------------------------------------------------------------------------
# 3. Facts about the labels (outputs of 02)
# ---------------------------------------------------------------------------
obs = lab[lab.observation.notna()]
rec_with_pred = pred.groupby("common_name")["folder"].nunique()
rec_with_obs = (by_rec.set_index("recorder") > 0).sum()
rows = []
for s in ["African Black-headed Oriole", "Abyssinian Nightjar", "Three-banded Plover", "Red-billed Firefinch"]:
    p, o = int((lab.common_name == s).sum()), int((obs.common_name == s).sum())
    rows.append(f"| {s} | {n(p)} | {n(o)} | {100 * o / p:.1f}% | {rec_with_obs[s]} of {len(recorders)} ({rec_with_pred[s]} had {s.split()[-1]} predictions) |")
rows.append(f"| **All** | **{n(len(lab))}** | **{n(len(obs))}** | **{100 * len(obs) / len(lab):.1f}%** | **{int((by_rec.set_index('recorder').sum(axis=1) > 0).sum())} of {len(recorders)}** |")
results_table = "| Species | Predictions | Observations | Share kept | Recorders with at least one observation |\n|---|---|---|---|---|\n" + "\n".join(rows)
reasons = lab.label_reason.value_counts()
by_method = obs.groupby("threshold_method").size()
seg = lab.groupby(["begin_path", "begin_time_s"]).size()
M.update({"n_obs": n(len(obs)), "n_obs_curve": n(by_method[[m for m in by_method.index if m.startswith("logistic")]].sum()), "n_obs_empirical": n(by_method[[m for m in by_method.index if m.startswith("empirical")]].sum()),
          "n_below": n(reasons.get("below_threshold", 0)), "n_no_thr": n(reasons.get("no_threshold_for_species", 0)), "n_invalid": n(reasons.get("invalid_input", 0)),
          "no_thr_species": ", ".join(lab.loc[lab.label_reason == "no_threshold_for_species", "common_name"].unique()),
          "n_cols_added": len(lab.columns) - n_raw_cols, "n_rec_zero": int((by_rec.set_index("recorder").sum(axis=1) == 0).sum()),
          "n_double_segments": int((seg > 1).sum()), "nj_share": f"{100 * (obs.common_name == 'Abyssinian Nightjar').sum() / (lab.common_name == 'Abyssinian Nightjar').sum():.0f}",
          "or_share": f"{100 * (obs.common_name == 'African Black-headed Oriole').sum() / (lab.common_name == 'African Black-headed Oriole').sum():.0f}",
          "or_obs": n((obs.common_name == "African Black-headed Oriole").sum())})

# ---------------------------------------------------------------------------
# 4. Fill the template and refuse to write a report with anything left unfilled
# ---------------------------------------------------------------------------
text = open(os.path.join(HERE, "report_template.md")).read()
text = text.replace("{{bands}}", bands_table).replace("{{results}}", results_table)
text = re.sub(r"\{\{m:([a-zA-Z0-9_]+)\}\}", lambda mo: str(M[mo.group(1)]), text)
left = re.findall(r"\{\{[^}]+\}\}", text)
if left:
    sys.exit(f"ERROR: unfilled placeholders, report not written: {sorted(set(left))}")
open(os.path.join(HERE, "REPORT.md"), "w").write(text)
print(f"REPORT.md written; {len(M)} numbers filled from the data")
