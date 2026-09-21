from __future__ import annotations

from statistics import mean

from app.digital_twin.schemas import (
    HealthBand,
    HealthMetric,
    HealthReport,
    ReservoirState,
    TwinStatus,
)


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


class HealthEngine:
    def evaluate(self, state: ReservoirState) -> HealthReport:
        metrics: list[HealthMetric] = []
        recommendations: list[str] = []

        pressure_values = [
            well.pressure
            for well in state.wells.values()
            if well.pressure is not None
        ]
        water_cuts = []
        for well in state.wells.values():
            total_liquid = (well.oil_rate or 0.0) + (well.water_rate or 0.0)
            if total_liquid > 0:
                water_cuts.append((well.water_rate or 0.0) / total_liquid)

        pressure_score = 75.0
        if pressure_values:
            spread = max(pressure_values) - min(pressure_values)
            reference = max(mean(pressure_values), 1.0)
            pressure_score = _clamp(100.0 - (spread / reference) * 200.0)
        else:
            recommendations.append("Provide pressure data for depletion and connectivity monitoring.")

        metrics.append(
            HealthMetric(
                name="pressure_stability",
                score=pressure_score,
                weight=0.30,
                message="Pressure stability across available wells.",
                evidence={"well_count": len(pressure_values)},
            )
        )

        water_score = 80.0
        if water_cuts:
            average_water_cut = mean(water_cuts)
            water_score = _clamp(100.0 - average_water_cut * 100.0)
            if average_water_cut >= 0.60:
                recommendations.append("Investigate water breakthrough and coning risk.")
        else:
            recommendations.append("Provide oil and water rates for water-cut monitoring.")

        metrics.append(
            HealthMetric(
                name="water_management",
                score=water_score,
                weight=0.25,
                message="Water-cut and breakthrough screening.",
                evidence={"average_water_cut": mean(water_cuts) if water_cuts else None},
            )
        )

        active = sum(
            well.status == TwinStatus.active
            for well in state.wells.values()
        )
        total = len(state.wells)
        availability_score = 100.0 if total == 0 else _clamp((active / total) * 100.0)
        if total and active < total:
            recommendations.append("Review inactive or suspended wells and associated production loss.")

        metrics.append(
            HealthMetric(
                name="well_availability",
                score=availability_score,
                weight=0.20,
                message="Share of wells currently active.",
                evidence={"active_wells": active, "total_wells": total},
            )
        )

        porosity_values = [
            well.porosity
            for well in state.wells.values()
            if well.porosity is not None
        ]
        saturation_values = [
            well.water_saturation
            for well in state.wells.values()
            if well.water_saturation is not None
        ]

        reservoir_quality_score = 65.0
        if porosity_values or saturation_values:
            phi_component = (
                _clamp(mean(porosity_values) / 0.25 * 100.0)
                if porosity_values
                else 60.0
            )
            sw_component = (
                _clamp((1.0 - mean(saturation_values)) * 100.0)
                if saturation_values
                else 60.0
            )
            reservoir_quality_score = 0.55 * phi_component + 0.45 * sw_component
        else:
            recommendations.append("Provide porosity and saturation data for reservoir-quality scoring.")

        metrics.append(
            HealthMetric(
                name="reservoir_quality",
                score=_clamp(reservoir_quality_score),
                weight=0.25,
                message="Reservoir quality from porosity and water saturation.",
                evidence={
                    "average_porosity": mean(porosity_values) if porosity_values else None,
                    "average_water_saturation": (
                        mean(saturation_values) if saturation_values else None
                    ),
                },
            )
        )

        weighted_sum = sum(metric.score * metric.weight for metric in metrics)
        total_weight = sum(metric.weight for metric in metrics)
        overall = _clamp(weighted_sum / total_weight if total_weight else 0.0)
        risk = _clamp(100.0 - overall)

        if overall >= 85:
            band = HealthBand.excellent
        elif overall >= 70:
            band = HealthBand.good
        elif overall >= 55:
            band = HealthBand.watch
        elif overall >= 35:
            band = HealthBand.poor
        else:
            band = HealthBand.critical

        return HealthReport(
            reservoir_id=state.reservoir_id,
            overall_score=round(overall, 3),
            risk_score=round(risk, 3),
            band=band,
            metrics=metrics,
            recommendations=sorted(set(recommendations)),
        )


health_engine = HealthEngine()