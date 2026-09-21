"""Publish inventory-based data allocation and preparation plan."""
import collections,json,re,hashlib
from pathlib import Path
from inventory_all_data import writecsv
BASE=Path(r"E:\PETROEDGE_AI\codex\data")
OUT=BASE/"catalogs/all_data_003"
summary=json.loads((OUT/"SUMMARY.json").read_text())
rows=list(map(json.loads,(OUT/"catalog.jsonl").read_text(encoding="utf-8").splitlines()))
groups=collections.defaultdict(list)
for row in rows:
    if row["well"]:groups[(row["collection"],row["field"] or "FIELD_UNRESOLVED",row["well"])].append(row)
def safe(s):return "group_"+re.sub(r"[^A-Za-z0-9_-]+","_",s)[:70]+"_"+hashlib.sha256(s.encode()).hexdigest()[:12]
for (collection,field,well),records in groups.items():
    writecsv(OUT/"by_field_well"/safe(collection)/safe(field)/safe(well)/"sources.csv",records,["file_id","source_path","detected_format","field","well","uwi","varieties","feature_candidates"])
import csv
with (OUT/"ARCHIVE_MEMBERS.csv").open(encoding="utf-8-sig",newline="") as f:members=list(csv.DictReader(f))
for task in sorted({t for m in members for t in json.loads(m["feature_candidates"])}):
    writecsv(BASE/"tasks"/task/"catalogs"/"archive_member_candidates.csv",[m for m in members if task in json.loads(m["feature_candidates"])])
