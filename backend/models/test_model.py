import joblib
import pandas as pd

model = joblib.load(
    "models/hydrocarbon_xgb.pkl"
)

sample = pd.DataFrame(
    [{
        "gamma_ray_api":40,
        "resistivity_ohmm":80,
        "density_gcc":2.2,
        "neutron_porosity_vv":0.28,
        "sonic_usft":80,
        "caliper_in":8.5
    }]
)

prediction = model.predict(sample)

probability = model.predict_proba(sample)

print("Prediction:", prediction)
print("Probability:", probability)