"""Deterministic answers from one authorized, integrity-checked saved result."""
from app.services.analysis_records import get

METRICS = {"lithology":"classification", "hydrocarbon_probability":"model/heuristic blend or fallback score; not calibrated confidence", "porosity":"heuristic estimate (v/v)", "water_saturation":"heuristic estimate (v/v)", "permeability_md":"heuristic estimate (mD)"}
LIMITATION = "One saved sample only; no interval thickness, reserves, deployment readiness or independent confidence can be established from this record."

def answer(analysis_id, question):
    record = get(analysis_id)
    q = question.lower().strip()
    selected = [k for k in METRICS if k.replace("_", " ") in q or k.split("_")[0] in q]
    if any(word in q for word in ["summary", "summarise", "summarize", "result"]):
        selected = [k for k in METRICS if k in record]
    evidence = [{"analysis_id":analysis_id,"path":"provenance","href":f"/api/v1/analytics/saved/{analysis_id}"}]
    if any(word in q for word in ["source", "dataset", "provenance", "model", "fallback"]):
        facts = {"provenance":record["provenance"], "model_details":record.get("explanation", {})}
        text = "The stored source and model evidence is shown below. No new inference was run."
        evidence.append({"analysis_id":analysis_id,"path":"explanation","href":f"/api/v1/analytics/saved/{analysis_id}"})
    elif selected:
        facts = {k:{"value":record[k],"method":METRICS[k]} for k in selected if k in record}
        text = "Saved values: " + "; ".join(f"{k}: {v['value']} ({v['method']})" for k,v in facts.items()) if facts else "The requested value is absent from this saved result."
        evidence += [{"analysis_id":analysis_id,"path":k,"href":f"/api/v1/analytics/saved/{analysis_id}"} for k in facts]
    else:
        facts = {}
        text = "This saved sample does not support that question. Ask for its summary, recorded properties, source provenance or model/fallback details."
    return {"answer":text,"facts":facts,"citations":evidence,"limitation":LIMITATION,"mode":"saved_record_lookup","analysis_id":analysis_id}
