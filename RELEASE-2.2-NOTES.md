# PetroEdge AI Release 2.2

## Corrected edge replay

Release 2.2 removes the ambiguous deterministic score and the fixed sliding-window prediction count.

The replay now reads the selected dataset directly from the backend dataset store and examines every row. A valid interpretation is generated for each row containing usable depth, gamma ray and deep resistivity values. The interface reports total rows, valid interpretations and skipped rows separately.

## Depth-indexed outputs

Each valid depth sample produces:

- gamma ray and resistivity;
- shale volume;
- density/neutron or GR-derived porosity;
- effective porosity;
- permeability in mD;
- Archie water saturation;
- water, oil and gas probability indicators;
- hydrocarbon probability;
- reservoir/non-reservoir classification;
- hydrocarbon pay-zone flag;
- well-log anomaly score and flag;
- plain-language interpretation.

When a validated multi-output GRU/BiGRU ONNX model is unavailable, the runtime is explicitly labelled `industry-standard-deterministic-petrophysics`. It does not present a synthetic neural-network score as a geological prediction.

## Live visualisation

The replay speed is adjustable from maximum throughput to 2,000 ms per depth sample. The live workspace includes a scrolling result table and a GR versus depth plot with RT in hover metadata and reservoir/non-reservoir discrimination. The backend interprets all valid rows; the plot retains up to 1,200 representative display points to protect browser performance.

## Minimum curves

Required:

- depth: `DEPTH`, `DEPT`, `MD`, `TVD`, `TVDSS`, `TVD_COMP` or `TVDSS_COMP`;
- gamma ray: `GR`, `GR_COMP`, `GAMMA` or `GAMMA_RAY`;
- resistivity: `RT`, `RT_COMP`, `ILD`, `LLD`, `RES` or `RESISTIVITY`.

Optional RHOB and NPHI curves improve porosity and gas indication.
