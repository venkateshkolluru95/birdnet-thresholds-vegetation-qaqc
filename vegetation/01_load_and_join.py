"""
WHAT THIS FILE DOES, IN PLAIN LANGUAGE
--------------------------------------
The herbaceous vegetation survey arrives from ODK as four export tables plus eleven "entity
lists" (lookup tables such as the species list, the registered plots, the placeholder list for
species named in the field). This script reads the ones the analysis needs, joins them on their
ID columns, and writes five tidy tables that the QA checks (02) and the report (03) use without
re-doing any joins:

  surveys_clean.csv          one row per submitted survey form (= one visit to one plot)
  quadrats_clean.csv         one row per quadrat (20 per survey)
  species_records_long.csv   one row per species entry in a quadrat (the analysis table)
  plots_clean.csv            one row per registered plot, with context and transect geometry
  centroids_clean.csv        the 51 prescribed sampling points and whether each was used

Three layers are kept apart in the species records, because they are different things:
  * label_raw         exactly what was recorded in the field (never edited)
  * identity_key      the stable field identity: source list + entity UUID. The same entity can
                      appear under two labels (its typed name and its herb_### placeholder), so
                      labels over-count and identities are what richness is computed on
  * supplied_name     the identification later supplied in species_extra_ids.csv, attached as a
                      dated lookup, never written back into the label

Nothing is corrected. Values are copied as recorded; names are shortened and IDs resolved to
labels so the tables are readable.

INPUT : data/raw/vegetation/ODK Data Exports/*.csv  and  data/raw/vegetation/Entity lists/*.csv
OUTPUT: vegetation/outputs/*.csv (the five tables above)
"""

import os
import math
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw", "vegetation")
EXP = os.path.join(RAW, "ODK Data Exports")
ENT = os.path.join(RAW, "Entity lists")
OUT = os.path.join(ROOT, "vegetation", "outputs")
PROJECT_TZ = "Africa/Nairobi"            # the project's local time zone (UTC+3); device clocks recorded +02:00, see surveys table

# ---------------------------------------------------------------------------
# 1. Read the raw tables (ODK column names are long; we rename the ones we use)
# ---------------------------------------------------------------------------
survey_raw = pd.read_csv(os.path.join(EXP, "herbaceous_veg_survey.csv"))                     # 32 submissions
quadrat_raw = pd.read_csv(os.path.join(EXP, "herbaceous_veg_survey-quadrat_repeat.csv"))     # 640 quadrats
extra_raw = pd.read_csv(os.path.join(EXP, "herbaceous_veg_survey-additional_species_repeat.csv"))  # 1,296 additional-species rows
register_raw = pd.read_csv(os.path.join(EXP, "register_vegetation_plots.csv"))               # 31 plot registrations
species = pd.read_csv(os.path.join(ENT, "species.csv"))                 # the project species list (370 names, herbaceous + woody)
species_extra = pd.read_csv(os.path.join(ENT, "species_extra.csv"))     # placeholders for unknown / missing species, activated in the field
species_extra_ids = pd.read_csv(os.path.join(ENT, "species_extra_ids.csv"))   # identifications later supplied for those placeholders
centroids = pd.read_csv(os.path.join(ENT, "centroids.csv"))             # the 51 prescribed plot locations from the sampling design
vegplots = pd.read_csv(os.path.join(ENT, "vegplots.csv"))               # the 31 plots that were registered in the field

