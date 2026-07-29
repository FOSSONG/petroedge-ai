# PetroEdge V1.2 implementation

Implemented:
- persistent light/dark theme toggle;
- interactive Plotly reservoir tracks with pan, zoom, image export, drawing tools, shared reversed depth axis, and one-decimal x-axis labels;
- petroleum-standard track ranges;
- oil/gas/water/residual-hydrocarbon screening with probabilities and percentage confidence;
- high-resolution multi-track PDF log-signature endpoint;
- expanded dataset-grounded assistant with generic numeric aggregations and explicit unsupported-evidence responses;
- model evaluation centre using stored experiment metrics and interactive comparison charts.

Validation:
- Python source compilation passed for the revised reservoir API.
- TypeScript strict compilation passed.
- Vite bundling was not executable in the Linux packaging environment because the available node_modules contained Windows Rollup native bindings. Run a clean npm install on Windows before building.
