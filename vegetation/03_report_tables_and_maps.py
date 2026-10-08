"""
WHAT THIS FILE DOES, IN PLAIN LANGUAGE
--------------------------------------
Builds the numbers, tables, figures and maps that the data quality report is written from.
It reads the cleaned tables (01) and the issues table (02) and writes:

  outputs/tables/*.md         Markdown tables pasted into DATA_QUALITY_REPORT.md by 04
  outputs/metrics.json        every number quoted in the report's prose, so the prose regenerates too
  outputs/survey_summary.csv, plot_summary.csv, design_coverage.csv, accumulation_by_quadrat.csv
  figures/fig_v1_effort_timeline.png      who surveyed what, when, and for how long (device clock)
  figures/fig_v2_richness_by_plot.png     identities per plot: list names, supplied names, still unknown
  figures/fig_v3_species_accumulation.png do 20 quadrats capture the plot? do 30 plots capture the area?
  figures/fig_v4_transect_geometry.png    transect length and midpoint offset against the SOP numbers
  figures/map_transects.png               map (overview + the plot with the most off-transect quadrats)

Populations: only retained (not rejected) submissions feed the summaries; issue counts are reported
for the retained population. Richness is counted on field identities (source list + entity UUID),
not on display labels, because one entity can carry two labels (its typed name and its placeholder).
"""

import os
import json
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "vegetation", "outputs")
TAB = os.path.join(OUT, "tables")
FIG = os.path.join(ROOT, "vegetation", "figures")
os.makedirs(TAB, exist_ok=True)
M = {}                                           # metrics quoted in the report prose; written to metrics.json at the end

surveys = pd.read_csv(os.path.join(OUT, "surveys_clean.csv"), parse_dates=["start_time", "end_time", "submission_date"])
quadrats = pd.read_csv(os.path.join(OUT, "quadrats_clean.csv"))
records = pd.read_csv(os.path.join(OUT, "species_records_long.csv"))
plots = pd.read_csv(os.path.join(OUT, "plots_clean.csv"))
centroids = pd.read_csv(os.path.join(OUT, "centroids_clean.csv"))
issues = pd.read_csv(os.path.join(OUT, "qa_issues.csv"))
qa_summary = pd.read_csv(os.path.join(OUT, "qa_summary.csv"))
surveys["review_state"] = surveys["review_state"].fillna("")
for c in ("supplied_name", "supplied_note", "identity_type"):
    records[c] = records[c].fillna("")

# retained population only; records with a blank label are dropped; an identity entered twice in one quadrat counts once
acc = surveys[surveys.population == "retained"].copy()
acc_keys = set(acc.submission_key)
quad = quadrats[quadrats.submission_key.isin(acc_keys)].copy()
rec = records[records.submission_key.isin(acc_keys) & records.identity_key.notna()].copy()
rec = rec.drop_duplicates(["quadrat_key", "identity_key"])
ret_issues = issues[issues.population != "rejected"]

def to_md(df, path, floatfmt=".2f"):
    """Save a DataFrame as a Markdown table."""
    with open(os.path.join(TAB, path), "w") as f:
        f.write(df.to_markdown(index=False, floatfmt=floatfmt))

def short(name):
    """'SavMon_LW_Plot_05' -> 'Plot_05'."""
    return name.replace("SavMon_LW_", "")

# ---------------------------------------------------------------------------
# A. SURVEY-LEVEL SUMMARY: one row per retained plot visit
# ---------------------------------------------------------------------------
# issues attached to a submission directly (survey level) and through its quadrats (descendants)
direct = ret_issues[(ret_issues.level == "survey") & ret_issues.severity.isin(["error", "warning"])].groupby("item_key").size()
q_parent = pd.concat([quadrats.set_index("quadrat_key").submission_key, records.set_index("record_key").submission_key])
desc = (ret_issues[(ret_issues.level == "quadrat") & ret_issues.severity.isin(["error", "warning"])]
        .assign(sub=lambda d: d.item_key.map(q_parent)).groupby("sub").size())
ident = rec.groupby("submission_key").agg(
    identity_count=("identity_key", "nunique"),
    label_count=("species_label", "nunique"),
    identities_named=("identity_key", lambda s: rec.loc[s.index].groupby("identity_key").has_supplied_name.first().sum()),
    quadrats_with_records=("quadrat_key", "nunique"))
