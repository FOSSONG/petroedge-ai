from pathlib import Path
import json,hashlib,collections,itertools
import numpy as np
import pandas as pd
import lasio
B=Path(r"E:\PETROEDGE_AI\codex");O=B/"docs/assessment/model_diagnostics_036";O.mkdir(parents=True,exist_ok=False)
checks={}
def read(p):
 checks[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 return json.loads(p.read_text(encoding="utf-8-sig"))
def stats(s):
 x=pd.to_numeric(s,errors="coerce");v=x[np.isfinite(x)]
 return dict(rows=len(x),finite=len(v),missing_or_nonfinite=int((~np.isfinite(x)).sum()),minimum=float(v.min()) if len(v) else None,median=float(v.median()) if len(v) else None,maximum=float(v.max()) if len(v) else None,zero_count=int(v.eq(0).sum()),one_count=int(v.eq(1).sum()))
cat=read(B/"data/prepared/platform_manifest_001.json");old=read(B/"models/exploratory_020/report.json");development=read(B/"models/regression_development_027/REPORT.json")
oldmap={e['dataset_id']:e for e in old['experiments']};devmap={e['dataset_id']:e for e in development['experiments']}
coverage=[];distribution=[];align=[];reg=[];folds=[];group_rows=[]
for key,c in cat['datasets'].items():
 p=B/'data/prepared'/c['path'];actual=hashlib.sha256(p.read_bytes()).hexdigest();assert actual==c['sha256'];checks[str(p)]=actual
 d=pd.read_csv(p);target=c['target_column'];e=oldmap[key];features=c['feature_columns'];assert not d.specimen_id.duplicated().any()
 for f in features:coverage.append(dict(task=c['name'],feature=f,**stats(d[f])))
 alignment=next((f for f in ['alignment_distance_m','depth_delta_m'] if f in d),None)
 align.append(dict(task=c['name'],alignment_column=alignment,alignment_summary=stats(d[alignment]) if alignment else None,shift_status=d.shift_status.value_counts().to_dict() if 'shift_status' in d else {},note='Nearest-depth distance does not prove correct datum or geological alignment.'))
 for g in d.split_group_id.unique():group_rows.append(dict(task=c['name'],target=c['target_definition'],condition=c['condition'],parent_group=g,rows=int(d.split_group_id.eq(g).sum()),independent_test_available=False))
 record=dict(dataset=key,name=c['name'],target=c['target_definition'],condition=c['condition'],source_rows=len(d),unique_depths=int(d.log_depth_m.nunique()),duplicate_log_depth_rows=int(d.log_depth_m.duplicated().sum()),groups=d.split_group_id.unique().tolist(),status=e['status'],label_kind_counts=d.target_kind.value_counts().to_dict() if 'target_kind' in d else {},target_summary=stats(d[target]))
 if e['status']=='trained_experimental':
  assignments=Path(e['artifact_directory'])/'assignments.csv';assert hashlib.sha256(assignments.read_bytes()).hexdigest()==e['artifact_sha256']['assignments.csv']
  a=pd.read_csv(assignments)[['specimen_id','partition']];d=d.merge(a,on='specimen_id',validate='one_to_one');tr=d[d.partition.eq('train')]
  for part,g in d.groupby('partition'):
   distribution.append(dict(task=c['name'],partition=part,column=target,**stats(g[target])))
   for f in features:
    vals=pd.to_numeric(g[f],errors='coerce');lo,hi=tr[f].min(),tr[f].max()
    distribution.append(dict(task=c['name'],partition=part,column=f,outside_training_range=int(((vals<lo)|(vals>hi)).sum()),**stats(vals)))
  record.update(partitions=d.partition.value_counts().to_dict(),historical_selected_model=e['selected_model'],historical_test=e['test'],development_selection=devmap[key]['selected_by_validation_mae'],development_validation_rows=devmap[key]['validation_rows'])
  # Proposed expanding-window development folds use ONLY the existing training partition.
  depths=np.sort(tr.log_depth_m.unique());n=len(depths)
  for fold,(start,end) in enumerate([(0.5,.67),(.67,.84),(.84,1.0)],1):
   k=int(n*start);stop=int(n*end);td=depths[:max(0,k-1)];vd=depths[k:stop]
   if len(td)<8 or len(vd)<3:continue
   for role,ds in [('train',td),('validation',vd)]:
    for _,r in tr[tr.log_depth_m.isin(ds)].iterrows():folds.append(dict(task=c['name'],fold=fold,role=role,specimen_id=r.specimen_id,depth_m=r.log_depth_m,original_partition='train',scope='within_well_development_only'))
 else:record['blocked_reason']=e.get('reason')
 reg.append(record)
lith=read(B/'models/lithology_development_025/REPORT.json');ld=pd.read_csv(B/'models/lithology_development_025/DEVELOPMENT_DATA.csv');assert set(ld.well).isdisjoint(lith['prior_test_wells_not_used'])
for f in ['gr_api','sonic_us_ft','density_g_cm3','sp_mv']:coverage.append(dict(task='lithology_development',feature=f,**stats(ld[f])))
lf=[]
for held in sorted(ld.well.unique()):
 for _,r in ld.iterrows():lf.append(dict(held_well=held,role='validation' if r.well==held else 'train',well=r.well,source_row=int(r.excel_row),sample_number=r.sample_number,label=r.label))
pd.DataFrame(lf).to_csv(O/'LITHOLOGY_DEVELOPMENT_FOLDS.csv',index=False)
lithreview=dict(rows=len(ld),class_counts=ld.groupby('well').label.value_counts().unstack(fill_value=0).to_dict('index'),input_coverage=lith['feature_coverage'],alignment_ft=stats(ld.distance_ft),assumption=lith['assumption'],performance=lith['results']['forest_gr']['pooled_out_of_well'],evaluation=lith['evaluation'],excluded_prior_test_wells=lith['prior_test_wells_not_used'],duplicate_well_depth_rows=int(ld.duplicated(['well','sidewall_depth_raw']).sum()))
# Inspect original saturation volume channels, not just paired target ranges.
f=read(B/'models/field_x_saturation_035/REPORT.json');sd=pd.read_csv(B/'models/field_x_saturation_035/SPLIT_MANIFEST.csv');suspects=[];volumechecks=[]
D=Path(r"F:\DATA_PETROEDGE_AI\Niger delta Fields\Field X\X_FIELD_Well logs\X-005")
for name,sw,vw in [('las7738.las','SW:2','VUWA'),('las8098.las','SW','VUWA:2'),('las8374.las','SW','VUWA')]:
 p=D/name;assert hashlib.sha256(p.read_bytes()).hexdigest()==f['source_hashes'][name]
 l=lasio.read(str(p));x=l.df()[[sw,'SO','VUOI',vw]].dropna();z=x[sw].eq(0)&x.SO.eq(0)
 assert len(x)==len(sd[sd.file.eq(name)])
 volumechecks.append(dict(file=name,null_marker=float(l.well.NULL.value),paired_rows=len(x),both_zero_rows=int(z.sum()),both_zero_volume_rows=int((x.loc[z,'VUOI'].eq(0)&x.loc[z,vw].eq(0)).sum()),nonzero_pairs_close_to_one=int(np.isclose((x[sw]+x.SO)[~z],1,atol=.001).sum())))
 for depth,row in x[z].iterrows():suspects.append(dict(file=name,depth_ft=depth,sw=row[sw],so=row.SO,oil_volume=row.VUOI,water_volume=row[vw],reason='Both reported saturations and oil/water volumes zero; interpretation-mask or other state unresolved; not relabeled as gas',recommended_action='Hold pending provenance review; do not treat as confirmed physical label'))
assert len(suspects)==223
for part,g in sd.groupby('split'):
 for col in ['sw','so','gamma_ray_api','density_gcc']:distribution.append(dict(task='Field X RST saturation',partition=part,column=col,**stats(g[col])))
for col in ['gamma_ray_api','density_gcc']:
 coverage.append(dict(task='Field X RST saturation',feature=col,**stats(sd[col])))
satreview=dict(pairs=len(sd),source_volume_checks=volumechecks,suspicious_zero_pairs=len(suspects),suspect_percentage=100*len(suspects)/len(sd),working_date=f['protocol']['working_date'],date_basis='User-authorized assumption; raw acquisition dates unchanged',alignment_ft={c:stats(sd[c]) for c in ['gamma_ray_api_depth_delta_ft','density_gcc_depth_delta_ft']},missing_features=['neutron porosity','sonic','resistivity in deepest test interval'],historical_performance=[{k:v for k,v in e.items() if k not in ['artifact','sha256']} for e in f['results']],interpretation='Zero-coded intervals may contribute to failure, but causal effect is untested. All other pairs sum to one within 0.001; no independent gas label exists. No post-hoc filtered test score calculated.')
core=read(B/'models/core_saturation_031/REPORT.json');cs=pd.read_csv(B/'models/core_saturation_031/SPLIT_MANIFEST.csv')
corereview=dict(total_rows=len(cs),split_counts=cs.split.value_counts().to_dict(),limits=core['protocol']['limitations'],status=core['status'])
for task,frame,targetnames,partcol in [('Volve reported-core saturation',cs,['core_water_fraction','core_oil_fraction'],'split')]:
 for part,g in frame.groupby(partcol):
  for col in targetnames:distribution.append(dict(task=task,partition=part,column=col,**stats(g[col])))
pd.DataFrame(coverage).to_csv(O/'INPUT_COVERAGE.csv',index=False);pd.DataFrame(distribution).to_csv(O/'PARTITION_DISTRIBUTIONS.csv',index=False);pd.DataFrame(suspects).to_csv(O/'SATURATION_LABELS_REQUIRING_REVIEW.csv',index=False);pd.DataFrame(group_rows).to_csv(O/'PARENT_WELL_CONDITION_REGISTER.csv',index=False)
ff=pd.DataFrame(folds);ff.to_csv(O/'REGRESSION_DEVELOPMENT_FOLDS.csv',index=False)
for (_,fold),g in ff.groupby(['task','fold']):
 a=g[g.role.eq('train')];v=g[g.role.eq('validation')];assert set(a.specimen_id).isdisjoint(v.specimen_id) and a.depth_m.max()<v.depth_m.min()
protocol=dict(status='Prepared, not executed; no new model performance claimed',lithology='Reuse explicit development wells only. GR-only baseline vs fixed regularized tree/linear candidates; leave-one-well-out; report all-class confusion and single-class folds separately. No density model with all-missing density.',regression='Use supplied expanding depth folds within original training rows only; fit preprocessing inside each fold; reserve existing validation for limited development confirmation, not fresh certification. Median, Ridge with train-only scaling and RF128 min_leaf3 are a small fixed comparison. Permeability log1p target requires inverse-space errors and residual bias review.',saturation='Stop interpreting phase035 as qualified labels. Review 223 zero-coded pairs, formation masks and processing definitions first. Preserve them with flags; no automatic deletion or gas relabeling. Use task-specific GR+density and GR+density+resistivity variants only where inputs exist. More algorithms cannot establish date or label validity.',physical_baseline='Density-porosity baseline needs declared matrix/fluid density and lithology applicability. Archie saturation requires defensible Rw at temperature, porosity, a/m/n and applicability; assumed scenarios are not training truth. No universal permeability baseline imposed across fluids/stress conditions.',metrics='Classification: macro F1, balanced accuracy and per-class recall. Regression: original-unit MAE/RMSE, bias and R2; permeability also log-space errors. Compare paired baseline errors by held-out well, not pooled row accuracy alone.',fresh_evaluation='Existing inspected tests are historical diagnostics only. New parent wells, all sidetracks and duplicate acquisitions grouped together, label/units approved and hashes frozen before training. Do not random-split depth rows to create an allegedly new independent test.',promotion='Must beat the predefined baseline on fresh independent wells and meet task-specific tolerances agreed before evaluation; no promotion from reused validation or this diagnostic. Report failure cases and uncertainty; allow abstention for missing/unit-invalid/out-of-domain inputs.')
(O/'NEXT_EXPERIMENT_PROTOCOL.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
report=dict(scope='Diagnostic of existing prepared datasets and experiments. No retraining, test retuning, label replacement or production change.',regression=reg,lithology=lithreview,field_x_saturation=satreview,core_saturation=corereview,alignment_review=align,source_checks=checks,protocol=protocol)
(O/'REPORT.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
lines=['# PetroEdge model diagnostics: points 1-5','',report['scope'],'','## 1. Labels and depth alignment','','Field X: 223/826 rows (27.0%) have both oil/water saturations AND both corresponding fluid-volume curves equal to zero. Raw NULL is -999.25, so these are not automatically recognized nulls. Their meaning is unresolved: masking, processing conventions or another state need source confirmation. Every remaining pair sums to one within 0.001. No gas label can be inferred. The earlier range-only check was insufficient; historical errors must not be treated as qualified saturation performance.','', 'All 826 input joins satisfy the recorded numeric depth tolerance, but that does not validate acquisition timing. The adopted 1998 date remains an assumption. Volve core saturation remains a separate laboratory target with its own preservation/invasion limitations.','', 'Lithology alignment remains conditional on feet/MD/drill-floor interpretation. Regression source hashes and specimen uniqueness checked; matching distance and shift evidence are retained separately in REPORT.json.','', '## 2. Task-specific input coverage','','Lithology: GR 180/180; sonic 115/180; SP 73/180; density 0/180. Use the GR-only model as the current conditional development reference; all-missing density provides no evidence.','', 'Field X saturation uses GR+density. Missing neutron/sonic and absent deep-interval resistivity limit possible models. No missing curves are synthesized. Regression coverage and nulls are tabulated by dataset in INPUT_COVERAGE.csv; core stress/fluid conditions remain separate.','', '## 3. Development design','','Prepared explicit development fold manifests and NEXT_EXPERIMENT_PROTOCOL.json. Regression folds draw only from original training partitions; lithology excludes prior test wells X-006/X-008. These are development comparisons, not new independent tests. No model was retrained during this diagnostic.','', '## 4. Independent evaluation','','The 16 regression contracts represent only three parent groups: Freeman-4 including ST1, Gabo-51, and Volve15/9-19 including sidetracks. Conditions/targets differ, so three groups are not automatically three comparable training cohorts. Every condition-specific dataset lacks an independent held-out parent well in its existing design.','', 'New independent wells must be qualified and locked before evaluation. Keep parent/sidetracks and duplicate acquisitions together across tasks. Existing test results are historical evidence, not a reusable certification set. See PARENT_WELL_CONDITION_REGISTER.csv.','', '## 5. Findings by prediction task','','| Task | Finding | Next justified action |','|---|---|---|','| Lithology | GR-only development macro F1 0.943 on 180 rows/four wells; conditional depth assumption; one single-class fold | Resolve depth datum, retain sand/shale scope and seek fresh wells with both classes |','| Porosity | Small within-well splits and mixed measurement conditions across contracts | Verify condition-specific targets, compare density baseline where applicable, use prepared development folds |','| Permeability | Strong condition/fluid dependence; some median baselines win | Keep air/brine/nitrogen and stress conditions distinct; compare original-unit and log-space residuals |','| Core saturation | One well, 65 included samples; reported recovered-core targets | Obtain independent comparable core measurements; do not treat missing pore fraction as gas |','| Field X saturation | Zero-coded label intervals, shifted input distributions, date assumption and failed test baseline comparison | Review zero-coded rows and RST processing before another training attempt |','','### Regression detail','','| Dataset | Train / validation / test | Selected historical model | Historical test MAE | Development selection |','|---|---|---|---:|---|']
for e in reg:
 if e['status']=='trained_experimental':
  z=e['partitions'];lines.append(f"| {e['name']} | {z.get('train',0)} / {z.get('validation',0)} / {z.get('test',0)} | {e['historical_selected_model']} | {e['historical_test']['mae']:.4g} | {e['development_selection']} |")
 else:lines.append(f"| {e['name']} | Blocked | - | - | {e['blocked_reason']} |")
lines+=['','Errors retain each target unit (porosity fraction or permeability mD); do not compare unlike targets numerically. Validation reuse is disclosed; no improvement is claimed.','','## Deliverables','','REPORT.json, INPUT_COVERAGE.csv, PARTITION_DISTRIBUTIONS.csv, SATURATION_LABELS_REQUIRING_REVIEW.csv, PARENT_WELL_CONDITION_REGISTER.csv, REGRESSION_DEVELOPMENT_FOLDS.csv, LITHOLOGY_DEVELOPMENT_FOLDS.csv, NEXT_EXPERIMENT_PROTOCOL.json.','','Priority: resolve zero-coded saturation semantics and lithology depth provenance; then run only the qualified development experiments. More model complexity is not the first remedy.']
(O/'README.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps(dict(regression_contracts=len(reg),trained=sum(e['status']=='trained_experimental' for e in reg),source_files_verified=len(checks),saturation_suspect_rows=len(suspects),regression_development_folds=int(ff.groupby(['task','fold']).ngroups),lithology_folds=len(ld.well.unique()),output=str(O)),indent=2))
