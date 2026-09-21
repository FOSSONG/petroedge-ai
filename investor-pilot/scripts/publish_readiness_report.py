"""Publish the readiness audit from completed machine-readable outputs."""
import csv,json,collections,hashlib
from pathlib import Path
from profile_log_core import OUT
def table(path):
 with (OUT/path).open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
s=json.loads((OUT/"READINESS_SUMMARY.json").read_text())
core=json.loads((OUT/"CORE_SUMMARY.json").read_text())
wells=table("WELL_MODEL_READINESS.csv")
best=sorted(wells,key=lambda r:(-int(r["within_0_25m_and_3_families"]),-int(r["within_0_25m_rows"]),r["well_source"]))
welltable="\n".join(f'| {r["well_source"]} | {r["unique_source_rows"]} | {r["porosity_rows"]} | {r["permeability_rows"]} | {r["within_0_25m_rows"]} | {r["within_0_25m_and_3_families"]} |' for r in best)
status="\n".join(f"| {k} | {v:,} |" for k,v in s["log_file_statuses"].items())
frame="\n".join(f"| {k} | {v:,} |" for k,v in s["frame_statuses"].items())
matches=table("LOG_CORE_MATCH_REVIEW.csv")
block=collections.Counter(b for r in matches for b in json.loads(r["blockers"]))
blocktable="\n".join(f"| {k} | {v:,} |" for k,v in block.most_common())
sheets=table("CORE_SHEET_REVIEW.csv")
error_sheets=sorted([r for r in sheets if int(r["formula_error_cells"])],key=lambda r:-int(r["formula_error_cells"]))
errors="\n".join(f'- {Path(r["source_path"]).name}, sheet {r["sheet"]}: {r["formula_error_cells"]} cached error cells.' for r in error_sheets[:8])
text=f"""# PetroEdge AI: log-core matching and model-readiness audit

19 September 2026. All outputs are under E:\\PETROEDGE_AI. Sources on F: were read only. Geographic origin was not used to admit or exclude data.

## Result

Profiled **{s['log_files_profiled']:,} LAS/DLIS files** and inspected **{core['candidate_workbooks']} core-candidate workbooks**. Extracted **{s['core_source_rows']:,} source rows**, identified **{s['duplicate_core_rows']:,} semantically identical extracted records**, and retained **{s['unique_core_source_rows']:,} distinct source records** across **{s['core_source_well_names']} source well names**.

Found **{s['shifted_sample_matches']:,} core records** with a source-name match, documented core-to-log shift and decoded log sample within a provisional **0.25 m** tolerance. Of those, **{s['shifted_matches_with_3_families']:,}** have observations from at least three mapped common curve families at the selected sample.

These are structurally supported candidates, **not approved training examples**. Identity/datum confirmation, laboratory-condition selection, label semantics, curve QC and independent split design remain. No model has been trained or evaluated on these records.

The most useful deliverable is WELL_MODEL_READINESS.csv, followed by LOG_CORE_MATCH_REVIEW.csv, which traces each proposed match to its source workbook cell/row, shift table, log file and frame. Candidate ranking uses input coverage and distance, not target values or model performance.

## Log decoding and curve coverage

| File status | Files |
|---|---:|
{status}

| Frame payload status | Frames |
|---|---:|
{frame}

A file with status decoded can contain frames whose numerical arrays were not decoded. Large files (over 96 MiB), multidimensional waveforms and unsupported frames remain explicitly marked; metadata availability is not numerical validation. LAS 3 multi-section pressure/time-series records require a dedicated typed adapter, rather than the LAS 2 depth-curve parser. Worker timeouts use a 120-second per-file limit.

For successfully decoded scalar data, the audit records curve names/units, finite ranges, nonfinite values, possible null sentinels, usable candidate counts, depth range, monotonicity and duplicate indexes. LAS null handling is performed by lasio; additional suspected sentinels are reported separately. A finite number does not establish physical validity.

The curve-family dictionary recognizes common GR, density, neutron, sonic, resistivity and caliper names, including inspected composite suffixes such as GR_COMP and RHOB_COMP. Unmapped channels remain in CURVE_COVERAGE.csv. They are not discarded, and curve meaning is not inferred solely from numerical similarity. Derived porosity/saturation curves are not automatically used as input features or measured labels.

Depth conversion supports explicit source units, including meters, feet and DLIS tenths of an inch. Unknown units are not guessed. MD/TVD/TVDSS and reference datums still require task-specific review before final joins.

DLIS processing preserves logical-file/frame boundaries; a binary file can contain several distinct acquisitions. Reader behavior follows the [dlisio documentation](https://dlisio.readthedocs.io/en/latest/dlis/userguide.html) and [lasio documentation](https://lasio.readthedocs.io/en/latest/basic-example.html).

## Core targets and depth matching

| Source well name | Distinct source rows | Porosity rows | Permeability rows | Within 0.25 m after shift | Also >=3 curve families |
|---|---:|---:|---:|---:|---:|
{welltable}

Counts above are source records, not necessarily independent core plugs. Multiple pressures, orientations, laboratory fluids and representations of one specimen remain separate. Exact file hashes identified **{s['exact_log_duplicate_groups']} duplicate log groups / {s['exact_log_duplicate_extra_files']} extra log copies** within the profiled subset; identical copies are excluded from candidate matching. Content-variant logs still need sample-level duplicate review.

The core workbook files have **{core['exact_duplicate_files']} byte-identical copies** in this selected set. Similar filenames were not treated as proof of identical content. Identical extracted records were deduplicated separately, preserving references to excluded copies. REPEATED_SPECIMEN_REVIEW.csv flags repeated well/depth entries whose labels or conditions differ; these were not silently merged.

Specific findings:
- GABO-51 contains explicit porosity/permeability units and separate measurements at 190 and 225 bar. Its estimated shift table provides +3.15 m, +3.95 m and +6.5 m for specified intervals. Conditions remain separate and the shifts retain their source-estimated status.
- Volve core sheets include porosity, directional gas/liquid permeability, descriptions and some laboratory oil/water saturations. Core-shift tables provide interval endpoints. Laboratory saturation is not automatically an in-situ reservoir saturation label.
- Freeman includes raw laboratory sheets and compiled/derived tables. Compiled in-situ estimates and stress conditions must not be mixed indiscriminately with laboratory measurements.
- Field X sidewall tables contain explicit lithology classes and descriptions, but source names include X-001, XX-001 and AHIA-003. The audit does not silently merge these identifiers or infer missing depth units.
- GABO-12/13 contain core/log shift notes. Notes and summary counts were kept out of the sample records. Missing explicit absolute-depth units are still unresolved.
- Alwyn student/solution workbooks are educational datasets. Their units, answer-derived content and duplicates need qualification before inclusion in production-model evaluation.

The shift algorithm maps core depths using documented interval endpoints and refuses ambiguous overlapping intervals. Matching uses a provisional 0.25 m nearest-sample tolerance, not interpolation of targets. The three-family coverage check is an engineering screening criterion, not an established model acceptance threshold.

## Remaining blockers

Counts overlap because a record may have several blockers.

| Blocker | Records |
|---|---:|
{blocktable}

Cached spreadsheet error cells total **{core['formula_error_cells']:,}** across the inspected sheets. Errors in a lookup/derived region do not invalidate unrelated measured data. Calculated in-situ columns were not promoted to measured targets.

{errors}

CORE_TARGET_VALUES.csv preserves original target values and cells. Only explicit percent/fraction and mD values are normalized; basic bounds are checked. Passing a range check does not verify the measurement method or its suitability for a particular deployment.

## Model-by-model readiness

| Task | Evidence obtained | Work required before training |
|---|---|---|
| Porosity | Source core measurements, conditions and potential matched log coverage | Choose a consistent porosity definition/condition; confirm depth datum and identity; QC channels and core values; establish independent groups. |
| Permeability | Gas/air/liquid/brine and directional/stress-dependent measurements | Choose the prediction target, direction and stress/fluid convention; handle censored/NMP entries; inspect possible specimen repeats; avoid mixing incompatible conditions. |
| Lithology | Explicit sidewall classes and core descriptions | Resolve sidewall names/units; map classes to an expert-reviewed taxonomy. Descriptions such as A.A. depend on preceding text and cannot be treated as independent class names. |
| Fluid saturation | Some laboratory oil/water measurements | Establish preservation/measurement conditions and in-situ relevance; validate units and depth matching. No qualified gas-saturation target was established in this pass. |
| Reservoir / pay | Supporting log/core evidence | Supply independent reference intervals or explicitly versioned rule-derived labels; no independent reservoir/pay ground truth was established by this extraction. |

More diverse sources do not remove these requirements. Adjacent depth samples, duplicate curves, repeated core specimens and multiple conditions for one plug must stay in the same train/validation/test group. A single well with many depths is not evidence of cross-well generalization.

## What was saved

Folder: E:\\PETROEDGE_AI\\codex\\data\\readiness\\log_core_001

- LOG_FILES.csv: file status, identity headers, hashes and usable family coverage.
- CURVE_COVERAGE.csv: per-file/frame/channel numerical QC and units.
- WELL_MODEL_READINESS.csv: per-source-well targets and match coverage.
- LOG_CORE_MATCH_REVIEW.csv: proposed joins, source evidence and blockers.
- CORE_TARGET_VALUES.csv: original and explicitly normalized target values, units, conditions and source cells.
- CORE_SHEET_REVIEW.csv: every inspected sheet, extraction scope and cached error counts.
- DUPLICATE_LOG_FILES.csv, DUPLICATE_CORE_RECORDS.csv and REPEATED_SPECIMEN_REVIEW.csv.
- core_samples.jsonl, core_shifts.jsonl and core_workbooks/: structured source extraction.
- files/, indexes/ and parser_logs/: individual log metadata, numeric depth/feature indexes and diagnostics.
- READINESS_SUMMARY.json: machine-readable totals.

Coverage is deliberately explicit: this pass addresses the catalog's 516 LAS-formatted files, 607 DLIS files and 27 core-candidate workbooks. It does not claim to have decoded all core PDFs/images, generic text exports, LIS/tape files, Petrel components or archive members.

## Next preparation action

Prioritize the wells with documented shifts and strong common-curve coverage. Confirm canonical identities and depth references, select comparable measured targets and resolve repeated specimens. Then produce versioned joined training tables and a reviewed field/well split manifest. For unresolved sidewall identities/units, consult source records; do not guess aliases. In parallel, implement the LAS 3/time-series and remaining binary-format adapters as a separate ingestion task.

Training has not started: **0 approved training rows**, no locked model-development split, and no performance or production-readiness claim. The extraction/matching test suite passed 42 checks before final artifact verification; see the final test log for any later count.
"""
p=Path(r"E:\PETROEDGE_AI\codex\docs\assessment\LOG_CORE_READINESS_REPORT.md")
p.write_text(text,encoding="utf-8")
artifacts=[p,*[OUT/n for n in ["READINESS_SUMMARY.json","LOG_FILES.csv","CURVE_COVERAGE.csv","WELL_MODEL_READINESS.csv","LOG_CORE_MATCH_REVIEW.csv","CORE_TARGET_VALUES.csv"]]]
manifest={"report":str(p),"artifacts":{str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in artifacts},"source_policy":"read_only","scope":"first log/core readiness audit; no models fitted"}
(OUT/"AUDIT_ARTIFACTS.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
print(json.dumps({"report":str(p),"well_rows":len(wells)}))