sv = acc.merge(ident, on="submission_key", how="left")
sv["date"] = sv.start_clock_device.str[:10]
sv["start_device_clock"] = sv.start_clock_device.str[11:16]
sv["quadrats_with_herbs"] = sv.submission_key.map(quad[quad.herbs_present == "yes"].groupby("submission_key").size()).fillna(0).astype(int)
sv["identities_unknown"] = sv.identity_count - sv.identities_named
sv["issues_direct"] = sv.submission_key.map(direct).fillna(0).astype(int)
sv["issues_quadrats"] = sv.submission_key.map(desc).fillna(0).astype(int)
sv["plot"] = sv.plot_name.map(short)
survey_summary = sv[["plot", "date", "start_device_clock", "recorder", "team_size", "duration_min", "quadrats_with_herbs",
                     "quadrats_with_species_form", "quadrats_with_records", "label_count", "identity_count", "identities_named",
                     "identities_unknown", "issues_direct", "issues_quadrats"]].sort_values(["date", "start_device_clock"])
survey_summary["duration_min"] = survey_summary.duration_min.round(0).astype(int)
survey_summary.to_csv(os.path.join(OUT, "survey_summary.csv"), index=False)
to_md(survey_summary, "a_survey_summary.md", floatfmt=".1f")

by_identity = rec.groupby("identity_key").agg(named=("has_supplied_name", "first"), itype=("identity_type", "first"), label_is_ph=("label_is_placeholder", "max"))
M.update({
    "n_submissions": len(surveys), "n_rejected": int((surveys.population == "rejected").sum()), "n_retained": len(acc),
    "n_primary_surveyed": int(acc.plot_name.isin(plots[plots.sample_status == "primary"].plot_name).sum()),
    "n_backup_surveyed": int(acc.plot_name.isin(plots[plots.sample_status == "backup"].plot_name).sum()),
    "date_first": acc.start_clock_device.min()[:10], "date_last": acc.start_clock_device.max()[:10],
    "recorders": ", ".join(f"{k} ({v})" for k, v in acc.recorder.value_counts().items()),
    "n_quadrats": len(quad), "n_quadrats_herbs": int((quad.herbs_present == "yes").sum()), "n_records": len(rec),
    "label_count": int(rec.species_label.nunique()), "identity_count": int(rec.identity_key.nunique()),
    "identities_list": int((by_identity.itype == "project_list").sum()), "identities_typed": int((by_identity.itype == "missing_species").sum()),
    "identities_placeholder": int((by_identity.itype == "unknown_species").sum()),
    "identities_named": int(by_identity.named.sum()), "identities_unknown": int((~by_identity.named).sum()),
    "placeholder_labels": int(rec.loc[rec.label_is_placeholder, "species_label"].nunique()),
    "alias_entities": int((rec.groupby("identity_key").species_label.nunique() > 1).sum()),
    "survey_minutes": int(round(acc.duration_min.sum())), "person_hours": round((acc.duration_min * acc.team_size).sum() / 60, 1),
    "person_hours_per_plot": round((acc.duration_min * acc.team_size).sum() / 60 / len(acc), 1),
    "device_offset": surveys.device_utc_offset.mode().iloc[0],
    "s04_retained": int(((ret_issues.check_id == "S04")).sum()), "s04_all": int((issues.check_id == "S04").sum()),
})
overall = pd.DataFrame({
    "measure": ["Submissions received", "Rejected in ODK review (excluded)", "Retained surveys (unreviewed, not rejected)", "Plots surveyed (primary / backup)",
                "Survey dates (device clock)", "Recorders", "Quadrats in retained surveys", "Quadrats with herbaceous species",
                "Species records (quadrat x identity, counted once per quadrat)", "Distinct recorded labels", "Distinct field identities (list + entity UUID)",
                "of which from the project list", "of which typed names created in the field", "of which placeholders created in the field",
                "Identities with a name (list name or supplied identification)", "Identities still 'Unknown'",
                "Form-open time, retained surveys (minutes)", "Nominal person-hours (minutes x team size / 60)"],
    "value": [M["n_submissions"], M["n_rejected"], M["n_retained"], f"{M['n_primary_surveyed']} / {M['n_backup_surveyed']}",
              f"{M['date_first']} to {M['date_last']}", M["recorders"], M["n_quadrats"], M["n_quadrats_herbs"], M["n_records"],
              M["label_count"], M["identity_count"], M["identities_list"], M["identities_typed"], M["identities_placeholder"],
              M["identities_named"], M["identities_unknown"], M["survey_minutes"], M["person_hours"]]})
