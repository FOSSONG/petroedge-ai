from __future__ import annotations

from typing import Any
import math
from io import BytesIO

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.rbac import require_roles
from app.platform_v1.datasets import get_dataset, get_dataset_path
from app.preprocessing.curve_aliases import canonical_name_for, map_curve_columns, missing_ai_curves

router = APIRouter(tags=["Reservoir Intelligence V1"])
READ_ROLES = require_roles("admin", "administrator", "operator", "engineer", "geoscientist", "petrophysicist", "viewer")


def _frame(dataset_id: str, limit: int = 2000) -> tuple[pd.DataFrame, dict[str, str | None]]:
    path = get_dataset_path(dataset_id)
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path, nrows=limit)
    elif path.suffix.lower() == ".parquet":
        frame = pd.read_parquet(path).head(limit)
    elif path.suffix.lower() == ".las":
        import lasio
        frame = lasio.read(path).df().reset_index().head(limit)
    else:
        raise ValueError("Unsupported dataset type.")
    original = [str(c) for c in frame.columns]
    result = map_curve_columns(frame)
    mapping = {column: canonical_name_for(column) for column in original}
    mapped = result.dataframe.copy()
    for column in mapped.columns:
        if column not in {"well_id", "date"}:
            mapped[column] = pd.to_numeric(mapped[column], errors="coerce")
    return mapped, mapping


def _series(frame: pd.DataFrame, name: str, default: float) -> pd.Series:
    if name in frame.columns:
        return pd.to_numeric(frame[name], errors="coerce").fillna(default)
    return pd.Series([default] * len(frame), index=frame.index, dtype=float)