# ---------------------------------------------------------------------------
# 2. Surveys: one row per submitted form
# ---------------------------------------------------------------------------
start_text = survey_raw["survey_begin-start_time"]                      # e.g. 2026-05-27T09:41:43.843+02:00 (device clock + its offset)
surveys = pd.DataFrame({
    "submission_key": survey_raw["KEY"],                                        # ODK's unique ID of the submission
    "plot_name": survey_raw["plot_selection-plot_name"],
    "plot_entity_id": survey_raw["plot_selection-selected_plot_uuid"],          # points to vegplots.__id (NOT centroids)
    "survey_label": survey_raw["survey_begin-get_survey_label"],                # e.g. savmon|lw|herbs|ho
    "survey_entity_id": survey_raw["survey_begin-selected_survey_uuid"],        # points to surveys.__id
    "target_group": survey_raw["survey_begin-target_group"],
    "replicate": survey_raw["survey_begin-replicate"],                          # e.g. lw_baseline
    "recorder": survey_raw["field_team_specifics-recorder_label"],
    "team_size": survey_raw["field_team_specifics-selected_project_team_uuid_multi"].str.split().str.len(),
    "transport": survey_raw["field_team_specifics-transport_type_label"],
    "start_time": pd.to_datetime(start_text, utc=True),                         # the instant, in UTC
    "end_time": pd.to_datetime(survey_raw["survey_end-end_time"], utc=True),
    "submission_date": pd.to_datetime(survey_raw["SubmissionDate"], utc=True),  # when the form reached the server
    "start_clock_device": start_text.str[:16].str.replace("T", " "),            # what the device's clock showed, as recorded
    "device_utc_offset": start_text.str[-6:],                                   # the offset the device applied (+02:00 here)
    "quadrat_count": survey_raw["observations-quadrat_repeat_count"],           # how many quadrat blocks the form holds
    "quadrats_with_species_form": survey_raw["survey_end-quadrats_with_species"],  # the form's own count on its final screen
    "active_placeholders_at_start": survey_raw["base_active_herb_count"],       # how many herb placeholders were already active on the device
    "confirm_submission": survey_raw["survey_end-confirm_submission"],
    "notes": survey_raw["survey_end-herbaceous_veg_notes"],
    "review_state": survey_raw["ReviewState"].fillna(""),                       # ODK Central review flag: blank (unreviewed), approved, rejected
    "form_version": survey_raw["FormVersion"],
    "device_id": survey_raw["DeviceID"],
})
surveys["duration_min"] = (surveys["end_time"] - surveys["start_time"]).dt.total_seconds() / 60   # form open time, start to end
surveys["population"] = surveys["review_state"].map(lambda s: "rejected" if s == "rejected" else "retained")   # retained = not rejected (unreviewed)
surveys = surveys.sort_values(["plot_name", "start_time"]).reset_index(drop=True)

# ---------------------------------------------------------------------------
# 3. Quadrats: one row per quadrat, with the parent survey's plot and population attached
# ---------------------------------------------------------------------------
quadrats = pd.DataFrame({
    "quadrat_key": quadrat_raw["KEY"],
    "submission_key": quadrat_raw["PARENT_KEY"],
    "quadrat_number": quadrat_raw["quadrat_number"],
    "herbs_present": quadrat_raw["herbs_present"],
    "all_unknown_unidentifiable": quadrat_raw["herb_species-all_unknown_unidentifiable"].fillna(""),
    "list_species_ids": quadrat_raw["herb_species-selected_herb_species_uuids"].fillna(""),   # space-separated species.__id values
    "n_list_species_form": quadrat_raw["herb_species-count_herb_species"].fillna(0).astype(int),
    "additional_species_present": quadrat_raw["additional_species_present"].fillna(""),
    "lat": quadrat_raw["location_quadrat-Latitude"],
    "lon": quadrat_raw["location_quadrat-Longitude"],
    "accuracy_m": quadrat_raw["location_quadrat-Accuracy"],
    "image": quadrat_raw["quadrat_image"],
    "comment": quadrat_raw["quadrat_comment"].fillna(""),
})
quadrats = quadrats.merge(surveys[["submission_key", "plot_name", "review_state", "population"]], on="submission_key", how="left")

# ---------------------------------------------------------------------------
# 4. Species records: one row per (quadrat, species entry). Two sources are stacked:
#    (a) species ticked from the official list  -> IDs resolved through species.csv
#    (b) "additional species" rows (placeholders and typed names) -> resolved through species_extra
#        and, for the identification supplied later, species_extra_ids
# ---------------------------------------------------------------------------
# (a) explode the space-separated ID string into one row per ID
from_list = quadrats[["quadrat_key", "list_species_ids"]].copy()
from_list["entity_id"] = from_list["list_species_ids"].str.split()            # string -> list of IDs
from_list = from_list.explode("entity_id").dropna(subset=["entity_id"])        # one row per ID
from_list = from_list.merge(species[["__id", "label", "groups"]], left_on="entity_id", right_on="__id", how="left")
from_list = pd.DataFrame({
    "record_key": from_list["quadrat_key"] + "|" + from_list["entity_id"],     # unique key of this entry
    "quadrat_key": from_list["quadrat_key"],
    "source": "project_list",
    "entry_mode": "selected_from_list",
    "entity_id": from_list["entity_id"],
    "label_raw": from_list["label"],                       # e.g. "Indigofera schimperi"
    "entity_label": from_list["label"],
    "identity_type": "project_list",                       # a name from the curated list
    "supplied_name": from_list["label"],                   # the list name is the identification
    "supplied_note": "",
    "species_group": from_list["groups"],                  # should always be 'herbaceous' in this form
})

