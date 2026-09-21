from pathlib import Path
import json,hashlib,zipfile,re,xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
import sklearn,lasio
from sklearn.dummy import DummyRegressor,DummyClassifier
from sklearn.ensemble import RandomForestRegressor,RandomForestClassifier
from sklearn.linear_model import Ridge,LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.compose import TransformedTargetRegressor
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score,f1_score,balanced_accuracy_score,confusion_matrix
B=Path(r"E:\PETROEDGE_AI\codex");O=B/'models/development_comparison_037';O.mkdir(parents=True,exist_ok=False)
D=B/'docs/assessment/model_diagnostics_036';C=B/'data/prepared/platform_manifest_001.json'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
cat=json.loads(C.read_text(encoding='utf-8-sig'));previous=json.loads((B/'models/exploratory_020/report.json').read_text());old={e['name']:e for e in previous['experiments']}
foldfile=D/'REGRESSION_DEVELOPMENT_FOLDS.csv';folds=pd.read_csv(foldfile);assert folds.original_partition.eq('train').all()
protocol=dict(seed=37,scope='Conditional development only; no held-out test inference or new model binaries',regression=['median','scaled_ridge_alpha10','random_forest_128_leaf3'],lithology=['majority','scaled_logistic_C1','random_forest_128_leaf3'],selection='Equal-fold mean original-unit MAE; report fold wins and out-of-range predictions, never production promotion',source_hashes={str(C):sha(C),str(foldfile):sha(foldfile)},preprocessing='Scaler fits only inside each fold; permeability log1p transform fixed; no imputations',test_policy='Original regression validation/test and purged rows excluded from fitting and scoring. Lithology prior test wells X-006/X-008 excluded.',new_artifacts_saved=False)
(O/'PROTOCOL.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
reg=[];preds=[]
for task,groups in folds.groupby('task'):
 e=old[task];entry=cat['datasets'][e['dataset_id']];path=C.parent/entry['path'];assert sha(path)==entry['sha256']
 a=pd.read_csv(Path(e['artifact_directory'])/'assignments.csv');allowed=set(a[a.partition.eq('train')].specimen_id);assert set(groups.specimen_id)<=allowed
 raw=pd.read_csv(path).set_index('specimen_id');f=entry['feature_columns'];target=entry['target_column'];log='permeability' in entry['target_definition']
 for fold,g in groups.groupby('fold'):
  tr=raw.loc[g[g.role.eq('train')].specimen_id];va=raw.loc[g[g.role.eq('validation')].specimen_id]
  assert set(tr.index).isdisjoint(va.index) and tr.log_depth_m.max()<va.log_depth_m.min()
  assert np.isfinite(tr[f+[target]]).all().all() and np.isfinite(va[f+[target]]).all().all()
  models={'median':DummyRegressor(strategy='median'),'scaled_ridge_alpha10':make_pipeline(StandardScaler(),Ridge(alpha=10)),'random_forest_128_leaf3':RandomForestRegressor(n_estimators=128,min_samples_leaf=3,random_state=37,n_jobs=1)}
  for name,model in models.items():
   if log and name!='median':model=TransformedTargetRegressor(regressor=model,func=np.log1p,inverse_func=np.expm1)
   model.fit(tr[f],tr[target]);yp=model.predict(va[f]);y=va[target].to_numpy();assert np.isfinite(yp).all()
   invalid=int((yp<0).sum()) if log else int(((yp<0)|(yp>1)).sum())
   row=dict(task=task,fold=int(fold),model=name,train_rows=len(tr),validation_rows=len(va),mae=float(mean_absolute_error(y,yp)),rmse=float(np.sqrt(mean_squared_error(y,yp))),bias=float(np.mean(yp-y)),r2=float(r2_score(y,yp)) if np.var(y)>0 else None,out_of_range=invalid,unit=entry['constant_columns']['target_unit'],log1p_mae=float(np.mean(abs(np.log1p(y)-np.log1p(yp)))) if log and invalid==0 else None)
   reg.append(row)
   for specimen,truth,v in zip(va.index,y,yp):preds.append(dict(task=task,fold=int(fold),model=name,specimen_id=specimen,observed=float(truth),predicted=float(v)))
 print(task,'completed',flush=True)
rdf=pd.DataFrame(reg);rdf.to_csv(O/'REGRESSION_FOLD_METRICS.csv',index=False);pd.DataFrame(preds).to_csv(O/'REGRESSION_DEVELOPMENT_PREDICTIONS.csv',index=False)
summary=[]
for task,g in rdf.groupby('task'):
 mean=g.groupby('model').mae.mean();base=float(mean['median']);eligible=[n for n,h in g.groupby('model') if h.out_of_range.sum()==0];winner=min(eligible,key=lambda n:mean[n]);pivot=g.pivot(index='fold',columns='model',values='mae')
 summary.append(dict(task=task,folds=int(g.fold.nunique()),lowest_mean_mae=winner,mean_mae=float(mean[winner]),baseline_mean_mae=base,reduction_percent=float(100*(1-mean[winner]/base)) if base else 0,fold_wins_vs_baseline=int((pivot[winner]<pivot['median']).sum()),mae_by_model={k:float(v) for k,v in mean.items()},production_eligible=False))
# Conditional GR-only lithology: no missing-density constant, no test wells.
ld=pd.read_csv(B/'models/lithology_development_025/DEVELOPMENT_DATA.csv');assert set(ld.well).isdisjoint({'X-006','X-008'});assert ld.gr_api.notna().all();labels=['sand','shale'];lrows=[];lp=[];evidence=[]
for path in ld.source_path.unique():
 expected=ld[ld.source_path.eq(path)].source_sha256.unique();assert len(expected)==1 and sha(path)==expected[0]
 with zipfile.ZipFile(path) as z:
  texts=[]
  for n in z.namelist():
   if n.endswith('.xml') and any(k in n for k in ['sharedStrings','comments','sheet']):texts += [e.text for e in ET.fromstring(z.read(n)).iter() if e.tag.endswith('}t') and e.text]
 hits=[t for t in texts if re.search(r'\b(depth|feet|ft|metres|meters|datum|rkb|md|tvd|drill floor)\b',t,re.I)]
 evidence.append(dict(source_path=path,sha256=sha(path),metadata_hits=hits,conclusion='No explicit depth units/datum found in inspected worksheet text/comments; assumption remains'))
for well in sorted(ld.well.unique()):
 tr=ld[ld.well.ne(well)];va=ld[ld.well.eq(well)]
 models={'majority':DummyClassifier(strategy='most_frequent'),'scaled_logistic_C1':make_pipeline(StandardScaler(),LogisticRegression(C=1,max_iter=1000,random_state=37)),'random_forest_128_leaf3':RandomForestClassifier(n_estimators=128,min_samples_leaf=3,random_state=37,n_jobs=1)}
 for name,model in models.items():
  model.fit(tr[['gr_api']],tr.label);yp=model.predict(va[['gr_api']]);lrows.append(dict(held_well=well,model=name,rows=len(va),classes=va.label.value_counts().to_dict(),macro_f1_fixed_two_classes=float(f1_score(va.label,yp,labels=labels,average='macro',zero_division=0)),balanced_accuracy=float(balanced_accuracy_score(va.label,yp)) if va.label.nunique()==2 else None,confusion=confusion_matrix(va.label,yp,labels=labels).tolist()))
  for (_,r),v in zip(va.iterrows(),yp):lp.append(dict(well=well,source_row=int(r.excel_row),model=name,observed=r.label,predicted=v))
lp=pd.DataFrame(lp);lp.to_csv(O/'LITHOLOGY_DEVELOPMENT_PREDICTIONS.csv',index=False)
ls=[]
for name,g in lp.groupby('model'):ls.append(dict(model=name,pooled_macro_f1=float(f1_score(g.observed,g.predicted,labels=labels,average='macro',zero_division=0)),pooled_balanced_accuracy=float(balanced_accuracy_score(g.observed,g.predicted)),confusion=confusion_matrix(g.observed,g.predicted,labels=labels).tolist()))
# Label provenance review restricted to original train/validation exports; no prior test export read.
root=Path(r"F:\DATA_PETROEDGE_AI\Niger delta Fields\Field X\X_FIELD_Well logs\X-005");sat=[]
for name,vw in [('las8374.las','VUWA'),('las8098.las','VUWA:2')]:
 d=lasio.read(str(root/name)).df()[['SW','SO','VUOI',vw]].dropna();zero=d.SW.eq(0)&d.SO.eq(0);positive=d.VUOI+d[vw]>0;ratio=d.loc[positive,vw]/(d.loc[positive,'VUOI']+d.loc[positive,vw])
 sat.append(dict(file=name,sha256=sha(root/name),rows=len(d),zero_pair_rows=int(zero.sum()),zero_volume_rows=int((d.loc[zero,'VUOI'].eq(0)&d.loc[zero,vw].eq(0)).sum()),max_difference_sw_vs_volume_ratio=float(abs(d.loc[positive,'SW']-ratio).max()),conclusion='Zero pairs coincide with zero oil/water volumes, so the volume-ratio denominator is zero. Mask/provenance remains unresolved; do not label these rows as water-free or gas-filled. Saturation retraining deferred.'))
report=dict(protocol=protocol,regression_summary=summary,lithology_pooled=ls,lithology_folds=lrows,lithology_depth_evidence=evidence,saturation_source_review=sat,models_fitted=len(reg)+len(lrows),model_binaries_saved=0,production_changes=0,sklearn=sklearn.__version__,limitations=['Small within-well regression folds; original validation/test excluded. Better development MAE is not independent-well evidence.','Lithology retains unverified depth-datum assumption and one single-class held-well fold. Pooled development scores are not fresh final tests.','No additional hyperparameter search or saturation relabeling performed.'])
(O/'REPORT.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
lines=['# Conditional development comparisons 037','','Fixed development comparisons completed. No previous test data scored. No model binaries saved, deployed or promoted.','','## Porosity and permeability','','| Task | Lowest mean fold MAE | MAE | Baseline MAE | Fold wins |','|---|---|---:|---:|---:|']
for e in summary:lines.append(f"| {e['task']} | {e['lowest_mean_mae']} | {e['mean_mae']:.4g} | {e['baseline_mean_mae']:.4g} | {e['fold_wins_vs_baseline']}/{e['folds']} |")
lines+=['','Units: porosity fraction or permeability mD as recorded per task. Do not compare unlike conditions. Lowest equal-fold MAE is descriptive selection, not confirmation.','','## Lithology','','| GR-only model | Pooled development macro F1 | Balanced accuracy |','|---|---:|---:|']
for e in ls:lines.append(f"| {e['model']} | {e['pooled_macro_f1']:.4f} | {e['pooled_balanced_accuracy']:.4f} |")
lines+=['','Depth workbooks provide only a depth label, not explicit units/datum in the inspected text. The conditional assumption persists. No density inputs were fabricated. The X-005 held fold contains only sand; full per-fold results disclose this.','','## Saturation','','Original training/validation exports confirm zero saturation pairs coincide with zero fluid-volume values. These are unresolved labels, not confirmed gas, and cannot be repaired by changing the acquisition date. The original saturation test export was not read or rescored in this run. No new saturation model was fitted.','','## Next action','','Prioritize regression targets with consistent development-fold improvement for a separate confirmation stage, keeping laboratory conditions distinct. Resolve lithology datum and saturation processing/masking evidence before claiming physical validation. Fresh independent parent-well data remains required for customer qualification.','','Artifacts: REPORT.json, PROTOCOL.json, REGRESSION_FOLD_METRICS.csv, REGRESSION_DEVELOPMENT_PREDICTIONS.csv and LITHOLOGY_DEVELOPMENT_PREDICTIONS.csv.']
(O/'README.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps(dict(fits=report['models_fitted'],regression_winners=pd.Series([e['lowest_mean_mae'] for e in summary]).value_counts().to_dict(),lithology=ls,output=str(O)),indent=2))
