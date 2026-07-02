# Models

The platform has model slots for:

- Hydrocarbon detection
- Lithology classification
- Facies prediction
- Anomaly detection

The current code ships rule-based and statistical baselines to make the application deployable without a training phase. The codebase includes PyTorch, TensorFlow, Scikit-learn, and MLflow dependencies so these baselines can be replaced by trained models.

Recommended production workflow:

1. Validate ingested curves with QC rules.
2. Build labeled feature sets from clean LAS, core, mudlog, and test data.
3. Train candidate models in notebooks or pipelines.
4. Log parameters, metrics, artifacts, and explainability outputs to MLflow.
5. Promote approved model versions into staging and production.
6. Monitor prediction drift, data drift, and alert quality.

Petrophysical outputs:

- Porosity from density-neutron averaging
- Water saturation using Archie-style equations
- Shale volume from gamma ray index
- Net-to-gross from configurable petrophysical cutoffs
- Permeability from an empirical porosity and irreducible water relationship

