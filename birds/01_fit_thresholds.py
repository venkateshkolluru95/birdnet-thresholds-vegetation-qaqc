"""
WHAT THIS FILE DOES, IN PLAIN LANGUAGE
--------------------------------------
BirdNET gives every 3-second audio clip a "confidence" between 0 and 1 for a species.
That number is NOT a probability and means different things for different species.
An ornithologist listened to 551 clips and marked each prediction correct (1) or wrong (0).

The rule applied here (from Wood & Kahl 2024): for each species, draw an S-shaped curve
(logistic regression) through those correct/wrong marks, with the logit of the confidence
on the x-axis, and read off the confidence where the curve reaches a 0.99 probability of
being correct. Predictions above that confidence count as observations.

This script does that for each species and handles the two cases where the curve cannot
give an answer:
  * every checked clip is correct -> no curve can be fitted (statisticians call this
    "complete separation"). We then use a counting rule instead of a curve, in the spirit of
    Tseng et al. (2025): threshold = the lowest confidence that was checked, and we report the
    lower bound on precision that many all-correct clips support (rule of three).
  * the curve reaches 0.99 only above every checked clip -> the threshold has no evidence
    behind it and no prediction of that species is called an observation (Scanferla et al.
    2025 met the related case, thresholds above a confidence of 1, for 16 of 72 species).

INPUT : data/raw/birds/validation_results.csv   (551 ornithologist-checked clips)
OUTPUT: birds/outputs/species_thresholds.csv     (one row per species, the decision table)
        birds/outputs/validation_by_bin.csv      (correct / checked per 0.1 confidence bin)
        birds/figures/fig1_precision_curves.png  (the four fitted curves)
"""

import os                                   # to build file paths that work on any computer
import warnings                             # to silence one expected, harmless warning (see below)
import numpy as np                          # basic maths on arrays
import pandas as pd                         # tables (DataFrames)
import statsmodels.api as sm                # the logistic regression (same as R's glm(..., binomial))
from statsmodels.tools.sm_exceptions import PerfectSeparationWarning, ConvergenceWarning
from scipy.stats import beta                # exact binomial confidence bound for precision
import matplotlib                           # plotting
matplotlib.use("Agg")                       # draw to files, not to a screen (works on servers)
import matplotlib.pyplot as plt

# During the bootstrap, some random resamples happen to contain only correct clips; statsmodels
# then warns about "perfect separation". That is expected: those resamples are skipped and counted
# below (bootstrap_fits_ok), so the warnings would only clutter the log.
warnings.simplefilter("ignore", PerfectSeparationWarning)
warnings.simplefilter("ignore", ConvergenceWarning)
warnings.simplefilter("ignore", RuntimeWarning)

# ---------------------------------------------------------------------------
# 0. Settings: the few numbers a reviewer might want to change
# ---------------------------------------------------------------------------
TARGET_PRECISION = 0.99     # the specification asks for 99% probability that a prediction is correct
CLIP_LOW, CLIP_HIGH = 0.0001, 0.9999   # confidence 0 or 1 has no finite logit, so we clip to these
N_BOOTSTRAP = 1000          # resamples used to put an uncertainty range around each threshold
RANDOM_SEED = 42            # makes the bootstrap reproducible

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository folder
VAL_FILE = os.path.join(ROOT, "data", "raw", "birds", "validation_results.csv")
OUT_DIR = os.path.join(ROOT, "birds", "outputs")
FIG_DIR = os.path.join(ROOT, "birds", "figures")

# ---------------------------------------------------------------------------
# 1. Load the ornithologist's validation table
# ---------------------------------------------------------------------------
val = pd.read_csv(VAL_FILE)                                  # 551 rows: species, confidence, outcome (1 = correct)
val = val.rename(columns={"commonName": "species"})          # shorter, clearer column name
val["conf_clipped"] = val["confidence"].clip(CLIP_LOW, CLIP_HIGH)       # keep 1.0 scores usable (see header)
val["logit_conf"] = np.log(val["conf_clipped"] / (1 - val["conf_clipped"]))   # logit = ln(c / (1 - c)); Wood & Kahl's x-axis

# ---------------------------------------------------------------------------
# 2. Helper functions. Each one does one small job and is used below.
# ---------------------------------------------------------------------------
def logit(p):
    """Turn a probability (0-1) into the logit scale. logit(0.99) = 4.595."""
    return np.log(p / (1 - p))

def inv_logit(x):
    """Turn a logit value back into a probability / confidence between 0 and 1."""
    return 1 / (1 + np.exp(-x))

def fit_curve(x, y):
    """
    Fit the logistic regression  P(correct) = inv_logit(intercept + slope * x).
    x = logit of confidence, y = 1/0 correct/wrong.
    Returns (intercept, slope). Returns (None, None) if the fit cannot be computed.
    """
    design = sm.add_constant(x)                      # adds the column of 1s for the intercept
    try:
        model = sm.Logit(y, design).fit(disp=0)      # disp=0 just silences the printed iteration log
    except Exception:                                 # statsmodels raises an error on perfect separation
        return None, None
    if not model.mle_retvals.get("converged", False):   # the optimiser gave up: no trustworthy curve
        return None, None
    params = np.asarray(model.params)                # [intercept, slope]
    return float(params[0]), float(params[1])