def _interpret(dataset_id: str) -> dict[str, Any]:
    dataset = get_dataset(dataset_id)
    frame, mapping = _frame(dataset_id)
    if frame.empty:
        raise ValueError("The dataset contains no readable rows.")
    depth = _series(frame, "depth_m", 0.0)
    if not depth.any():
        depth = pd.Series(range(len(frame)), dtype=float)
    gr = _series(frame, "gamma_ray_api", 75.0).clip(0, 250)
    rt = _series(frame, "resistivity_ohmm", 1.0).clip(0.01, 10000)
    rhob = _series(frame, "density_gcc", 2.45).clip(1.5, 3.2)
    nphi = _series(frame, "neutron_porosity_vv", 0.18).clip(-0.15, 0.7)
    dt = _series(frame, "sonic_usft", 90.0).clip(35, 250)
    cali = _series(frame, "caliper_in", 8.5).clip(2, 30)
    vsh = (gr / 150.0).clip(0, 1)
    density_phi = ((2.65 - rhob) / (2.65 - 1.0)).clip(0, 0.6)
    porosity = ((density_phi + nphi.clip(0, 0.6)) / 2.0).clip(0, 0.6)
    sw = ((0.1 / (porosity.replace(0, 0.01) ** 2 * rt)) ** 0.5).clip(0.05, 1.0)
    perm = (1000 * (porosity ** 3) / ((sw.clip(0.1, 1)) ** 2)).clip(0, 5000)
    clean = (1 - vsh).clip(0, 1)
    rt_score = ((rt.apply(lambda x: math.log10(max(x, .01))) + 1) / 3).clip(0, 1)
    hc = (0.45 * rt_score + 0.25 * clean + 0.20 * (porosity / .30).clip(0, 1) + 0.10 * (1-sw)).clip(0, 1)
    # Transparent fluid screening. Gas evidence is driven primarily by density-neutron
    # separation and sonic response; oil evidence is hydrocarbon response without a
    # pronounced gas effect; water evidence is dominated by high Sw/low HC response.
    nd_sep = (density_phi - nphi).clip(-0.35, 0.35)
    gas_effect = ((nd_sep - 0.04) / 0.18).clip(0, 1)
    sonic_gas = ((dt - 95.0) / 55.0).clip(0, 1)
    gas_score = (0.60 * gas_effect + 0.20 * sonic_gas + 0.20 * hc).clip(0, 1)
    oil_score = (hc * (1.0 - 0.72 * gas_effect)).clip(0, 1)
    water_score = (0.72 * sw + 0.28 * (1.0 - hc)).clip(0, 1)
    residual_score = (0.20 * hc * (1.0 - porosity / 0.35).clip(0, 1)).clip(0, 1)
    fluid_total = (gas_score + oil_score + water_score + residual_score).replace(0, 1)
    gas_probability = gas_score / fluid_total
    oil_probability = oil_score / fluid_total
    water_probability = water_score / fluid_total
    residual_probability = residual_score / fluid_total
    fluid_labels = pd.DataFrame({"gas": gas_probability, "oil": oil_probability, "water": water_probability, "residual_hydrocarbon": residual_probability}).idxmax(axis=1)
    lith = pd.Series("Shale", index=frame.index)
    lith[(vsh < .65) & (vsh >= .35)] = "Sandy shale"
    lith[(vsh < .35) & (vsh >= .20)] = "Shaly sand"
    lith[vsh < .20] = "Sandstone"
    pay = (hc >= .55) & (sw <= .60) & (vsh <= .45) & (porosity >= .10)
    samples=[]
    for i in range(len(frame)):
        samples.append({"depth":round(float(depth.iloc[i]),3),"gr":round(float(gr.iloc[i]),3),"rt":round(float(rt.iloc[i]),4),"rhob":round(float(rhob.iloc[i]),4),"nphi":round(float(nphi.iloc[i]),4),"dt":round(float(dt.iloc[i]),3),"caliper":round(float(cali.iloc[i]),3),"porosity":round(float(porosity.iloc[i]),4),"water_saturation":round(float(sw.iloc[i]),4),"permeability_md":round(float(perm.iloc[i]),3),"shale_volume":round(float(vsh.iloc[i]),4),"hydrocarbon_probability":round(float(hc.iloc[i]),4),"fluid_type":str(fluid_labels.iloc[i]),"fluid_confidence":round(float(max(gas_probability.iloc[i],oil_probability.iloc[i],water_probability.iloc[i],residual_probability.iloc[i])),4),"fluid_probabilities":{"oil":round(float(oil_probability.iloc[i]),4),"gas":round(float(gas_probability.iloc[i]),4),"water":round(float(water_probability.iloc[i]),4),"residual_hydrocarbon":round(float(residual_probability.iloc[i]),4)},"lithology":str(lith.iloc[i]),"pay_flag":"Pay" if bool(pay.iloc[i]) else "Non-pay"})
    intervals=[]
    active=None
    for item in samples:
        is_pay=item["pay_flag"]=="Pay"
        if is_pay and active is None: active={"top_depth":item["depth"],"base_depth":item["depth"],"samples":1}
        elif is_pay and active is not None: active["base_depth"]=item["depth"];active["samples"]+=1
        elif not is_pay and active is not None: intervals.append(active);active=None
    if active: intervals.append(active)
    mean_fluid_probs={"oil":float(oil_probability.mean()),"gas":float(gas_probability.mean()),"water":float(water_probability.mean()),"residual_hydrocarbon":float(residual_probability.mean())}
    primary_fluid=max(mean_fluid_probs,key=mean_fluid_probs.get)
    summary={"rows_interpreted":len(samples),"mapped_curves":sum(1 for v in mapping.values() if v),"mean_porosity":round(float(porosity.mean()),4),"mean_water_saturation":round(float(sw.mean()),4),"mean_hydrocarbon_probability":round(float(hc.mean()),4),"pay_samples":int(pay.sum()),"pay_intervals":len(intervals),"primary_fluid":primary_fluid,"fluid_probabilities":{k:round(v,4) for k,v in mean_fluid_probs.items()},"fluid_confidence":round(mean_fluid_probs[primary_fluid],4),"fluid_method":"density-neutron-sonic-resistivity screening","calibration":"Niger Delta screening calibration"}
    return {"dataset":dataset.model_dump(),"curve_mapping":mapping,"summary":summary,"intervals":intervals,"samples":samples}


class AssistantRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


@router.get("/datasets/{dataset_id}/interpretation")
def interpretation(dataset_id: str, _: dict[str, Any] = Depends(READ_ROLES)) -> dict[str, Any]:
    try: return _interpret(dataset_id)
    except KeyError as exc: raise HTTPException(status_code=404, detail="Dataset not found.") from exc
    except (ValueError, FileNotFoundError) as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/datasets/{dataset_id}/las-wizard")
def las_wizard(dataset_id: str, _: dict[str, Any] = Depends(READ_ROLES)) -> dict[str, Any]:
    try:
        frame, mapping = _frame(dataset_id)
        missing = missing_ai_curves(frame.columns)
        return {"dataset_id":dataset_id,"detected_curves":[str(c) for c in frame.columns],"mnemonic_mapping":mapping,"qc":{"row_count":len(frame),"missing_cells":int(frame.isna().sum().sum()),"duplicate_rows":int(frame.duplicated().sum()),"ready":len(missing)<=2},"missing_recommended_curves":missing,"steps":["File read","Headers normalised","Curve aliases mapped","Quality control completed","Ready for interpretation"]}
    except KeyError as exc: raise HTTPException(status_code=404, detail="Dataset not found.") from exc


@router.get("/datasets/{dataset_id}/replay")
def replay(
    dataset_id: str,
    limit: int = 500,
    top_depth: float | None = None,
    bottom_depth: float | None = None,
    _: dict[str, Any] = Depends(READ_ROLES),
) -> dict[str, Any]:
    result = _interpret(dataset_id)
    rows = result["samples"]
    if top_depth is not None or bottom_depth is not None:
        available_depths = [float(row["depth"]) for row in rows]
        minimum = min(available_depths) if available_depths else 0.0
        maximum = max(available_depths) if available_depths else 0.0
        top = minimum if top_depth is None else float(top_depth)
        bottom = maximum if bottom_depth is None else float(bottom_depth)
        low, high = sorted((top, bottom))
        rows = [row for row in rows if low <= float(row["depth"]) <= high]
    rows = rows[:max(1, min(limit, 1000))]
    events=[]
    for index,row in enumerate(rows):
        alerts=[]
        if row["pay_flag"]=="Pay": alerts.append("Potential hydrocarbon pay detected")
        if row["caliper"]>10.5: alerts.append("Possible borehole enlargement")
        events.append({"sequence":index+1,"depth":row["depth"],"logs":{"gr":row["gr"],"rt":row["rt"],"rhob":row["rhob"],"nphi":row["nphi"],"dt":row["dt"]},"prediction":{"lithology":row["lithology"],"porosity":row["porosity"],"water_saturation":row["water_saturation"],"hydrocarbon_probability":row["hydrocarbon_probability"],"pay_flag":row["pay_flag"]},"alerts":alerts})
    return {"dataset_id":dataset_id,"event_count":len(events),"events":events}