# (b) additional species. The label shown in the field sits in one of three columns depending on how
#     the species was entered; the entity id likewise. "fillna" chained = take the first column that is filled.
extra_label = (extra_raw["entity_label_to_write"]                 # a new placeholder or typed name created in this quadrat
               .fillna(extra_raw["reused_unknown_label"])         # a placeholder reused from earlier (e.g. herb_017)
               .fillna(extra_raw["reused_missing_label"]))        # a typed name reused from earlier
extra_id = (extra_raw["target_extra_name"]
            .fillna(extra_raw["select_reuse_unknown"])
            .fillna(extra_raw["select_reuse_missing"]))
# resolve the entity: its current label, its placeholder index and why it was created
se = species_extra[["__id", "label", "unknown_index", "new_record_reason", "group_type", "review_status"]].rename(
    columns={"__id": "entity_id", "label": "entity_label", "review_status": "entity_review_status"})
se["species_number"] = se.apply(lambda r: f"{'herb' if r.group_type == 'herb' else 'wood'}_{int(r.unknown_index):03d}", axis=1)
# the identification supplied later (species_extra_ids keys on species_number, e.g. herb_016 -> "Cenchrus ciliaris")
ids = species_extra_ids[["species_number", "species_name", "notes"]].rename(columns={"species_name": "supplied_name", "notes": "supplied_note"})
assert ids["species_number"].is_unique, "species_extra_ids must have one row per placeholder number"
se = se.merge(ids, on="species_number", how="left")
from_extra = pd.DataFrame({
    "record_key": extra_raw["KEY"],                        # the additional-species row's own ODK key
    "quadrat_key": extra_raw["PARENT_KEY"],
    "source": "additional_species",
    "entry_mode": extra_raw["species_entry_mode"],         # new_unknown / reuse_unknown / new_missing / reuse_missing
    "entity_id": extra_id,                                 # points to species_extra.__id
    "label_raw": extra_label,
    "species_group": "herbaceous",
}).merge(se[["entity_id", "entity_label", "new_record_reason", "species_number", "supplied_name", "supplied_note", "entity_review_status"]],
         on="entity_id", how="left")
from_extra["identity_type"] = from_extra["new_record_reason"].fillna("")      # unknown_species (placeholder) or missing_species (typed name)
from_extra["supplied_note"] = from_extra["supplied_note"].fillna("")

records = pd.concat([from_list, from_extra], ignore_index=True)
records["label_blank"] = records["label_raw"].isna()                               # an additional-species row with nothing chosen
records["species_label"] = records["label_raw"].fillna("").astype(str).str.strip()  # trimmed copy for grouping by label
records["label_is_placeholder"] = records["species_label"].str.match(r"^herb_\d+$")  # herb_017 style label
records["identity_key"] = records["source"] + ":" + records["entity_id"].astype(str)   # the stable field identity
records.loc[records["entity_id"].isna(), "identity_key"] = pd.NA
records["has_supplied_name"] = records["supplied_name"].notna() & (records["supplied_name"] != "Unknown")   # identified by someone
records = records.merge(quadrats[["quadrat_key", "submission_key", "plot_name", "quadrat_number", "review_state", "population"]],
                        on="quadrat_key", how="left")
# proof that the joins neither lost nor multiplied rows: every record came from exactly one list ID or one additional row
assert len(records) == quadrat_raw["herb_species-selected_herb_species_uuids"].str.split().str.len().sum() + len(extra_raw)
assert records["submission_key"].notna().all(), "a species record is not attached to a survey"
assert records["record_key"].is_unique, "record keys must be unique"

