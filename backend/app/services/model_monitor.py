def summarize_predictions(results):

    if not results:
        return {}

    avg_prob = sum(
        r["hydrocarbon_probability"]
        for r in results
    ) / len(results)

    anomalies = sum(
        1
        for r in results
        if r["is_anomaly"]
    )

    return {
        "records": len(results),
        "average_hydrocarbon_probability": round(
            avg_prob,
            3,
        ),
        "anomalies": anomalies,
    }