def threshold_from_curve(intercept, slope, p=TARGET_PRECISION):
    """
    Solve the fitted curve for the x where P(correct) = p, then convert to a confidence.
    This is Wood & Kahl's formula: threshold_logit = (logit(p) - intercept) / slope.
    Returns (threshold_logit, threshold_confidence). A solution above CLIP_HIGH (the cap used
    for the logit) is returned as None: no checked clip can sit that high, so it is not usable.
    """
    if slope is None or slope <= 0:                  # a flat or downward curve: no upward crossing to solve for
        return None, None
    t_logit = (logit(p) - intercept) / slope
    t_conf = inv_logit(t_logit)
    if t_conf > CLIP_HIGH:                           # 0.99 is only reached above the logit cap, beyond any checked clip
        return t_logit, None
    return t_logit, t_conf

def precision_lower_bound(n_correct, n_total, confidence_level=0.95):
    """
    One-sided exact binomial (Clopper-Pearson) lower bound on precision.
    Example: 150 correct of 150 -> 0.980 (we are 95% sure precision is at least 98%).
    This is the formal version of the 'rule of three' (3/n ~ 0.02 for n = 150).
    """
    if n_total == 0 or n_correct == 0:               # nothing above the threshold: undefined; all wrong: the bound is 0
        return np.nan if n_total == 0 else 0.0
    if n_correct == n_total:                         # all correct: closed form
        return (1 - confidence_level) ** (1 / n_total)
    return beta.ppf(1 - confidence_level, n_correct, n_total - n_correct + 1)

def bootstrap_threshold(x, y, n_boot=N_BOOTSTRAP, seed=RANDOM_SEED):
    """
    Uncertainty around the threshold: resample the checked clips with replacement, refit,
    recompute the threshold, repeat n_boot times, and return the 2.5% and 97.5% values.
    Resamples where the curve cannot be fitted or cannot reach 0.99 are skipped and counted.
    """
    rng = np.random.default_rng(seed)
    results = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(x), len(x))        # pick len(x) clips at random, with replacement
        b0, b1 = fit_curve(x[idx], y[idx])
        _, t_conf = threshold_from_curve(b0, b1)
        if t_conf is not None:
            results.append(t_conf)
    if len(results) < n_boot * 0.5:                  # if most resamples fail, the range is not trustworthy
        return np.nan, np.nan, len(results)
    return float(np.percentile(results, 2.5)), float(np.percentile(results, 97.5)), len(results)

# ---------------------------------------------------------------------------
# 3. Fit one species at a time and record the decision
# ---------------------------------------------------------------------------
rows = []                                            # one dictionary per species, turned into a table at the end
curves = {}                                          # the fitted (intercept, slope) per species, for the figure

for species, grp in val.groupby("species"):
    x = grp["logit_conf"].to_numpy()                 # logit confidence of each checked clip
    y = grp["outcome"].to_numpy()                    # 1 = ornithologist said correct, 0 = wrong
    n, n_correct = len(y), int(y.sum())

    if n_correct == n or n_correct == 0:
        # CASE A: every clip correct (or every clip wrong). The S-curve has no step to find,
        # so logistic regression has no finite answer. Use the empirical rule instead:
        # the lowest confidence that was actually checked and found correct.
        method = "empirical: all validated clips correct" if n_correct == n else "no correct clips"
        b0 = b1 = None
        t_logit = None
        t_conf = float(grp["confidence"].min()) if n_correct == n else None
        ci_low = ci_high = np.nan
        n_boot_ok = 0
    else:
        # CASE B: the normal Wood & Kahl path.
        method = "logistic regression (Wood & Kahl 2024)"
        b0, b1 = fit_curve(x, y)
        t_logit, t_conf = threshold_from_curve(b0, b1)
        ci_low, ci_high, n_boot_ok = bootstrap_threshold(x, y)
        if t_conf is None:
            method += "; 0.99 not reachable below confidence 1.0 -> no threshold"

    # How many checked clips sit at or above the chosen threshold, and how many were correct?
    # This is the plain-counting evidence behind the threshold (the clips were selected by it).
    if t_conf is not None:
        above = grp[grp["confidence"] >= t_conf]
        n_above, k_above = len(above), int(above["outcome"].sum())
    else:
        n_above = k_above = 0

    # Safety rule: a threshold that no validated clip actually sits above is an extrapolation of
    # the curve, not evidence. We do not use such a threshold to create observations.
    if t_conf is not None and n_above == 0:
        method += "; curve reaches 0.99 only at {:.3f}, above every validated clip -> unsupported, not used".format(t_conf)
        t_conf = None

    rows.append({
        "species": species,
        "n_validated": n,
        "n_correct": n_correct,
        "method": method,
        "intercept": b0,
        "slope": b1,
        "threshold_logit": t_logit,
        "threshold_confidence": t_conf,
        "threshold_ci95_low": ci_low,
        "threshold_ci95_high": ci_high,
        "bootstrap_fits_ok": n_boot_ok,
        "validated_at_or_above_threshold": n_above,
        "correct_at_or_above_threshold": k_above,
        "precision_lower_bound_95": precision_lower_bound(k_above, n_above),
    })
    curves[species] = (b0, b1, t_conf)

