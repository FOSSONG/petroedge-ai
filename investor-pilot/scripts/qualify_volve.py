"""Build traceable Volve core/log review tables; never promote unresolved quality flags."""
import csv, hashlib, json, math
from pathlib import Path
import lasio
import numpy as np
BASE=Path(r'E:\PETROEDGE_AI\codex')
OUT=BASE/'data/prepared/volve_003'
RAW=Path(r'F:\DATA_PETROEDGE_AI\Well_logs')
def sha(p):
 return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def writecsv(p,rows):
 with p.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def number(v):
 try:
  n=float(v);return n if math.isfinite(n) else None
 except (ValueError,TypeError):return None
def shifted(depth,core,rows):
 matches=[r for r in rows if number(r[2])==core and float(r[7])<=depth<=float(r[8])]
 if len(matches)!=1:return None
 r=matches[0];a,b,c,d=map(float,r[7:11])
 return c+(depth-a)*(d-c)/(b-a)
def run():
 if OUT.exists():raise RuntimeError('Immutable version already exists')
 OUT.mkdir(parents=True)
 books=[json.loads(p.read_text(encoding='utf-8')) for p in (BASE/'data/readiness/log_core_001/core_workbooks').glob('*.json')]
 ledger=[];sources={};stats=[]
 for tag,folder,xls,las in [('A','15_9-19 A','15919A.XLS','159-19A_LFP.las'),('BT2','15_9-19 BT2','15919bt2.xls','159-19BT2_LFP.las')]:
  book=next(b for b in books if Path(b['source_path']).name==xls)
  shift=next(b for b in books if Path(b['source_path']).name==folder+'_core shift.xlsx')
  lp=RAW/'06.LFP'/folder/las;l=lasio.read(lp)
  uwi='NO '+folder.replace('_','/')
  assert l.well.UWI.value==uwi
  assert all(r[0]==uwi for r in shift['sheets'][0]['rows'][1:])
  for p in [Path(book['source_path']),Path(shift['source_path']),lp]:sources[str(p)]=sha(p)
  assert sources[book['source_path']]==book['sha256']
  assert sources[shift['source_path']]==shift['sha256']
  units={'DEPTH':'M','LFP_GR':'API','LFP_NPHI':'v/v_decimal','LFP_RHOB':'g/cm3','LFP_RT':'ohm.m'}
  assert all(l.curves[k].unit==v for k,v in units.items())
  depth=l['DEPTH']; assert np.all(np.isfinite(depth)) and np.all(np.diff(depth)>0)
  rows=book['sheets'][0]['rows'];count=0
  for rn,r in enumerate(rows,1):
   if len(r)<17 or number(r[0]) is None or number(r[1]) is None or number(r[2]) is None:continue
   core=number(r[0]);cd=number(r[2]);sd=shifted(cd,core,shift['sheets'][0]['rows'][1:]);idx=int(np.argmin(abs(depth-sd))) if sd is not None else None
   delta=abs(float(depth[idx])-sd) if idx is not None else None
   vals={k:float(l[k][idx]) if idx is not None and np.isfinite(l[k][idx]) else None for k in ['LFP_GR','LFP_NPHI','LFP_RHOB','LFP_RT','LFP_BADDATA','LFP_RHOBLOGFLAG']}
   valid=(delta is not None and delta<=.25 and all(vals[k] is not None for k in units if k!='DEPTH'))
   plausible=valid and 0<=vals['LFP_NPHI']<=1 and 1<=vals['LFP_RHOB']<=4 and vals['LFP_RT']>0 and vals['LFP_GR']>=0
   desc=str(r[16]);flags=['lfp_quality_flag_semantics_unresolved','lithology_description_review_required']
   if not plausible:flags.append('missing_or_out_of_range_input_or_depth')
   if 'frac' in desc.lower():flags.append('fracture_mentioned')
   if 'a.a' in desc.lower():flags.append('description_refers_to_previous_sample')
   specimen=f'VOLVE_19_{tag}_core{int(core)}_sample{int(number(r[1]))}_row{rn}'
   for target,col,unit,condition in [('porosity_helium_horizontal',9,'v/v','confining_pressure_not_stated_for_porosity'),('permeability_nitrogen_horizontal',3,'mD','20_bar_confining'),('permeability_klinkenberg_empirical_horizontal',5,'mD','empirically_corrected_from_nitrogen_at_20_bar')]:
    value=number(r[col]);value=value/100 if value is not None and col==9 else value
    targetvalid=value is not None and (0<value<1 if col==9 else value>0)
    ledger.append(dict(specimen_id=specimen,well=uwi,field='VOLVE',split_group_id='VOLVE_15_9_19_parent_and_sidetracks',split='unassigned',core_number=int(core),core_depth_m=cd,shifted_depth_m=sd,log_depth_m=float(depth[idx]) if idx is not None else None,depth_delta_m=delta,target=target,target_raw=r[col],target_value=value,target_unit=unit,condition=condition,gr_api=vals['LFP_GR'],neutron_porosity_v_v=vals['LFP_NPHI'],bulk_density_g_cm3=vals['LFP_RHOB'],resistivity_ohm_m=vals['LFP_RT'],bad_data_flag=vals['LFP_BADDATA'],density_log_flag=vals['LFP_RHOBLOGFLAG'],structural_candidate=bool(plausible and targetvalid),training_eligible=False,status='quarantined_pending_quality_review',review_reasons=';'.join(flags),lithology_description=desc,source_path=book['source_path'],source_sheet=book['sheets'][0]['name'],source_row=rn,log_path=str(lp),shift_path=shift['source_path']))
   count+=1
  stats.append({'well':uwi,'source_specimens':count})
  for p in (RAW/'06.LFP'/folder).glob('*.pdf'):
   sources[str(p)]=sha(p)
  cp=RAW/'09.CORE'/folder/('15-9-19a-core.pdf' if tag=='A' else '15_9-19bt2.pdf');sources[str(cp)]=sha(cp)
 writecsv(OUT/'REVIEW_LEDGER.csv',ledger)
 for target in sorted({r['target'] for r in ledger}):
  dest=OUT/target;dest.mkdir();writecsv(dest/'review_candidates.csv',[r for r in ledger if r['target']==target])
 summary={'wells':stats,'target_rows':len(ledger),'structural_candidates':sum(r['structural_candidate'] for r in ledger),'training_eligible_rows':0,'models_trained':0,'parent_groups_added_for_review':1,'status':'review_only_previous_active_registry_unchanged'}
 (OUT/'SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
 (OUT/'SOURCE_HASHES.json').write_text(json.dumps(sources,indent=2),encoding='utf-8')
 assert len({(r['specimen_id'],r['target']) for r in ledger})==len(ledger)
 assert all(not r['training_eligible'] and r['split']=='unassigned' for r in ledger)
 assert all(r['depth_delta_m']<=.25 for r in ledger if r['structural_candidate'])
 report='''# Volve core/log qualification — review version 003

Two source-linked wellbores, 15/9-19 A and BT2, are grouped under one conservative parent-well split identity. Their exact LAS UWI values match the core-shift workbooks. No geographic filter was applied.

## Evidence recovered

- Core report 10177-97 (A), PDF page 11: nitrogen gas permeability measured at 20 bar confining pressure; Kl is an empirical Klinkenberg correction, not measured brine permeability.
- Core report 10201-98 (BT2), PDF page 9: same nitrogen method and pressure, with vertical-plug text crossed out. Page 10: helium grain volume and mercury bulk volume for porosity. The 20 bar permeability condition is not assigned to porosity.
- A PDF page 10: Dean-Stark oil/water analyses, no saturation data for cores 5–7. Page 11 describes tracer-based water corrections; oil values were not corrected. No saturation targets were promoted.
- LFP petrophysics PDFs, page 1: GR, NPHI and RT source versions. A density is described as unedited; BT2 page 2 identifies RHOB as RHOB_LOG. Synthetic/substituted density, calculated porosity/permeability and model curves are excluded from the input whitelist.
- Both petrophysics reports page 2 describe constant fluid assignments. Those are modeling assumptions, not measured fluid-saturation training labels.

## Remaining quality issues

LAS neutron values include values far above the declared decimal-fraction range. No automatic divide-by-100 correction is applied. LFP_BADDATA is uniformly 0 in A and 1 in BT2; code semantics remain unresolved, so neither flag is assumed to mean pass. Every row remains quarantined even when a structural match passes. Lithology shorthand referring to earlier rows and fracture descriptions require contextual review.

REVIEW_LEDGER.csv retains all extracted target slots, missing/non-numeric originals, source rows, core-specific shifts, nearest log depths, source paths and quality flags. Task folders separate helium porosity, measured nitrogen permeability, and empirical corrected permeability. Thresholds are structural screening rules, not proof of log quality. Core-to-log shifts use source core identifiers and interval interpolation; maximum accepted depth mismatch is 0.25 m.

## Split decision

The new wellbores supply one additional parent family for review, not two independent validation wells. Existing Freeman, GABO and Volve measurements have different conditions and provenance. A defensible locked train/validation/test split is still pending quality clearance and compatible target definitions. Existing active development tables remain unchanged. No training or production-readiness claim is made.

Next: resolve LFP quality-code semantics against the supplied LFP reports or original composite logs; verify neutron scaling per interval; review linked lithology descriptions before promoting any rows. Then qualify additional independent parent wells under compatible laboratory definitions.
'''
 report+='\n## Counts\n\n'+json.dumps(summary,indent=2)+'\n'
 (OUT/'README.md').write_text(report,encoding='utf-8')
 (BASE/'docs/assessment/VOLVE_QUALIFICATION_003.md').write_text(report,encoding='utf-8')
 (OUT/'VERIFICATION.json').write_text(json.dumps({'unique_specimen_target_keys':True,'source_hash_checks':True,'exact_uwi_links':True,'declared_input_units_checked':True,'all_rows_quarantined':True,'candidate_depth_tolerance_checked':True},indent=2),encoding='utf-8')
 (OUT/'ARTIFACT_HASHES.json').write_text(json.dumps({str(p.relative_to(OUT)):sha(p) for p in OUT.rglob('*') if p.is_file()},indent=2),encoding='utf-8')
 print(json.dumps(summary))
if __name__=='__main__':run()
