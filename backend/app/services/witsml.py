def normalize_witsml_sample(sample):

    return {
        "well_id": sample.get(
            "well_id",
            "WITSML-DEMO"
        ),
        "channels": sample.get(
            "channels",
            {}
        ),
    }