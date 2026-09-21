from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.compose import TransformedTargetRegressor
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
B=Path(r"E:\PETROEDGE_AI\codex");O=B/'models/regression_confirmation_038';O.mkdir(parents=True,exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
C=B/'data/prepared/platform_manifest_001.json';cat=json.loads(C.read_text(encoding='utf-8-sig'))
P=B/'models/development_comparison_037/REPORT.json';prior=json.loads(P.read_text());chosen=[e for e in prior['regression_summary'] if e['fold_wins_vs_baseline']==e['folds']];assert len(chosen)==6
old=json.loads((B/'models/exploratory_020/report.json').read_text());lookup={e['name']:e for e in old['experiments']}
protocol=dict(selection='Six phase037 candidates that beat the median on all three internal development folds; same algorithms/seed/target transforms; no tuning.',evaluation='Existing validation partitions only; previously used in phases020/027/028, so not fresh independent confirmation. Historical test partitions are excluded from fitting, prediction and metrics.',seed=37,source_report_sha256=sha(P),catalog_sha256=sha(C),artifact_policy='Metrics and predictions only; no model binaries or deployment.',decision='Development confirmation passes only if original-unit MAE beats train-median baseline and predictions meet physical ranges. Passing does not imply production qualification.')
(O/'PROTOCOL.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
results=[];predictions=[];paired={}
for selected in chosen:
 e=lookup[selected['task']];c=cat['datasets'][e['dataset_id']];path=C.parent/c['path'];assert sha(path)==c['sha256']==e['source_sha256']
 ap=Path(e['artifact_directory'])/'assignments.csv';assert sha(ap)==e['artifact_sha256']['assignments.csv'];a=pd.read_csv(ap)
 trainids=a.loc[a.partition.eq('train'),'specimen_id'];validids=a.loc[a.partition.eq('validation'),'specimen_id'];testids=set(a.loc[a.partition.eq('test'),'specimen_id']);assert not(set(trainids)|set(validids))&testids
 data=pd.read_csv(path).set_index('specimen_id');tr=data.loc[trainids];va=data.loc[validids];assert tr.log_depth_m.max()<va.log_depth_m.min()
 features=c['feature_columns'];target=c['target_column'];assert np.isfinite(tr[features+[target]]).all().all() and np.isfinite(va[features+[target]]).all().all()
 model=RandomForestRegressor(n_estimators=128,min_samples_leaf=3,random_state=37,n_jobs=1) if selected['lowest_mean_mae']=='random_forest_128_leaf3' else make_pipeline(StandardScaler(),Ridge(alpha=10))
 perm='permeability' in c['target_definition']
 if perm:model=TransformedTargetRegressor(regressor=model,func=np.log1p,inverse_func=np.expm1)
 model.fit(tr[features],tr[target]);baseline=DummyRegressor(strategy='median').fit(tr[features],tr[target]);yp=model.predict(va[features]);bp=baseline.predict(va[features]);y=va[target].to_numpy();assert np.isfinite(yp).all()
 invalid=(yp<0) if perm else ((yp<0)|(yp>1));mae=float(mean_absolute_error(y,yp));bm=float(mean_absolute_error(y,bp))
 metrics=dict(mae=mae,baseline_mae=bm,mae_reduction_percent=100*(1-mae/bm) if bm else None,rmse=float(np.sqrt(mean_squared_error(y,yp))),bias=float(np.mean(yp-y)),r2=float(r2_score(y,yp)) if np.var(y)>0 else None,out_of_range=int(invalid.sum()),rows_improved_vs_baseline=int((abs(y-yp)<abs(y-bp)).sum()),rows_worse_vs_baseline=int((abs(y-yp)>abs(y-bp)).sum()))
 outside={col:int(((va[col]<tr[col].min())|(va[col]>tr[col].max())).sum()) for col in features}
 passed=mae<bm and not invalid.any()
 results.append(dict(task=e['name'],model=selected['lowest_mean_mae'],training_rows=len(tr),validation_rows=len(va),test_rows_excluded=len(testids),unit=c['constant_columns']['target_unit'],metrics=metrics,outside_training_feature_range=outside,development_confirmation_pass=bool(passed),production_eligible=False,source_sha256=sha(path),assignments_sha256=sha(ap)))
 for sid,truth,v,base in zip(va.index,y,yp,bp):predictions.append(dict(task=e['name'],specimen_id=sid,observed=float(truth),predicted=float(v),baseline=float(base),partition='existing_validation'))
 if 'NO 15/9-19 A / permeability' in e['name']:
  part=data.loc[list(trainids)+list(validids)].copy();paired[c['target_definition']]=part[['log_depth_m',target]].reset_index()
 print(e['name'],'pass' if passed else 'fail',round(mae,6),'baseline',round(bm,6),flush=True)
keys=list(paired);comparison={}
if len(keys)==2:
 l=paired[keys[0]];r=paired[keys[1]];j=l.merge(r,on='specimen_id',suffixes=('_left','_right'),validate='one_to_one')
 comparison=dict(targets=keys,shared_development_specimens=len(j),same_log_depth=bool(np.allclose(j.log_depth_m_left,j.log_depth_m_right)),exact_equal_values=int(np.isclose(j.target_value_left,j.target_value_right,rtol=0,atol=0).sum()),pearson_correlation=float(j.target_value_left.corr(j.target_value_right)),interpretation='Different target values on the same specimens; empirical Klinkenberg correction derives from nitrogen permeability. These are related targets, not independent datasets or independent confirmations.')
report=dict(protocol=protocol,results=results,passes=sum(e['development_confirmation_pass'] for e in results),related_volve_targets=comparison,model_binaries_saved=0,test_predictions_made=0,production_changes=0)
pd.DataFrame(predictions).to_csv(O/'VALIDATION_PREDICTIONS.csv',index=False)
(O/'REPORT.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
lines=['# Regression development confirmation 038','','Six fixed phase037 candidates evaluated on existing validation partitions. These partitions have already informed earlier development; this is a stability check, not fresh independent validation. Historical tests were not predicted or rescored.','','| Task | Candidate | Validation rows | MAE | Median MAE | Development check |','|---|---|---:|---:|---:|---|']
for e in results:lines.append(f"| {e['task']} | {e['model']} | {e['validation_rows']} | {e['metrics']['mae']:.5g} | {e['metrics']['baseline_mae']:.5g} | {'Pass' if e['development_confirmation_pass'] else 'Fail'} |")
lines+=['','MAE units follow the target: porosity fraction or permeability mD. Full metrics include bias, R2, per-row wins and input-range extrapolation.','','## Related target check','',comparison.get('interpretation','No comparison available'),f"Shared development specimens: {comparison.get('shared_development_specimens')}; correlation: {comparison.get('pearson_correlation')}. Exact equality count: {comparison.get('exact_equal_values')}.",'','## Decision','','Only passing candidates remain on the development shortlist. No automatic model promotion: laboratory conditions, limited validation rows and reused partitions prevent customer qualification. No additional model binaries saved.','','Next: obtain or qualify genuinely new parent wells with matching target definitions/conditions and pre-register acceptance tolerances before evaluation. If no new data is available, use passing candidates only in clearly labeled research demonstrations with explicit input and domain checks.']
(O/'README.md').write_text('\n'.join(lines),encoding='utf-8');print(json.dumps(dict(passes=report['passes'],related_targets=comparison),indent=2))