formats="\n".join(f"| {k} | {v:,} |" for k,v in list(summary["formats"].items())[:30])
varieties="\n".join(f"| {k} | {v:,} |" for k,v in summary["varieties"].items())
features="\n".join(f"| {k} | {v:,} |" for k,v in summary["features"].items())
text=f"""# PetroEdge AI: full inventory and feature training plan

19 September 2026. Scope: all of F:\\DATA_PETROEDGE_AI. Geographic admission filtering is disabled as requested. This supersedes the previous Niger Delta selection policy for this stage.

## Completed work and limits

Traversed **{summary['directories']:,} directories**, cataloging **{summary['physical_files']:,} physical files / {summary['physical_bytes']:,} bytes ({summary['physical_bytes']/1e9:.2f} GB)**. Indexed **{summary['archive_members']:,} compressed file entries** separately; these are not additional unique datasets.

Created catalogs by format, variety, collection and feature, plus **{len(groups):,} provisional collection/field/well groups** from source header identities. Metadata includes **{summary['las_metadata_files']:,} files with LAS curves** and **{summary['workbook_metadata_files']:,} workbooks with cached sheet metadata**. There are **{len(summary['errors'])} recorded scan errors**; see SUMMARY.json.

Raw sources remain unchanged on F:. All new outputs are on E:. These are reference-based groups, avoiding duplicate copies of the source collection. Sources can support several features. The train/validation/test directories exist but remain unassigned until identity, labels, duplicates and alignment are reviewed. No model was trained or production deployment performed by this inventory task.

This was a full directory traversal with bounded content inspection, not full payload validation. PDF text/OCR and DLIS/LIS channel decoding remain pending. Proprietary data may need exports. Domain classification includes path hints. Candidate membership is not proof of usable labels. An archive filename encoding error interrupted snapshot all_data_001; it is marked incomplete. Snapshot all_data_002 was interrupted by the Windows reserved PRN filename. Generated filenames now use a safe prefix. The corrected snapshot is all_data_003.

## Output locations

Active catalog folder: E:\\PETROEDGE_AI\\codex\\data\\catalogs\\all_data_003

- MASTER_CATALOG.csv: every physical file, its detected format, candidate uses and inspection scope.
- by_format/, by_variety/, by_collection/: separate reference catalogs.
- by_field_well/: provisional source-scoped field/well groups. Equal names in different collections are not automatically merged.
- FIELD_WELL_INDEX.csv: available source identities, not a reviewed canonical registry.
- ARCHIVE_MEMBERS.csv: member paths/formats and proposed uses; no archive extraction.
- DIRECTORIES.csv: all visited directories, including empty ones.
- SUMMARY.json and *_COUNTS.csv: counts, errors and limitations.

Feature folders: E:\\PETROEDGE_AI\\codex\\data\\tasks\\<feature>. The active catalogs are catalogs/all_data_candidates.csv and, where applicable, archive_member_candidates.csv. Geography-restricted catalogs are preserved as historical and superseded. CURRENT.json and ALL_DATA_POLICY.json identify the current policy.

## File formats found

Physical-file counts below. Signatures take priority where recognized; some formats remain extension-only classifications. FORMATS_COUNTS.csv lists all formats.

| Format | Files |
|---|---:|
{formats}

Important distinctions:
- Some .dat files actually contain LAS ASCII logs.
- Petrel .ptd files include well-log and trajectory components and unresolved project components; preserve projects and sidecars together.
- .pds and .cgm represent plot/vector documents, not automatically numerical curve tables.
- .dex includes StrataBugs paleo/biostratigraphy exchange files.
- .lti/.lis require legacy log/tape readers. DLIS needs channel/frame decoding.
- SEG-Y, ZGY and proprietary seismic volumes need different adapters.
- Workbooks can contain multiple domains on different sheets.
- Production CSVs can have a well name on line one and headers on line two.
- Credentials, shortcuts, executables, temporary office files and system metadata are excluded from training candidates.

## Data varieties

Counts overlap: a core workbook is both a table and core data; a seismic report is also a document. These are candidate classifications, with evidence recorded in the catalog.

| Variety | Candidate files |
|---|---:|
{varieties}

Examples include GABO logs and a GABO-51 routine core K/Phi workbook; Freeman core workbooks with Poroperm, Facies, depth shifts and stressed measurements; PVT_Composition CSVs and fluid-composition workbooks; production/pressure time series; seismic surveys; Petrel components; deviation/well-header tables; biostratigraphy; the 3W archive; and Pason drilling logs. Their presence does not yet establish matched log/core labels, CO2-specific calibration data or unambiguous well identities.

## How each feature will use the data

| Feature / model | Inputs and labels | Training and validation |
|---|---|---|
| Lithology | GR, density, neutron, sonic, resistivity and other logs; aligned core descriptions/facies or qualified lithology intervals. Tops/biostratigraphy add context. | Compare RF, XGBoost and MLP with a documented class taxonomy. Hold out wells/fields; evaluate macro-F1, per-class recall, confusion matrix and calibrated probabilities. |
| Porosity | Logs matched to core porosity or independently qualified references; distinguish total/effective porosity and measurement conditions. | RF/XGBoost/MLP regression. Evaluate MAE/RMSE, bias by well/facies and interval coverage. Never include the target porosity curve among inputs. |
| Permeability | Core permeability matched to logs/facies; record direction, fluid and stress conditions. | Consider log-permeability regression with explicit censoring/detection-limit handling. Report log-space and physical-unit errors. Upstream predicted porosity used in training must be out-of-fold. |
| Fluid saturation | Logs plus rock/fluid context and qualified Sw/So/Sg targets. SCAL, pressure/fluid samples, contacts and PVT can constrain interpretation. | Separate saturation regression from oil/gas/water classification. Enforce bounds and appropriate sum-to-one constraints; evaluate each phase. PVT alone is not a depth-specific saturation label. Mark interpreted targets as interpreted. |
| Reservoir/non-reservoir | Expert intervals or documented rock-quality rules and logs/core. | Separate classifier and transparent cutoff baseline. Evaluate precision/recall and interval continuity. Learning cutoff-derived labels demonstrates rule reproduction, not independent geological accuracy. |
| HC pay/non-pay | Qualified fluid evidence, rock quality, saturation, thickness and versioned pay cutoffs. | Separate classifier/rule layer. Measure missed-pay, false-pay and net-pay thickness errors; examine cutoff sensitivity. Avoid circular labels generated from the same predictions used as inputs. |
| Log viewer / interactive signatures | Numeric curves, units, depth reference, tops, core points and model prediction tracks. | Plotting and crossplots do not require model training. Normalize units/depth, preserve gaps and validate sampled displayed values against sources. Show uncertainty and provenance beside predictions. |
| Edge computing | 3W events, Pason drilling, suitable production/pressure/operational telemetry and event labels. | Separate real, simulated and drawn data. Split wells/events before constructing causal windows with temporal gaps. RF/XGBoost baselines, then justified GRU/TCN models. Measure event PR-AUC, false alarms/day, lead time, latency and memory. Bidirectional models are offline only. |
| CCUS | Logs/core, pore volume, seismic faults/caprock, pressure/temperature, geomechanics, brine/CO2 properties and injection histories where present. | Retain screening physics. Train injectivity/capacity/plume/pressure surrogates only against suitable measurements or validated simulation cases. Hold out sites/realizations/scenarios. Oil/gas PVT cannot replace CO2-brine properties. Calibrated CO2 scenarios/leakage labels have not yet been verified. |
| Digital twin | Static well/geomodel/seismic/log/core state plus PVT, pressure, rates and operating/injection controls. | History-match using an earlier period, then test future forecasts and unseen scenarios. Constrain residual/forecast surrogates physically and quantify uncertainty. No future measurements in past predictions. |
| AI agents | Typed numerical data, specialist seismic tools/attributes/picks, document passages, images and analysis artifacts. | Parse and retrieve relevant evidence, execute scoped tools. Optional tuning requires curated expert-approved task/tool traces, not raw mixed files. Evaluate numerical correctness, tool outcomes, citations, access control and abstention on held-out tasks/document families/wells. |
| Analysis assistant | Authorized data and saved analyses, model versions, metrics, plots and document evidence. | Ground answers in retrieved results and computation. Cite page/file or well/depth/run. Test evidence accuracy and cross-user isolation; exclude evaluation answers from retrieval. |
| User training studio | Uploaded typed datasets with selected task, targets, features and group/time IDs. | Validate schema/units/labels and use the shared split/training service for RF/XGBoost/MLP. Save the complete preprocessing/model pipeline, schema, units, lineage, metrics and environment in a private user registry. |

Candidate physical files routed to each feature (overlapping, not sample counts):

| Feature | Files |
|---|---:|
{features}

## Dataset preparation and independent evaluation

1. Register sources and extracted artifacts with checksum, parent/container, parser version and source reference. Resolve duplicates across copies, archives and derived formats before splitting.
2. Decode into typed log, core, time-series, PVT, seismic, trajectory/top and simulation tables. Preserve original values/units plus normalized values. Keep documents and images in an evidence store with page/image provenance.
3. Review canonical field/well identities using UWI/API, aliases, coordinates and source metadata. Record CRS and MD/TVD/TVDSS datums. Do not join by filename alone.
4. Align core and logs using recorded depth shifts and interval support. Document tolerances and uncertainty; sparse core labels must not become thousands of falsely independent targets through interpolation.
5. Build per-well input/target availability matrices. Distinguish measured, interpreted, simulated and missing targets. Offer a common-log baseline plus richer models for deployments with more channels.
6. Lock partitions before learned imputation, scaling, feature selection, augmentation or window/patch generation. Approximate 70/15/15 is a starting proposal, subject to independent group and target coverage.
7. Compare algorithms on identical partitions. Tune on validation only; group internal cross-validation and early-stopping sets. The current MLP internal random early-stopping split should be replaced by a grouped approach or disabled.
8. Freeze and evaluate once on the locked test set. Report performance per well, field, facies, instrument/channel availability and source domain, plus uncertainty and failure cases.
9. Save the model with preprocessing, features/order, units, target semantics, split lock, source hashes, dependency versions and task-specific acceptance results.

The current split script holds out **canonical fields**, requires at least three independent fields and requires every task to have all three partitions. Where that is infeasible, introduce an explicit reviewed well-level strategy; never silently fall back to random depth rows. All derivatives and tasks from a held-out group must share its assignment. Stacked models require out-of-fold upstream predictions.

Seismic needs spatial blocks/surveys with buffers so adjacent traces and patches do not leak. Time series need forward validation with gaps covering the input/target horizon. Agent evaluations need independent document families, wells and task/answer variants.

Diversity can improve coverage, but inconsistent units, instruments and label conventions can reduce accuracy. Generalization must be measured on unseen groups. Grouped evaluation and train-only preprocessing follow [scikit-learn cross-validation guidance](https://scikit-learn.org/stable/modules/cross_validation.html) and [leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html).

## Platform integration needs found in the release

Working baseline: commit 83e01618a1516b52cabe4f39cbbdc137ae795dff.

- The ML lifecycle supports CSV/Parquet/LAS and RF/XGBoost/sklearn MLP, but currently has two-way train/validation splitting. Integrate a locked independent test set. A separate ml_platform training implementation needs consolidation.
- Add DLIS/LIS and workbook sheet adapters. Documents/seismic need separate parsers and specialist evidence tools, not direct ingestion into a tabular regressor.
- Connect upload -> prepared dataset version -> reviewed split -> training job -> private model registry -> predictions -> log/twin visualization -> saved analysis -> agent/assistant evidence.
- Reservoir interpretation includes rule/physics fallbacks. Display which model/rule produced each result and its version.
- Existing domain agents use rules; the reservoir assistant uses bounded intent/statistical responses. They are not yet trained multimodal agents.
- CCUS currently provides screening calculations and heuristic rankings, not calibrated plume/geomechanical forecasts.
- Twin scenarios currently maintain state and apply perturbations; that is not proof of a history-matched physics twin.
- Audit ownership/tenant filtering for datasets, jobs, model listings, artifacts and retrieval indexes. User-trained pipelines must remain accessible only to authorized users.
- Propagate a shared run ID and dataset/model versions across modules; version or invalidate dependent results when inputs change.

This inventory task documents those changes; it does not claim to have implemented them.

## Preparation sequence

A. Decode LAS/DLIS and core workbooks; publish reviewed log/core matches and actual label availability.
B. Normalize PVT, pressure, production and trajectory tables and resolve canonical identities.
C. Decode seismic geometry/attributes; index documents with text/OCR and citations.
D. Review 3W/Pason event definitions and build causal edge benchmarks.
E. Identify actual CCUS/twin calibration evidence and missing simulation/measurement targets.
F. Lock task-appropriate partitions, train baseline comparisons and connect qualified models to the platform.

The geographic gate is removed from the split utility. Identity, units, label provenance, checksum, duplicate and edge causal-review safeguards remain. Validation log: ALL_DATA_PIPELINE_TESTS.log (33 passing tests, including the archive-filename encoding regression). Production readiness still requires model evaluation, end-to-end feature testing, access control and deployment validation.
"""
report=Path(r"E:\PETROEDGE_AI\codex\docs\assessment\ALL_DATA_FEATURE_TRAINING_PLAN.md")
report.write_text(text,encoding="utf-8")
print(json.dumps({"report":str(report),"field_well_groups":len(groups),"archive_members":len(members)}))