# ---------------------------------------------------------------------------
# 5. Plots: one row per registration, plus context, prescribed centroid and transect geometry
# ---------------------------------------------------------------------------
def haversine_m(lat1, lon1, lat2, lon2):
    """Distance in metres between two lat/lon points on the Earth (standard formula)."""
    if any(pd.isna(v) for v in (lat1, lon1, lat2, lon2)):
        return float("nan")
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def bearing_deg(lat1, lon1, lat2, lon2):
    """Compass direction (0 = north, 90 = east) from point 1 to point 2."""
    if any(pd.isna(v) for v in (lat1, lon1, lat2, lon2)):
        return float("nan")
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlmb = math.radians(lon2 - lon1)
    x = math.sin(dlmb) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlmb)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def dist_to_segment_m(lat, lon, lat1, lon1, lat2, lon2):
    """Shortest distance (m) from a point to the straight line between two points, on a flat local grid."""
    if any(pd.isna(v) for v in (lat, lon, lat1, lon1, lat2, lon2)):
        return float("nan")
    k = 111320.0                                             # metres per degree of latitude
    kx = k * math.cos(math.radians(lat))                     # metres per degree of longitude at this latitude
    px, py = (lon - lon1) * kx, (lat - lat1) * k
    sx, sy = (lon2 - lon1) * kx, (lat2 - lat1) * k
    seg_len2 = sx * sx + sy * sy
    t = 0 if seg_len2 == 0 else max(0, min(1, (px * sx + py * sy) / seg_len2))
    return math.hypot(px - t * sx, py - t * sy)


g = "plot_metadata-collect_points-"            # prefix shared by the three geopoint columns
species_label = species.set_index("__id")["label"]
plots = pd.DataFrame({
    "plot_name": register_raw["plot_selection-plot_name"],
    "registration_key": register_raw["KEY"],
    "centroid_entity_id": register_raw["plot_selection-selected_plot_uuid"],   # points to centroids.__id
    "sample_status": register_raw["plot_selection-sample_status"],             # primary or backup
    "stratum": register_raw["plot_selection-stratum_label"],
    "is_viable": register_raw["plot_selection-is_plot_viable"],
    "not_viable_reason": register_raw["plot_selection-plot_establishment_notes"].fillna(""),
    "ecosystem_type": register_raw["plot_metadata-ecosystem_type_name"],
    "woody_present": register_raw["plot_metadata-woody_species_present"],
    "dominant_woody": register_raw["plot_metadata-known_dominant_woody_species"].fillna("").str.split()
                        .map(lambda ids_: ", ".join(species_label.get(i, i) for i in ids_)),   # ids -> names
    "dominant_woody_unlisted": register_raw["plot_metadata-unknown_dominant_woody_species"].fillna(""),  # typed, not on the list
    "canopy_height_m": register_raw["plot_metadata-canopy_height_m"],
    "canopy_structure": register_raw["plot_metadata-canopy_structure"],
    "soil_type": register_raw["plot_metadata-soil_type"],
    "ground_cover": register_raw["plot_metadata-ground_cover"],
    "water_present": register_raw["plot_metadata-water_present"],
    "disturbance": register_raw["plot_metadata-disturbance_types"],
    "a_lat": register_raw[g + "endpoint_a-location_endpoint_a-Latitude"],
    "a_lon": register_raw[g + "endpoint_a-location_endpoint_a-Longitude"],
    "a_accuracy_m": register_raw[g + "endpoint_a-location_endpoint_a-Accuracy"],
    "mid_lat": register_raw[g + "midpoint-location_midpoint-Latitude"],
    "mid_lon": register_raw[g + "midpoint-location_midpoint-Longitude"],
    "mid_accuracy_m": register_raw[g + "midpoint-location_midpoint-Accuracy"],
    "b_lat": register_raw[g + "endpoint_b-location_endpoint_b-Latitude"],
    "b_lon": register_raw[g + "endpoint_b-location_endpoint_b-Longitude"],
    "b_accuracy_m": register_raw[g + "endpoint_b-location_endpoint_b-Accuracy"],
    "registered_by": register_raw["field_team_specifics-recorder_label"],
    "registered_start": pd.to_datetime(register_raw["survey_begin-start_time"], utc=True),
    "registration_notes": register_raw["survey_end-plot_establishment_notes"].fillna(""),
    "registration_review_state": register_raw["ReviewState"].fillna(""),
})

# prescribed location from the sampling design. ODK stores a geopoint as the text
# "latitude longitude altitude accuracy"; the values here are ~0.22 and ~37.48, which is Laikipia,
# Kenya (0.2 N, 37.5 E), confirming column 0 is latitude and column 1 is longitude.
cen_xy = centroids["geometry"].str.split(expand=True).iloc[:, :2].astype(float)   # first two numbers
centroids["design_lat"], centroids["design_lon"] = cen_xy[0], cen_xy[1]