@router.post("/datasets/{dataset_id}/assistant")
def assistant(dataset_id: str, payload: AssistantRequest, _: dict[str, Any] = Depends(READ_ROLES)) -> dict[str, Any]:
    try:
        result = _interpret(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    question = payload.question.strip()
    q = question.lower()
    samples = result.get("samples") or []
    intervals = result.get("intervals") or []
    summary = result.get("summary") or {}
    dataset_name = result.get("dataset", {}).get("name", dataset_id)
    if not samples:
        raise HTTPException(status_code=422, detail="No interpretable samples were found in the selected dataset.")

    def pct(value: float) -> str:
        return f"{float(value):.1%}"

    best_hc = max(samples, key=lambda row: float(row.get("hydrocarbon_probability", 0)))
    best_phi = max(samples, key=lambda row: float(row.get("porosity", 0)))
    lowest_sw = min(samples, key=lambda row: float(row.get("water_saturation", 1)))
    highest_rt = max(samples, key=lambda row: float(row.get("rt", 0)))
    cleanest = min(samples, key=lambda row: float(row.get("gr", 999)))
    lith_counts = pd.Series([row.get("lithology", "Unknown") for row in samples]).value_counts().to_dict()

    intent = "summary"
    target = best_hc
    answer = ""

    if any(term in q for term in ("pay interval", "pay zone", "show pay", "depths of pay", "all pay")):
        intent = "pay_intervals"
        if intervals:
            parts = []
            for idx, interval in enumerate(intervals, 1):
                top = float(interval.get("top_depth", 0)); base = float(interval.get("base_depth", top))
                parts.append(f"Pay {idx}: {top:.2f}â€“{base:.2f} m, gross thickness {abs(base-top):.2f} m")
            answer = f"{dataset_name} contains {len(intervals)} potential pay interval(s): " + "; ".join(parts) + "."
        else:
            answer = f"No interval in {dataset_name} satisfies the current pay-screening thresholds."
    elif "highest porosity" in q or "best porosity" in q or "maximum porosity" in q:
        intent = "highest_porosity"; target = best_phi
        answer = f"The highest interpreted porosity occurs at {float(target['depth']):.2f} m: {pct(target['porosity'])}. The sample is {target['lithology']} with Sw {pct(target['water_saturation'])} and hydrocarbon probability {pct(target['hydrocarbon_probability'])}."
    elif "lowest water" in q or "lowest sw" in q or "minimum sw" in q:
        intent = "lowest_water_saturation"; target = lowest_sw
        answer = f"The lowest interpreted water saturation occurs at {float(target['depth']):.2f} m: {pct(target['water_saturation'])}, with porosity {pct(target['porosity'])} and hydrocarbon probability {pct(target['hydrocarbon_probability'])}."
    elif "highest resist" in q or "maximum resist" in q or "strongest resist" in q:
        intent = "highest_resistivity"; target = highest_rt
        answer = f"The highest mapped resistivity occurs at {float(target['depth']):.2f} m: {float(target['rt']):.2f} ohmÂ·m. The corresponding interpretation is {target['lithology']}, porosity {pct(target['porosity'])}, Sw {pct(target['water_saturation'])}."
    elif "cleanest" in q or "lowest gamma" in q or "minimum gr" in q:
        intent = "cleanest_interval"; target = cleanest
        answer = f"The cleanest interpreted sample occurs at {float(target['depth']):.2f} m with GR {float(target['gr']):.1f} API and shale volume {pct(target['shale_volume'])}. It is classified as {target['lithology']}."
    elif "anomal" in q or "outlier" in q:
        intent = "anomaly_screening"
        rt_values = pd.Series([float(row.get("rt", 0)) for row in samples])
        threshold = float(rt_values.quantile(.95))
        anomalies = [row for row in samples if float(row.get("rt", 0)) >= threshold or float(row.get("caliper", 0)) > 10.5]
        target = max(anomalies or samples, key=lambda row: float(row.get("hydrocarbon_probability", 0)))
        answer = f"The screening identified {len(anomalies)} anomalous sample(s), based on upper-tail resistivity or borehole enlargement. The most relevant anomaly is at {float(target['depth']):.2f} m with RT {float(target['rt']):.2f} ohmÂ·m and caliper {float(target['caliper']):.2f} in."
    elif any(term in q for term in ("why", "explain", "contributed", "contribution", "which curve", "feature importance")):
        intent = "explanation"; target = best_hc
        answer = f"The strongest hydrocarbon indication occurs at {float(target['depth']):.2f} m. Its interpretation reflects the combined resistivity, clean-formation response, porosity and water-saturation evidence. It is classified as {target['lithology']} with porosity {pct(target['porosity'])}, Sw {pct(target['water_saturation'])}, and hydrocarbon probability {pct(target['hydrocarbon_probability'])}."
    elif "litholog" in q or "sandstone" in q or "shale" in q:
        intent = "lithology"
        distribution = ", ".join(f"{name}: {count}" for name, count in lith_counts.items())
        answer = f"The interpreted lithology distribution for {dataset_name} is {distribution}. The strongest hydrocarbon sample is classified as {best_hc['lithology']} at {float(best_hc['depth']):.2f} m."
    elif any(term in q for term in ("fluid", "oil or gas", "oil", "gas", "water bearing")):
        intent = "fluid_typing"
        probabilities = summary.get("fluid_probabilities", {})
        primary = str(summary.get("primary_fluid", "uncertain")).replace("_", " ")
        confidence = float(summary.get("fluid_confidence", 0))
        ranked = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)
        distribution = ", ".join(f"{name.replace('_',' ').title()} {pct(value)}" for name, value in ranked)
        answer = (f"The current log-based screening classifies {dataset_name} predominantly as {primary.title()} with {pct(confidence)} confidence. "
                  f"Probability distribution: {distribution}. This is an evidence-weighted screening result; formation testing, PVT, mud-log shows or production data are required for definitive fluid confirmation.")
        target = best_hc
    elif "compare" in q:
        intent = "comparison_required"
        answer = "A defensible comparison requires two selected datasets or wells. Use the Digital Twin comparison view or select another dataset so PetroEdge can calculate the same metrics for both assets."
    else:
        # Generic grounded aggregation over all interpreted numeric fields. This avoids a
        # fixed FAQ response while keeping answers strictly tied to the selected dataset.
        field_aliases = {
            "porosity":"porosity", "phi":"porosity", "water saturation":"water_saturation", "sw":"water_saturation",
            "permeability":"permeability_md", "perm":"permeability_md", "gamma ray":"gr", "gr":"gr",
            "resistivity":"rt", "rt":"rt", "density":"rhob", "rhob":"rhob", "neutron":"nphi",
            "sonic":"dt", "shale volume":"shale_volume", "vsh":"shale_volume",
            "hydrocarbon probability":"hydrocarbon_probability", "hc probability":"hydrocarbon_probability",
            "fluid confidence":"fluid_confidence", "depth":"depth"
        }
        matched = next(((alias,key) for alias,key in sorted(field_aliases.items(),key=lambda item:len(item[0]),reverse=True) if alias in q), None)
        operation = "mean"
        if any(word in q for word in ("highest","maximum","max","largest","best")): operation="max"
        elif any(word in q for word in ("lowest","minimum","min","smallest")): operation="min"
        elif any(word in q for word in ("average","mean","typical")): operation="mean"
        elif any(word in q for word in ("median",)): operation="median"
        if matched:
            alias,key = matched
            valid=[row for row in samples if isinstance(row.get(key),(int,float)) and math.isfinite(float(row[key]))]
            if valid:
                series=pd.Series([float(row[key]) for row in valid])
                unit = "%" if key in {"porosity","water_saturation","shale_volume","hydrocarbon_probability","fluid_confidence"} else {"permeability_md":" mD","gr":" API","rt":" ohmÂ·m","rhob":" g/cc","nphi":" v/v","dt":" Âµs/ft","depth":" m"}.get(key,"")
                if operation=="max": target=max(valid,key=lambda row:float(row[key])); value=float(target[key]); descriptor=f"maximum {alias}"
                elif operation=="min": target=min(valid,key=lambda row:float(row[key])); value=float(target[key]); descriptor=f"minimum {alias}"
                elif operation=="median": value=float(series.median()); target=min(valid,key=lambda row:abs(float(row[key])-value)); descriptor=f"median {alias}"
                else: value=float(series.mean()); target=min(valid,key=lambda row:abs(float(row[key])-value)); descriptor=f"mean {alias}"
                display=f"{value*100:.1f}%" if unit=="%" else f"{value:.3f}{unit}"
                answer=f"The {descriptor} in {dataset_name} is {display}. The representative depth is {float(target['depth']):.2f} m, where lithology is {target['lithology']} and the pay classification is {target['pay_flag']}."
                intent=f"dataset_{operation}_{key}"
            else:
                answer=f"I found the requested field ({alias}) but no valid numeric values are available in {dataset_name}."
                intent="insufficient_numeric_evidence"
        elif any(word in q for word in ("summary","overview","describe","analyse","analyze")):
            answer=(f"{dataset_name} contains {int(summary.get('rows_interpreted',len(samples)))} interpreted samples and {len(intervals)} potential pay interval(s). Mean porosity is {pct(summary.get('mean_porosity',0))}, mean Sw is {pct(summary.get('mean_water_saturation',0))}, and the predominant fluid screening is {str(summary.get('primary_fluid','uncertain')).replace('_',' ').title()} at {pct(summary.get('fluid_confidence',0))} confidence.")
            intent="dataset_summary"
        else:
            answer=("I could not derive a defensible answer from the selected dataset, its interpreted curves, workflow outputs or the petroleum rules available to this assistant. "
                    "Please ask about a measured or interpreted property, depth interval, lithology, pay zone, fluid type, uncertainty, or model result available in PetroEdge.")
            intent="unsupported_by_available_evidence"

    contributions = {
        "Resistivity": 0.45 * float(target.get("hydrocarbon_probability", 0)),
        "Clean formation / GR": 0.25 * (1 - float(target.get("shale_volume", 1))),
        "Porosity": 0.20 * min(float(target.get("porosity", 0)) / 0.30, 1),
        "Low water saturation": 0.10 * (1 - float(target.get("water_saturation", 1))),
    }
    total = sum(max(v, 0) for v in contributions.values()) or 1.0
    feature_importance = [
        {"feature": key, "contribution": round(max(value, 0) / total, 4)}
        for key, value in sorted(contributions.items(), key=lambda item: item[1], reverse=True)
    ]
    evidence = [
        f"Dataset: {dataset_name}",
        f"Question intent: {intent.replace('_', ' ')}",
        f"Rows interpreted: {summary.get('rows_interpreted', len(samples))}",
        f"Mapped curves: {summary.get('mapped_curves', 'not reported')}",
        f"Calibration: {summary.get('calibration', 'Niger Delta screening calibration')}",
        f"Target depth: {float(target['depth']):.2f} m",
    ]
    return {
        "question": question,
        "intent": intent,
        "answer": answer,
        "evidence": evidence,
        "grounded": True,
        "explanation": {
            "depth": target["depth"],
            "prediction": target["pay_flag"],
            "lithology": target["lithology"],
            "confidence": target["hydrocarbon_probability"],
            "porosity": target["porosity"],
            "water_saturation": target["water_saturation"],
            "feature_importance": feature_importance,
        },
        "intervals": intervals,
    }


