"""Read-only source inventory and conservative Niger Delta evidence catalog.

This command never trains a model or treats filename hints as geological proof.
Reruns create separate snapshots. Source data is referenced, never modified.
"""
from __future__ import annotations
import argparse
import collections
import csv
import hashlib
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

TASKS = ["edge_computing", "lithology", "porosity", "permeability",
         "fluid_saturation", "reservoir_classification", "hc_pay_classification",
         "ccus", "ai_agents", "digital_well_twin", "analysis_assistant"]
MISSING = {"", "UNKNOWN", "NONE", "NULL", "N/A", "-999.25"}
TARGETS = {
    "lithology": {"LITH", "LITHO", "LITHOLOGY", "FACIES"},
    "porosity": {"PHI", "PHIE", "PHIT", "POR", "POROSITY", "CPOR"},
    "permeability": {"PERM", "PERMEABILITY", "K", "KH", "KLOGH"},
    "fluid_saturation": {"SW", "SO", "SG", "SWAT", "SOIL", "SGAS"},
    "reservoir_classification": {"RESFLAG", "RESERVOIR", "NETRES"},
    "hc_pay_classification": {"PAY", "PAYFLAG", "NETPAY"},
}
def normal(value):
    return re.sub(r"[^A-Z0-9]+", "", str(value).upper())

def las_header(path):
    lines, section, headers, curves = [], "", {}, []
    # Bound the read even for malformed files. Do not ingest numeric rows.
    with path.open("r", encoding="latin-1") as stream:
        for _ in range(4000):
            line = stream.readline(8192)
            if not line:
                break
            stripped = line.strip()
            if stripped.upper().startswith("~A"):
                break
            lines.append(line)
            if stripped.startswith("~"):
                section = stripped[1:2].upper()
                continue
            if not stripped or stripped.startswith("#"):
                continue
            match = re.match(r"^\s*([^\s.]+)\s*\.(\S*)\s*(.*?)\s*(?::(.*))?$", line.rstrip())
            if not match:
                continue
            mnemonic, unit, value, description = match.groups()
            if section == "W":
                headers[mnemonic.upper()] = {"value": value.strip(), "unit": unit}
            elif section == "C":
                curves.append({"mnemonic": mnemonic, "unit": unit, "description": (description or "").strip()})
    return headers, curves, "".join(lines)

def geography(headers, text, relative):
    country = headers.get("CTRY", headers.get("COUNTRY", {})).get("value", "").strip().upper()
    # Evaluate basin evidence in LAS source metadata only, not arbitrary reports.
    explicit_delta = bool(re.search(r"NIGER[\s_-]+DELTA", text, re.I))
    outside_country = country in {"NORWAY", "NOR", "NORWEGIAN NORTH SEA", "UNITED STATES", "USA", "BRAZIL", "BRASIL", "UNITED KINGDOM", "UK"}
    if explicit_delta and outside_country:
        return "conflicting_metadata", "Niger Delta header reference conflicts with country=" + country
    if explicit_delta:
        return "source_header_niger_delta", "Explicit Niger Delta reference in LAS source header; independent verification pending"
    if outside_country:
        return "outside_nigeria_header", "LAS country=" + country
    if country in {"NG", "NGA", "NIGERIA", "NIGERIAN"}:
        return "nigeria_basin_unverified", "Country is Nigeria; basin has not been established"
    if country and country not in MISSING:
        return "ambiguous_country_code", "Country code needs a documented mapping: " + country
    if re.search(r"niger[\s_-]+delta", relative, re.I):
        return "niger_delta_path_hint_only", "Folder/filename only; not accepted as basin evidence"
    return "unknown", "No sufficient basin evidence inspected"

def modality(relative):
    p = Path(relative)
    suffix = p.suffix.lower()
    name = relative.lower()
    if p.name.startswith("~$") or p.name.lower() in {"thumbs.db", "desktop.ini", ".ds_store"}:
        return "restricted_or_non_data"
    if suffix in {".las", ".dlis", ".lis"}:
        return "well_logs"
    if suffix in {".segy", ".sgy", ".zgy", ".cdp", ".vel"}:
        return "seismic"
    if suffix in {".zip", ".tar", ".gz", ".7z", ".rar"}:
        return "archives"
    if suffix in {".exe", ".lnk", ".url", ".share", ".dll"} or re.search(r"credential|password|secret|token", p.name, re.I):
        return "restricted_or_non_data"
    if suffix in {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".pptm", ".rtf", ".png", ".jpg", ".tif", ".tiff"}:
        return "unstructured"
    for category, pattern in [
        ("pvt", r"\bpvt\b|pressure.volume|fluid.propert"),
        ("production", r"production|prod[_ -]hist|well[_ -]test|rate[_ -]history"),
        ("drilling_telemetry", r"witsml|pason|drillingdata|drilling[_ -]data|3w_dataset"),
        ("core", r"core|scal|rcal|plug"),
        ("trajectory_tops", r"deviation|trajectory|tops|checkshot"),
        ("simulation_geology", r"\.grdecl$|\.inc$|\.data$"),
    ]:
        if re.search(pattern, name, re.I):
            return category
    if suffix in {".csv", ".xls", ".xlsx", ".parquet", ".txt", ".asc", ".ascii", ".dat", ".xml", ".json"}:
        return "tabular_or_text_unclassified"
    return "specialist_format_unclassified"

