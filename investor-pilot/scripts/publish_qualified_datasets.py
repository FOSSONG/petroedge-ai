"""Publish the source-qualified dataset registry, manifests and correction notice."""
import csv,collections,hashlib,json
from pathlib import Path
from qualify_log_core import OUT,BASE,REQUIRED,outcsv,jwrite
summary=json.loads((OUT/"SUMMARY.json").read_text())
identity=json.loads((OUT/"IDENTITY_REVIEW_SUMMARY.json").read_text())
verification=json.loads((OUT/"VERIFICATION.json").read_text())
sources=json.loads((OUT/"SOURCE_HASHES.json").read_text())
def read(name):
 with (OUT/name).open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
ledger=read("SAMPLE_TARGET_LEDGER.csv")
exclusions=collections.Counter(x for r in ledger if r["target_kind"]!="missing" for x in json.loads(r["exclusion_reasons"]))
registry=summary["datasets"]
for d in registry:
 folder=Path(d["path"]).parent
 target_basis="helium porosity reported by core laboratory" if d["target"]=="porosity" else "air permeability; horizontal" if d["target"]=="permeability_air_horizontal" else "air permeability; direction not explicitly stated in selected sheet" if d["target"]=="permeability_air" else "brine permeability; direction not explicitly stated in selected sheet"
 manifest={**d,"schema_version":1,"dataset_version":"log_core_002","required_features":REQUIRED,"join_key":"specimen_id","target_column":"target_value","target_definition":target_basis,"laboratory_condition":d["condition"],"porosity_unit":"fraction" if d["target"]=="porosity" else None,"permeability_unit":"mD" if "permeability" in d["target"] else None,"split":"unassigned","learned_preprocessing":"none","geographic_filter":False,"data_file_sha256":{name:hashlib.sha256((folder/name).read_bytes()).hexdigest() for name in ["dataset.csv","features.csv","targets.csv"]},"quality_policy":"exclude source-compromised samples, unexplained asterisk IDs, unresolved alignment, missing required curves, invalid targets and censored targets from primary regression tables","remaining_requirements":["confirm geological datum/log processing suitability","choose compatible cross-well laboratory conditions","establish independent train/validation/test grouping","integrate prepared dataset registry with platform training service"],"source_hash_registry":str(OUT/"SOURCE_HASHES.json")}
 jwrite(folder/"MANIFEST.json",manifest)
for task in ["porosity","permeability"]:
 chosen=[d for d in registry if d["target"].startswith(task)]
 dest=BASE/"tasks"/task/"catalogs"/"prepared_datasets_v002.csv"
 outcsv(dest,chosen)
