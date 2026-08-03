import pandas as pd

from app.services.shap_service import explain

sample = pd.DataFrame(
    [
        {
            "gamma_ray_api": 30,
            "resistivity_ohmm": 120,
            "density_gcc": 2.1,
            "neutron_porosity_vv": 0.28,
            "sonic_usft": 70,
            "caliper_in": 8.5,
        }
    ]
)

print(
    explain(sample)
)