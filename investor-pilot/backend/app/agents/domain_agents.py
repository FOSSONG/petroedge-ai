from __future__ import annotations

from statistics import mean
from typing import Any

from app.agents.base import BaseAgent
from app.agents.schemas import AgentDomain, AgentFinding, AgentResult, Severity


def _average(agent: BaseAgent, rows: list[dict[str, Any]], *columns: str) -> tuple[str | None, float | None]:
    for column in columns:
        values = agent.numeric_values(rows, column)
        if values:
            return column, mean(values)
    return None, None


class GeologistAgent(BaseAgent):
    key = "geologist"
    name = "Geologist Agent"
    domain = AgentDomain.geology

    async def analyse(self, inputs: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        rows = self.rows_from_inputs(inputs)
        gr_column, gr_mean = _average(self, rows, "GR", "GR_COMP.GAPI")
        findings = []
        confidence = 0.45

        if gr_mean is not None:
            confidence = 0.80
            if gr_mean < 60:
                statement = "The interval is predominantly clean and sand-prone."
                recommendation = "Prioritise the interval for reservoir-quality screening."
            elif gr_mean < 90:
                statement = "The interval is moderately shaly and may represent shaly sand."
                recommendation = "Integrate density-neutron and resistivity evidence before net-pay classification."
            else:
                statement = "The interval is shale-prone."
                recommendation = "Treat reservoir potential cautiously unless supported by core or image-log evidence."
            findings.append(
                AgentFinding(
                    title="Lithology screening",
                    statement=statement,
                    confidence=confidence,
                    evidence=[f"Mean {gr_column} = {gr_mean:.2f}"],
                    recommendations=[recommendation],
                    metrics={"mean_gamma_ray": gr_mean},
                )
            )

        if not findings:
            findings.append(
                AgentFinding(
                    title="Insufficient geological evidence",
                    statement="No recognised gamma-ray curve was available for lithology screening.",
                    confidence=0.30,
                    severity=Severity.medium,
                    recommendations=["Provide GR and depth-indexed log data."],
                )
            )

        return AgentResult(
            agent_key=self.key,
            agent_name=self.name,
            domain=self.domain,
            confidence=confidence,
            findings=findings,
            summary=findings[0].statement,
            limitations=[] if gr_mean is not None else ["Gamma-ray data unavailable."],
        )


class PetrophysicistAgent(BaseAgent):
    key = "petrophysicist"
    name = "Petrophysicist Agent"
    domain = AgentDomain.petrophysics

    async def analyse(self, inputs: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        rows = self.rows_from_inputs(inputs)
        phi_column, phi_mean = _average(self, rows, "PHI_D", "PHI", "POROSITY")
        sw_column, sw_mean = _average(self, rows, "SW_ARCHIE", "SW", "WATER_SATURATION")
        findings = []
        evidence = []
        confidence = 0.40

        if phi_mean is not None:
            evidence.append(f"Mean {phi_column} = {phi_mean:.3f}")
        if sw_mean is not None:
            evidence.append(f"Mean {sw_column} = {sw_mean:.3f}")

        if phi_mean is not None or sw_mean is not None:
            confidence = 0.88 if phi_mean is not None and sw_mean is not None else 0.72
            quality = "uncertain"
            if phi_mean is not None and sw_mean is not None:
                if phi_mean >= 0.18 and sw_mean <= 0.45:
                    quality = "favourable"
                elif phi_mean < 0.10 or sw_mean > 0.70:
                    quality = "poor"
                else:
                    quality = "moderate"

            findings.append(
                AgentFinding(
                    title="Reservoir quality",
                    statement=f"Petrophysical reservoir quality is {quality}.",
                    confidence=confidence,
                    evidence=evidence,
                    recommendations=[
                        "Validate cut-offs against core-calibrated porosity, saturation and permeability."
                    ],
                    metrics={
                        "mean_porosity": phi_mean,
                        "mean_water_saturation": sw_mean,
                    },
                )
            )
        else:
            findings.append(
                AgentFinding(
                    title="Insufficient petrophysical evidence",
                    statement="No recognised porosity or water-saturation curves were available.",
                    confidence=0.30,
                    severity=Severity.medium,
                    recommendations=["Run the petrophysical workflow before multi-agent interpretation."],
                )
            )

        return AgentResult(
            agent_key=self.key,
            agent_name=self.name,
            domain=self.domain,
            confidence=confidence,
            findings=findings,
            summary=findings[0].statement,
            limitations=[] if evidence else ["Porosity and saturation evidence unavailable."],
        )


class ReservoirEngineerAgent(BaseAgent):
    key = "reservoir_engineer"
    name = "Reservoir Engineer Agent"
    domain = AgentDomain.reservoir_engineering

    async def analyse(self, inputs: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        rows = self.rows_from_inputs(inputs)
        pressure_column, pressure_mean = _average(self, rows, "PRESSURE", "Pressure", "pressure")
        perm_column, perm_mean = _average(self, rows, "PERM", "PERMEABILITY", "k")
        evidence = []
        if pressure_mean is not None:
            evidence.append(f"Mean {pressure_column} = {pressure_mean:.2f}")
        if perm_mean is not None:
            evidence.append(f"Mean {perm_column} = {perm_mean:.2f}")

        if evidence:
            confidence = 0.70
            statement = "Reservoir deliverability can be screened, but connectivity requires spatial or pressure-transient evidence."
            limitations = ["Connectivity cannot be confirmed from scalar averages alone."]
        else:
            confidence = 0.28
            statement = "Reservoir-engineering evidence is insufficient for connectivity or recovery assessment."
            limitations = ["Pressure and permeability evidence unavailable."]

        finding = AgentFinding(
            title="Reservoir engineering screen",
            statement=statement,
            confidence=confidence,
            evidence=evidence,
            recommendations=[
                "Integrate pressure, production, PVT, completion and spatial data for dynamic assessment."
            ],
            metrics={"mean_pressure": pressure_mean, "mean_permeability": perm_mean},
        )
        return AgentResult(
            agent_key=self.key,
            agent_name=self.name,
            domain=self.domain,
            confidence=confidence,
            findings=[finding],
            summary=statement,
            limitations=limitations,
        )


class ProductionEngineerAgent(BaseAgent):
    key = "production_engineer"
    name = "Production Engineer Agent"
    domain = AgentDomain.production_engineering

    async def analyse(self, inputs: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        rows = self.rows_from_inputs(inputs)
        oil_column, oil_mean = _average(self, rows, "Qoil STB/d", "oil_rate", "QOIL")
        water_column, water_mean = _average(self, rows, "Qwat STB/d", "water_rate", "QWAT")
        evidence = []
        if oil_mean is not None:
            evidence.append(f"Mean {oil_column} = {oil_mean:.2f}")
        if water_mean is not None:
            evidence.append(f"Mean {water_column} = {water_mean:.2f}")

        if oil_mean is not None:
            confidence = 0.72
            statement = "Production performance is measurable from the supplied rate data."
            recommendations = ["Add ordered dates and cumulative production for decline and breakthrough analysis."]
            limitations = []
        else:
            confidence = 0.25
            statement = "Production performance cannot be evaluated because no recognised oil-rate curve was supplied."
            recommendations = ["Provide date-indexed oil, gas and water production histories."]
            limitations = ["Production-rate evidence unavailable."]

        finding = AgentFinding(
            title="Production performance",
            statement=statement,
            confidence=confidence,
            evidence=evidence,
            recommendations=recommendations,
            metrics={"mean_oil_rate": oil_mean, "mean_water_rate": water_mean},
        )
        return AgentResult(
            agent_key=self.key,
            agent_name=self.name,
            domain=self.domain,
            confidence=confidence,
            findings=[finding],
            summary=statement,
            limitations=limitations,
        )


class DrillingEngineerAgent(BaseAgent):
    key = "drilling_engineer"
    name = "Drilling Engineer Agent"
    domain = AgentDomain.drilling_engineering

    async def analyse(self, inputs: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        rows = self.rows_from_inputs(inputs)
        rop_column, rop_mean = _average(self, rows, "ROP", "rate_of_penetration")
        caliper_column, caliper_mean = _average(self, rows, "CALI", "CALIPER")
        evidence = []
        if rop_mean is not None:
            evidence.append(f"Mean {rop_column} = {rop_mean:.2f}")
        if caliper_mean is not None:
            evidence.append(f"Mean {caliper_column} = {caliper_mean:.2f}")

        confidence = 0.68 if evidence else 0.22
        statement = (
            "Available drilling measurements support a preliminary operational screen."
            if evidence
            else "Drilling hazards cannot be assessed from the supplied dataset."
        )
        finding = AgentFinding(
            title="Drilling risk screen",
            statement=statement,
            confidence=confidence,
            evidence=evidence,
            recommendations=[
                "Integrate mud weight, ECD, torque, drag, caliper, ROP and loss-event data."
            ],
            metrics={"mean_rop": rop_mean, "mean_caliper": caliper_mean},
        )
        return AgentResult(
            agent_key=self.key,
            agent_name=self.name,
            domain=self.domain,
            confidence=confidence,
            findings=[finding],
            summary=statement,
            limitations=[] if evidence else ["Drilling measurements unavailable."],
        )


class CCUSAgent(BaseAgent):
    key = "ccus"
    name = "CCUS Agent"
    domain = AgentDomain.ccus

    async def analyse(self, inputs: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        rows = self.rows_from_inputs(inputs)
        phi_column, phi_mean = _average(self, rows, "PHI_D", "PHI", "POROSITY")
        perm_column, perm_mean = _average(self, rows, "PERM", "PERMEABILITY", "k")
        evidence = []
        if phi_mean is not None:
            evidence.append(f"Mean {phi_column} = {phi_mean:.3f}")
        if perm_mean is not None:
            evidence.append(f"Mean {perm_column} = {perm_mean:.2f}")

        confidence = 0.62 if evidence else 0.20
        statement = (
            "The interval has preliminary storage-characterisation evidence, but seal integrity and injectivity remain unverified."
            if evidence
            else "CCUS suitability cannot be assessed from the supplied evidence."
        )
        finding = AgentFinding(
            title="CCUS suitability screen",
            statement=statement,
            confidence=confidence,
            evidence=evidence,
            recommendations=[
                "Add caprock, pressure, fault, geomechanical, fluid and dynamic injectivity evidence."
            ],
            metrics={"mean_porosity": phi_mean, "mean_permeability": perm_mean},
        )
        return AgentResult(
            agent_key=self.key,
            agent_name=self.name,
            domain=self.domain,
            confidence=confidence,
            findings=[finding],
            summary=statement,
            limitations=["This is a screening result, not a storage certification."],
        )