plots = plots.merge(centroids[["__id", "choice_name", "design_lat", "design_lon", "sample_status", "stratum_label"]]
                        .rename(columns={"__id": "centroid_entity_id", "choice_name": "design_plot_name",
                                         "sample_status": "design_sample_status", "stratum_label": "design_stratum"}),
                    on="centroid_entity_id", how="left")

# transect geometry measures used by the QA checks. SOP: 50 m transect, midpoint within 25 m of the
# prescribed point, endpoints 25 m either side, laid out north-south unless rotated. Two lengths are kept:
# the straight A-to-B distance and the A-mid-B polyline, because the recorded midpoint is often off the line.
plots["midpoint_offset_m"] = [haversine_m(r.mid_lat, r.mid_lon, r.design_lat, r.design_lon) for r in plots.itertuples()]
plots["transect_length_m"] = [haversine_m(r.a_lat, r.a_lon, r.b_lat, r.b_lon) for r in plots.itertuples()]
plots["a_to_mid_m"] = [haversine_m(r.a_lat, r.a_lon, r.mid_lat, r.mid_lon) for r in plots.itertuples()]
plots["mid_to_b_m"] = [haversine_m(r.mid_lat, r.mid_lon, r.b_lat, r.b_lon) for r in plots.itertuples()]
plots["polyline_length_m"] = plots["a_to_mid_m"] + plots["mid_to_b_m"]
plots["midpoint_off_line_m"] = [dist_to_segment_m(r.mid_lat, r.mid_lon, r.a_lat, r.a_lon, r.b_lat, r.b_lon) for r in plots.itertuples()]
plots["bearing_a_to_b_deg"] = [bearing_deg(r.a_lat, r.a_lon, r.b_lat, r.b_lon) for r in plots.itertuples()]

# ---------------------------------------------------------------------------
# 6. Centroids: was each prescribed point registered and surveyed?
# ---------------------------------------------------------------------------
centroids_clean = pd.DataFrame({
    "plot_name": centroids["choice_name"],
    "centroid_entity_id": centroids["__id"],
    "sample_status": centroids["sample_status"],
    "stratum": centroids["stratum_label"],
    "design_year": centroids["survey_year"],
    "design_lat": centroids["design_lat"],
    "design_lon": centroids["design_lon"],
    "linked_flag_in_entity": centroids["vegplot_linked"].fillna(""),
})
centroids_clean["registered"] = centroids_clean["plot_name"].isin(plots["plot_name"])
viable_names = plots.loc[plots["is_viable"] == "yes", "plot_name"]
centroids_clean["registered_viable"] = centroids_clean["plot_name"].isin(viable_names)
retained = surveys[surveys["population"] == "retained"]                        # rejected submissions do not count as a survey
centroids_clean["surveyed"] = centroids_clean["plot_name"].isin(retained["plot_name"])

# ---------------------------------------------------------------------------
# 7. Save
# ---------------------------------------------------------------------------
surveys.to_csv(os.path.join(OUT, "surveys_clean.csv"), index=False)
quadrats.to_csv(os.path.join(OUT, "quadrats_clean.csv"), index=False)
records.to_csv(os.path.join(OUT, "species_records_long.csv"), index=False)
plots.to_csv(os.path.join(OUT, "plots_clean.csv"), index=False)
centroids_clean.to_csv(os.path.join(OUT, "centroids_clean.csv"), index=False)

print(f"surveys {len(surveys)} ({int((surveys.population == 'retained').sum())} retained) | quadrats {len(quadrats)} | "
      f"species records {len(records)} (list {int((records.source == 'project_list').sum())}, additional {int((records.source == 'additional_species').sum())}) "
      f"| plots {len(plots)} | centroids {len(centroids_clean)}")
print("unresolved list species IDs:", int(records.loc[records.source == "project_list", "entity_label"].isna().sum()),
      "| additional entities without species_extra row:", int(records.loc[(records.source == "additional_species") & records.entity_id.notna(), "entity_label"].isna().sum()))
r_ret = records[(records.population == "retained") & records.identity_key.notna()]
print("retained: distinct labels", r_ret.species_label.nunique(), "| distinct identities", r_ret.identity_key.nunique(),
      "| identities with a supplied name", r_ret.groupby("identity_key").has_supplied_name.first().sum())
print(centroids_clean.groupby(["stratum", "sample_status"])[["registered", "registered_viable", "surveyed"]].sum())