to_md(overall, "a_overall.md")

# ---------------------------------------------------------------------------
# B. PLOT-LEVEL SUMMARY: registration context + geometry + richness/diversity on identities
# ---------------------------------------------------------------------------
def shannon(counts):
    """Shannon diversity H = -sum(p ln p) from frequency counts (how many quadrats each identity occupied)."""
    p = np.asarray(counts, dtype=float); p = p / p.sum()
    return float(-(p * np.log(p)).sum()) if len(p) else np.nan

freq = rec.groupby(["plot_name", "identity_key"]).agg(n_quadrats=("quadrat_key", "size"), named=("has_supplied_name", "first")).reset_index()
div = freq.groupby("plot_name").apply(lambda g: pd.Series({
    "identity_count": g.identity_key.nunique(),
    "identities_named": int(g.named.sum()),
    "shannon_identities": shannon(g.n_quadrats),
    "mean_identities_per_quadrat": g.n_quadrats.sum() / 20,
}), include_groups=False).reset_index()
labels_per_plot = rec.groupby("plot_name").species_label.nunique().rename("label_count")
pl = plots.merge(div, on="plot_name", how="left").merge(labels_per_plot, on="plot_name", how="left")
pl["plot"] = pl.plot_name.map(short)
pl["surveyed"] = pl.plot_name.isin(acc.plot_name)
pl["geometry_flags"] = pl.plot_name.map(ret_issues[ret_issues.check_id.isin(["P02", "P03", "P04"]) & (ret_issues.severity != "info")].groupby("plot_name").size()).fillna(0).astype(int)
pl["quadrats_off_transect"] = pl.plot_name.map(ret_issues[ret_issues.check_id == "Q02"].groupby("plot_name").size()).fillna(0).astype(int)
plot_summary = pl[["plot", "sample_status", "is_viable", "surveyed", "ecosystem_type", "canopy_structure", "canopy_height_m", "soil_type", "disturbance",
                   "transect_length_m", "polyline_length_m", "midpoint_offset_m", "midpoint_off_line_m", "bearing_a_to_b_deg", "geometry_flags",
                   "quadrats_off_transect", "label_count", "identity_count", "identities_named", "mean_identities_per_quadrat", "shannon_identities"]]
plot_summary.to_csv(os.path.join(OUT, "plot_summary.csv"), index=False)
to_md(plot_summary.round(2), "b_plot_summary.md", floatfmt=".1f")

viable = plots[plots.is_viable == "yes"]
dist = viable.disturbance.fillna("")
ctx = pd.DataFrame({
    "field": ["Woody plants present", "Water nearby", "Canopy structure", "Canopy height (m)", "Soil type", "Ecosystem recorded",
              "Disturbance recorded", "Ground cover selections (overlapping)", "Dominant woody species listed (overlapping)"],
    "result among the viable registered plots": [
        ", ".join(f"{k} {v}" for k, v in viable.woody_present.value_counts().items()),
        ", ".join(f"{k} {v}" for k, v in viable.water_present.value_counts().items()),
        ", ".join(f"{k} {v}" for k, v in viable.canopy_structure.value_counts().items()),
        ", ".join(f"{int(k)} m: {v}" for k, v in sorted(viable.canopy_height_m.value_counts().items())),
        ", ".join(f"{k} {v}" for k, v in viable.soil_type.value_counts().items()),
        ", ".join(f"{k} {v}" for k, v in viable.ecosystem_type.value_counts().items()),
        f"none {int((dist == 'none').sum())}; wildlife {int(dist.str.contains('wildlife').sum())}; human or livestock {int(dist.str.contains('human').sum())}; both {int((dist.str.contains('wildlife') & dist.str.contains('human')).sum())}",
        ", ".join(f"{k} {v}" for k, v in viable.ground_cover.fillna("").str.split().explode().value_counts().items()),
        ", ".join(f"{k} {v}" for k, v in viable.dominant_woody.fillna("").str.split(", ").explode().replace("", np.nan).dropna().value_counts().items()),
    ]})
