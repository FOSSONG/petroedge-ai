from pathlib import Path
import json,hashlib,re,itertools
import pandas as pd
import numpy as np
import lasio
B=Path(r"E:\PETROEDGE_AI\codex");O=B/"data/prepared/field_x_rst_034";O.mkdir(parents=True,exist_ok=False)
D=Path(r"F:\DATA_PETROEDGE_AI\Niger delta Fields\Field X\X_FIELD_Well logs\X-005")
headers=[];curves=[];frames={};raw=[]
for p in sorted(D.glob("*.las")):
 section="";ev=[]
 for line in p.read_text(errors="replace").splitlines():
  if line.strip().upper().startswith("~A"):break
  if line.startswith("~"):section=line.strip()
  if re.match(r"^(DATE|WELL|LMF|LNAM|EDF|R[1-5] )",line):ev.append(dict(section=section,text=re.sub(r"\s+"," ",line).strip()))
 headers.append(dict(file=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),evidence=ev))
 l=lasio.read(str(p));df=l.df();frames[p.name]=df
 for c in l.curves:
  v=np.asarray(l[c.mnemonic],dtype=float);v=v[np.isfinite(v)]
  curves.append(dict(file=p.name,channel=c.mnemonic,unit=c.unit,description=c.descr,finite_rows=len(v),minimum=float(v.min()) if len(v) else None,maximum=float(v.max()) if len(v) else None))
 if p.name in ["las7738.las","las8098.las","las8374.las"]:
  sw="SW:2" if p.name=="las7738.las" else "SW"
  for depth,row in df.iterrows():
   if np.isfinite(row[sw]) and np.isfinite(row.SO):raw.append(dict(file=p.name,depth_ft=float(depth),sw=float(row[sw]),so=float(row.SO),channel_sw=sw,in_range=bool(0<=row[sw]<=1 and 0<=row.SO<=1),sum_above_one=bool(row[sw]+row.SO>1.0001),training_approved=False))
a=pd.DataFrame(raw);assert len(a)>0
assert a.groupby('file').depth_ft.apply(lambda v:v.is_unique).all()
a.to_csv(O/"PAIRED_RST_VALUES.csv",index=False)
comparisons=[]
for left,right in itertools.combinations(a.file.unique(),2):
 x=a[a.file.eq(left)].merge(a[a.file.eq(right)],on="depth_ft",suffixes=("_a","_b"))
 delta=np.maximum(abs(x.sw_a-x.sw_b),abs(x.so_a-x.so_b))
 comparisons.append(dict(left=left,right=right,overlap_depths=len(x),agree_within_1e_4=int((delta<=.0001).sum()),conflicting_depths=int((delta>.0001).sum()),max_absolute_fraction_difference=float(delta.max()) if len(x) else None))
union=[]
for depth,g in a.groupby("depth_ft"):
 conflict=bool(g.sw.max()-g.sw.min()>.0001 or g.so.max()-g.so.min()>.0001)
 union.append(dict(depth_ft=depth,exports=len(g),sources=";".join(g.file),sw_min=g.sw.min(),sw_max=g.sw.max(),so_min=g.so.min(),so_max=g.so.max(),conflict=conflict,range_or_sum_failure=bool((~g.in_range|g.sum_above_one).any()),training_approved=False))
u=pd.DataFrame(union);u.to_csv(O/"DEPTH_OVERLAP_REVIEW.csv",index=False)
x=frames['las7738.las'][['SW:1','SW:2']].dropna();diff=abs(x['SW:1']-x['SW:2'])
channel_comparison=dict(paired_depths=len(x),different_above_1e_4=int((diff>.0001).sum()),max_absolute_difference=float(diff.max()) if len(x) else None)
pd.DataFrame(curves).to_csv(O/"CURVE_INVENTORY.csv",index=False)
(O/"HEADER_EVIDENCE.json").write_text(json.dumps(headers,indent=2),encoding="utf-8")
report=dict(files_scanned=len(headers),paired_export_rows=len(a),unique_paired_depths=len(u),conflicting_depths=int(u.conflict.sum()),range_or_sum_failure_depths=int(u.range_or_sum_failure.sum()),pairwise_comparisons=comparisons,repeated_sw_channel_comparison=channel_comparison,date_finding="1966/05/13 is in Well Information Block; 1998/12/06 is in RST parameter sections. 1998 is a run-specific acquisition candidate, not externally confirmed.",input_finding="FDC G/C3 density, GRL API gamma and LL3R OHMM resistivity exist in separate exports; no NPHI/CNL neutron-porosity curve found in the eleven curve inventories. Acquisition alignment remains unqualified.",label_scope="RST interpreted oil/water saturation, not independently measured core truth",training_pairs_approved=0,models_trained=0,production_eligible=False,next_steps=["Confirm RST processing and acquisition metadata; paired intervals are disjoint, so export agreement cannot be evaluated","Verify run-specific dates and depth registration of input logs; static older logs do not automatically provide contemporaneous saturation predictors","Use only an explicitly scoped RST interpretation-reproduction experiment if qualified; do not combine these targets with core saturation truth","Keep all X-005 intervals together for any future independent-well test"],checks="Unique depths per export, finite paired values, boundedness and closure flags, exact-depth overlap comparisons; no interpolation, averaging or clipping")
(O/"REPORT.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
(O/"README.md").write_text("# Field X RST qualification\n\n"+json.dumps(report,indent=2)+"\n\nPAIRED_RST_VALUES.csv preserves source values. DEPTH_OVERLAP_REVIEW.csv exposes disagreements without averaging them. HEADER_EVIDENCE.json retains section context and source hashes. CURVE_INVENTORY.csv records raw mnemonics and units. All rows remain held; source files and running application unchanged.\n",encoding="utf-8")
print(json.dumps(report,indent=2))
