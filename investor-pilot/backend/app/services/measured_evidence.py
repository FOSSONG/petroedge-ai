"""Bounded, owner-scoped measured evidence. No model or probability claims."""
import pandas as pd
import re
from app.platform_v1.datasets import get_dataset,get_dataset_path,_checksum
from app.api.routes.reservoir_v1 import _frame,SCREENING_RANGES

def snapshot(dataset_id,top=None,bottom=None):
 dataset=get_dataset(dataset_id);path=get_dataset_path(dataset_id)
 if _checksum(path)!=dataset.checksum_sha256:raise ValueError("Dataset checksum changed; register the new version.")
 frame,mapping=_frame(dataset_id)
 issues=frame.attrs.get("blocking_issues",[])
 if top is not None or bottom is not None:
  if "depth_m" not in frame or any("depth" in x.lower() for x in issues):raise ValueError("A qualified measured-depth column is required for an interval filter.")
  depth=frame.depth_m
  frame=frame.loc[(depth>=top if top is not None else depth.notna())&(depth<=bottom if bottom is not None else depth.notna())]
 stats={}
 for curve,(lo,hi) in SCREENING_RANGES.items():
  if curve not in frame:continue
  # A known unit ambiguity invalidates that quantity, even if its numbers look plausible.
  sources=[s for s,t in mapping.items() if t==curve]
  blocked=any(curve in issue or any(issue.startswith(s+":") for s in sources) for issue in issues)
  values=pd.to_numeric(frame[curve],errors="coerce")
  valid=values[values.between(lo,hi)] if not blocked else values.iloc[:0]
  stats[curve]={"valid":len(valid),"excluded":len(frame)-len(valid),"minimum":float(valid.min()) if len(valid) else None,"maximum":float(valid.max()) if len(valid) else None,"median":float(valid.median()) if len(valid) else None}
 if _checksum(path)!=dataset.checksum_sha256:raise ValueError("Source changed during analysis.")
 return {"dataset_id":dataset_id,"name":dataset.name,"sha256":dataset.checksum_sha256,"rows":len(frame),"curves":stats,"issues":issues,"mapping":mapping,"mode":"measured_statistics_not_trained_predictions"}

def answer(evidence,question):
 q=" ".join(re.findall(r"[a-z0-9]+",question.lower()));aliases={"gamma_ray_api":["gamma","gr"],"density_gcc":["density","rhob"],"resistivity_ohmm":["resistivity","rt"],"neutron_porosity_vv":["neutron","nphi"],"depth_m":["depth"],"sonic_usft":["sonic","dt"]}
 if any(t in q for t in ["quality","missing","units","summary","summarise","summarize"]):
  lines=[f"{evidence['rows']} source rows inspected."]+[f"{k}: {v['valid']} valid, {v['excluded']} excluded." for k,v in evidence['curves'].items()]+evidence['issues']
 else:
  keys=[k for k,terms in aliases.items() if any(t in q.split() or (len(t)>3 and t in q) for t in terms)]
  lines=[f"{k}: median {evidence['curves'][k]['median']}, minimum {evidence['curves'][k]['minimum']}, maximum {evidence['curves'][k]['maximum']} in canonical units; {evidence['curves'][k]['valid']} valid rows." for k in keys if k in evidence['curves']]
  if not lines:lines=["The selected measured evidence cannot answer this question. Ask about data quality, depth, GR, density, neutron, sonic or resistivity. Use saved-analysis evidence for completed model runs."]
 return {"answer":" ".join(lines),"evidence":[f"Dataset {evidence['dataset_id']}: {evidence['name']}",f"SHA256 {evidence['sha256']}"],"mode":evidence['mode'],"limitations":["Deterministic evidence lookup, not a trained language model.","Does not infer reserves, oil/gas phase, porosity or permeability from these summaries."]}
