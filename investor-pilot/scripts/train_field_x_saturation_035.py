from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd
import lasio,joblib,sklearn
from sklearn.ensemble import RandomForestRegressor
from sklearn.dummy import DummyRegressor
from sklearn.metrics import mean_absolute_error,r2_score
B=Path(r"E:\PETROEDGE_AI\codex");O=B/"models/field_x_saturation_035";O.mkdir(parents=True,exist_ok=False)
D=Path(r"F:\DATA_PETROEDGE_AI\Niger delta Fields\Field X\X_FIELD_Well logs\X-005")
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
review=B/"data/prepared/field_x_rst_034";old=json.loads((review/"HEADER_EVIDENCE.json").read_text())
for h in old:assert sha(D/h['file'])==h['sha256']
d=pd.read_csv(review/"PAIRED_RST_VALUES.csv").sort_values('depth_ft');features=['gamma_ray_api','density_gcc']
for name,curve,target in [('las3890.las','GRL',features[0]),('las2735.las','FDC',features[1])]:
 l=lasio.read(str(D/name));assert l.curves[0].unit=='F'
 x=l.df()[[curve]].reset_index();x.columns=[target+'_depth_ft',target];assert x.iloc[:,0].is_unique
 d=pd.merge_asof(d,x.sort_values(x.columns[0]),left_on='depth_ft',right_on=x.columns[0],direction='nearest',tolerance=.26)
 d[target+'_depth_delta_ft']=(d.depth_ft-d[x.columns[0]]).abs()
d['split']=d.file.map({'las8374.las':'train','las8098.las':'validation','las7738.las':'test'})
d['hold_reason']='';good=d.gamma_ray_api.between(0,250)&d.density_gcc.between(1.5,3.2)&d.sw.between(0,1)&d.so.between(0,1)
d.loc[~good,'hold_reason']='Missing or out-of-range input/target';d.loc[~good,'split']='excluded'
d['adopted_working_date']='1998-12-06';d['date_basis']='User-authorized assumption; original 1966 input-log and 1998 RST dates retained in source evidence'
d['label_scope']='RST interpretation reproduction, not measured in-situ truth';d['well']='X-005'
d['training_approved']=good;d['production_eligible']=False
assert d.depth_ft.is_unique and d.split.notna().all()
parts={s:d[d.split.eq(s)] for s in ['train','validation','test']};assert all(len(v)>=20 for v in parts.values())
assert parts['train'].depth_ft.max()<parts['validation'].depth_ft.min()<parts['test'].depth_ft.min()
limits=['One well with interval holdouts; not independent-well validation.','User-adopted 1998 date is an assumption, not a correction to raw source headers.','GR and density only. No resistivity, neutron or sonic requirement; no imputation.','Targets are RST interpretations; no independent core-validation claim.','No gas label exists. Oil and water predictions are separate, not three-phase probabilities.','No tuning or refitting after held-out test evaluation.','LL3R resistivity unavailable in the deepest test interval.']
protocol=dict(features=features,units=['API','g/cm3'],working_date='1998-12-06',counts={k:len(v) for k,v in parts.items()},excluded=int((~good).sum()),design='Fixed RF128 min_leaf3 seed35 and train-median baseline per target; all train-only fits, both predefined methods evaluated once; disjoint depth intervals',limitations=limits,production_eligible=False)
(O/'PROTOCOL.json').write_text(json.dumps(protocol,indent=2));d.to_csv(O/'SPLIT_MANIFEST.csv',index=False)
results=[];preds=[]
for target in ['sw','so']:
 for name,model in [('median',DummyRegressor(strategy='median')),('random_forest',RandomForestRegressor(n_estimators=128,min_samples_leaf=3,random_state=35,n_jobs=1))]:
  model.fit(parts['train'][features],parts['train'][target]);f=O/f'{target}_{name}.joblib';joblib.dump(dict(model=model,required_features=features,target=target,target_unit='fraction',protocol=protocol),f)
  metrics={}
  for split in ['validation','test']:
   x=parts[split];y=model.predict(x[features]);np.testing.assert_allclose(y,joblib.load(f)['model'].predict(x[features]),rtol=0,atol=0)
   assert np.isfinite(y).all() and ((y>=0)&(y<=1)).all()
   metrics[split]=dict(mae_percentage_points=float(100*mean_absolute_error(x[target],y)),r2=float(r2_score(x[target],y)))
   for (_,row),v in zip(x.iterrows(),y):preds.append(dict(depth_ft=row.depth_ft,split=split,target=target,model=name,observed=row[target],predicted=float(v)))
  results.append(dict(target=target,model=name,metrics=metrics,artifact=str(f),sha256=sha(f)))
r=dict(status='experimental_under_declared_date_assumption',protocol=protocol,results=results,source_hashes={h['file']:h['sha256'] for h in old},verification='Source hashes, disjoint depths, input/target QC, exact saved-artifact reload predictions passed',production_eligible=False)
pd.DataFrame(preds).to_csv(O/'PREDICTIONS.csv',index=False);(O/'REPORT.json').write_text(json.dumps(r,indent=2,allow_nan=False))
(O/'README.md').write_text('# Field X experimental fluid saturation models\n\n'+json.dumps(r,indent=2)+'\n\nSource headers are unchanged. No gas model or production promotion. Saved models require complete, finite GR in API and density in g/cm3. Original alias mapping and units must be explicit.\n')
print(json.dumps(dict(protocol=protocol,results=[{k:v for k,v in row.items() if k not in ['artifact','sha256']} for row in results]),indent=2))
