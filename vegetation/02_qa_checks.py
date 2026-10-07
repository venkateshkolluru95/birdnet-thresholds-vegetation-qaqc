"""
WHAT THIS FILE DOES, IN PLAIN LANGUAGE
--------------------------------------
Runs the quality checks on the cleaned vegetation tables written by 01_load_and_join.py.
Every rule has an id (S = survey level, P = plot level, Q = quadrat level, X = species level) and
writes one row per problem found into a single "issues" table. Nothing is corrected: the
requirement is to flag, not to fix.

Each issue row carries two things reviewers need:
  * population: "retained" (the submission is not rejected in ODK Central), "rejected", or
    "shared" for plot, design and species findings that do not belong to one submission.
    The report counts the retained population; the catalogue keeps everything.
  * item_key: the exact record the finding is about, so it can be traced to its source row.

Severity: error = breaks an SOP rule or makes the record unusable; warning = needs a decision by
the field or data team; info = context, no action needed. Rules that found nothing are still listed
in the summary with status "pass".

INPUT : vegetation/outputs/{surveys,quadrats,species_records_long,plots,centroids}_clean.csv
OUTPUT: vegetation/outputs/qa_issues.csv     (one row per flagged item)
        vegetation/outputs/qa_summary.csv    (every rule: rows flagged, all exports and retained, or pass)
"""

import os
import re
import math
import requests                                 # one small web call per typed species name (GBIF name matching)
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "vegetation", "outputs")
ENT = os.path.join(ROOT, "data", "raw", "vegetation", "Entity lists")

surveys = pd.read_csv(os.path.join(OUT, "surveys_clean.csv"), parse_dates=["start_time", "end_time"])
quadrats = pd.read_csv(os.path.join(OUT, "quadrats_clean.csv"))
records = pd.read_csv(os.path.join(OUT, "species_records_long.csv"))
plots = pd.read_csv(os.path.join(OUT, "plots_clean.csv"))
centroids = pd.read_csv(os.path.join(OUT, "centroids_clean.csv"))
species_list = pd.read_csv(os.path.join(ENT, "species.csv"))

# Fill blanks so comparisons below are simple strings, never NaN
for df, cols in [(quadrats, ["additional_species_present", "list_species_ids"]), (surveys, ["review_state"]),
                 (plots, ["not_viable_reason"]), (records, ["species_label", "label_raw"])]:
    for c in cols:
        df[c] = df[c].fillna("").astype(str)

# The numbers the rules test against. SOP = stated in the two SOPs. CONFIG = tolerances I chose where the
# SOPs give none; they are analysis policy, not SOP requirements.
SOP = {
    "quadrats_per_plot": 20,          # Herbaceous SOP 3.1: fixed count of 20 quadrats
    "gps_accuracy_max_m": 5.0,        # both SOPs 4.2: geopoints with 5 m accuracy or better
    "midpoint_offset_max_m": 25.0,    # Registration SOP 5.5: midpoint cannot be moved more than 25 m
    "transect_length_m": 50.0,        # Registration SOP: 50 m belt transect
    "half_length_m": 25.0,            # endpoints 25 m either side of the midpoint
    "canonical_pattern": r"^[A-Z][a-z\-]+_[a-z\-]+$",   # Herbaceous SOP 5.7: Genus_species joined by an underscore
}
CONFIG = {
    "transect_length_warn_m": 5.0,    # warn beyond 45-55 m, error beyond 40-60 m
    "half_length_tolerance_m": 7.5,
    "midpoint_offset_warn_m": 15.0,   # warn at 15-25 m (inside the SOP limit), error above 25 m
    "orientation_tolerance_deg": 20,  # SOP says north-south first; rotation is allowed, so this is info only
    "quadrat_offline_warn_m": 10.0,   # quadrats sit within 2.5 m of the tape; this allows for GPS error on both sides
    "quadrat_offline_error_m": 25.0,
    "survey_min_minutes": 30,         # 20 quadrats in under 30 minutes is implausible
    "survey_max_minutes": 180,
}

issues = []                                     # every rule appends dictionaries here
sub_pop = surveys.set_index("submission_key")["population"]
quad_pop = quadrats.set_index("quadrat_key")["population"]
rec_pop = records.set_index("record_key")["population"]

def population_of(level, item_key):
    """Which population a finding belongs to: the submission's (retained/rejected) or shared."""
    if level == "survey":
        return sub_pop.get(item_key, "retained")
    if level == "quadrat":
        return quad_pop.get(item_key, rec_pop.get(item_key, "retained"))
    return "shared"

