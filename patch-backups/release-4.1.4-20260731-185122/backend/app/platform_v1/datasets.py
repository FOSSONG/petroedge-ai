from __future__ import annotations

import csv, hashlib, json, shutil, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Any

from app.platform_v1.database import audit, connection, utcnow
from app.platform_v1.schemas import DatasetLineageNode, DatasetSummary, LasProcessRequest
from app.preprocessing.curve_aliases import canonical_name_for

ALLOWED_EXTENSIONS = {".csv", ".parquet", ".las", ".xlsx", ".xls"}
DATASET_TYPES = {"well_log", "processed_well_log", "fluid_data", "pvt_data", "formation_water", "fluid_contacts", "pressure_data", "temperature_data", "core_data", "production_data", "training_dataset", "prediction_output"}
MAX_UPLOAD_BYTES = 500 * 1024 * 1024

def storage_root() -> Path:
    root = Path.cwd() / "dataset_store"; root.mkdir(parents=True, exist_ok=True); return root.resolve()

def _checksum(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b""): digest.update(chunk)
    return digest.hexdigest()

def _frame(path: Path, limit: int | None = None):
    import pandas as pd
    suffix=path.suffix.lower()
    if suffix==".csv": return pd.read_csv(path, nrows=limit)
    if suffix==".parquet":
        frame=pd.read_parquet(path); return frame.head(limit) if limit else frame
    if suffix in {".xlsx", ".xls"}: return pd.read_excel(path, nrows=limit)
    if suffix==".las":
        import lasio
        frame=lasio.read(path).df().reset_index(); return frame.head(limit) if limit else frame
    raise ValueError("Unsupported dataset type.")

def _profile(path: Path):
    frame=_frame(path)
    columns=[str(c) for c in frame.columns]
    missing={str(k):int(v) for k,v in frame.isna().sum().items()}
    units: dict[str,str]={}
    metadata: dict[str,Any]={}
    if path.suffix.lower()==".las":
        import lasio
        las=lasio.read(path)
        units={str(c.mnemonic):str(c.unit or "") for c in las.curves}
        metadata={"well": {str(item.mnemonic): str(item.value) for item in las.well}}
    return int(len(frame)), columns, missing, units, metadata