to_md(ctx, "b_registration_context.md")
M.update({"n_viable": len(viable), "dist_none": int((dist == "none").sum()), "dist_any": int((dist != "none").sum()),
          "dist_wildlife": int(dist.str.contains("wildlife").sum()), "dist_human": int(dist.str.contains("human").sum()),
          "dist_both": int((dist.str.contains("wildlife") & dist.str.contains("human")).sum()),
          "length_min": round(viable.transect_length_m.min(), 1), "length_max": round(viable.transect_length_m.max(), 1),
          "length_warn": int((abs(viable.transect_length_m - 50) > 5).sum()), "length_err": int((abs(viable.transect_length_m - 50) > 10).sum()),
          "offset_max": round(viable.midpoint_offset_m.max(), 1), "offset_max_plot": short(viable.loc[viable.midpoint_offset_m.idxmax(), "plot_name"]),
          "offset_over25": int((viable.midpoint_offset_m > 25).sum()), "offset_15_25": int(((viable.midpoint_offset_m > 15) & (viable.midpoint_offset_m <= 25)).sum()),
          "bearing_min": round(viable.bearing_a_to_b_deg.min()), "bearing_max": round(viable.bearing_a_to_b_deg.max()),
          "midpoint_off_line_n": int((viable.midpoint_off_line_m > 5).sum()), "midpoint_off_line_max": round(viable.midpoint_off_line_m.max(), 1),
          "richness_min": int(plot_summary.identity_count.min()), "richness_max": int(plot_summary.identity_count.max()),
          "richness_min_plot": plot_summary.loc[plot_summary.identity_count.idxmin(), "plot"], "richness_max_plot": plot_summary.loc[plot_summary.identity_count.idxmax(), "plot"],
          "q02_retained": int((ret_issues.check_id == "Q02").sum()), "q02_retained_err": int(((ret_issues.check_id == "Q02") & (ret_issues.severity == "error")).sum()),
          "q02_all": int((issues.check_id == "Q02").sum())})

# ---------------------------------------------------------------------------
# C. SAMPLING EFFORT: design coverage, accumulation
# ---------------------------------------------------------------------------
cov = (centroids.groupby(["stratum", "sample_status"])
       .agg(prescribed=("plot_name", "size"), registered=("registered", "sum"), viable=("registered_viable", "sum"), surveyed=("surveyed", "sum")).reset_index())
cov.to_csv(os.path.join(OUT, "design_coverage.csv"), index=False)
to_md(cov, "c_design_coverage.md", floatfmt=".0f")
prim = centroids[centroids.sample_status == "primary"]
M.update({"n_primary_design": len(prim), "n_primary_surveyed_design": int(prim.surveyed.sum()),
          "shrub_primary": int((prim.stratum == "shrubland").sum()), "shrub_backup": int(((centroids.stratum == "shrubland") & (centroids.sample_status == "backup")).sum()),
          "year_missing": int(centroids.design_year.isna().sum())})

# accumulation within a plot: cumulative distinct identities after quadrat 1, 2, ... 20, in the recorded order
rows = []
for key, g in rec.groupby("submission_key"):
    seen = set()
    for qn in range(1, 21):
        seen |= set(g.loc[g.quadrat_number == qn, "identity_key"])
        rows.append({"submission_key": key, "plot": short(g.plot_name.iloc[0]), "quadrat": qn, "cum_identities": len(seen)})
accum = pd.DataFrame(rows)
accum.to_csv(os.path.join(OUT, "accumulation_by_quadrat.csv"), index=False)
final = accum[accum.quadrat == 20].set_index("submission_key").cum_identities
at15 = accum[accum.quadrat == 15].set_index("submission_key").cum_identities
sat = pd.DataFrame({"plot": accum[accum.quadrat == 20].set_index("submission_key")["plot"],
                    "identities_after_20": final, "share_found_by_quadrat_15": (at15 / final).round(2),
                    "new_identities_in_last_5_quadrats": final - at15}).sort_values("share_found_by_quadrat_15")
to_md(sat, "c_saturation_by_plot.md")
M.update({"share15_mean": round(float((at15 / final).mean()) * 100), "share15_median": round(float((at15 / final).median()) * 100),
          "share15_min": round(float((at15 / final).min()) * 100), "late_plots": int(((final - at15) > 0).sum()), "n_plots_acc": len(final)})

# accumulation across plots: average over 200 random plot orders (sample-based, plot = sampling unit)
plot_sets = [set(g.identity_key) for _, g in rec.groupby("submission_key")]
rng = np.random.default_rng(42)
curves = []
for _ in range(200):
    order = rng.permutation(len(plot_sets)); seen = set(); c = []
    for i in order:
        seen |= plot_sets[i]; c.append(len(seen))
    curves.append(c)
