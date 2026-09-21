"""Administrator research inference from server-owned, hash-checked artifacts."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
import joblib
from pydantic import BaseModel,Field
from app.platform_v1.datasets import get_dataset,get_dataset_path,_frame
MAX_RESEARCH_ROWS=100_000
PREDICTION_BATCH_ROWS=2048
ROOT=Path(__file__).resolve().parents[2]/"research_models"
class ResearchRequest(BaseModel):
 model_id:str=Field(min_length=1,max_length=100)
 dataset_id:str=Field(min_length=1,max_length=100)
 mapping:dict[str,str]
 units:dict[str,str]
 acknowledge_experimental:bool=False

def _catalog():
 p=ROOT/'manifest.json'
 if not p.exists():return {'enabled':False,'models':[]}
 c=json.loads(p.read_text(encoding='utf-8'))
 if not c.get('enabled'):return {'enabled':False,'models':[]}
 return c

def catalog():
 c=_catalog();return {'enabled':c['enabled'],'models':[{k:v for k,v in m.items() if k not in ['artifact','sha256','source_sha256']} for m in c['models']]}

def predict(req:ResearchRequest):
 if not req.acknowledge_experimental:raise ValueError('Acknowledge the experimental scope before running research predictions.')
 c=_catalog()
 if not c['enabled']:raise ValueError('Research inference is disabled by the administrator.')
 m=next((m for m in c['models'] if m['id']==req.model_id),None)
 if m is None:raise ValueError('Unknown research model.')
 dataset=get_dataset(req.dataset_id);path=get_dataset_path(req.dataset_id)
 # Full checksum ties returned provenance to the registered immutable dataset.
 if path.stat().st_size>50_000_000:raise ValueError('Research datasets must be smaller than 50 MB.')
 hasher=hashlib.sha256()
 with path.open('rb') as handle:
  for block in iter(lambda:handle.read(1024*1024),b''):hasher.update(block)
 digest=hasher.hexdigest()
 if digest!=dataset.checksum_sha256:raise ValueError('Dataset checksum changed; upload a new version.')
 frame=_frame(path,limit=MAX_RESEARCH_ROWS+1)
 if len(frame)>MAX_RESEARCH_ROWS:raise ValueError(f'Research runs support up to {MAX_RESEARCH_ROWS:,} rows. Prepare a single-well subset within this limit; no partial result was generated.')
 if frame.empty:raise ValueError('Dataset has no rows.')
 names=[f['name'] for f in m['features']]
 if set(req.mapping)!=set(names) or len(set(req.mapping.values()))!=len(names):raise ValueError('Map every required feature to a distinct source column.')
 factors={'API':{'API':1,'GAPI':1},'g/cm3':{'G/CM3':1,'G/C3':1,'G/CC':1,'KG/M3':.001},'v/v':{'V/V':1,'FRAC':1,'PU':.01,'%':.01},'ohm.m':{'OHM.M':1,'OHMM':1,'OHM-M':1}}
 x=pd.DataFrame(index=frame.index);reasons=[[] for _ in range(len(frame))]
 for feature in m['features']:
  f=feature['name'];source=req.mapping[f]
  if source not in frame:raise ValueError('Mapped source column is missing: '+source)
  unit=req.units.get(f,'').strip().upper().replace(' ','')
  factor=factors[feature['unit']].get(unit)
  if factor is None:raise ValueError('Declare supported units for '+f)
  stored=dataset.units.get(source,'').strip().upper().replace(' ','')
  if stored and stored!=unit:raise ValueError('Declared unit conflicts with dataset metadata for '+source+'; correct metadata in preparation first.')
  values=pd.to_numeric(frame[source],errors='coerce').replace([-999.25,-999,-9999,-99999,9999],np.nan)*factor
  x[f]=values
  for i,value in enumerate(values):
   if not np.isfinite(value):reasons[i].append(f+': missing or invalid')
   elif value<feature['min'] or value>feature['max']:reasons[i].append(f+': outside training range')
 artifact=(ROOT/m['artifact']).resolve()
 if not artifact.is_relative_to(ROOT.resolve()) or artifact.suffix!='.joblib':raise ValueError('Invalid research artifact configuration.')
 if hashlib.sha256(artifact.read_bytes()).hexdigest()!=m['sha256']:raise ValueError('Research artifact integrity check failed.')
 valid=np.array([not r for r in reasons]);predictions=[None]*len(frame)
 if valid.any():
  model=joblib.load(artifact);positions=np.flatnonzero(valid)
  for start in range(0,len(positions),PREDICTION_BATCH_ROWS):
   batch=positions[start:start+PREDICTION_BATCH_ROWS]
   values=model.predict(x.iloc[batch][names])
   if len(values)!=len(batch):raise ValueError('Research model returned an invalid prediction count.')
   for i,v in zip(batch,values):
    if not np.isfinite(v) or v<0 or ('porosity' in m['target'] and v>1):reasons[i].append('Prediction outside physical range')
    else:predictions[i]=float(v)
 return dict(processing={'batch_rows':PREDICTION_BATCH_ROWS,'row_limit':MAX_RESEARCH_ROWS,'complete':True},mode='research_only_not_for_operational_decisions',dataset_id=req.dataset_id,dataset_sha256=digest,model_id=m['id'],model_sha256=m['sha256'],training_source_sha256=m['source_sha256'],model_name=m['name'],target=m['target'],condition=m['condition'],unit=m['unit'],mapping=req.mapping,declared_units=req.units,features=m['features'],validation_mae=m['validation_mae'],validation_rows=m['validation_rows'],limitations=m['limitations'],production_eligible=False,rows=len(frame),predicted_rows=sum(v is not None for v in predictions),samples=[dict(source_row=i,prediction=v,status='predicted' if v is not None else 'withheld',reasons=reasons[i]) for i,v in enumerate(predictions)])
