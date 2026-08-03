# PetroEdge AI Release 4.1.2

- Added Data Preparation Studio before model training.
- Added editable tabular preview, cell editing, copy/paste, row/column deletion, row/column creation, column rename and formula-derived columns.
- All edits create a new lineage-tracked dataset; source files remain unchanged.
- Added petroleum null-code detection and configurable handling for -999.25, -999, -9999, -99999, 999.25 and 9999.
- Zero is only treated as missing for explicitly selected columns.
- Added depth sorting, duplicate-depth checks, short-gap interpolation, Hampel despiking, optional smoothing and physical-range clipping.
- Added standard, min-max and robust scaling options. Model pipelines continue to apply algorithm-aware scaling.
- Added dataset quality reports and non-blocking unit warnings. Missing units are flagged but never stop training or inference.
- Added downloadable cleaned datasets and complete prediction CSV outputs.