@router.get("/datasets/{dataset_id}/report.pdf")
def log_signature_pdf(dataset_id: str, _: dict[str, Any] = Depends(READ_ROLES)):
    try:
        result = _interpret(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, A3
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FormatStrFormatter

    dataset = result["dataset"]
    samples = result["samples"]
    summary = result["summary"]
    depth = [float(r["depth"]) for r in samples]
    curve_specs = [("gr","GR (API)",False),("rt","RT (ohmÂ·m)",True),("rhob","RHOB (g/cc)",False),("nphi","NPHI (v/v)",False),("porosity","Porosity (v/v)",False),("water_saturation","Sw (v/v)",False),("hydrocarbon_probability","HC probability",False)]
    fig, axes = plt.subplots(1, len(curve_specs), figsize=(18, 11), sharey=True)
    for ax,(key,title,is_log) in zip(axes,curve_specs):
        values=[float(r.get(key,0) or 0) for r in samples]
        ax.plot(values,depth,linewidth=.75)
        ax.set_title(title,fontsize=8)
        ax.grid(True,alpha=.25)
        ax.tick_params(labelsize=7)
        if is_log: ax.set_xscale("log")
        ax.xaxis.set_major_formatter(FormatStrFormatter("%.1f"))
    axes[0].set_ylabel("Depth (m)")
    axes[0].invert_yaxis()
    fig.suptitle(f"PetroEdge Multi-track Log Interpretation â€” {dataset.get('name', dataset_id)}",fontsize=14,fontweight="bold")
    fig.tight_layout(rect=[0,0,1,.97])
    image_buffer=BytesIO();fig.savefig(image_buffer,format="png",dpi=220,bbox_inches="tight");plt.close(fig);image_buffer.seek(0)

    output=BytesIO();doc=SimpleDocTemplate(output,pagesize=landscape(A3),rightMargin=28,leftMargin=28,topMargin=28,bottomMargin=28)
    styles=getSampleStyleSheet();story=[Paragraph("PetroEdge AI â€” Interactive Log Signature Report",styles["Title"]),Spacer(1,8)]
    fluid=str(summary.get("primary_fluid","uncertain")).replace("_"," ").title();confidence=float(summary.get("fluid_confidence",0))*100
    table_data=[["Dataset",dataset.get("name",dataset_id),"Fluid screening",fluid],["Rows interpreted",summary.get("rows_interpreted"),"Fluid confidence",f"{confidence:.1f}%"],["Mean porosity",f"{float(summary.get('mean_porosity',0))*100:.1f}%","Mean Sw",f"{float(summary.get('mean_water_saturation',0))*100:.1f}%"],["Pay intervals",summary.get("pay_intervals"),"HC probability",f"{float(summary.get('mean_hydrocarbon_probability',0))*100:.1f}%"]]
    t=Table(table_data,colWidths=[100,220,110,220]);t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.5,colors.grey),("BACKGROUND",(0,0),(0,-1),colors.HexColor("#dceff1")),("BACKGROUND",(2,0),(2,-1),colors.HexColor("#dceff1")),("FONTNAME",(0,0),(-1,-1),"Helvetica"),("FONTSIZE",(0,0),(-1,-1),9),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story.extend([t,Spacer(1,12),Image(image_buffer,width=1100,height=650),Spacer(1,10),Paragraph("Interpretation note",styles["Heading2"]),Paragraph("Fluid typing is a transparent screening interpretation based on density-neutron separation, sonic response, resistivity, porosity and water saturation. Confirm oil or gas using pressure-gradient data, formation testing, PVT, mud-log shows or production evidence before operational decisions.",styles["BodyText"])])
    doc.build(story);output.seek(0)
    filename=f"petroedge-{dataset_id}-log-signature.pdf"
    return StreamingResponse(output,media_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="{filename}"'})


@router.get("/edge-runtime")
def edge_runtime(_: dict[str, Any] = Depends(READ_ROLES)) -> dict[str, Any]:
    now = pd.Timestamp.utcnow()
    phase = int(now.timestamp()) % 20
    return {
        "device_id": "petroedge-edge-sim-01",
        "device_name": "PetroEdge Rig Edge Simulator",
        "status": "online",
        "runtime": "ONNX/CPU simulation",
        "cpu_percent": 18 + phase,
        "memory_percent": 34 + (phase // 2),
        "queue_depth": phase % 4,
        "inference_latency_ms": 38 + phase * 2,
        "sync_status": "synchronised",
        "last_heartbeat": now.isoformat(),
        "deployment_target": "Jetson, Intel NUC or rugged industrial PC",
    }


@router.get("/modules")
def modules(_: dict[str, Any] = Depends(READ_ROLES)) -> list[dict[str, Any]]:
    return [
        {"module":"Formation Evaluation","slug":"formation-evaluation","status":"active","mvp_functional":True},
        {"module":"Reservoir Characterisation","slug":"reservoir-characterisation","status":"active","mvp_functional":True},
        {"module":"Production Forecasting","slug":"production-forecasting","status":"planned","mvp_functional":False},
        {"module":"CCUS Screening","slug":"ccus-screening","status":"planned","mvp_functional":False},
        {"module":"Seismic Interpretation","slug":"seismic-interpretation","status":"planned","mvp_functional":False},
        {"module":"Drilling Optimisation","slug":"drilling-optimisation","status":"planned","mvp_functional":False},
        {"module":"Environmental Intelligence","slug":"environmental-intelligence","status":"planned","mvp_functional":False},
        {"module":"Economic Evaluation","slug":"economic-evaluation","status":"planned","mvp_functional":False},
    ]
