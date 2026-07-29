# PetroEdge RC1 frontend stabilisation

Implemented:
- crash-safe lazy loading for Plotly charts, eliminating blank Reservoir Intelligence and Model Evaluation pages;
- per-panel error boundaries with visible retry states;
- explicit loading, empty-data and chart-load failure states;
- fully opaque, high-contrast Intelligence Modules hero and cards;
- WCAG-oriented light and dark semantic colour tokens across cards, forms, tabs, tables and text;
- connected Assets → Datasets → Operations navigation with persisted well/dataset context;
- unified refresh coordination that invalidates and refetches all active React Query data when any Refresh or Retry button is used;
- dedicated refresh controls for Assets, Datasets, Operations, Reservoir Intelligence and Model Evaluation.
