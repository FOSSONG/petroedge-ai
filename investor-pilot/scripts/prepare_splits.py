"""Create locked three-way manifests from explicitly reviewed data records.

The catalog is not an approved input. This utility rejects unresolved evidence
and never reads test samples to choose splits or fits any preprocessing.
"""
import argparse, csv, hashlib, json, re
from pathlib import Path

REQUIRED = ["file_id","source_path","sha256","field_id","well_id","task",
            "identity_status","label_status","units_status"]
MISSING = {"", "unknown", "none", "null", "unresolved", "n/a"}

def validate(records, verify_files=True):
    if not records:
        raise ValueError("No reviewed records supplied")
    ids, digest_groups, well_fields = set(), {}, {}
    for row in records:
        absent = [key for key in REQUIRED if str(row.get(key, "")).strip().lower() in MISSING]
        if absent:
            raise ValueError("Unresolved fields: " + ", ".join(absent))
        if row["file_id"] in ids:
            raise ValueError("Duplicate file_id")
        ids.add(row["file_id"])
        if row["identity_status"] != "verified" or row["label_status"] != "verified" or row["units_status"] != "verified":
            raise ValueError("Identity, label provenance and units must be verified")
        if row["task"] == "edge_computing":
            if row.get("causal_review") != "verified":
                raise ValueError("Edge data requires causal-window review")
        field, well = row["field_id"].strip(), row["well_id"].strip()
        if well in well_fields and well_fields[well] != field:
            raise ValueError("A canonical well is assigned to multiple fields")
        well_fields[well] = field
        digest = row["sha256"].lower()
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Invalid SHA-256 digest")
        if digest in digest_groups:
            raise ValueError("Identical file content must be deduplicated before splitting")
        digest_groups[digest] = (field,well)
        if verify_files:
            path = Path(row["source_path"])
            if not path.is_file():
                raise ValueError("Missing reviewed source file")
            with path.open("rb") as stream:
                actual = hashlib.file_digest(stream,"sha256").hexdigest()
            if actual.lower() != row["sha256"].lower():
                raise ValueError("Source checksum changed after review")

def plan(records, seed=42):
    validate(records, verify_files=False)
    fields = sorted({row["field_id"].strip() for row in records},
        key=lambda field:hashlib.sha256(f"{seed}:{field}".encode()).hexdigest())
    if len(fields) < 3:
        raise ValueError("Three-way field split requires at least three independent fields")
    ntest = max(1,round(.15*len(fields)))
    nval = max(1,round(.15*len(fields)))
    mapping = {field:("test" if i<ntest else "validation" if i<ntest+nval else "train") for i,field in enumerate(fields)}
    result = [dict(row,split=mapping[row["field_id"].strip()]) for row in records]
    for task in {r["task"] for r in result}:
        if {r["split"] for r in result if r["task"]==task} != {"train","validation","test"}:
            raise ValueError(f"Task {task} lacks coverage in all partitions; acquire more fields or review the field-level plan")
    return result

def run(manifest, output, seed=42):
    if output.exists():
        raise ValueError("Refusing to overwrite a locked split directory")
    with manifest.open(encoding="utf-8-sig",newline="") as stream:
        records=list(csv.DictReader(stream))
    validate(records)
    assigned=plan(records,seed)
    output.mkdir(parents=True,exist_ok=False)
    columns=list(dict.fromkeys([*records[0],"split"]))
    for split in ["train","validation","test"]:
        with (output/(split+".csv")).open("w",encoding="utf-8-sig",newline="") as stream:
            writer=csv.DictWriter(stream,fieldnames=columns)
            writer.writeheader()
            writer.writerows(r for r in assigned if r["split"]==split)
    payload={"status":"locked_manifest","seed":seed,"split_unit":"canonical_field",
      "manifest_sha256":hashlib.sha256(manifest.read_bytes()).hexdigest(),
      "fields":{r["field_id"]:r["split"] for r in assigned},
      "note":"No preprocessing fitted or model trained. Approximate 70/15/15 by field count, not sample count. Test set must remain sealed during tuning.",
      "outputs":{split:hashlib.sha256((output/(split+".csv")).read_bytes()).hexdigest() for split in ["train","validation","test"]}}
    (output/"split_lock.json").write_text(json.dumps(payload,indent=2),encoding="utf-8")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--reviewed-manifest",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--seed",type=int,default=42)
    args=parser.parse_args()
    run(args.reviewed_manifest,args.output,args.seed)

