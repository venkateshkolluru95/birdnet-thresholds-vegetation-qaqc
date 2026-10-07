"""
WHAT THIS FILE DOES, IN PLAIN LANGUAGE
--------------------------------------
Takes the species thresholds produced by 01_fit_thresholds.py and applies them to every
BirdNET prediction (29,491 clips). A prediction whose confidence is at or above its
species' threshold becomes an "observation" of that species; everything else stays an
unconfirmed prediction. A second column records WHY each clip got its label, so nothing
is hidden behind an empty cell.

INPUT : data/raw/birds/birdnet_predictions.csv
        birds/outputs/species_thresholds.csv
OUTPUT: birds/outputs/birdnet_predictions_labeled.csv   (all original columns + threshold_confidence, threshold_method, observation, label_reason)
        birds/outputs/summary_by_species.csv            (predictions vs observations per species)
        birds/outputs/summary_by_recorder.csv           (observations per recorder and species)
        birds/figures/fig2_predictions_vs_observations.png
"""

import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRED_FILE = os.path.join(ROOT, "data", "raw", "birds", "birdnet_predictions.csv")
THR_FILE = os.path.join(ROOT, "birds", "outputs", "species_thresholds.csv")
OUT_DIR = os.path.join(ROOT, "birds", "outputs")
FIG_DIR = os.path.join(ROOT, "birds", "figures")

# ---------------------------------------------------------------------------
# 1. Load predictions and thresholds, and join them on the species name
# ---------------------------------------------------------------------------
pred = pd.read_csv(PRED_FILE)                                   # 29,491 rows, one per 3-second clip and species
n_rows_in = len(pred)                                           # remembered so we can prove no row was lost or duplicated
thr = pd.read_csv(THR_FILE)[["species", "threshold_confidence", "method"]].rename(columns={"method": "threshold_method"})   # the cutoff and how it was set

# left join: every prediction keeps its row; the threshold and its method are added (NaN if the species has none)
pred = pred.merge(thr, how="left", left_on="common_name", right_on="species").drop(columns="species")
assert len(pred) == n_rows_in, "the join changed the number of rows"   # a duplicated species in the thresholds table would do this

# ---------------------------------------------------------------------------
# 2. Decide the label for every clip
# ---------------------------------------------------------------------------
# an input row we cannot judge: no species name, or a confidence outside 0 to 1 (none in this file, but the
# platform will see them one day, and they must never be labeled as observations by accident)
invalid = pred["common_name"].isna() | pred["confidence"].isna() | (pred["confidence"] < 0) | (pred["confidence"] > 1)
has_threshold = pred["threshold_confidence"].notna() & ~invalid              # species for which a threshold exists
passes = has_threshold & (pred["confidence"] >= pred["threshold_confidence"])  # clip at or above its species' cutoff

pred["observation"] = pred["common_name"].where(passes, other="")        # species name if it passes, else empty
pred["label_reason"] = "below_threshold"                                 # default reason
pred.loc[passes, "label_reason"] = "at_or_above_threshold"
pred.loc[~has_threshold, "label_reason"] = "no_threshold_for_species"    # e.g. Red-billed Firefinch
pred.loc[invalid, "label_reason"] = "invalid_input"                      # bad rows are reported, never silently dropped

pred.to_csv(os.path.join(OUT_DIR, "birdnet_predictions_labeled.csv"), index=False)

# ---------------------------------------------------------------------------
# 3. Summaries: how many predictions became observations, by species and by recorder
# ---------------------------------------------------------------------------
by_species = (pred.groupby("common_name")
                  .agg(predictions=("confidence", "size"),          # all clips for the species
                       observations=("observation", lambda s: (s != "").sum()),   # clips that passed
                       threshold=("threshold_confidence", "first"))
                  .reset_index())
by_species["share_kept"] = (by_species["observations"] / by_species["predictions"]).round(3)
by_species.to_csv(os.path.join(OUT_DIR, "summary_by_species.csv"), index=False)

# recorder x species table of observation counts: this is what a dashboard would show per site
by_recorder = (pred[pred["observation"] != ""]
                 .pivot_table(index="folder", columns="common_name", values="observation",
                              aggfunc="size", fill_value=0)
                 .reindex(index=sorted(pred["folder"].unique()), columns=sorted(pred["common_name"].unique()), fill_value=0)   # keep recorders and species with zero observations
                 .reset_index()
                 .rename(columns={"folder": "recorder"}))
by_recorder.to_csv(os.path.join(OUT_DIR, "summary_by_recorder.csv"), index=False)

# ---------------------------------------------------------------------------
# 4. Figure: predictions vs observations per species
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(9, 5))
xpos = range(len(by_species))
ax.bar([x - 0.2 for x in xpos], by_species["predictions"], width=0.4, color="#c9d4de", label="BirdNET predictions")
ax.bar([x + 0.2 for x in xpos], by_species["observations"], width=0.4, color="#2E5E8C", label="observations (pass threshold)")
for x, (p, o) in zip(xpos, zip(by_species["predictions"], by_species["observations"])):
    ax.text(x - 0.2, p * 1.08, f"{p:,}", ha="center", va="bottom", fontsize=9)
    ax.text(x + 0.2, max(o, 1) * 1.08, f"{o:,}", ha="center", va="bottom", fontsize=9)   # a 0 cannot be drawn on a log axis, so label it at the floor
ax.set_xticks(list(xpos))
ax.set_xticklabels(by_species["common_name"].str.replace(" ", "\n", n=1), fontsize=9)   # two-line labels so they do not overlap
ax.set_ylabel("number of 3-second clips")
ax.set_yscale("log")                                   # species differ by 100x, so a log axis keeps all bars visible
ax.set_ylim(1, by_species["predictions"].max() * 3)
ax.legend(frameon=False, loc="upper right")
ax.set_title("From predictions to observations, per species (log scale)", fontsize=11)
fig.tight_layout()
fig.savefig(os.path.join(FIG_DIR, "fig2_predictions_vs_observations.png"), dpi=200)

# ---------------------------------------------------------------------------
# 5. Print the summary
# ---------------------------------------------------------------------------
print(by_species.to_string(index=False))
print()
print(pred["label_reason"].value_counts().to_string())
