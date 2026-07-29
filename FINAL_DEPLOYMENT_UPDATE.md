# PetroEdge AI MVP — Final Additive Release

Baseline: `PetroEdge-AI-MVP-GitHub-Docker-Final` (APPLY_FINAL_MVP).

This release preserves the approved dark/light theme and engineering UI, and adds:

- Edge Computing first-class tab
- AI Agents first-class tab
- Model Evaluation first-class tab with defensive empty/error states
- Dataset-driven Well Log Analysis with a 100-row initial preview
- Depth interval selection, lithology/fluid screening, and conditional industry crossplots
- SafePlot-based chart rendering to prevent invalid React element/Plotly import failures
- Intelligence Module navigation to the corresponding first-class workspaces
- Neutral Models empty state
- Windows backend/frontend launcher scripts

## Validation

- Backend Python compilation: passed.
- Frontend source was audited for empty `onClick={() => {}}` and `console.log(...)` placeholder handlers: none found.
- Full frontend dependency build must be run on Windows using `npm install` followed by `npm run build` because dependencies are not bundled into this archive.