def candidates(kind):
    mapping = {
        "well_logs": TASKS[1:7] + ["ccus", "digital_well_twin", "analysis_assistant"],
        "seismic": ["ccus", "digital_well_twin", "analysis_assistant"],
        "pvt": ["fluid_saturation", "hc_pay_classification", "ccus", "digital_well_twin", "analysis_assistant"],
        "production": ["edge_computing", "digital_well_twin", "ccus", "analysis_assistant"],
        "drilling_telemetry": ["edge_computing"],
        "core": TASKS[1:7] + ["ccus", "digital_well_twin", "analysis_assistant"],
        "trajectory_tops": ["digital_well_twin", "ccus", "analysis_assistant"],
        "simulation_geology": ["digital_well_twin", "ccus", "analysis_assistant"],
        "unstructured": ["ai_agents", "analysis_assistant"],
    }
    return mapping.get(kind, [])

def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def stable_id(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")

def write_csv(path, records, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({k: json.dumps(record.get(k), ensure_ascii=False) if isinstance(record.get(k), (list, dict)) else record.get(k, "") for k in columns})

def proposed_fields(records):
    # A reproducible proposal only: no training manifest is emitted here.
    fields = sorted({normal(r["field"]) for r in records if r["geography_status"] == "source_header_niger_delta" and r["field"].upper() not in MISSING and r["well"].upper() not in MISSING})
    ranked = sorted(fields, key=lambda f: stable_id("petroedge-42:" + f))
    if len(ranked) < 3:
        return {}
    ntest = max(1, round(len(ranked) * .15))
    nval = max(1, round(len(ranked) * .15))
    return {field: ("test" if i < ntest else "validation" if i < ntest + nval else "train") for i, field in enumerate(ranked)}

def scan(source, output):
    source, output = source.resolve(), output.resolve()
    if not source.is_dir() or output == source or source in output.parents:
        raise ValueError("Source must exist; output must be outside source")
    output.mkdir(parents=True, exist_ok=False)
    records, archive_rows = [], []
    paths = sorted((p for p in source.rglob("*") if p.is_file()), key=lambda p: str(p).casefold())
    for index, path in enumerate(paths):
        relative = path.relative_to(source).as_posix()
        stat = path.stat()
        kind = modality(relative)
        record = dict(file_id=stable_id(relative), relative_path=relative, source_path=str(path),
                      collection=relative.split("/")[0], bytes=stat.st_size, modified_ns=stat.st_mtime_ns,
                      modality=kind, modality_basis="extension_or_path_hint_pending_content_review",
                      geography_status="unknown", geography_evidence="not inspected",
                      field="", well="", uwi="", curves=[], target_candidates={},
                      candidate_tasks=candidates(kind), sha256="", hash_status="deferred",
                      split="unassigned", training_ready=False, errors=[])
        if path.is_symlink():
            record["errors"].append("symlink_not_followed")
        elif kind == "restricted_or_non_data":
            record["errors"].append("contents_not_read")
        else:
            try:
                if path.suffix.lower() == ".las":
                    headers, curves, header_text = las_header(path)
                    record["geography_status"], record["geography_evidence"] = geography(headers, header_text, relative)
                    record["geography_excerpt"] = [line.strip() for line in header_text.splitlines() if re.search(r"NIGER[\s_-]+DELTA", line, re.I)][:3]
                    record["field"] = headers.get("FLD", headers.get("FIELD", {})).get("value", "")
                    record["well"] = headers.get("WELL", {}).get("value", "")
                    record["uwi"] = headers.get("UWI", {}).get("value", "")
                    record["well_header"] = headers
                    record["curves"] = curves
                    mnemonics = {normal(c["mnemonic"]) for c in curves}
                    record["target_candidates"] = {task: sorted(mnemonics & aliases) for task, aliases in TARGETS.items() if mnemonics & aliases}
                    record["modality_basis"] = "LAS header inspected; numeric samples and label provenance pending"
                    if stat.st_size <= 128 * 1024**2:
                        record["sha256"] = sha256(path)
                        record["hash_status"] = "full_sha256"
                elif path.suffix.lower() == ".csv":
                    with path.open("r", encoding="utf-8-sig", errors="replace") as stream:
                        sample = stream.read(65536)
                    try:
                        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
                        rows = list(csv.reader(sample.splitlines()[:10], dialect))
                        record["column_preview"] = rows[0][:100] if rows else []
                    except csv.Error:
                        record["errors"].append("csv_dialect_unresolved")
                elif path.suffix.lower() == ".zip":
                    with zipfile.ZipFile(path) as archive:
                        for member in archive.infolist():
                            if not member.is_dir():
                                archive_rows.append(dict(container_id=record["file_id"], container=relative,
                                    member=member.filename, bytes=member.file_size, compressed_bytes=member.compress_size,
                                    modality=modality(member.filename), status="not_extracted_not_geographically_verified"))
                if record["geography_status"] == "unknown" and re.search(r"niger[\s_-]+delta", relative, re.I):
                    record["geography_status"] = "niger_delta_path_hint_only"
                    record["geography_evidence"] = "Folder/filename only; not accepted as basin evidence"
            except Exception as exc:
                record["errors"].append(type(exc).__name__ + ": " + str(exc)[:300])
        after = path.stat()
        if (after.st_size, after.st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
            record["errors"].append("source_changed_during_scan")
            record["hash_status"] = "invalid_source_changed"
        record["nonedge_gate"] = ("basin_header_evidence_review_identity_and_labels" if record["geography_status"] == "source_header_niger_delta" else "blocked_pending_niger_delta_evidence")
        records.append(record)
        if (index + 1) % 100 == 0:
            print(json.dumps({"files_scanned": index + 1, "total": len(paths)}), flush=True)
    duplicates = collections.defaultdict(list)
    for record in records:
        if record["hash_status"] == "full_sha256":
            duplicates[record["sha256"]].append(record["file_id"])
    duplicate_groups = {key: values for key, values in duplicates.items() if len(values) > 1}
    with (output / "catalog.jsonl").open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    columns = ["file_id", "relative_path", "bytes", "modality", "geography_status", "geography_evidence", "field", "well", "uwi", "candidate_tasks", "target_candidates", "hash_status", "sha256", "nonedge_gate", "split", "training_ready", "errors"]
    write_csv(output / "CATALOG.csv", records, columns)
    write_csv(output / "ARCHIVE_MEMBERS.csv", archive_rows, ["container_id", "container", "member", "bytes", "compressed_bytes", "modality", "status"])
    write_json(output / "EXACT_DUPLICATES.json", duplicate_groups)
    for kind in sorted({r["modality"] for r in records}):
        write_csv(output / "by_modality" / kind / "manifest.csv", [r for r in records if r["modality"] == kind], columns)
    for task in TASKS:
        task_records = [r for r in records if task in r["candidate_tasks"]]
        write_csv(output / "by_task" / task / "candidates.csv", task_records, columns)
    grouped = collections.defaultdict(list)
    for record in records:
        if record["field"].upper() not in MISSING and record["well"].upper() not in MISSING:
            grouped[(normal(record["field"]), normal(record["well"]))].append(record["file_id"])
    for (field, well), identifiers in grouped.items():
        write_json(output / "by_field_well" / field[:80] / well[:80] / "sources.json",
                   {"field_key": field, "well_key": well, "file_ids": identifiers,
                    "identity_status": "source_header_grouping_requires_alias_review", "split": "unassigned"})
    proposal = proposed_fields(records)
    write_json(output / "FIELD_SPLIT_PROPOSAL.json", {"status": "proposal_not_locked_not_for_training", "seed": 42,
        "unit": "field", "fields": proposal, "blockers": ["Review field/well aliases and conflicting duplicate metadata",
        "Verify basin evidence, labels and units", "Choose independent evaluation fields before fitting",
        "Review rare-class coverage without moving individual wells across field splits"]})
    summary = {"created_utc": datetime.now(timezone.utc).isoformat(), "source_root": str(source),
        "file_count": len(records), "total_bytes": sum(r["bytes"] for r in records),
        "by_modality": dict(collections.Counter(r["modality"] for r in records)),
        "by_geography": dict(collections.Counter(r["geography_status"] for r in records)),
        "hashed_files": sum(r["hash_status"] == "full_sha256" for r in records),
        "exact_duplicate_groups": len(duplicate_groups), "archive_members": len(archive_rows),
        "field_well_groups": len(grouped), "files_with_read_errors_or_exclusions": sum(bool(r["errors"]) for r in records),
        "training_ready_files": 0, "calibration_status": "not calibrated",
        "limits": ["Header/filename inventory, not full content QA", "Only LAS <=128MiB fully hashed",
        "Binary logs, seismic, workbooks and unstructured content require dedicated adapters",
        "Archive members have not been extracted or ingested", "No geography inferred from folder names",
        "Model targets and provenance not independently verified", "No production rights determination"]}
    write_json(output / "SUMMARY.json", summary)
    (output / "README.md").write_text("# Niger Delta data catalog\n\n"
        "This snapshot references original files without moving or modifying them. CATALOG.csv is the readable index; catalog.jsonl retains headers and curve metadata.\n\n"
        "Task manifests list candidate uses only. All splits remain unassigned. FIELD_SPLIT_PROPOSAL.json is a review proposal, not a training input. "
        "Source-header Niger Delta evidence is recorded separately from independent verification. Country=NG alone and folder names do not establish basin membership.\n\n"
        "Edge data may come from outside the Niger Delta but still requires task, label, units, provenance and causal-window checks. "
        "Unstructured records are candidate evidence for retrieval, not automatically language-model fine-tuning examples. "
        "Credentials, links and executables are not read as datasets.\n\n"
        "Current calibration status: **not calibrated**. See SUMMARY.json for counts and scope limitations.\n", encoding="utf-8")
    print(json.dumps(summary), flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    scan(args.source, args.output)

