"""Reproducible local exploratory training. Never modifies the approved catalog."""
from pathlib import Path
import hashlib, json, platform, sys
import numpy as np
import pandas as pd
import sklearn, joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.dummy import DummyRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ROOT=Path(r"E:\PETROEDGE_AI\codex")
CAT=ROOT/"data/prepared/platform_manifest_001.json"
OUT=ROOT/"models/exploratory_020"

def metrics(y,p):
    return {"mae":float(mean_absolute_error(y,p)),"rmse":float(np.sqrt(mean_squared_error(y,p))),"r2":float(r2_score(y,p)) if len(y)>1 and np.var(y)>0 else None}

def run():
    OUT.mkdir(parents=True,exist_ok=True)
    catalog=json.loads(CAT.read_text(encoding="utf-8-sig"))
    report={"status":"EXPERIMENTAL_NOT_FOR_PRODUCTION","evaluation_scope":"Within-well depth extrapolation only; parent-well groups cross partitions. Not independent-well validation. Quality approval pending.","catalog_sha256":hashlib.sha256(CAT.read_bytes()).hexdigest(),"python":platform.python_version(),"sklearn":sklearn.__version__,"seed":42,"experiments":[]}
    previous=json.loads((OUT/"report.json").read_text()) if (OUT/"report.json").exists() else {}
    completed={e["dataset_id"]:e for e in previous.get("experiments",[]) if e["status"]=="trained_experimental"}
    for key,item in catalog["datasets"].items():
        if key in completed:
            report["experiments"].append(completed[key]);continue
        record={"dataset_id":key,"name":item["name"],"target":item["target_definition"],"condition":item["condition"]}
        try:
            path=(CAT.parent/item["path"]).resolve()
            assert path.is_relative_to(CAT.parent.resolve()),"Path outside catalog"
            raw=path.read_bytes()
            assert hashlib.sha256(raw).hexdigest()==item["sha256"],"Checksum mismatch"
            frame=pd.read_csv(path)
            assert len(frame)==item["rows"],"Row count mismatch"
            features=item["feature_columns"]; target=item["target_column"]
            for col,expected in item.get("constant_columns",{}).items():
                assert frame[col].notna().all() and set(frame[col].astype(str))=={str(expected)},"Mixed target conditions"
            assert not frame.specimen_id.duplicated().any(),"Duplicate specimens"
            if "well_id" not in frame and "well" in frame:frame=frame.rename(columns={"well":"well_id"})
            assert frame.well_id.nunique()==1,"Expected a single-well contract"
            numeric=frame[features+[target,"log_depth_m"]].apply(pd.to_numeric,errors="coerce")
            good=np.isfinite(numeric).all(axis=1)
            if "target_kind" in frame:
                good &= frame["target_kind"].eq("exact") & frame["status"].eq("eligible_for_development")
                good &= frame["exclusion_reasons"].eq("[]")
                good &= ~frame["compromised"].astype(str).str.lower().eq("true")
                good &= ~frame["sample_marker_unresolved"].astype(str).str.lower().eq("true")
            else:
                # Respect recorded development qualification; missing bad-data flags do not pass.
                good &= frame["development_eligible"].astype(str).str.lower().eq("true")
                good &= pd.to_numeric(frame["bad_data_flag"],errors="coerce").eq(0)
                good &= pd.to_numeric(frame["target_raw"],errors="coerce").notna()
            permeability="permeability" in item["target_definition"]
            good &= numeric[target].gt(0) if permeability else numeric[target].between(0,1)
            clean=frame.loc[good].copy(); clean[numeric.columns]=numeric.loc[good]
            depths=np.sort(clean.log_depth_m.unique())
            assert len(depths)>=20,"Fewer than 20 eligible distinct log depths"
            a=int(len(depths)*.6); b=int(len(depths)*.8)
            # Remove one unique depth on each side of both boundaries.
            groups={"train":depths[:a-1],"validation":depths[a+1:b-1],"test":depths[b+1:]}
            parts={name:clean[clean.log_depth_m.isin(ds)].copy() for name,ds in groups.items()}
            assert all(len(f)>=3 for f in parts.values()),"Partition too small"
            folder=OUT/key.replace(":","_");folder.mkdir()
            assigned=frame[["specimen_id","well_id","split_group_id","log_depth_m"]].copy();assigned["partition"]="excluded_qc"
            assigned.loc[good,"partition"]="purged_boundary"
            for name,f in parts.items():assigned.loc[f.index,"partition"]=name
            assigned.to_csv(folder/"assignments.csv",index=False)
            train=parts["train"];val=parts["validation"];test=parts["test"]
            # Log target transformation is fixed in advance, not fitted on holdouts.
            transform=np.log10 if permeability else lambda x:x
            invert=lambda x:10**x if permeability else x
            models={"median_baseline":DummyRegressor(strategy="median"),"random_forest":RandomForestRegressor(n_estimators=128,min_samples_leaf=3,max_features=1.0,random_state=42,n_jobs=1)}
            scores={}
            for name,model in models.items():
                model.fit(train[features],transform(train[target]))
                scores[name]=metrics(val[target],invert(model.predict(val[features])))
                joblib.dump({"model":model,"feature_columns":features,"target_transform":"log10" if permeability else "identity","target_unit":item["constant_columns"]["target_unit"],"condition":item["condition"],"status":"experimental","source_sha256":item["sha256"]},folder/(name+".joblib"))
            winner=min(scores,key=lambda n:scores[n]["mae"])
            # Freeze selection by validation MAE; evaluate selected model once on test.
            pred=invert(models[winner].predict(test[features]))
            test_scores=metrics(test[target],pred)
            pd.DataFrame({"specimen_id":test.specimen_id,"log_depth_m":test.log_depth_m,"measured":test[target],"predicted":pred}).to_csv(folder/"test_predictions.csv",index=False)
            record.update(status="trained_experimental",source_sha256=item["sha256"],feature_columns=features,source_rows=len(frame),eligible_rows=len(clean),excluded_qc=int((~good).sum()),purged_rows=int(assigned.partition.eq("purged_boundary").sum()),partition_rows={n:len(f) for n,f in parts.items()},depth_ranges={n:[float(f.log_depth_m.min()),float(f.log_depth_m.max())] for n,f in parts.items()},validation=scores,selected_model=winner,test=test_scores,target_unit=item["constant_columns"]["target_unit"],artifact_directory=str(folder))
            record["artifact_sha256"]={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in folder.iterdir()}
            (folder/"model_card.json").write_text(json.dumps(record,indent=2,allow_nan=False),encoding="utf-8")
        except Exception as exc:
            record.update(status="blocked",reason=str(exc))
        report["experiments"].append(record)
        print(json.dumps({k:record[k] for k in ("name","status")}|({"selected_model":record["selected_model"],"test":record["test"]} if "test" in record else {"reason":record.get("reason")})),flush=True)
        (OUT/"report.json").write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
    rows=["# Exploratory core/log training", "",report["evaluation_scope"],"", "No catalog approval, production registry or deployed model was changed.","", "| Dataset | Selected by validation MAE | Test MAE | Test R2 |", "|---|---|---|---|"]
    for e in report["experiments"]:
        rows.append(f"| {e['name']} | {e.get('selected_model',e.get('reason','blocked'))} | {e.get('test',{}).get('mae','')} | {e.get('test',{}).get('r2','')} |")
    (OUT/"README.md").write_text("\n".join(rows),encoding="utf-8")
if __name__=="__main__":run()
