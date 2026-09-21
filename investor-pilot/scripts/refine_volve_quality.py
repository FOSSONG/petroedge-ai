"""Immutable quality refinement of Volve 003, retaining explicit holdbacks."""
import csv,json,hashlib,re,math
from pathlib import Path
import numpy as np
import lasio
BASE=Path(r'E:\PETROEDGE_AI\codex'); PREV=BASE/'data/prepared/volve_003'; OUT=BASE/'data/prepared/volve_004'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def writecsv(p,rows):
 with p.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def eligibility(r,raw):
 reasons=[]
 if r['structural_candidate']!='True':reasons.append('prior_structural_or_target_failure')
 if not math.isfinite(raw) or not 1<=raw<=4:reasons.append('raw_density_missing_or_implausible')
 desc=r['lithology_description'].lower()
 if re.search(r'\ba\s*\.\s*a\s*\.',desc):reasons.append('context_dependent_description')
 if re.search(r'frac|chip|broken',desc):reasons.append('sample_damage_or_fracture_mentioned')
 if not desc.strip():reasons.append('missing_description')
 return reasons

def run():
 if OUT.exists():raise RuntimeError('Version exists')
 OUT.mkdir(parents=True)
 rows=list(csv.DictReader((PREV/'REVIEW_LEDGER.csv').open(encoding='utf-8')))
 sources=json.loads((PREV/'SOURCE_HASHES.json').read_text()); audit=[]; corrected=[]; evidence=[]
 for tag,name in [('A','159-19A_LFP.las'),('BT2','159-19BT2_LFP.las')]:
  folder=Path(r'F:\DATA_PETROEDGE_AI\Well_logs\06.LFP')/('15_9-19 '+tag)
  lp=folder/name;assert digest(lp)==sources[str(lp)]
  l=lasio.read(lp);assert l.curves['LFP_RHOB_LOG'].unit=='g/cm3'
  for dp in folder.glob('*.doc'):
   sources[str(dp)]=digest(dp)
   text='\n'.join(x.decode('latin1') for x in re.findall(rb'[\x20-\x7e\r\n\t]{12,}',dp.read_bytes()))
   (OUT/(tag+'_report_printable_text.txt')).write_text(text,encoding='utf-8')
   evidence.append({'path':str(dp),'extraction':'printable ASCII runs, discovery only; table layout not preserved','sha256':digest(dp)})
  d=l['DEPTH'];n=l['LFP_NPHI'];bad=np.isfinite(n)&((n<0)|(n>1));b=l['LFP_BADDATA']
  audit.append({'well':tag,'total_log_rows':len(d),'neutron_outlier_count':int(bad.sum()),'neutron_outlier_depths_m':d[bad].tolist(),'bad_data_flag_null_count':int(np.isnan(b).sum()),'bad_data_flag_nonnull_values':np.unique(b[np.isfinite(b)]).tolist(),'raw_density_unit':l.curves['LFP_RHOB_LOG'].unit})
  for r in rows:
   if r['well']!='NO 15/9-19 '+tag:continue
   raw=float('nan');delta=None
   if r['log_depth_m']:
    idx=int(np.argmin(abs(d-float(r['log_depth_m']))));assert abs(d[idx]-float(r['log_depth_m']))<1e-7
    raw=float(l['LFP_RHOB_LOG'][idx]);delta=float(l['LFP_RHOB'][idx])-raw
    assert np.isfinite(n[idx]) and 0<=n[idx]<=1
   reasons=eligibility(r,raw)
   r['previous_processed_density_g_cm3']=r['bulk_density_g_cm3'];r['bulk_density_g_cm3']=raw if math.isfinite(raw) else ''
   r['density_channel']='LFP_RHOB_LOG';r['processed_minus_raw_density_g_cm3']=delta if delta is not None and math.isfinite(delta) else ''
   r['development_eligible']=not reasons;r['training_eligible']=False;r['status']='development_candidate_no_independent_split' if not reasons else 'held_for_review'
   r['review_reasons']=';'.join(reasons);r['quality_interpretation']='matched_neutron_within_declared_fraction_range;raw_density_used;missing_bad_data_flag_not_interpreted_as_pass'
   corrected.append(r)
 writecsv(OUT/'REVIEW_LEDGER.csv',corrected)
 candidates=[r for r in corrected if r['development_eligible']]
 registry=[]
 for w in sorted({r['well'] for r in candidates}):
  for t in sorted({r['target'] for r in candidates}):
   subset=[r for r in candidates if r['well']==w and r['target']==t]
   if not subset:continue
   dest=OUT/w.replace('/','_').replace(' ','_')/t;dest.mkdir(parents=True)
   writecsv(dest/'dataset.csv',subset)
   fs=['specimen_id','gr_api','neutron_porosity_v_v','bulk_density_g_cm3','resistivity_ohm_m']
   writecsv(dest/'features.csv',[{k:r[k] for k in fs} for r in subset]);writecsv(dest/'targets.csv',[{k:r[k] for k in ['specimen_id','target_value','target_unit']} for r in subset])
   registry.append({'well':w,'target':t,'rows':len(subset),'dataset_path':str(dest/'dataset.csv'),'status':'development_only_split_unassigned','condition':subset[0]['condition']})
 writecsv(OUT/'DATASET_REGISTRY.csv',registry)
 summary={'source_specimens':len({r['specimen_id'] for r in corrected}),'target_slots':len(corrected),'development_candidate_rows':len(candidates),'development_candidate_specimens':len({r['specimen_id'] for r in candidates}),'tables':len(registry),'held_target_rows':len(corrected)-len(candidates),'models_trained':0,'split':'unassigned','density_changed_matched_specimens':len({r['specimen_id'] for r in corrected if r['processed_minus_raw_density_g_cm3']!='' and abs(r['processed_minus_raw_density_g_cm3'])>1e-5})}
 for name,obj in [('SUMMARY.json',summary),('LOG_QUALITY_AUDIT.json',audit),('SOURCE_HASHES.json',sources),('DOCUMENT_EVIDENCE.json',evidence)]:
  (OUT/name).write_text(json.dumps(obj,indent=2),encoding='utf-8')
 report='''# Volve quality refinement, version 004

This version supersedes the quality interpretation in review 003; original artifacts remain unchanged. No model has been trained.

## Corrections and decisions

The matched neutron values are within the declared decimal-fraction range. The full logs contain 5 outliers in A and 6 in BT2; their exact depths are in LOG_QUALITY_AUDIT.json. No unit conversion or imputation was applied. Unmatched core rows remain held.

The prior statement that BT2 BADDATA is uniformly 1 was incorrect: only its non-null values are 1. There are 1,247 such rows and 5,708 null rows; matched core intervals have null flags. A has 3,905 zero flags. Missing flags are not evidence of good quality.

BT2's supplied Word report describes synthetic density replacement in the shallow interval, outside the matched cores. Printable text extraction is saved for traceability; it does not preserve table layout and is not used alone to decode every flag. Numerical comparison shows BT2 processed density equals RHOB_LOG at every matched specimen.

A's processed density differs from RHOB_LOG at 490 matched specimens despite its density flag being 1. Inputs now use the explicitly named original density channel LFP_RHOB_LOG, whose units are checked, for both wellbores. Processed values and differences are retained in the ledger. This avoids relying on a flag to infer whether density was modified. The origin of all A processing differences remains unresolved; processed density is excluded from model inputs.

Development candidates require the previous structural/target checks, finite plausible original density, and an explicit description without fracture/chip/broken references. Context-dependent A.A. descriptions remain held rather than inheriting an assumed clean condition. These are conservative development candidates, not independently validated training data.

## Targets and evidence

Nitrogen permeability at 20 bar confining pressure remains distinct from empirical Klinkenberg-corrected permeability. Helium porosity has no assumed confining pressure. Laboratory method evidence is documented in version 003, with source PDF page references and image extracts. Synthetic fluid assignments and computed porosity are excluded from features and ground-truth labels.

All rows retain their parent-well split group and unassigned split. The new dataset registry is supplemental to the existing GABO/Freeman registry, which remains active. These CSVs are not yet registered in the running application's database. Source files on F are unchanged.

## Next implementation step

Connect these versioned manifests to the shared training workflow with enforced parent-well grouping, target-condition separation and a locked independent test partition. Additional compatible independent wells are still required before claiming generalization. Held descriptions and the A processing discrepancy remain visible review items.
'''
 report+='\n## Counts\n\n'+json.dumps(summary,indent=2)+'\n'
 (OUT/'README.md').write_text(report,encoding='utf-8');(BASE/'docs/assessment/VOLVE_QUALITY_004.md').write_text(report,encoding='utf-8')
 assert len(corrected)==len(rows)
 assert len({(r['specimen_id'],r['target']) for r in corrected})==len(rows)
 assert all(not r['training_eligible'] and r['split']=='unassigned' for r in corrected)
 (OUT/'ARTIFACT_HASHES.json').write_text(json.dumps({str(p.relative_to(OUT)):digest(p) for p in OUT.rglob('*') if p.is_file()},indent=2),encoding='utf-8')
 print(json.dumps(summary))
if __name__=='__main__':run()