def flag(check_id, check_name, severity, level, plot_name, item_key, detail):
    """Record one problem. Called by every rule below."""
    issues.append({"check_id": check_id, "check_name": check_name, "severity": severity, "level": level,
                   "population": population_of(level, item_key), "plot_name": plot_name, "item_key": item_key, "detail": detail})

def haversine_m(lat1, lon1, lat2, lon2):
    """Distance in metres between two lat/lon points."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin(math.radians(lat2 - lat1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))

def dist_to_segment_m(lat, lon, lat1, lon1, lat2, lon2):
    """Shortest distance (m) from a point to the straight line between two points, on a flat local grid."""
    k = 111320.0                                             # metres per degree of latitude
    kx = k * math.cos(math.radians(lat))                     # metres per degree of longitude at this latitude
    px, py = (lon - lon1) * kx, (lat - lat1) * k
    sx, sy = (lon2 - lon1) * kx, (lat2 - lat1) * k
    seg_len2 = sx * sx + sy * sy
    t = 0 if seg_len2 == 0 else max(0, min(1, (px * sx + py * sy) / seg_len2))
    return math.hypot(px - t * sx, py - t * sy)

# ---------------------------------------------------------------------------
# SURVEY-LEVEL RULES (one survey = one submitted form = one plot visit)
# ---------------------------------------------------------------------------
def check_surveys():
    """S01 duplicates, S02 rejected, S03 quadrat count, S04 form count, S05 duration, S06 placeholders."""
    # S01: the same plot submitted more than once for the same survey
    for (plot, label), grp in surveys.groupby(["plot_name", "survey_label"]):
        if len(grp) > 1:
            unresolved = (grp.review_state != "rejected").sum() > 1      # more than one copy still counts
            for k in grp.submission_key:
                flag("S01", "duplicate submission for plot", "error" if unresolved else "info", "survey", plot, k,
                     f"{len(grp)} submissions; " + ("more than one copy still active" if unresolved else "resolved by ODK review state"))
    # S02: rejected submissions are excluded from every summary; listed so the exclusion is visible
    for r in surveys[surveys.review_state == "rejected"].itertuples():
        flag("S02", "rejected submission (excluded from summaries)", "info", "survey", r.plot_name, r.submission_key,
             f"recorder {r.recorder}, device clock {r.start_clock_device}, {r.duration_min:.0f} min")
    # S03: exactly 20 quadrats, numbered 1 to 20 once each (SOP)
    numbers = quadrats.groupby("submission_key")["quadrat_number"].apply(sorted)
    for r in surveys.itertuples():
        if r.quadrat_count != SOP["quadrats_per_plot"] or numbers.get(r.submission_key, []) != list(range(1, SOP["quadrats_per_plot"] + 1)):
            flag("S03", "quadrat count or numbering not 1 to 20", "error", "survey", r.plot_name, r.submission_key, f"{r.quadrat_count} quadrats")
    # S04: the form shows a 'quadrats with species' count on its final screen. Its calculation tests the list-species
    # field at the wrong nesting level, so it only counts quadrats with additional species (verified: equal in all 32).
    with_species = records[~records.label_blank].groupby("submission_key")["quadrat_key"].nunique()
    for r in surveys.itertuples():
        recount = int(with_species.get(r.submission_key, 0))
        if recount != r.quadrats_with_species_form:
            flag("S04", "form's end-of-survey species count differs from recount", "warning", "survey", r.plot_name, r.submission_key,
                 f"stored {r.quadrats_with_species_form}, recomputed {recount}")
    # S05: implausibly short or long form-open time (CONFIG; the SOP gives no limits)
    for r in surveys.itertuples():
        if r.duration_min < CONFIG["survey_min_minutes"] or r.duration_min > CONFIG["survey_max_minutes"]:
            flag("S05", "survey duration outside 30 to 180 minutes", "warning", "survey", r.plot_name, r.submission_key,
                 f"{r.duration_min:.0f} minutes for 20 quadrats")
    # S06: zero active placeholders at start is expected on the campaign's first survey; on a later survey it means
    # the device had not refreshed its entity list (SOP 4.2)
    first = surveys.sort_values("start_time").submission_key.iloc[0]
    for r in surveys[surveys.active_placeholders_at_start == 0].itertuples():
        if r.submission_key == first:
            flag("S06", "no active placeholders at start (first survey of the campaign, expected)", "info", "survey", r.plot_name, r.submission_key, "base_active_herb_count = 0")
        else:
            flag("S06", "no active placeholders at start on a later survey", "warning", "survey", r.plot_name, r.submission_key, "device entity list may not have been refreshed")

# ---------------------------------------------------------------------------
# PLOT-LEVEL RULES (registration geometry and sampling design)
# ---------------------------------------------------------------------------
def check_plots():
    """P01 viability, P02 midpoint offset, P03 length, P04 half-lengths and midpoint off the line, P05 orientation."""
    for r in plots[plots.is_viable != "yes"].itertuples():
        flag("P01", "plot registered as not viable", "info", "plot", r.plot_name, r.plot_name, f"reason given: '{r.not_viable_reason or 'none'}'")
    for r in plots[plots.is_viable == "yes"].itertuples():
        if r.midpoint_offset_m > SOP["midpoint_offset_max_m"]:
            flag("P02", "midpoint moved > 25 m from prescribed point (SOP limit)", "error", "plot", r.plot_name, r.plot_name, f"{r.midpoint_offset_m:.1f} m")
        elif r.midpoint_offset_m > CONFIG["midpoint_offset_warn_m"]:
            flag("P02", "midpoint 15-25 m from prescribed point (inside SOP limit)", "warning", "plot", r.plot_name, r.plot_name, f"{r.midpoint_offset_m:.1f} m")
        dev = abs(r.transect_length_m - SOP["transect_length_m"])
        if dev > 2 * CONFIG["transect_length_warn_m"]:
            flag("P03", "straight A-B distance far from 50 m", "error", "plot", r.plot_name, r.plot_name, f"A to B = {r.transect_length_m:.1f} m")
        elif dev > CONFIG["transect_length_warn_m"]:
            flag("P03", "straight A-B distance outside 45-55 m", "warning", "plot", r.plot_name, r.plot_name, f"A to B = {r.transect_length_m:.1f} m")
        for half, name in [(r.a_to_mid_m, "A to midpoint"), (r.mid_to_b_m, "midpoint to B")]:
            if abs(half - SOP["half_length_m"]) > CONFIG["half_length_tolerance_m"]:
                flag("P04", "endpoint not ~25 m from midpoint", "warning", "plot", r.plot_name, f"{r.plot_name}|{name}", f"{name} = {half:.1f} m")
        if r.midpoint_off_line_m > SOP["gps_accuracy_max_m"]:
            flag("P04", "recorded midpoint off the straight A-B line", "info", "plot", r.plot_name, f"{r.plot_name}|midpoint",
                 f"{r.midpoint_off_line_m:.1f} m perpendicular to A-B")
        off_ns = min(r.bearing_a_to_b_deg % 180, 180 - r.bearing_a_to_b_deg % 180)   # degrees away from the north-south line
        if off_ns > CONFIG["orientation_tolerance_deg"]:
            flag("P05", "transect not north-south; rotation reason not recorded", "info", "plot", r.plot_name, r.plot_name,
                 f"bearing {r.bearing_a_to_b_deg:.0f} deg; SOP allows rotation to avoid obstacles")

def check_design():
    """P06 backup surveyed, P07 prescribed primaries with no registration in these exports."""
    for r in centroids[(centroids.sample_status == "backup") & centroids.surveyed].itertuples():
        flag("P06", "backup plot surveyed", "info", "plot", r.plot_name, r.plot_name, "the export does not record which primary it replaces")
    primaries = centroids[centroids.sample_status == "primary"]
    for stratum, grp in primaries.groupby("stratum"):
        n_missing = int((~grp.registered).sum())
        if n_missing:
            names = ", ".join(grp.loc[~grp.registered, "plot_name"].str.replace("SavMon_LW_", ""))
            flag("P07", "prescribed primary plots with no registration in these exports", "error" if n_missing == len(grp) else "warning",
                 "design", f"stratum: {stratum}", stratum, f"{n_missing} of {len(grp)} primary plots in '{stratum}' ({names})")

# ---------------------------------------------------------------------------
# QUADRAT-LEVEL RULES
# ---------------------------------------------------------------------------
def check_quadrats():
    """Q01 location and photo, Q02 off transect, Q03 no herbs, Q04 answer vs rows, Q05 duplicate identity, Q06 count, Q07 blank row."""
    geo = plots.set_index("plot_name")
    n_extra_rows = records[records.source == "additional_species"].groupby("quadrat_key").size()
    for r in quadrats.itertuples():
        key = f"{r.plot_name} q{r.quadrat_number}"
        # Q01: geopoint or photo missing; GPS accuracy worse than 5 m (SOP)
        if pd.isna(r.lat) or pd.isna(r.lon) or pd.isna(r.image) or pd.isna(r.accuracy_m):
            flag("Q01", "quadrat geopoint, accuracy or photo missing", "error", "quadrat", r.plot_name, r.quadrat_key, key)
        else:
            if r.accuracy_m > SOP["gps_accuracy_max_m"]:
                flag("Q01", "quadrat GPS accuracy worse than 5 m", "warning", "quadrat", r.plot_name, r.quadrat_key, f"{key}: {r.accuracy_m} m")
            # Q02: distance to the registered transect, taken as the nearer of its two legs (A-mid, mid-B), which is what the maps draw
            p = geo.loc[r.plot_name]
            d = min(dist_to_segment_m(r.lat, r.lon, p.a_lat, p.a_lon, p.mid_lat, p.mid_lon),
                    dist_to_segment_m(r.lat, r.lon, p.mid_lat, p.mid_lon, p.b_lat, p.b_lon))
            if d > CONFIG["quadrat_offline_error_m"]:
                flag("Q02", "quadrat far from registered transect", "error", "quadrat", r.plot_name, r.quadrat_key, f"{key}: {d:.0f} m from A-mid-B")
            elif d > CONFIG["quadrat_offline_warn_m"]:
                flag("Q02", "quadrat off the registered transect", "warning", "quadrat", r.plot_name, r.quadrat_key, f"{key}: {d:.0f} m from A-mid-B")
        n_rows = int(n_extra_rows.get(r.quadrat_key, 0))
        n_ids = len(r.list_species_ids.split())
        if r.herbs_present == "no":
            flag("Q03", "no herbaceous species in quadrat", "info", "quadrat", r.plot_name, r.quadrat_key, key)
        if (r.additional_species_present == "yes") != (n_rows > 0):
            flag("Q04", "additional-species answer disagrees with rows", "warning", "quadrat", r.plot_name, r.quadrat_key,
                 f"{key}: answer='{r.additional_species_present or 'blank'}', additional rows={n_rows}")
        if r.n_list_species_form != n_ids:
            flag("Q06", "form species count differs from IDs", "error", "quadrat", r.plot_name, r.quadrat_key, f"{key}: {r.n_list_species_form} vs {n_ids}")
    # Q05: the same identity entered twice in one quadrat (by entity id, so an alias pair counts as the same identity)
    dup = records[records.identity_key.notna()].groupby(["quadrat_key", "plot_name", "quadrat_number", "identity_key"]).agg(
        n=("record_key", "size"), labels=("species_label", lambda s: " / ".join(sorted(set(s)))))
    for (qkey, plot, qn, ident), row in dup[dup.n > 1].iterrows():
        flag("Q05", "same species identity entered twice in a quadrat", "warning", "quadrat", plot, qkey, f"{plot} q{qn}: '{row.labels}' x{row.n}")
    # Q07: an additional-species row with nothing chosen
    for r in records[records.label_blank].itertuples():
        flag("Q07", "additional-species row with no species chosen", "warning", "quadrat", r.plot_name, r.record_key,
             f"{r.plot_name} q{r.quadrat_number}: entry mode '{r.entry_mode}' but nothing selected")

# ---------------------------------------------------------------------------
# SPECIES-LEVEL RULES (names typed in the field, identities)
# ---------------------------------------------------------------------------
def gbif_match(names):
    """
    Look each typed name up in the GBIF backbone (https://api.gbif.org/v1/species/match).
    Returns typed_name, match_type, gbif_name, gbif_status. Successful answers are cached to
    outputs/gbif_name_check.csv so later runs work offline; failed lookups are not cached, so they retry.
    """
    cache_file = os.path.join(OUT, "gbif_name_check.csv")
    cache = pd.read_csv(cache_file) if os.path.exists(cache_file) else pd.DataFrame(columns=["typed_name", "match_type", "gbif_name", "gbif_status"])
    new_rows, failed = [], []
    for name in names:
        if name in set(cache.typed_name):
            continue
        try:
            resp = requests.get("https://api.gbif.org/v1/species/match", params={"name": name, "kingdom": "Plantae"}, timeout=20)
            resp.raise_for_status()
            j = resp.json()
            new_rows.append({"typed_name": name, "match_type": j.get("matchType", "NONE"), "gbif_name": j.get("canonicalName", ""), "gbif_status": j.get("status", "")})
        except Exception as e:                         # no internet or service error: report, do not cache
            failed.append({"typed_name": name, "match_type": "LOOKUP_FAILED", "gbif_name": "", "gbif_status": str(e)[:60]})
    if new_rows:
        cache = pd.concat([cache, pd.DataFrame(new_rows)], ignore_index=True)
        cache.to_csv(cache_file, index=False)
    return pd.concat([cache[cache.typed_name.isin(names)], pd.DataFrame(failed)], ignore_index=True)

def check_species():
    """X01 name format, X02 already on the list, X03 GBIF spelling, X04 one entity under two labels."""
    official_lower = set(species_list["label"].astype(str).str.strip().str.lower())
    typed = records[records.entry_mode == "new_missing"][["plot_name", "label_raw", "species_label"]].drop_duplicates("label_raw")
    for r in typed.itertuples():
        if not re.match(SOP["canonical_pattern"], r.label_raw):
            flag("X01", "typed name not in Genus_species format", "warning", "species", r.plot_name, r.label_raw,
                 f"'{r.label_raw}' (SOP asks for Genus_species; the form's hint shows a space and only blocks , ; ( ))")
        if r.species_label.lower() in official_lower:
            flag("X02", "typed name already on the project species list", "warning", "species", r.plot_name, r.label_raw,
                 f"'{r.species_label}' exists in species.csv; should have been selected, not typed")
    for r in gbif_match(sorted(set(typed.species_label))).itertuples():
        if r.match_type != "EXACT":
            sev = "warning" if r.match_type in ("FUZZY", "LOOKUP_FAILED") else "info"
            flag("X03", "typed name not an exact GBIF match", sev, "species", "", r.typed_name,
                 f"'{r.typed_name}': GBIF {r.match_type}" + (f", suggests '{r.gbif_name}'" if r.gbif_name else "") + "; a suggestion to review, not an identification")
    by_id = records[records.identity_key.notna()].groupby("identity_key").agg(labels=("species_label", lambda s: sorted(set(s))), n=("record_key", "size"))
    for ident, row in by_id[by_id.labels.str.len() > 1].iterrows():
        flag("X04", "same entity recorded under two labels", "warning", "species", "", ident,
             f"labels {' | '.join(row.labels)} share one entity ({row.n} records); count as one identity")

# ---------------------------------------------------------------------------
# RUN EVERYTHING AND SAVE
# ---------------------------------------------------------------------------
RULES = {  # every rule id, so rules with no findings still appear in the summary
    "S01": "duplicate submission for plot", "S02": "rejected submission (excluded from summaries)", "S03": "quadrat count or numbering not 1 to 20",
    "S04": "form's end-of-survey species count differs from recount", "S05": "survey duration outside 30 to 180 minutes", "S06": "no active placeholders at survey start",
    "P01": "plot registered as not viable", "P02": "midpoint offset from prescribed point", "P03": "straight A-B distance vs 50 m",
    "P04": "endpoint half-lengths and midpoint off the A-B line", "P05": "transect not north-south", "P06": "backup plot surveyed",
    "P07": "prescribed primary plots with no registration",
    "Q01": "quadrat geopoint, accuracy or photo missing or inaccurate", "Q02": "quadrat off the registered transect", "Q03": "no herbaceous species in quadrat",
    "Q04": "additional-species answer disagrees with rows", "Q05": "same identity entered twice in a quadrat", "Q06": "form species count differs from IDs",
    "Q07": "additional-species row with no species chosen",
    "X01": "typed name not in Genus_species format", "X02": "typed name already on the project species list", "X03": "typed name not an exact GBIF match",
    "X04": "same entity recorded under two labels",
}
for check in [check_surveys, check_plots, check_design, check_quadrats, check_species]:
    check()

issues_df = pd.DataFrame(issues)
issues_df.to_csv(os.path.join(OUT, "qa_issues.csv"), index=False)

counts = issues_df.groupby("check_id").agg(n_all_exports=("item_key", "size"), n_retained=("population", lambda p: int((p != "rejected").sum())),
                                           severities=("severity", lambda s: "/".join(sorted(set(s)))))
summary = pd.DataFrame({"check_id": list(RULES), "rule": list(RULES.values())}).merge(counts, left_on="check_id", right_index=True, how="left")
summary["n_all_exports"] = summary.n_all_exports.fillna(0).astype(int)
summary["n_retained"] = summary.n_retained.fillna(0).astype(int)
summary["status"] = summary.n_all_exports.map(lambda n: "findings" if n else "pass")
summary["severities"] = summary.severities.fillna("")
summary.to_csv(os.path.join(OUT, "qa_summary.csv"), index=False)

pd.set_option("display.width", 220); pd.set_option("display.max_colwidth", 70)
print(summary.to_string(index=False))
ret = issues_df[issues_df.population != "rejected"]
print(f"\n{len(issues_df)} flagged rows in all exports; {len(ret)} in the retained population ({ret.severity.value_counts().to_dict()}); "
      f"rules passing: {int((summary.status == 'pass').sum())} of {len(summary)}")