group_counts=collections.Counter(r["split_group_id"] for r in ledger if r["status"]=="eligible_for_development")
jwrite(OUT/"SPLIT_REQUIREMENTS.json",{"status":"unassigned","parent_groups":dict(group_counts),"must_group_together":["Freeman-4 and Freeman-4 ST1","all targets and conditions for the same specimen","all copies/derivatives of one source interval"],"reason":"Only two parent-well groups and laboratory conditions differ. Random depth-row splitting would not measure unseen-well generalization.","field_status":{"GABO-51":"not declared in inspected LAS header","FREEMAN-4":"FREEMAN","FREEMAN-4-ST1":"FREEMAN"},"model_training_started":False})
table="\n".join(f"| {d['well']} | {d['condition']} | {d['target']} | {d['rows']} |" for d in registry)
exctable="\n".join(f"| {k} | {v} |" for k,v in exclusions.items())
maxdist=max(float(r["alignment_distance_m"]) for r in ledger if r["status"]=="eligible_for_development")
report=f"""# PetroEdge AI: prepared log/core candidate datasets

Version: log_core_002. Date: 19 September 2026.

## What is now available

Created **10 versioned candidate tables** from **242 distinct core specimens**, representing **572 task rows** across **GABO-51, Freeman-4 and Freeman-4 ST1**. A specimen can appear in multiple target tables; 572 is not the independent sample count.

These are source-checked development datasets. No model has been trained, no test split has been assigned, and no production suitability is claimed. Raw files on F: remain unchanged; outputs are on E:.

| Well | Source pressure label | Target | Primary rows |
|---|---|---|---:|
{table}

GABO measurements at 190 and 225 bar remain separate. Freeman measurements retain the source 1000 PSIG label, with air and brine permeability in separate targets. Pressure labels are preserved without conversion or unsupported normalization across test conditions. Porosity targets are reported helium porosity, converted from explicit percent units to fractions.

## How the datasets were prepared

- Verified SHA-256 checksums for **six source files** against the previous inspection before extraction.
- Used original core tables, including laboratory notes, rather than relying only on the earlier simplified target extraction.
- Matched GABO-51 core depths with its documented interval shifts. These shifts are described by the source as estimated.
- Matched Freeman laboratory rows to the same well/sample/core-depth entries in its Database sheet. Verified that the cached log depth minus core depth agrees with the corresponding Shifts entry. Feet are inherited from the explicitly labeled Corelab depth, supported by identical core depths and the shift arithmetic; the Database column itself does not repeat the unit.
- Read numerical log values from the selected LAS sources and verified curve units. Used nearest observed samples without inventing or interpolating core targets.
- Applied a provisional maximum matching distance of 0.25 m. The largest distance in the primary tables is **{maxdist:.4f} m**.
- Required four common numerical inputs: gamma ray, bulk density, neutron response and deep resistivity. Kept other available curves in the traceable dataset, but the default features.csv contains only those four plus specimen_id as the join key.
- Kept target values, depth, well identity and all metadata out of the predictor whitelist. No imputation, feature scaling or model fitting was performed.

The feature name neutron_porosity_v_v represents the measured neutron-log response; it is not a core-porosity target. Files identified as computed porosity/permeability interpretations were not automatically substituted for raw input logs.

## Source-quality decisions

The ledger contains **988 specimen/condition/target slots**, of which **635 have reported target content**. **572** enter the primary tables; **63 reported target slots** are held out. Many other slots are blank because a sample was not reported at both GABO pressures; those blanks are not corrupted observations.

GABO notes explicitly state that fractured/chipped samples may give optimistic porosity/permeability, broken samples lack measurements, and some permeability values fall below the instrument cutoff. The original descriptions and footnotes are retained.

**11 censored permeability results** are preserved in CENSORED_TARGETS.csv, with the original comparison operator and limit. A result such as less than 0.01 mD is neither zero nor an exact 0.01 mD target. It is excluded from ordinary exact-target regression tables pending a suitable treatment.

Samples with fracture/breakage concerns and unexplained asterisk IDs are held out. High/low grain-density notes remain visible; they are not automatically discarded as invalid geology.

Exclusion reasons among reported targets overlap:

| Reason | Target slots |
|---|---:|
{exctable}

This screening is reproducible but is not a laboratory certification. Full borehole-quality review, logging corrections, core preservation and final depth-reference interpretation remain relevant before model acceptance.

## Corrections and additional identities

**Correction to the previous audit:** the Corelab Poroperm sheet changes from Freeman-4 to Freeman-4 ST1 at row 66. The prior generic extraction carried Freeman-4 into the later section. **64 rows in the selected source workbook are now correctly assigned to Freeman-4 ST1.** The old audit is retained as historical, and EXTRACTION_CORRECTIONS.csv identifies every corrected row. Equivalent copies in earlier catalogs must follow this correction; they are not extra training samples.

The generic extraction script now respects repeated WELL ID headers, and a regression test covers this case.

Recovered **79 file-level well identities** where LAS exported duplicate WELL:1/WELL:2 fields that agreed. The previous profiler only looked for a single WELL key. Future extraction now accepts agreement and leaves conflicting values unresolved. These are 79 files, not 79 additional wells.

Found **seven file-level identifier links** to core-shift records by matching full source UWI values. For example, the 15/9-19 A LFP file has a general WELL display value but the explicit UWI identifies the A well. Those records still require input-curve provenance and measurement-condition review; an identity link alone does not make them training-ready.

The GABO-13-named LAS file has **OB051** in its well header. That conflict remains blocked. Field X sidewall identities and missing core-depth units also remain unresolved where source evidence is insufficient. No cross-field or sidetrack identities were guessed.

## Folder contents

Root: E:\\PETROEDGE_AI\\codex\\data\\prepared\\log_core_002

Each well/condition/target folder contains:
- dataset.csv: joined source values, targets, units, notes and provenance.
- features.csv: four required predictors plus specimen_id.
- targets.csv: aligned specimen_id, target value and unit.
- MANIFEST.json: target definition, schema, file hashes, conditions and remaining requirements.

Root files:
- DATASET_REGISTRY.csv: all ten datasets.
- SAMPLE_TARGET_LEDGER.csv: every source target slot, including exclusions.
- CENSORED_TARGETS.csv and EXCLUDED_RECORDS.csv.
- FEATURE_SCHEMA.json and SOURCE_HASHES.json.
- IDENTITY_EVIDENCE.csv, WELL_IDENTITY_REVIEW.csv and HEADER_IDENTITY_CORRECTIONS.csv.
- EXTRACTION_CORRECTIONS.csv and LABORATORY_NOTES.csv.
- SPLIT_REQUIREMENTS.json, SUMMARY.json and VERIFICATION.json.

Prepared-dataset references are also saved in the porosity and permeability task catalogs. The running platform's database/UI has not yet been connected to these files.

## Validation and next step

**51 tests passed.** Artifact checks confirmed source hashes, matching tolerances, specimen uniqueness within each target table, identical feature/target ordering, finite required features, valid target ranges, and exclusion of censored values from exact-target regression.

There are **two parent-well groups**, because Freeman-4 and its sidetrack must stay together for conservative evaluation. Laboratory conditions also differ. A random depth-row split would inflate the apparent independence of the data, so train/validation/test folders have not been populated.

The next preparation step is to qualify compatible measurements from additional independent wells. The recovered header identities and exact UWI links provide concrete candidates. Once enough compatible groups are available, lock the partitions and connect these versioned tables to PetroEdge's shared training/model registry before comparing Random Forest, XGBoost and neural networks.
"""
reportpath=Path(r"E:\PETROEDGE_AI\codex\docs\assessment\PREPARED_LOG_CORE_DATASETS.md")
reportpath.write_text(report,encoding="utf-8")
(OUT/"README.md").write_text("# Prepared log/core candidates\n\nSee "+str(reportpath)+" for definitions, exclusions, corrections and limitations. These are development candidates with unassigned splits. Use explicit feature whitelists and keep related wells/specimens together.\n",encoding="utf-8")
jwrite(BASE/"prepared/CURRENT.json",{"active_snapshot":"log_core_002","report":str(reportpath),"registry":str(OUT/"DATASET_REGISTRY.csv"),"models_trained":False})
old=json.loads((BASE/"readiness/CURRENT.json").read_text())
old.update(latest_qualification=str(OUT),latest_report=str(reportpath),corrections="Freeman-4/ST1 sheet sections and duplicated LAS WELL headers corrected in log_core_002; original audit is historical.")
jwrite(BASE/"readiness/CURRENT.json",old)
cat=json.loads((BASE/"catalogs/CURRENT.json").read_text())
cat.update(prepared_registry=str(OUT/"DATASET_REGISTRY.csv"))
jwrite(BASE/"catalogs/CURRENT.json",cat)
artifacts=[p for p in OUT.rglob("*") if p.is_file() and p.name!="ARTIFACT_HASHES.json"]
jwrite(OUT/"ARTIFACT_HASHES.json",{"files":{str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts},"report":{str(reportpath):hashlib.sha256(reportpath.read_bytes()).hexdigest()}})
print(json.dumps({"report":str(reportpath),"artifact_files":len(artifacts),"dataset_tables":len(registry)}))