def register_upload(name: str, description: str | None, filename: str, stream: BinaryIO, owner_id: str | None, *, dataset_type: str="well_log", field_name: str|None=None, well_name: str|None=None, reservoir_name: str|None=None) -> DatasetSummary:
    suffix=Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS: raise ValueError("Unsupported type. Use CSV, Parquet, LAS or Excel.")
    if dataset_type not in DATASET_TYPES: raise ValueError(f"Unsupported dataset type: {dataset_type}")
    dataset_id=f"ds-{uuid.uuid4().hex[:12]}"; destination=storage_root()/f"{dataset_id}{suffix}"; size=0
    with destination.open("wb") as output:
        while chunk:=stream.read(1024*1024):
            size+=len(chunk)
            if size>MAX_UPLOAD_BYTES: destination.unlink(missing_ok=True); raise ValueError("Dataset exceeds the 500 MB limit.")
            output.write(chunk)
    try: rows,columns,missing,units,metadata=_profile(destination)
    except Exception: destination.unlink(missing_ok=True); raise
    now=utcnow(); version_id=f"{dataset_id}-v1"; checksum=_checksum(destination)
    with connection() as conn:
        conn.execute("""INSERT INTO datasets(dataset_id,version_id,version_number,parent_dataset_id,root_dataset_id,dataset_type,name,description,source_type,file_path,file_name,file_size_bytes,checksum_sha256,row_count,column_count,columns_json,missing_json,units_json,metadata_json,processing_json,field_name,well_name,reservoir_name,status,owner_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (dataset_id,version_id,1,None,dataset_id,dataset_type,name,description,suffix.lstrip('.'),str(destination),filename,size,checksum,rows,len(columns),json.dumps(columns),json.dumps(missing),json.dumps(units),json.dumps(metadata),json.dumps({"operation":"upload"}),field_name,well_name,reservoir_name,"ready",owner_id,now,now))
    audit("dataset.registered","dataset",dataset_id,owner_id,{"file_name":filename,"dataset_type":dataset_type,"checksum":checksum})
    return get_dataset(dataset_id)

def _row_to_model(row) -> DatasetSummary:
    def load(name, default):
        try: return json.loads(row[name] or json.dumps(default))
        except Exception: return default
    return DatasetSummary(dataset_id=row["dataset_id"],version_id=row["version_id"] or f'{row["dataset_id"]}-v1',version_number=row["version_number"] or 1,parent_dataset_id=row["parent_dataset_id"],root_dataset_id=row["root_dataset_id"] or row["dataset_id"],dataset_type=row["dataset_type"] or "well_log",name=row["name"],description=row["description"],source_type=row["source_type"],file_name=row["file_name"],file_size_bytes=row["file_size_bytes"],checksum_sha256=row["checksum_sha256"] or "",row_count=row["row_count"],column_count=row["column_count"],columns=load("columns_json",[]),missing_values=load("missing_json",{}),units=load("units_json",{}),metadata=load("metadata_json",{}),processing=load("processing_json",{}),field_name=row["field_name"],well_name=row["well_name"],reservoir_name=row["reservoir_name"],status=row["status"],owner_id=row["owner_id"],created_at=row["created_at"],updated_at=row["updated_at"])

def list_datasets() -> list[DatasetSummary]:
    with connection() as conn: rows=conn.execute("SELECT * FROM datasets ORDER BY created_at DESC").fetchall()
    return [_row_to_model(row) for row in rows]

def get_dataset(dataset_id: str) -> DatasetSummary:
    with connection() as conn: row=conn.execute("SELECT * FROM datasets WHERE dataset_id=?",(dataset_id,)).fetchone()
    if row is None: raise KeyError(dataset_id)
    return _row_to_model(row)

def get_dataset_path(dataset_id: str) -> Path:
    with connection() as conn: row=conn.execute("SELECT file_path FROM datasets WHERE dataset_id=?",(dataset_id,)).fetchone()
    if row is None: raise KeyError(dataset_id)
    path=Path(row["file_path"])
    if not path.exists(): raise FileNotFoundError(f"Dataset file is missing: {path}")
    return path

def preview_dataset(dataset_id: str, limit: int=500):
    frame=_frame(get_dataset_path(dataset_id),limit).replace({float("inf"):None,float("-inf"):None}); frame=frame.where(frame.notna(),None); summary=get_dataset(dataset_id)
    return {"dataset_id":dataset_id,"columns":[str(c) for c in frame.columns],"rows":frame.to_dict(orient="records"),"total_rows":int(summary.row_count or len(frame))}

def process_las(dataset_id: str, request: LasProcessRequest, actor_id: str|None) -> DatasetSummary:
    parent=get_dataset(dataset_id); source=get_dataset_path(dataset_id)
    if source.suffix.lower()!=".las": raise ValueError("Only LAS datasets can create processed LAS versions.")
    import lasio, numpy as np
    las=lasio.read(source); mapping={}
    if request.normalise_mnemonics:
        for curve in las.curves:
            canonical=canonical_name_for(str(curve.mnemonic))
            if canonical and canonical!=curve.mnemonic: mapping[str(curve.mnemonic)]=canonical; curve.mnemonic=canonical
    for curve in las.curves:
        values=np.asarray(curve.data,dtype=float)
        for null in request.null_values: values[np.isclose(values,null,equal_nan=False)]=np.nan
        if request.interpolate_limit>0:
            import pandas as pd
            values=pd.Series(values).interpolate(limit=request.interpolate_limit,limit_direction="both").to_numpy()
        curve.data=values
    child_id=f"ds-{uuid.uuid4().hex[:12]}"; version=parent.version_number+1; destination=storage_root()/f"{child_id}.las"; las.write(destination,version=2.0)
    rows,columns,missing,units,metadata=_profile(destination); now=utcnow(); checksum=_checksum(destination)
    processing={"operation":"las_processing","curve_mapping":mapping,"null_values":request.null_values,"interpolate_limit":request.interpolate_limit,"normalise_mnemonics":request.normalise_mnemonics,"harmonise_units":request.harmonise_units}
    with connection() as conn:
        conn.execute("""INSERT INTO datasets(dataset_id,version_id,version_number,parent_dataset_id,root_dataset_id,dataset_type,name,description,source_type,file_path,file_name,file_size_bytes,checksum_sha256,row_count,column_count,columns_json,missing_json,units_json,metadata_json,processing_json,field_name,well_name,reservoir_name,status,owner_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (child_id,f"{parent.root_dataset_id}-v{version}",version,parent.dataset_id,parent.root_dataset_id,"processed_well_log",request.name or f"{parent.name} processed v{version}",request.description or f"Processed from {parent.version_id}","las",str(destination),f"{Path(parent.file_name).stem}-processed-v{version}.las",destination.stat().st_size,checksum,rows,len(columns),json.dumps(columns),json.dumps(missing),json.dumps(units),json.dumps(metadata),json.dumps(processing),parent.field_name,parent.well_name,parent.reservoir_name,"ready",actor_id,now,now))
        conn.execute("INSERT INTO dataset_lineage(parent_dataset_id,child_dataset_id,operation,parameters_json,actor_id,created_at) VALUES (?,?,?,?,?,?)",(parent.dataset_id,child_id,"las_processing",json.dumps(processing),actor_id,now))
    audit("dataset.version.created","dataset",child_id,actor_id,{"parent":parent.dataset_id,"version":version})
    return get_dataset(child_id)

def lineage(dataset_id: str) -> DatasetLineageNode:
    dataset=get_dataset(dataset_id)
    with connection() as conn:
        parents=[r[0] for r in conn.execute("SELECT parent_dataset_id FROM dataset_lineage WHERE child_dataset_id=?",(dataset_id,)).fetchall()]
        children=[r[0] for r in conn.execute("SELECT child_dataset_id FROM dataset_lineage WHERE parent_dataset_id=?",(dataset_id,)).fetchall()]
        ops=[{"parent_dataset_id":r[0],"child_dataset_id":r[1],"operation":r[2],"parameters":json.loads(r[3] or '{}'),"created_at":r[4]} for r in conn.execute("SELECT parent_dataset_id,child_dataset_id,operation,parameters_json,created_at FROM dataset_lineage WHERE parent_dataset_id=? OR child_dataset_id=? ORDER BY created_at",(dataset_id,dataset_id)).fetchall()]
    return DatasetLineageNode(dataset=dataset,parents=parents,children=children,operations=ops)

def delete_dataset(dataset_id: str, actor_id: str|None=None) -> None:
    with connection() as conn:
        row=conn.execute("SELECT file_path,file_name FROM datasets WHERE dataset_id=?",(dataset_id,)).fetchone()
        if row is None: raise KeyError(dataset_id)
        children=conn.execute("SELECT COUNT(*) FROM dataset_lineage WHERE parent_dataset_id=?",(dataset_id,)).fetchone()[0]
        if children: raise ValueError("Dataset has derived versions and cannot be deleted until its children are removed.")
        conn.execute("DELETE FROM experiments WHERE dataset_id=?",(dataset_id,)); conn.execute("DELETE FROM dataset_lineage WHERE child_dataset_id=?",(dataset_id,)); conn.execute("DELETE FROM datasets WHERE dataset_id=?",(dataset_id,))
    Path(row["file_path"]).unlink(missing_ok=True); audit("dataset.deleted","dataset",dataset_id,actor_id,{"file_name":row["file_name"]})


def _register_derived_frame(parent_id: str, frame, name: str, operation: dict[str, Any], actor_id: str | None):
    parent = get_dataset(parent_id)
    dataset_id = f"ds-{uuid.uuid4().hex[:12]}"
    destination = storage_root() / f"{dataset_id}.csv"
    frame.to_csv(destination, index=False)
    rows, columns, missing, units, metadata = _profile(destination)
    now = utcnow(); version_id = f"{dataset_id}-v1"; checksum = _checksum(destination)
    inherited_units = dict(parent.units or {})
    with connection() as conn:
        conn.execute("""INSERT INTO datasets(dataset_id,version_id,version_number,parent_dataset_id,root_dataset_id,dataset_type,name,description,source_type,file_path,file_name,file_size_bytes,checksum_sha256,row_count,column_count,columns_json,missing_json,units_json,metadata_json,processing_json,field_name,well_name,reservoir_name,status,owner_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (dataset_id,version_id,1,parent_id,parent.root_dataset_id,"processed_well_log",name,parent.description,"csv",str(destination),destination.name,destination.stat().st_size,checksum,rows,len(columns),json.dumps(columns),json.dumps(missing),json.dumps(inherited_units),json.dumps(metadata),json.dumps(operation),parent.field_name,parent.well_name,parent.reservoir_name,"ready",actor_id,now,now))
        conn.execute("INSERT INTO dataset_lineage(parent_dataset_id,child_dataset_id,operation,parameters_json,actor_id,created_at) VALUES (?,?,?,?,?,?)",(parent_id,dataset_id,operation.get("operation","derived"),json.dumps(operation),actor_id,now))
    audit("dataset.derived","dataset",dataset_id,actor_id,{"parent_dataset_id":parent_id,"operation":operation})
    return get_dataset(dataset_id)


def quality_report(dataset_id: str) -> dict[str, Any]:
    import numpy as np
    import pandas as pd
    from app.preprocessing.curve_aliases import canonical_name_for
    path = get_dataset_path(dataset_id); frame = _frame(path)
    summary = get_dataset(dataset_id)
    standard_nulls = [-999.25, -999.0, -9999.0, -99999.0, 999.25, 9999.0]
    warnings: list[str] = []; unit_warnings: list[str] = []; columns: list[dict[str, Any]] = []
    depth_candidates = [c for c in frame.columns if str(c).upper() in {"DEPTH","DEPT","MD","TVD","TVDSS"}]
    if not depth_candidates: warnings.append("No recognised depth column was found. Depth-dependent QC will be limited.")
    for column in frame.columns:
        series = frame[column]
        numeric = pd.to_numeric(series, errors="coerce")
        null_codes = int(sum(np.isclose(numeric.fillna(np.inf), marker, rtol=0, atol=1e-8).sum() for marker in standard_nulls)) if numeric.notna().any() else 0
        canonical = canonical_name_for(str(column))
        unit = (summary.units or {}).get(str(column), "")
        if canonical and not unit:
            unit_warnings.append(f"{column}: unit is missing. The curve remains usable, but unit-dependent conversions and physical limits require review.")
        columns.append({"column":str(column),"dtype":str(series.dtype),"missing":int(series.isna().sum()),"missing_percent":round(float(series.isna().mean()*100),3),"null_codes":null_codes,"unique":int(series.nunique(dropna=True)),"unit":unit,"canonical_curve":canonical})
    duplicate_rows = int(frame.duplicated().sum())
    if duplicate_rows: warnings.append(f"{duplicate_rows} duplicate rows detected.")
    if depth_candidates:
        depth = pd.to_numeric(frame[depth_candidates[0]], errors="coerce")
        duplicate_depth = int(depth.duplicated().sum()); non_monotonic = int((depth.diff().dropna() < 0).sum())
        if duplicate_depth: warnings.append(f"{duplicate_depth} duplicate depth samples detected in {depth_candidates[0]}.")
        if non_monotonic: warnings.append(f"{non_monotonic} non-monotonic depth transitions detected in {depth_candidates[0]}.")
    null_total = sum(c["null_codes"] for c in columns)
    if null_total: warnings.append(f"{null_total} petroleum null-code values detected and should be converted to missing values before modelling.")
    return {"dataset_id":dataset_id,"blocking_errors":[],"warnings":warnings,"unit_warnings":unit_warnings,"summary":{"rows":len(frame),"columns":len(frame.columns),"duplicate_rows":duplicate_rows,"petroleum_null_codes":null_total,"missing_cells":int(frame.isna().sum().sum())},"column_quality":columns,"ready_for_training":True}


def prepare_dataset(dataset_id: str, request, actor_id: str | None):
    import numpy as np
    import pandas as pd
    from sklearn.preprocessing import MinMaxScaler, RobustScaler, StandardScaler
    from app.preprocessing.pipeline import PipelineConfig, run_preprocessing_pipeline
    frame = _frame(get_dataset_path(dataset_id))
    for marker in request.null_values:
        for column in frame.columns:
            numeric = pd.to_numeric(frame[column], errors="coerce")
            mask = np.isclose(numeric.fillna(np.inf), marker, rtol=0, atol=1e-8)
            if mask.any(): frame.loc[mask, column] = np.nan
    for column in request.zero_as_null_columns:
        if column in frame.columns: frame.loc[pd.to_numeric(frame[column],errors="coerce").eq(0),column]=np.nan
    depth = request.depth_column or next((c for c in frame.columns if str(c).upper() in {"DEPTH","DEPT","MD","TVD","TVDSS"}), "depth_m")
    result = run_preprocessing_pipeline(frame, config=PipelineConfig(depth_column=depth, interpolation_limit=request.interpolate_limit, despike=request.despike, smooth=request.smooth, clip_to_physical_ranges=request.clip_physical_ranges))
    output = result.dataframe.copy()
    scale_columns = request.scaling_columns or [c for c in output.columns if pd.api.types.is_numeric_dtype(output[c]) and c != depth]
    scale_columns = [c for c in scale_columns if c in output.columns and pd.api.types.is_numeric_dtype(output[c])]
    if request.scaling != "none" and scale_columns:
        scaler = {"standard":StandardScaler(),"minmax":MinMaxScaler(),"robust":RobustScaler()}[request.scaling]
        output[scale_columns] = scaler.fit_transform(output[scale_columns])
    operation={"operation":"petroleum_preprocessing","configuration":request.model_dump(mode="json"),"pipeline_summary":result.summary(),"unit_policy":"warn_only"}
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    name=request.name or f"{get_dataset(dataset_id).name} · ML-ready · {timestamp}"
    return _register_derived_frame(dataset_id,output,name,operation,actor_id)


def edit_dataset(dataset_id: str, request, actor_id: str | None):
    import pandas as pd
    frame = _frame(get_dataset_path(dataset_id))
    for op in request.operations:
        action=op.get("action")
        if action=="rename_column": frame=frame.rename(columns={str(op.get("column")):str(op.get("new_name"))})
        elif action=="delete_column": frame=frame.drop(columns=[str(op.get("column"))],errors="ignore")
        elif action=="delete_row":
            index=int(op.get("row",-1))
            if 0<=index<len(frame): frame=frame.drop(frame.index[index]).reset_index(drop=True)
        elif action=="set_cell":
            row=int(op.get("row",-1)); column=str(op.get("column"))
            if 0<=row<len(frame) and column in frame.columns: frame.at[frame.index[row],column]=op.get("value")
        elif action=="add_column": frame[str(op.get("column") or f"column_{len(frame.columns)+1}")]=op.get("default_value")
        elif action=="add_row": frame=pd.concat([frame,pd.DataFrame([op.get("values") or {}])],ignore_index=True)
        elif action=="formula_column":
            column=str(op.get("column")); expression=str(op.get("expression"))
            frame[column]=frame.eval(expression,engine="python")
    name=request.name or f"{get_dataset(dataset_id).name} · edited"
    return _register_derived_frame(dataset_id,frame,name,{"operation":"spreadsheet_edit","operations":request.operations},actor_id)
