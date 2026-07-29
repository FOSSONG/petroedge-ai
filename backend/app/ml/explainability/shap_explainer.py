import joblib
import pandas as pd
import shap

model = joblib.load(
    "models/hydrocarbon_xgb.pkl"
)

df = pd.read_csv(
    "data/niger_delta_synthetic.csv"
)

X = df[
    [
        "gamma_ray_api",
        "resistivity_ohmm",
        "density_gcc",
        "neutron_porosity_vv",
        "sonic_usft",
        "caliper_in"
    ]
]

sample = X.sample(
    1000,
    random_state=42
)

explainer = shap.TreeExplainer(
    model
)

values = explainer.shap_values(
    sample
)

importance = pd.DataFrame(
    {
        "feature": sample.columns,
        "importance":
        abs(values).mean(axis=0)
    }
)

importance = importance.sort_values(
    "importance",
    ascending=False
)

print(importance)

importance.to_csv(
    "models/shap_importance.csv",
    index=False
)