across = np.mean(curves, axis=0)
M.update({"across25": round(float(across[24])), "across30": round(float(across[-1]))})

# ---------------------------------------------------------------------------
# D. FIGURES
# ---------------------------------------------------------------------------
# fig_v1: effort timeline on the device clock (as recorded, offset +02:00), one bar per submission
fig, ax = plt.subplots(figsize=(10, 4))
colors = {"Grace": "#2E5E8C", "Sam": "#993C1D"}
dev = pd.to_datetime(surveys.start_clock_device)
dev_end = dev + (surveys.end_time - surveys.start_time)
for r, t0, t1 in zip(surveys.itertuples(), dev, dev_end):
    y = t0.normalize(); x0 = t0.hour + t0.minute / 60; x1 = t1.hour + t1.minute / 60
    ax.plot([x0, x1], [y, y], lw=6, color=colors.get(r.recorder, "grey"), alpha=0.35 if r.review_state == "rejected" else 0.9, solid_capstyle="butt")
    ax.text((x0 + x1) / 2, y, r.plot_name.replace("SavMon_LW_Plot_", "P") + (" (rej.)" if r.review_state == "rejected" else ""),
            fontsize=7, ha="center", va="center", color="white" if r.review_state != "rejected" else "black")
days = sorted(set(dev.dt.normalize()))
ax.set_yticks(days); ax.set_yticklabels([d.strftime("%a %d %b") for d in days], fontsize=8); ax.invert_yaxis()
ax.set_xlabel(f"time of day on the device clock (recorded offset {M['device_offset']})"); ax.set_xlim(7.5, 18.5)
for name, c in colors.items():
    ax.plot([], [], lw=6, color=c, label=f"recorder: {name}")
ax.legend(frameon=False, fontsize=8, loc="lower right")
ax.set_title("Form-open time per submission, start to end (faded = rejected)", fontsize=10)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_v1_effort_timeline.png"), dpi=200); plt.close(fig)

# fig_v2: identities per plot: list names, supplied names for field entities, still unknown
ps = plot_summary[plot_summary.surveyed].sort_values("identity_count", ascending=False)
per_plot_type = freq.merge(by_identity.reset_index()[["identity_key", "itype"]], on="identity_key")
listc = per_plot_type[per_plot_type.itype == "project_list"].groupby("plot_name").size()
ps = ps.assign(list_names=ps["plot"].map(lambda p: listc.get("SavMon_LW_" + p, 0)))
ps["supplied_names"] = ps.identities_named - ps.list_names
ps["unknown"] = ps.identity_count - ps.identities_named
fig, ax = plt.subplots(figsize=(10, 4))
ax.bar(ps["plot"], ps.list_names, color="#1D7D5A", label="named from the project list")
ax.bar(ps["plot"], ps.supplied_names, bottom=ps.list_names, color="#5B7FA6", label="field entity with a supplied identification")
ax.bar(ps["plot"], ps.unknown, bottom=ps.list_names + ps.supplied_names, color="#B8860B", label="field entity still 'Unknown'")
ax.set_ylabel("field identities in 20 quadrats"); ax.tick_params(axis="x", rotation=90, labelsize=8)
ax.legend(frameon=False, fontsize=9); ax.set_title("Herbaceous richness per plot (field identities, not labels) and how much is identified", fontsize=10)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_v2_richness_by_plot.png"), dpi=200); plt.close(fig)

# fig_v3: accumulation curves
fig, axes = plt.subplots(1, 2, figsize=(11, 4))
for key, g in accum.groupby("submission_key"):
    axes[0].plot(g.quadrat, g.cum_identities / g.cum_identities.max(), color="#2E5E8C", alpha=0.25, lw=1)
mean_curve = accum.assign(frac=accum.cum_identities / accum.submission_key.map(final)).groupby("quadrat").frac.mean()
axes[0].plot(mean_curve.index, mean_curve.values, color="#12324f", lw=3, label=f"mean of {len(final)} plots")
axes[0].axvline(15, color="grey", ls=":"); axes[0].set_xlabel("quadrats surveyed, in recorded order"); axes[0].set_ylabel("share of identities found by quadrat 20")
axes[0].set_title("Within a plot: identities found after n quadrats", fontsize=10); axes[0].legend(frameon=False, fontsize=9)
axes[1].plot(range(1, len(across) + 1), across, color="#12324f", lw=3)
axes[1].set_xlabel("plots surveyed (random order, mean of 200 orders)"); axes[1].set_ylabel("distinct identities across plots")
axes[1].set_title("Across the sampled savanna: still rising at 30 plots", fontsize=10)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_v3_species_accumulation.png"), dpi=200); plt.close(fig)

