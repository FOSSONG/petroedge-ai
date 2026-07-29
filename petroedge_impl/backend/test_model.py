import pandas as pd
import joblib

model = joblib.load(
    "models/hydrocarbon_xgb.pkl"
)

sample = pd.DataFrame(
    [{
        "gamma_ray_api": 30,
        "resistivity_ohmm": 120,
        "density_gcc": 2.2,
        "neutron_porosity_vv": 0.28,
        "sonic_usft": 75,
        "caliper_in": 8.5
    }]
)

print(
    model.predict_proba(sample)
)