"""Question-directed, source-grounded specialist responses; no invented inference."""
import re

DOMAINS = {
 "geologist": ["lithology","shale","gamma","gr","formation","stratigraphy","facies","sand","sonic","dt"],
 "petrophysicist": ["porosity","density","rhob","neutron","nphi","resistivity","rt","saturation","permeability","pay","fluid","oil","gas","water"],
 "reservoir": ["reservoir","production","rate","pressure","connectivity","reserves","recovery","inject","capacity"],
 "drilling": ["drilling","caliper","washout","borehole","bit","alarm","rig"],
 "qa": ["quality","missing","null","unit","units","qc","valid","invalid","outlier","header"],
}
CURVES = {
 "geologist":["gamma_ray_api","sonic_usft"],
 "petrophysicist":["density_gcc","neutron_porosity_vv","resistivity_ohmm"],
 "reservoir":["depth_m","resistivity_ohmm"],
 "drilling":["caliper_in"],
 "qa":[],
}
UNITS={"gamma_ray_api":"API","sonic_usft":"us/ft","density_gcc":"g/cm3","neutron_porosity_vv":"v/v","resistivity_ohmm":"ohm.m","depth_m":"m","caliper_in":"in"}
def specialists(question):
 words=set(re.findall(r"[a-z]+",question.lower()))
 found=[key for key,terms in DOMAINS.items() if words.intersection(terms)]
 if found:return found
 return list(DOMAINS) if words.intersection({"evaluate","summary","summarise","summarize"}) else ["qa"]

def respond(key, question, measured):
 if not measured:return (["Select an uploaded dataset or a saved analysis to answer: "+question], [], "Attach the evidence needed for this question.")
 if measured.get("mode")=="extractive_pdf_retrieval":
  return ([measured["answer"]],measured["evidence"],"Open the cited pages to check the answer in its original context.")
 evidence=["Dataset "+measured["dataset_id"]+"; "+str(measured["rows"])+" inspected rows","SHA256 "+measured["sha256"]]
 relevant=specialists(question)
 if key not in relevant:return (["This question is outside this specialist's evidence scope. Use "+", ".join(relevant)+" or ask the team."],evidence,"Route the question to the relevant specialist.")
 words=set(re.findall(r"[a-z]+",question.lower()))
 if not any(words.intersection(v) for v in DOMAINS.values()) and not words.intersection({"summary","summarise","summarize","evaluate","dt"}):
  return (["The selected evidence does not answer: "+question],evidence,"Ask about an available measurement, data quality or a saved result.")
 curves=measured["curves"]
 if key=="qa":
  findings=[str(measured["rows"])+" rows checked."]+[name+": "+str(v["valid"])+" valid; "+str(v["excluded"])+" missing, outside QC bounds or blocked by units." for name,v in curves.items()]
  findings+=measured["issues"]
  return (findings,evidence,"Review excluded measurements in LAS Wizard before interpreting them." if any(v["excluded"] for v in curves.values()) or measured["issues"] else "Available mapped curves passed the applied range checks; review source calibration separately.")
 words=set(re.findall(r"[a-z]+",question.lower()))
 requested={"density_gcc":{"density","rhob"},"neutron_porosity_vv":{"neutron","nphi"},"resistivity_ohmm":{"resistivity","rt"},"gamma_ray_api":{"gr","gamma"},"sonic_usft":{"sonic","dt"},"caliper_in":{"caliper","washout","borehole"}}
 targets=[k for k in CURVES[key] if words.intersection(requested.get(k,set()))] or CURVES[key]
 findings=[]
 for name in targets:
  v=curves.get(name)
  if not v or not v["valid"]:findings.append(name+": no valid measurement available.");continue
  findings.append(name+": median "+str(v["median"])+" "+UNITS[name]+", range "+str(v["minimum"])+" to "+str(v["maximum"])+"; "+str(v["valid"])+" valid samples.")
 if words.intersection({"porosity","permeability","saturation","pay","oil","gas","water","lithology","reserves","connectivity","production","pressure"}):
  findings.append("These measured-log summaries do not establish the requested property. Select a completed saved analysis for its recorded estimate; pressure, production, connectivity and reserves require their own supporting measurements.")
 recommendations={"geologist":"Inspect the GR and sonic crossplots and correlate with core or formation tops.",
 "petrophysicist":"Compare density-neutron and Pickett plots using documented matrix density and formation-water resistivity.",
 "reservoir":"Connect production, pressure and completion evidence before calculating reservoir performance.",
 "drilling":"Compare caliper against the actual bit size and environmental corrections before attributing a log anomaly to washout."}
 return findings,evidence,recommendations[key]