# fig_v4: transect geometry vs the SOP numbers (bands are analysis tolerances, see 02 CONFIG)
geo = viable.sort_values("plot_name")
fig, axes = plt.subplots(1, 2, figsize=(11, 4))
x = geo.plot_name.str.replace("SavMon_LW_Plot_", "")
axes[0].bar(x, geo.transect_length_m, color="#5B7FA6", label="straight A to B"); axes[0].scatter(x, geo.polyline_length_m, color="#12324f", s=14, zorder=3, label="A-mid-B polyline")
axes[0].axhline(50, color="black", lw=1); axes[0].axhspan(45, 55, color="grey", alpha=0.15)
axes[0].set_ylabel("distance (m)"); axes[0].set_title("Transect length vs the 50 m SOP (band = 45-55 m warning tolerance)", fontsize=10); axes[0].legend(frameon=False, fontsize=8)
axes[1].bar(x, geo.midpoint_offset_m, color="#993C1D"); axes[1].axhline(25, color="black", lw=1)
axes[1].set_ylabel("midpoint offset from prescribed point (m)"); axes[1].set_title("Midpoint offset vs the 25 m SOP limit", fontsize=10)
for ax in axes:
    ax.tick_params(axis="x", rotation=90, labelsize=8)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_v4_transect_geometry.png"), dpi=200); plt.close(fig)

# ---------------------------------------------------------------------------
# E. MAP: all prescribed points by status, and the plot with the most off-transect quadrats
# ---------------------------------------------------------------------------
def status_of(r):
    """One phrase for how each prescribed point ended up in these exports."""
    if r.surveyed and r.sample_status == "backup": return "backup surveyed"
    if r.surveyed: return "surveyed"
    if r.registered and not r.registered_viable: return "not viable"
    if r.registered_viable: return "registered, not surveyed"
    return "primary, no registration" if r.sample_status == "primary" else "backup, unused"

cen = gpd.GeoDataFrame(centroids.assign(status=centroids.apply(status_of, axis=1)),
                       geometry=[Point(lon, lat) for lon, lat in zip(centroids.design_lon, centroids.design_lat)], crs="EPSG:4326")
lines = gpd.GeoDataFrame(viable[["plot_name", "transect_length_m", "polyline_length_m", "midpoint_offset_m"]],
                         geometry=[LineString([(r.a_lon, r.a_lat), (r.mid_lon, r.mid_lat), (r.b_lon, r.b_lat)]) for r in viable.itertuples()], crs="EPSG:4326")
qpts = gpd.GeoDataFrame(quad, geometry=[Point(lon, lat) for lon, lat in zip(quad.lon, quad.lat)], crs="EPSG:4326")
q02 = set(ret_issues[ret_issues.check_id == "Q02"].item_key)
qpts["off_transect"] = qpts.quadrat_key.isin(q02)
style = {"surveyed": ("#1D7D5A", "o"), "backup surveyed": ("#B8860B", "o"), "not viable": ("#993C1D", "X"),
         "registered, not surveyed": ("#5B7FA6", "o"), "primary, no registration": ("#993C1D", "s"), "backup, unused": ("#bbbbbb", "s")}
utm = "EPSG:32637"                                       # metres, UTM zone 37N (Kenya), so the zoomed panel has true distances
cen_m, lines_m, q_m = cen.to_crs(utm), lines.to_crs(utm), qpts.to_crs(utm)
M["status_counts"] = cen.status.value_counts().to_dict()

zoom = ret_issues[ret_issues.check_id == "Q02"].plot_name.value_counts().idxmax()   # the plot with the most off-transect quadrats
qz_rows = ret_issues[(ret_issues.check_id == "Q02") & (ret_issues.plot_name == zoom)].detail.str.extract(r": (\d+) m from A-mid-B")[0].astype(float)
M.update({"zoom_plot": short(zoom), "zoom_n_flagged": int(len(qz_rows)), "zoom_d_min": int(qz_rows.min()), "zoom_d_max": int(qz_rows.max())})