thresholds = pd.DataFrame(rows)

# A one-line plain-language verdict per species, so the table reads without the numbers.
def verdict(r):
    if r["threshold_confidence"] is None or pd.isna(r["threshold_confidence"]):
        if "unsupported" in r["method"]:
            return ("Curve reaches 99% only above every validated clip; no evidence at that score, "
                    "so no observations are assigned. Needs validation of high-confidence clips.")
        return "No observations possible: curve never reaches 99% within the score range."
    if r["method"].startswith("empirical"):
        return (f"All {r['n_validated']} checked clips correct; threshold = lowest checked score "
                f"({r['threshold_confidence']:.3f}). Checked clips support precision >= "
                f"{r['precision_lower_bound_95']:.3f}, not 0.99; more validation needed to support 0.99.")
    return (f"Curve reaches 99% at confidence {r['threshold_confidence']:.3f} "
            f"(95% range {r['threshold_ci95_low']:.3f} to {r['threshold_ci95_high']:.3f}).")

thresholds["verdict"] = thresholds.apply(verdict, axis=1)   # apply = run the function on every row
thresholds.to_csv(os.path.join(OUT_DIR, "species_thresholds.csv"), index=False)

# ---------------------------------------------------------------------------
# 4. Correct / checked per 0.1 confidence bin: the simple table behind the curves
# ---------------------------------------------------------------------------
val["bin"] = (val["confidence"] * 10).astype(int).clip(upper=9) / 10   # 0.1, 0.2, ... 0.9 (0.9 bin includes 1.0)
bins = (val.groupby(["species", "bin"])["outcome"]
           .agg(checked="size", correct="sum")                 # how many checked, how many correct
           .reset_index())
bins["share_correct"] = bins["correct"] / bins["checked"]
bins.to_csv(os.path.join(OUT_DIR, "validation_by_bin.csv"), index=False)

# ---------------------------------------------------------------------------
# 5. Figure: the checked clips, the fitted curve, the 0.99 line and the threshold
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(2, 2, figsize=(11, 8), sharex=True, sharey=True)
grid = np.linspace(0.02, 0.9999, 400)                       # confidence values to draw the curve on
rng = np.random.default_rng(RANDOM_SEED)
for ax, (species, grp) in zip(axes.ravel(), val.groupby("species")):
    jitter = rng.uniform(-0.03, 0.03, len(grp))              # nudge the 0/1 points so they do not hide each other
    ax.scatter(grp["confidence"], grp["outcome"] + jitter, s=14, alpha=0.5,
               color=np.where(grp["outcome"] == 1, "#2E5E8C", "#993C1D"))
    b0, b1, t_conf = curves[species]
    if b0 is not None:                                        # draw the curve only where one exists
        ax.plot(grid, inv_logit(b0 + b1 * np.log(grid / (1 - grid))), color="black", lw=2)
    ax.axhline(TARGET_PRECISION, color="grey", ls="--", lw=1)
    r = thresholds.set_index("species").loc[species]
    if t_conf is not None:
        ax.axvline(t_conf, color="#B8860B", lw=2)
        ax.text(t_conf + 0.02, 0.5, f"threshold {t_conf:.3f}" + ("\n(lowest checked clip;\nall correct, no curve)" if b0 is None else ""), color="#B8860B", fontsize=10)
    elif "unsupported" in r["method"]:
        ax.text(0.45, 0.55, f"no threshold used:\ncurve reaches 0.99 only at {inv_logit((logit(TARGET_PRECISION) - b0) / b1):.3f},"
                "\nabove every validated clip", ha="center", fontsize=10, color="#993C1D")
    else:
        ax.text(0.5, 0.5, "no threshold:\ncurve never reaches 0.99", ha="center", fontsize=10, color="#993C1D")
    ax.set_title(f"{species}  (n = {r.n_validated}, correct = {r.n_correct})", fontsize=11)
    ax.set_ylim(-0.1, 1.1)
for ax in axes[1]:
    ax.set_xlabel("BirdNET confidence")
for ax in axes[:, 0]:
    ax.set_ylabel("Pr(prediction is correct)")
fig.suptitle("Validated clips (blue = correct, red = wrong), fitted logistic curve, 0.99 target (dashed) and threshold (gold)",
             fontsize=11)
fig.tight_layout()
fig.savefig(os.path.join(FIG_DIR, "fig1_precision_curves.png"), dpi=200)

# ---------------------------------------------------------------------------
# 6. Print the decision table so the run log shows the result
# ---------------------------------------------------------------------------
pd.set_option("display.width", 200)
print(thresholds[["species", "n_validated", "n_correct", "threshold_confidence",
                  "threshold_ci95_low", "threshold_ci95_high", "precision_lower_bound_95"]].round(3).to_string(index=False))
print()
for v in thresholds["verdict"]:
    print("-", v)
