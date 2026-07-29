def classify_lithology(
    gamma_ray: float
) -> str:

    if gamma_ray < 50:
        return "Sandstone"

    if gamma_ray < 90:
        return "Siltstone"

    return "Shale"