fig, axes = plt.subplots(1, 2, figsize=(14, 5.2), gridspec_kw={"width_ratios": [2.1, 1]})
for st, (c, m) in style.items():
    sub = cen_m[cen_m.status == st]
    if len(sub):
        axes[0].scatter(sub.geometry.x / 1000, sub.geometry.y / 1000, c=c, marker=m, s=60, edgecolor="black", lw=0.5, label=f"{st} ({len(sub)})", zorder=3)
shrub = cen_m[cen_m.stratum == "shrubland"]
axes[0].scatter(shrub.geometry.x / 1000, shrub.geometry.y / 1000, facecolors="none", edgecolors="#993C1D", s=160, lw=1.2, label="shrubland stratum", zorder=4)
for r in cen_m.itertuples():
    axes[0].annotate(r.plot_name.replace("SavMon_LW_Plot_", ""), (r.geometry.x / 1000, r.geometry.y / 1000), fontsize=6, xytext=(3, 3), textcoords="offset points")
axes[0].set_xlabel("UTM 37N easting (km)"); axes[0].set_ylabel("UTM 37N northing (km)"); axes[0].set_aspect("equal")
axes[0].legend(frameon=False, fontsize=8, loc="upper left"); axes[0].set_title("All 51 prescribed plot locations and their status in these exports", fontsize=10)

lz = lines_m[lines_m.plot_name == zoom]; qz = q_m[q_m.plot_name == zoom]; cz = cen_m[cen_m.plot_name == zoom]
lz.plot(ax=axes[1], color="black", lw=2, zorder=2)
axes[1].scatter(qz.geometry.x, qz.geometry.y, c=np.where(qz.off_transect, "#993C1D", "#1D7D5A"), s=40, zorder=3, edgecolor="black", lw=0.4)
for r in qz.itertuples():
    axes[1].annotate(str(r.quadrat_number), (r.geometry.x, r.geometry.y), fontsize=6, xytext=(3, 2), textcoords="offset points")
axes[1].scatter(cz.geometry.x, cz.geometry.y, marker="*", s=220, c="#B8860B", edgecolor="black", zorder=4, label="prescribed centroid")
axes[1].add_patch(plt.Circle((cz.geometry.x.iloc[0], cz.geometry.y.iloc[0]), 25, fill=False, ls="--", color="#B8860B"))
mid = lz.geometry.iloc[0].coords[1]
axes[1].annotate("registered midpoint", mid, fontsize=8, xytext=(5, -10), textcoords="offset points")
axes[1].set_aspect("equal")
axes[1].set_title(f"{short(zoom)}: registered A-mid-B (black) and its 20 quadrats\nred = over 10 m from the transect (Q02); dashed = 25 m midpoint limit", fontsize=9)
axes[1].set_xlabel("easting (m)"); axes[1].set_ylabel("northing (m)"); axes[1].legend(frameon=False, fontsize=8, loc="lower right")
axes[1].ticklabel_format(useOffset=False, style="plain")
fig.tight_layout(); fig.savefig(os.path.join(FIG, "map_transects.png"), dpi=200); plt.close(fig)

# ---------------------------------------------------------------------------
# F. ISSUE COUNTS FOR THE REPORT, AND THE METRICS FILE
# ---------------------------------------------------------------------------
M.update({"issues_all": len(issues), "issues_retained": len(ret_issues), "errors_retained": int((ret_issues.severity == "error").sum()),
          "warnings_retained": int((ret_issues.severity == "warning").sum()), "info_retained": int((ret_issues.severity == "info").sum()),
          "n_rules": len(qa_summary), "n_rules_pass": int((qa_summary.status == "pass").sum()),
          "x01": int((ret_issues.check_id == "X01").sum()), "x03_fuzzy": int(((ret_issues.check_id == "X03") & (ret_issues.severity == "warning")).sum()),
          "x03_higher": int(((ret_issues.check_id == "X03") & (ret_issues.severity == "info")).sum()),
          "notes_n": int(rec[rec.supplied_note != ""].identity_key.nunique())})   # identities whose supplied identification carries a note (duplicate of, exclude)
with open(os.path.join(OUT, "metrics.json"), "w") as f:
    json.dump(M, f, indent=1, default=str)

print(open(os.path.join(TAB, "a_overall.md")).read())
print(); print({k: M[k] for k in ["share15_mean", "share15_median", "late_plots", "across25", "across30", "q02_retained", "zoom_plot", "zoom_d_min", "zoom_d_max", "alias_entities"]})
