from statistics import mean


def summarize_predictions(results: list[dict]) -> dict[str, float | int]:
    if not results:
        return {"count": 0, "avg_hydrocarbon_probability": 0.0, "anomaly_rate": 0.0}
    probabilities = [float(row.get("hydrocarbon_probability", 0.0)) for row in results]
    anomalies = [1.0 if row.get("is_anomaly") else 0.0 for row in results]
    return {
        "count": len(results),
        "avg_hydrocarbon_probability": round(mean(probabilities), 4),
        "anomaly_rate": round(mean(anomalies), 4),
        "data_drift_index": round(abs(mean(probabilities) - 0.42), 4),
    }

